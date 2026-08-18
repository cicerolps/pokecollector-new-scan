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

As of this version, an incremental backfill also runs on its own automatically
(services/scheduler.py + services/card_hash_backfill.py) after every full
sync, in bounded batches — this script remains for manual runs, a full
--force recompute, or a quick --limit test.
"""
from __future__ import annotations

import argparse
import logging

from services.card_hash_backfill import run_backfill

logger = logging.getLogger(__name__)


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
    stats = run_backfill(force=args.force, limit=args.limit)
    if stats is None:
        logger.info("card_hash_backfill: skipped — a run is already in progress")
        return 0
    return 1 if stats["failed"] and stats["hashed"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
