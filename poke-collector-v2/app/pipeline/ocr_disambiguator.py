"""EasyOCR-based disambiguation (Fase 4).

PROJECT_SPEC.md section 3.3: only runs when hash-matching is ambiguous.
Reads the collector-number crop (e.g. "25/198") — not the full card, which
sidesteps stylized name fonts and keeps the OCR pass small/fast on CPU.
The extracted number is cross-referenced against the hash-matching
candidates' Card.number to pick the one that actually matches.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Card
from app.pipeline.hash_matcher import Candidate

# Collector number lives in the bottom strip of a normalized card image.
# Heuristic crop (fraction of width/height) — generic across sets/eras
# rather than tuned to one specific layout; revisit if real-photo testing
# (PROJECT_SPEC.md Fase 3) shows it needs narrowing per era.
_CROP_TOP_FRACTION = 0.88
_CROP_BOTTOM_FRACTION = 1.0
_CROP_LEFT_FRACTION = 0.35
_CROP_RIGHT_FRACTION = 1.0

_NUMBER_PATTERN = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")


class OcrReader(Protocol):
    def readtext(self, image: np.ndarray, detail: int = ...) -> list: ...


@lru_cache
def _get_reader() -> OcrReader:
    """Lazy singleton — loading EasyOCR's model is expensive, do it once.

    Reads only from the weights baked into the image at build time
    (Dockerfile sets EASYOCR_MODULE_PATH); no network access needed or
    attempted at runtime.
    """
    import easyocr  # deferred: heavy import (torch), only pay for it if used

    settings = get_settings()
    return easyocr.Reader(
        list(settings.easyocr_languages),
        model_storage_directory=str(settings.easyocr_model_dir),
        download_enabled=False,
        gpu=False,
    )


def crop_number_region(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    top = int(height * _CROP_TOP_FRACTION)
    bottom = int(height * _CROP_BOTTOM_FRACTION)
    left = int(width * _CROP_LEFT_FRACTION)
    right = int(width * _CROP_RIGHT_FRACTION)
    return image[top:bottom, left:right]


def extract_number(image: np.ndarray, *, reader: OcrReader | None = None) -> str | None:
    """OCR the crop and return a normalized "N/N" string, or None."""
    reader = reader or _get_reader()
    crop = crop_number_region(image)
    results = reader.readtext(crop, detail=0)
    text = " ".join(results)
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def _numbers_match(ocr_number: str, card_number: str | None) -> bool:
    if not card_number:
        return False
    # Card.number may carry leading zeros ("025/198"); OCR usually won't.
    def normalize(value: str) -> tuple[int, int] | None:
        found = _NUMBER_PATTERN.search(value)
        if not found:
            return None
        return int(found.group(1)), int(found.group(2))

    return normalize(ocr_number) == normalize(card_number)


def disambiguate(
    db: Session,
    image: np.ndarray,
    candidates: list[Candidate],
    *,
    reader: OcrReader | None = None,
) -> Candidate | None:
    """Narrow `candidates` down to one using the OCR'd collector number.

    Returns None if OCR found nothing usable, or if the extracted number
    doesn't uniquely match exactly one candidate — callers should fall back
    to returning the top-N candidates for manual confirmation either way.
    """
    ocr_number = extract_number(image, reader=reader)
    if not ocr_number:
        return None

    cards = {
        card.id: card
        for card in db.query(Card).filter(Card.id.in_([c.card_id for c in candidates])).all()
    }

    matches = []
    for candidate in candidates:
        card = cards.get(candidate.card_id)
        if card and _numbers_match(ocr_number, card.number):
            matches.append(candidate)

    if len(matches) == 1:
        return matches[0]
    return None
