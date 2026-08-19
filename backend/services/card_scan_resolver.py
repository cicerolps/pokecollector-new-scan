"""Orchestrates preprocess -> hash match -> field-based scoring for the
local card scanner.

The hash matcher (services/card_scan_hash.py) generates a candidate pool
from the whole catalogue and settles the photo's orientation. From there,
OCR'd key fields — collector number/total, name, illustrator, set code
(services/card_scan_ocr.py) — deterministically narrow and re-rank that
pool: a wrong collector number excludes a candidate outright, a matching
name/artist promotes one, exactly like the old Gemini-era metadata ranker
did, just fed by OCR instead of an LLM's extraction. Perceptual hash
distance is the tie-breaker whenever fields don't discriminate — including
when OCR reads nothing useful at all, which quietly falls back to the
original hash-only behavior.

Produces the same {"recognized", "matches", "_number_match_count",
"_identity_confident", "_identity_decision"} shape the scan queue and
frontend already expect (see api/scan_jobs.py's resolve_scan_job_item,
which reads match["tcg_card_id"]), so nothing downstream needs to change.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import Card, Set
from services import card_scan_hash as hash_matcher
from services import card_scan_ocr as ocr
from services import card_scan_preprocess as preprocess
from services.card_scan_hash import Candidate

_NAME_MATCH_THRESHOLD = 0.72
_ARTIST_MATCH_THRESHOLD = 0.6
_NUMBER_SCORE = 3
_TOTAL_SCORE = 1
_NAME_SCORE = 2
_ARTIST_SCORE = 2
_SET_CODE_SCORE = 1


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


def score_candidate(card: Card, set_row: Set | None, fields: dict) -> int | None:
    """Deterministic field score for one candidate, or None if OCR'd fields
    directly contradict it (a wrong collector number) — callers should drop
    those candidates entirely rather than merely rank them low. Missing or
    unreadable fields are neutral: they contribute nothing, but never
    exclude a candidate on their own, since OCR name/artist reads are far
    less reliable than the number crop."""
    score = 0

    ocr_local = fields.get("number")
    if ocr_local:
        ocr_total = fields.get("total")
        printed_total = set_row.printed_total if set_row else None
        if not ocr.numbers_match(ocr_local, ocr_total, card.number, printed_total):
            return None
        score += _NUMBER_SCORE
        if ocr_total and printed_total not in (None, ""):
            score += _TOTAL_SCORE

    if fields.get("name") and card.name and ocr.name_similarity(fields["name"], card.name) >= _NAME_MATCH_THRESHOLD:
        score += _NAME_SCORE

    if fields.get("artist") and card.artist and ocr.name_similarity(fields["artist"], card.artist) >= _ARTIST_MATCH_THRESHOLD:
        score += _ARTIST_SCORE

    if fields.get("set_code") and set_row and set_row.abbreviation and fields["set_code"].lower() == set_row.abbreviation.lower():
        score += _SET_CODE_SCORE

    return score


def _rank_with_fields(db: Session, candidates: list[Candidate], fields: dict) -> list[tuple[Candidate, int]]:
    card_ids = [c.card_id for c in candidates]
    cards = {row.id: row for row in db.query(Card).filter(Card.id.in_(card_ids)).all()}

    set_pairs = {(card.set_id, card.lang) for card in cards.values() if card.set_id}
    sets_by_pair: dict[tuple, Set] = {}
    if set_pairs:
        set_ids = {pair[0] for pair in set_pairs}
        for row in db.query(Set).filter(Set.tcg_set_id.in_(set_ids)).all():
            sets_by_pair[(row.tcg_set_id, row.lang)] = row

    ranked = []
    for candidate in candidates:
        card = cards.get(candidate.card_id)
        if card is None:
            continue
        score = score_candidate(card, sets_by_pair.get((card.set_id, card.lang)), fields)
        if score is None:
            continue
        ranked.append((candidate, score))

    ranked.sort(key=lambda pair: (-pair[1], pair[0].combined_distance))
    return ranked


def resolve_local_scan(db: Session, image_bytes: bytes) -> dict:
    """Local, deterministic replacement for the old Gemini-driven match."""
    normalized = preprocess.preprocess_image(image_bytes)
    status, hash_candidates, winning_image = hash_matcher.match_with_rotations(db, normalized)

    if status == "no_match" or not hash_candidates:
        return {
            "recognized": {"language": None},
            "matches": [],
            "_number_match_count": 0,
            "_identity_confident": False,
            "_identity_decision": None,
        }

    fields = ocr.extract_fields(winning_image)
    ranked = _rank_with_fields(db, hash_candidates, fields)
    if not ranked:
        # Every candidate got excluded by a number contradiction — the OCR
        # read something, just not any of these cards. Rather than a bare
        # no-match, fall back to the original hash order so there's still
        # something for the trainer to review manually.
        ranked = [(candidate, 0) for candidate in hash_candidates]

    decision = None
    confident = False
    winner: Candidate | None = None

    top, top_score = ranked[0]
    if len(ranked) == 1:
        confident = True
        winner = top
        decision = "hash_fields" if top_score > 0 else "hash"
    else:
        _, second_score = ranked[1]
        if top_score > second_score:
            confident = True
            winner = top
            decision = "hash_fields"
        elif top_score == second_score:
            gap = ranked[1][0].combined_distance - top.combined_distance
            if gap >= hash_matcher.HASH_CONFIDENCE_GAP:
                confident = True
                winner = top
                decision = "hash"

    ordered_candidates = [candidate for candidate, _ in ranked]
    matches = _build_matches(db, ordered_candidates)
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
