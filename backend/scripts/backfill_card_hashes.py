"""Backfill perceptual hashes (card_hashes) for the local card scanner.

Run via docker exec, same as the app's other one-off scripts:

    docker compose exec backend python -m scripts.backfill_card_hashes
    docker compose exec backend python -m scripts.backfill_card_hashes --force
    docker compose exec backend python -m scripts.backfill_card_hashes --limit 200

Incremental by default: only cards without a card_hashes row yet are
processed, so a run interrupted partway through (or one card's image
download failing) just gets picked up by the next run — no --force needed
unless you actually want to recompute hashes that already exist (e.g. after
changing the preprocessing pipeline).

Skips custom cards (no canonical reference art) and digital-only cards
(nothing physical to ever scan).
"""
from __future__ import annotations

import argparse
import logging

import httpx

from database import SessionLocal
from models import Card, CardHash
from services.card_scan_hash import compute_hashes
from services.card_scan_preprocess import preprocess_image

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 20.0
COMMIT_EVERY = 200


def _hashable_card_ids(db, *, force: bool) -> list[str]:
    query = (
        db.query(Card.id)
        .filter(Card.is_custom.isnot(True))
        .filter(Card.is_digital.isnot(True))
        .filter((Card.images_large.isnot(None)) | (Card.images_small.isnot(None)))
    )
    all_ids = [row[0] for row in query.all()]
    if force:
        return all_ids
    already_hashed = {row[0] for row in db.query(CardHash.card_id).all()}
    return [card_id for card_id in all_ids if card_id not in already_hashed]


def backfill(*, force: bool = False, limit: int | None = None) -> dict:
    db = SessionLocal()
    stats = {"seen": 0, "hashed": 0, "failed": 0}
    try:
        card_ids = _hashable_card_ids(db, force=force)
        if limit:
            card_ids = card_ids[:limit]
        stats["seen"] = len(card_ids)
        logger.info("backfill_card_hashes: %d card(s) to hash", len(card_ids))

        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            for index, card_id in enumerate(card_ids, start=1):
                card = db.get(Card, card_id)
                image_url = card.images_large or card.images_small if card else None
                if not image_url:
                    continue
                try:
                    response = client.get(image_url)
                    response.raise_for_status()
                    normalized = preprocess_image(response.content)
                    hashes = compute_hashes(normalized)
                except Exception:
                    # One bad image/card must not abort a run covering
                    # thousands of cards — log and move on. It stays
                    # unhashed and gets retried by the next (incremental)
                    # run automatically.
                    logger.exception("backfill_card_hashes: failed on %s", card_id)
                    stats["failed"] += 1
                    continue

                existing = db.get(CardHash, card_id)
                if existing:
                    existing.phash = hashes["phash"]
                    existing.dhash = hashes["dhash"]
                    existing.whash = hashes["whash"]
                else:
                    db.add(CardHash(card_id=card_id, **hashes))
                stats["hashed"] += 1

                if index % COMMIT_EVERY == 0:
                    db.commit()
                    logger.info("backfill_card_hashes: %d/%d processed", index, len(card_ids))

        db.commit()
    finally:
        db.close()
    logger.info("backfill_card_hashes: done — %s", stats)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill perceptual hashes for the local card scanner")
    parser.add_argument(
        "--force", action="store_true", help="Recompute hashes for cards that already have one"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Process at most this many cards (for a quick test run)"
    )
    args = parser.parse_args()
    stats = backfill(force=args.force, limit=args.limit)
    return 1 if stats["failed"] and stats["hashed"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
