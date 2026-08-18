"""Orchestrates preprocess -> hash match -> (conditional) OCR disambiguation
for the local card scanner. This replaces Gemini text-extraction + TCGdex
name search + Gemini visual verification (api/recognize.py's old
match_card_info() path for single-card scans).

Produces the same {"recognized", "matches", "_number_match_count",
"_identity_confident", "_identity_decision"} shape the scan queue and
frontend already expect (see api/scan_jobs.py's resolve_scan_job_item,
which reads match["tcg_card_id"]), so nothing downstream needs to change.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import Card, Set
from services import card_scan_hash as hash_matcher
from services import card_scan_ocr as ocr_disambiguator
from services import card_scan_preprocess as preprocess
from services.card_scan_hash import Candidate


def _card_to_match_dict(card: Card, set_name: str | None) -> dict:
    return {
        "id": card.id,
        "tcg_card_id": card.tcg_card_id or card.id,
        "name": card.name,
        "set": set_name,
        "number": card.number,
        "image": card.images_large or card.images_small,
        "rarity": card.rarity,
        "lang": card.lang,
        "_lang": card.lang,
        "_number_extra": False,
    }


def _build_matches(db: Session, candidates: list[Candidate]) -> list[dict]:
    if not candidates:
        return []
    card_ids = [c.card_id for c in candidates]
    cards = {row.id: row for row in db.query(Card).filter(Card.id.in_(card_ids)).all()}

    set_pairs = {(card.set_id, card.lang) for card in cards.values() if card.set_id}
    set_names: dict[tuple, str] = {}
    if set_pairs:
        set_ids = {pair[0] for pair in set_pairs}
        for row in db.query(Set.tcg_set_id, Set.lang, Set.name).filter(
            Set.tcg_set_id.in_(set_ids)
        ).all():
            set_names[(row.tcg_set_id, row.lang)] = row.name

    matches = []
    for candidate in candidates:
        card = cards.get(candidate.card_id)
        if card is None:
            continue
        matches.append(_card_to_match_dict(card, set_names.get((card.set_id, card.lang))))
    return matches


def resolve_local_scan(db: Session, image_bytes: bytes) -> dict:
    """Local, deterministic replacement for the old Gemini-driven match."""
    normalized = preprocess.preprocess_image(image_bytes)
    status, candidates, winning_image = hash_matcher.match_with_rotations(db, normalized)

    decision = None
    confident = False
    winner: Candidate | None = None

    if status == "confident":
        confident = True
        winner = candidates[0]
        decision = "hash"
    elif status == "ambiguous":
        resolved = ocr_disambiguator.disambiguate(db, winning_image, candidates)
        if resolved is not None:
            confident = True
            winner = resolved
            decision = "hash_ocr"

    matches = _build_matches(db, candidates if status != "no_match" else [])
    if winner is not None:
        # Surface the accepted candidate first, same convention the old
        # metadata/pHash ranker used.
        matches.sort(key=lambda m: m["id"] != winner.card_id)

    recognized_language = None
    if winner is not None:
        matched = next((m for m in matches if m["id"] == winner.card_id), None)
        if matched:
            recognized_language = matched["lang"]

    return {
        "recognized": {"language": recognized_language},
        "matches": matches,
        "_number_match_count": 1 if winner is not None else 0,
        "_identity_confident": confident,
        "_identity_decision": decision,
    }
