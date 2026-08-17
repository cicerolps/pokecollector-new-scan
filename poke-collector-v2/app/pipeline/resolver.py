"""Pipeline orchestration (Fase 3-4).

Runs preprocess -> hash_matcher -> (conditionally) ocr_disambiguator and
decides the final confidence / candidate list, per PROJECT_SPEC.md 3.4:
returns a single matched card when confident (directly, or after OCR breaks
a tie), or the top-N candidates for the user to confirm manually otherwise.
Every attempt is logged to ScanLog for later threshold tuning (section 6.2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import ScanLog
from app.pipeline import hash_matcher, ocr_disambiguator, preprocess
from app.pipeline.hash_matcher import Candidate

# A candidate #1 this close to #2 even after OCR isn't worth trusting blindly.
_MAX_CONFIDENCE_DISTANCE = 64 * 3  # theoretical max combined distance (3 hashes x 64 bits)


@dataclass
class ScanResult:
    status: str  # "matched" | "ambiguous" | "no_match"
    card_id: str | None
    confidence: float | None
    candidates: list[Candidate] = field(default_factory=list)
    used_ocr_fallback: bool = False
    scan_log_id: int | None = None


def _confidence_score(candidate: Candidate) -> float:
    """0..1, higher is better — combined_distance inverted and normalized."""
    return max(0.0, 1.0 - candidate.combined_distance / _MAX_CONFIDENCE_DISTANCE)


def _photo_hash(image_bytes: bytes) -> str:
    """Hash of the raw uploaded photo itself, for scan_log dedupe/auditing."""
    return str(imagehash.phash(Image.open(BytesIO(image_bytes))))


def _log_scan(
    db: Session,
    *,
    image_bytes: bytes,
    result: ScanResult,
) -> int:
    log = ScanLog(
        image_hash=_photo_hash(image_bytes),
        matched_card_id=result.card_id,
        confidence=result.confidence,
        used_ocr_fallback=result.used_ocr_fallback,
        candidates_json=json.dumps(
            [
                {
                    "card_id": c.card_id,
                    "combined_distance": c.combined_distance,
                    "phash_distance": c.phash_distance,
                    "dhash_distance": c.dhash_distance,
                    "whash_distance": c.whash_distance,
                }
                for c in result.candidates
            ]
        ),
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log.id


def resolve_scan(
    db: Session, image_bytes: bytes, *, settings: Settings | None = None
) -> ScanResult:
    settings = settings or get_settings()

    normalized = preprocess.preprocess_image(image_bytes, settings.card_output_size)
    status, candidates, winning_image = hash_matcher.match_with_rotations(
        db, normalized, settings=settings
    )

    if status == "no_match":
        result = ScanResult(status="no_match", card_id=None, confidence=None, candidates=[])
        result.scan_log_id = _log_scan(db, image_bytes=image_bytes, result=result)
        return result

    if status == "confident":
        top = candidates[0]
        result = ScanResult(
            status="matched",
            card_id=top.card_id,
            confidence=_confidence_score(top),
            candidates=candidates,
        )
        result.scan_log_id = _log_scan(db, image_bytes=image_bytes, result=result)
        return result

    # Ambiguous: try OCR to break the tie before giving up to manual review.
    resolved = ocr_disambiguator.disambiguate(db, winning_image, candidates)
    if resolved is not None:
        result = ScanResult(
            status="matched",
            card_id=resolved.card_id,
            confidence=_confidence_score(resolved),
            candidates=candidates,
            used_ocr_fallback=True,
        )
        result.scan_log_id = _log_scan(db, image_bytes=image_bytes, result=result)
        return result

    result = ScanResult(
        status="ambiguous",
        card_id=None,
        confidence=None,
        candidates=candidates[:3],
        used_ocr_fallback=True,
    )
    result.scan_log_id = _log_scan(db, image_bytes=image_bytes, result=result)
    return result
