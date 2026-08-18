"""Catalog/hash sync batch job (Fase 2).

Usage (matches PROJECT_SPEC.md 4.1 — run via docker exec or a systemd timer,
same pattern as the homelab's other scripts):

    python -m app.jobs.sync_catalog --sets base1,base2
    python -m app.jobs.sync_catalog --sets base1 --force
    python -m app.jobs.sync_catalog --all

tcgdex.dev is the catalog's primary source: pokemontcg.io's team moved to
the commercial Scrydex product and the legacy free API has become
unreliable in practice (repeated bare 500/502s observed live, independent
of request shape or rate) — see app/integrations/pokemontcg_client.py.
tcgdex.dev needs no API key and is what this project's original production
backend already relies on.

For each card: downloads its reference image into Settings.catalog_dir
(cached on disk, never re-downloaded once present), computes phash/dhash/
whash, and upserts app.db.models.Card / CardHash.

Incremental: a card that already has a CardHash row is skipped unless
--force is passed — the reference art never changes once hashed
(PROJECT_SPEC.md section 4.2), so re-running the job to pick up a newly
released set costs nothing for sets already synced.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Card, CardHash
from app.db.session import SessionLocal, init_db
from app.integrations.tcgdex_client import TcgdexClient
from app.pipeline import hash_matcher, preprocess

logger = logging.getLogger("sync_catalog")

SOURCE_API = "tcgdex"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _image_cache_path(catalog_dir: Path, card_id: str, url: str) -> Path:
    suffix = Path(httpx.URL(url).path).suffix or ".webp"
    return catalog_dir / "images" / SOURCE_API / f"{card_id}{suffix}"


def _infer_variant(rarity: str | None) -> str:
    """Best-effort tag from the printed rarity string.

    tcgdex.dev's brief per-set card listing doesn't include rarity (only a
    full per-card fetch does, which we skip here to keep the sync job to one
    request per set — see sync_set). rarity is always None for now, so this
    always returns "normal". A single reference image can't represent
    multiple physical foil variants anyway — revisit if Fase 3 accuracy
    testing shows it matters.
    """
    if not rarity:
        return "normal"
    lowered = rarity.lower()
    if "reverse" in lowered:
        return "reverse_holo"
    if "holo" in lowered:
        return "holo"
    return "normal"


async def _download_image(http_client: httpx.AsyncClient, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = await http_client.get(url)
    response.raise_for_status()
    dest.write_bytes(response.content)


def _compute_hashes(image_path: Path, output_size: tuple[int, int]) -> dict[str, str]:
    """Hash a cached reference image through the *exact* same preprocess ->
    hash_matcher pipeline a scanned photo goes through at match time.

    Found live: hashing the raw reference file directly (no resize, no
    CLAHE) made every reference hash systematically different from what
    resolve_scan() computes for the same image at scan time — most cards
    still matched by luck (the drift stayed under the confidence
    threshold), but some (e.g. base1-4/Charizard) drifted past it,
    producing "no_match" against the exact image that was hashed. Reusing
    the pipeline functions here instead of a second hand-rolled
    implementation makes that impossible by construction.
    """
    image_bytes = image_path.read_bytes()
    normalized = preprocess.preprocess_image(image_bytes, output_size)
    return hash_matcher.compute_hashes(normalized)


async def sync_set(
    db: Session,
    api_client: TcgdexClient,
    http_client: httpx.AsyncClient,
    catalog_dir: Path,
    set_id: str,
    *,
    lang: str | None = None,
    force: bool = False,
    output_size: tuple[int, int] = (600, 825),
) -> dict[str, int]:
    """Sync one set's cards. Commits once at the end of the set."""
    stats = {"cards_seen": 0, "cards_hashed": 0, "cards_skipped": 0, "cards_failed": 0}

    set_data = await api_client.get_set(set_id, lang=lang)
    if set_data is None:
        logger.warning("Set %s not found on tcgdex.dev, skipping", set_id)
        return stats
    set_name = set_data.get("name", set_id)
    card_count = set_data.get("cardCount") or {}
    printed_total = card_count.get("official")

    cards = set_data.get("cards", [])
    for card_data in cards:
        stats["cards_seen"] += 1
        card_id = card_data["id"]

        if not force and db.get(CardHash, card_id) is not None:
            stats["cards_skipped"] += 1
            continue

        image_base = card_data.get("image")
        if not image_base:
            logger.warning("Card %s has no reference image, skipping", card_id)
            stats["cards_failed"] += 1
            continue
        image_url = f"{image_base}/high.webp"

        image_path = _image_cache_path(catalog_dir, card_id, image_url)
        try:
            if not image_path.exists():
                await _download_image(http_client, image_url, image_path)
            hashes = _compute_hashes(image_path, output_size)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Failed to fetch/hash %s: %s", card_id, exc)
            stats["cards_failed"] += 1
            continue

        raw_number = card_data.get("localId", "")
        number = f"{raw_number}/{printed_total}" if printed_total else str(raw_number)

        db.merge(
            Card(
                id=card_id,
                source_api=SOURCE_API,
                name=card_data.get("name", ""),
                set_id=set_id,
                set_name=set_name,
                number=number,
                rarity=card_data.get("rarity"),
                variant=_infer_variant(card_data.get("rarity")),
                image_url=image_url,
                last_synced_at=_utcnow(),
            )
        )
        db.merge(CardHash(card_id=card_id, **hashes))
        stats["cards_hashed"] += 1

    db.commit()
    return stats


async def sync_sets(
    set_ids: list[str],
    *,
    settings: Settings | None = None,
    lang: str | None = None,
    force: bool = False,
) -> dict[str, dict[str, int]]:
    settings = settings or get_settings()
    init_db()
    db = SessionLocal()
    results: dict[str, dict[str, int]] = {}
    failed_sets: list[str] = []
    try:
        async with TcgdexClient(settings) as api_client, httpx.AsyncClient(
            timeout=settings.http_timeout_seconds
        ) as http_client:
            for set_id in set_ids:
                logger.info("Syncing set %s...", set_id)
                try:
                    stats = await sync_set(
                        db,
                        api_client,
                        http_client,
                        settings.catalog_dir,
                        set_id,
                        lang=lang,
                        force=force,
                        output_size=settings.card_output_size,
                    )
                except Exception:
                    # A single flaky set (network blip that outlasts the
                    # client's own retries, an unexpected API response
                    # shape, ...) must not abort a multi-hour --all run and
                    # discard every set queued after it. Roll back any
                    # partial work from this set and move on; re-running the
                    # job later only redoes sets that never finished, since
                    # already-hashed cards are skipped (see sync_set).
                    logger.exception("Set %s failed, skipping it for this run", set_id)
                    db.rollback()
                    failed_sets.append(set_id)
                    continue
                logger.info("Set %s done: %s", set_id, stats)
                results[set_id] = stats
    finally:
        db.close()

    if failed_sets:
        logger.warning(
            "%d/%d sets failed and were skipped: %s",
            len(failed_sets),
            len(set_ids),
            ", ".join(failed_sets),
        )
    return results


async def sync_all(
    *, settings: Settings | None = None, lang: str | None = None, force: bool = False
) -> dict[str, dict[str, int]]:
    settings = settings or get_settings()
    async with TcgdexClient(settings) as api_client:
        all_sets = await api_client.list_sets(lang=lang)
    set_ids = [s["id"] for s in all_sets]
    logger.info("Found %d sets to sync", len(set_ids))
    return await sync_sets(set_ids, settings=settings, lang=lang, force=force)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sync the card catalog + perceptual hash bank")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sets", help="Comma-separated set IDs to sync (e.g. base1,base2)")
    group.add_argument("--all", action="store_true", help="Sync every set in the catalog")
    parser.add_argument("--lang", default=None, help="tcgdex.dev language code (default: en)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download/re-hash cards that already have a hash row",
    )
    args = parser.parse_args()

    if args.all:
        asyncio.run(sync_all(lang=args.lang, force=args.force))
    else:
        set_ids = [s.strip() for s in args.sets.split(",") if s.strip()]
        asyncio.run(sync_sets(set_ids, lang=args.lang, force=args.force))


if __name__ == "__main__":
    main()
