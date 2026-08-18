"""Perceptual hash computation and lookup against the local card_hashes table.

Replaces Gemini as the primary identification step: instead of asking an
LLM to read the card and searching TCGdex by name, the photo's own hash is
compared directly against every pre-computed catalogue hash. See
services/card_scan_preprocess.py for the geometry step that runs first, and
scripts/backfill_card_hashes.py for how card_hashes gets populated.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import cv2
import imagehash
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from models import CardHash
from services.card_scan_preprocess import four_rotations

MatchStatus = Literal["confident", "ambiguous", "no_match"]

# Candidate #1 is accepted directly when its combined Hamming distance is at
# least this much lower than candidate #2's; otherwise OCR disambiguation
# kicks in. Below HASH_NO_MATCH_DISTANCE for candidate #1, treat as no match.
HASH_MATCH_TOP_N = int(os.environ.get("SCAN_HASH_TOP_N", "5"))
HASH_CONFIDENCE_GAP = int(os.environ.get("SCAN_HASH_CONFIDENCE_GAP", "10"))
HASH_NO_MATCH_DISTANCE = int(os.environ.get("SCAN_HASH_NO_MATCH_DISTANCE", "60"))


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
        return 64  # max distance for an 8x8 hash — missing data reads as "no match"
    # imagehash's ImageHash.__sub__ returns numpy.int64, not a plain int —
    # cast so Candidate distances stay JSON-serializable (scan_job_items.matches).
    return int(imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b))


def search_candidates(db: Session, hashes: dict[str, str], *, top_n: int = HASH_MATCH_TOP_N) -> list[Candidate]:
    """Rank every hashed card by combined Hamming distance to `hashes`.

    A full scan in Python is fine at this catalogue's scale (tens of
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


def evaluate_confidence(candidates: list[Candidate]) -> MatchStatus:
    if not candidates:
        return "no_match"
    if candidates[0].combined_distance >= HASH_NO_MATCH_DISTANCE:
        return "no_match"
    if len(candidates) == 1:
        return "confident"
    gap = candidates[1].combined_distance - candidates[0].combined_distance
    return "confident" if gap >= HASH_CONFIDENCE_GAP else "ambiguous"


def match_with_rotations(
    db: Session, image: np.ndarray
) -> tuple[MatchStatus, list[Candidate], np.ndarray]:
    """Try all 4 rotations of `image`, keep the one with the best top candidate.

    Returns (status, candidates, the winning rotation's image) — the image
    is returned too since OCR disambiguation needs to crop the same
    orientation that hash-matching settled on.
    """
    best: tuple[list[Candidate], np.ndarray] | None = None

    for rotated in four_rotations(image):
        hashes = compute_hashes(rotated)
        candidates = search_candidates(db, hashes)
        if not candidates:
            continue
        if best is None or candidates[0].combined_distance < best[0][0].combined_distance:
            best = (candidates, rotated)

    if best is None:
        return "no_match", [], image

    candidates, winning_image = best
    return evaluate_confidence(candidates), candidates, winning_image
