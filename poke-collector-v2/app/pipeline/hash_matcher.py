"""Perceptual hash computation and lookup (Fase 3).

PROJECT_SPEC.md section 3.2: compute phash/dhash/whash for the normalized
card image, search the pre-computed bank (app.db.models.CardHash) for the
closest candidates by combined Hamming distance, and try all 4 rotations
since preprocessing doesn't guarantee orientation (see
pipeline.preprocess.four_rotations).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import imagehash
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import CardHash
from app.pipeline.preprocess import four_rotations

MatchStatus = Literal["confident", "ambiguous", "no_match"]


@dataclass
class Candidate:
    card_id: str
    phash_distance: int
    dhash_distance: int
    whash_distance: int

    @property
    def combined_distance(self) -> int:
        return self.phash_distance + self.dhash_distance + self.whash_distance


def compute_hashes(image: np.ndarray) -> dict[str, str]:
    """phash/dhash/whash for an in-memory BGR (OpenCV) image."""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    return {
        "phash": str(imagehash.phash(pil_image)),
        "dhash": str(imagehash.dhash(pil_image)),
        "whash": str(imagehash.whash(pil_image)),
    }


def _hamming(hash_a: str | None, hash_b: str | None) -> int:
    if not hash_a or not hash_b:
        return 64  # max distance for a 8x8 hash — treat missing data as "no match"
    # imagehash's ImageHash.__sub__ returns numpy.int64, not a plain int —
    # cast so Candidate distances stay JSON-serializable (scan_log.candidates_json).
    return int(imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b))


def search_candidates(
    db: Session, hashes: dict[str, str], *, top_n: int = 5
) -> list[Candidate]:
    """Rank every hashed card by combined Hamming distance to `hashes`.

    A full scan in Python is fine at homelab catalog scale (tens of
    thousands of rows of short hex strings) — no need for an ANN index.
    """
    candidates = [
        Candidate(
            card_id=row.card_id,
            phash_distance=_hamming(hashes.get("phash"), row.phash),
            dhash_distance=_hamming(hashes.get("dhash"), row.dhash),
            whash_distance=_hamming(hashes.get("whash"), row.whash),
        )
        for row in db.query(CardHash).all()
    ]
    candidates.sort(key=lambda c: c.combined_distance)
    return candidates[:top_n]


def evaluate_confidence(
    candidates: list[Candidate], *, settings: Settings | None = None
) -> MatchStatus:
    """Decide confident / ambiguous / no_match per PROJECT_SPEC.md 3.2."""
    settings = settings or get_settings()
    if not candidates:
        return "no_match"
    if candidates[0].combined_distance >= settings.hash_no_match_distance:
        return "no_match"
    if len(candidates) == 1:
        return "confident"
    gap = candidates[1].combined_distance - candidates[0].combined_distance
    return "confident" if gap >= settings.hash_confidence_gap else "ambiguous"


def match_with_rotations(
    db: Session,
    image: np.ndarray,
    *,
    settings: Settings | None = None,
) -> tuple[MatchStatus, list[Candidate], np.ndarray]:
    """Try all 4 rotations of `image`, keep the one with the best top candidate.

    Returns (status, candidates, the winning rotation's image) — the image is
    returned too since ocr_disambiguator needs to crop the same orientation
    that hash-matching settled on.
    """
    settings = settings or get_settings()
    best: tuple[list[Candidate], np.ndarray] | None = None

    for rotated in four_rotations(image):
        hashes = compute_hashes(rotated)
        candidates = search_candidates(db, hashes, top_n=settings.hash_match_top_n)
        if not candidates:
            continue
        if best is None or candidates[0].combined_distance < best[0][0].combined_distance:
            best = (candidates, rotated)

    if best is None:
        return "no_match", [], image

    candidates, winning_image = best
    status = evaluate_confidence(candidates, settings=settings)
    return status, candidates, winning_image
