"""Perceptual-hash backfill for the local card scanner (card_hashes table).

Owns the actual backfill logic plus a process-wide running guard, so the
same code path can be driven from three places without racing each other:

- the scheduler (services/scheduler.py), on an interval, incremental only
- the admin-only API (api/card_hashes.py), for manual/forced runs from the UI
- the CLI wrapper (scripts/backfill_card_hashes.py), for docker exec use
"""
from __future__ import annotations

import logging
import threading

import httpx
from sqlalchemy import func

from database import SessionLocal
from models import Card, CardHash
from services.card_scan_hash import compute_hashes
from services.card_scan_preprocess import preprocess_image

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 20.0
COMMIT_EVERY = 200

_lock = threading.Lock()
_running = False
_last_result: dict | None = None


def is_running() -> bool:
    return _running


def last_result() -> dict | None:
    return _last_result


def _hashable_cards_query(db):
    return (
        db.query(Card)
        .filter(Card.is_custom.isnot(True))
        .filter(Card.is_digital.isnot(True))
        .filter((Card.images_large.isnot(None)) | (Card.images_small.isnot(None)))
    )


def _hashable_card_ids(db, *, force: bool) -> list[str]:
    all_ids = [row[0] for row in _hashable_cards_query(db).with_entities(Card.id).all()]
    if force:
        return all_ids
    already_hashed = {row[0] for row in db.query(CardHash.card_id).all()}
    return [card_id for card_id in all_ids if card_id not in already_hashed]


def hash_coverage_counts() -> dict:
    """Cheap counts for the Settings UI: how many hashable cards exist,
    how many already have a hash, and how many are still missing one."""
    db = SessionLocal()
    try:
        total = _hashable_cards_query(db).with_entities(func.count(Card.id)).scalar() or 0
        hashed = db.query(func.count(CardHash.card_id)).scalar() or 0
        hashed = min(hashed, total)
        return {"total_hashable": total, "hashed": hashed, "missing": max(total - hashed, 0)}
    finally:
        db.close()


def _run(*, force: bool, limit: int | None) -> dict:
    db = SessionLocal()
    stats = {"seen": 0, "hashed": 0, "failed": 0}
    try:
        card_ids = _hashable_card_ids(db, force=force)
        if limit:
            card_ids = card_ids[:limit]
        stats["seen"] = len(card_ids)
        logger.info("card_hash_backfill: %d card(s) to hash (force=%s)", len(card_ids), force)

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
                    logger.exception("card_hash_backfill: failed on %s", card_id)
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
                    logger.info("card_hash_backfill: %d/%d processed", index, len(card_ids))

        db.commit()
    finally:
        db.close()
    logger.info("card_hash_backfill: done — %s", stats)
    return stats


def run_backfill(*, force: bool = False, limit: int | None = None) -> dict | None:
    """Run the backfill if nothing else is already running. Returns None
    (instead of running) when a run is already in progress — callers should
    treat that as "already running", not as a failure."""
    global _running, _last_result
    if not _lock.acquire(blocking=False):
        return None
    try:
        _running = True
        result = {**_run(force=force, limit=limit), "force": force}
        _last_result = result
        return result
    finally:
        _running = False
        _lock.release()
