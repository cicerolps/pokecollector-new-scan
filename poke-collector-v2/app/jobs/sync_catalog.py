"""Catalog/hash sync batch job (Fase 2).

Usage (matches PROJECT_SPEC.md 4.1 — run via docker exec or a systemd timer,
same pattern as the homelab's other scripts):

    python -m app.jobs.sync_catalog --sets base1,base2
    python -m app.jobs.sync_catalog --sets base1 --force
    python -m app.jobs.sync_catalog --all

pokemontcg.io is the catalog's primary source (PROJECT_SPEC.md section 4).
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
import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Card, CardHash
from app.db.session import SessionLocal, init_db
from app.integrations.pokemontcg_client import PokemonTcgClient

logger = logging.getLogger("sync_catalog")

SOURCE_API = "pokemontcg"
PAGE_SIZE = 250


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _image_cache_path(catalog_dir: Path, card_id: str, url: str) -> Path:
    suffix = Path(httpx.URL(url).path).suffix or ".png"
    return catalog_dir / "images" / SOURCE_API / f"{card_id}{suffix}"


def _infer_variant(rarity: str | None) -> str:
    """Best-effort tag from the printed rarity string.

    pokemontcg.io ties variant availability (normal/holo/reverse) to
    tcgplayer price buckets rather than a single flag on the card, and a
    single reference image can't represent multiple physical foil variants
    anyway. This is a coarse label for now, not a source of per-variant
    hashes — revisit if Fase 3 accuracy testing shows it matters.
    """
    if not rarity:
        return "normal"
    lowered = rarity.lower()
    if "reverse" in lowered:
        return "reverse_holo"
    if "holo" in lowered:
        return "holo"
    return "normal"


async def _fetch_all_cards(api_client: PokemonTcgClient, set_id: str) -> list[dict[str, Any]]:
    all_cards: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = await api_client.list_cards(set_id=set_id, page=page, page_size=PAGE_SIZE)
        if not batch:
            break
        all_cards.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return all_cards


async def _download_image(http_client: httpx.AsyncClient, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = await http_client.get(url)
    response.raise_for_status()
    dest.write_bytes(response.content)


def _compute_hashes(image_path: Path) -> dict[str, str]:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        return {
            "phash": str(imagehash.phash(img)),
            "dhash": str(imagehash.dhash(img)),
            "whash": str(imagehash.whash(img)),
        }


async def sync_set(
    db: Session,
    api_client: PokemonTcgClient,
    http_client: httpx.AsyncClient,
    catalog_dir: Path,
    set_id: str,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Sync one set's cards. Commits once at the end of the set."""
    stats = {"cards_seen": 0, "cards_hashed": 0, "cards_skipped": 0, "cards_failed": 0}

    set_data = await api_client.get_set(set_id)
    if set_data is None:
        logger.warning("Set %s not found on pokemontcg.io, skipping", set_id)
        return stats
    set_name = set_data.get("name", set_id)
    printed_total = set_data.get("printedTotal")

    cards = await _fetch_all_cards(api_client, set_id)
    for card_data in cards:
        stats["cards_seen"] += 1
        card_id = card_data["id"]

        if not force and db.get(CardHash, card_id) is not None:
            stats["cards_skipped"] += 1
            continue

        images = card_data.get("images") or {}
        image_url = images.get("large") or images.get("small")
        if not image_url:
            logger.warning("Card %s has no reference image, skipping", card_id)
            stats["cards_failed"] += 1
            continue

        image_path = _image_cache_path(catalog_dir, card_id, image_url)
        try:
            if not image_path.exists():
                await _download_image(http_client, image_url, image_path)
            hashes = _compute_hashes(image_path)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Failed to fetch/hash %s: %s", card_id, exc)
            stats["cards_failed"] += 1
            continue

        raw_number = card_data.get("number", "")
        number = f"{raw_number}/{printed_total}" if printed_total else raw_number

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


async def sync_sets(set_ids: list[str], *, settings: Settings | None = None, force: bool = False) -> dict[str, dict[str, int]]:
    settings = settings or get_settings()
    init_db()
    db = SessionLocal()
    results: dict[str, dict[str, int]] = {}
    try:
        async with PokemonTcgClient(settings) as api_client, httpx.AsyncClient(
            timeout=settings.http_timeout_seconds
        ) as http_client:
            for set_id in set_ids:
                logger.info("Syncing set %s...", set_id)
                stats = await sync_set(
                    db, api_client, http_client, settings.catalog_dir, set_id, force=force
                )
                logger.info("Set %s done: %s", set_id, stats)
                results[set_id] = stats
    finally:
        db.close()
    return results


async def sync_all(*, settings: Settings | None = None, force: bool = False) -> dict[str, dict[str, int]]:
    settings = settings or get_settings()
    async with PokemonTcgClient(settings) as api_client:
        all_sets = await api_client.list_sets()
    set_ids = [s["id"] for s in all_sets]
    logger.info("Found %d sets to sync", len(set_ids))
    return await sync_sets(set_ids, settings=settings, force=force)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sync the card catalog + perceptual hash bank")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sets", help="Comma-separated set IDs to sync (e.g. base1,base2)")
    group.add_argument("--all", action="store_true", help="Sync every set in the catalog")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download/re-hash cards that already have a hash row",
    )
    args = parser.parse_args()

    if args.all:
        asyncio.run(sync_all(force=args.force))
    else:
        set_ids = [s.strip() for s in args.sets.split(",") if s.strip()]
        asyncio.run(sync_sets(set_ids, force=args.force))


if __name__ == "__main__":
    main()
