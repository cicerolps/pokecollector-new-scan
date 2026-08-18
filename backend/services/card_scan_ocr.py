"""EasyOCR-based disambiguation for the local card scanner.

Only runs when hash-matching is ambiguous. Reads the collector-number crop
(e.g. "25/198") — not the full card — and cross-references it against the
ambiguous candidates' Card.number + their set's printed_total to pick the
one that actually matches.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Protocol

import numpy as np
from sqlalchemy.orm import Session

from models import Card, Set
from services.card_scan_hash import Candidate

_CROP_TOP_FRACTION = 0.88
_CROP_BOTTOM_FRACTION = 1.0
_CROP_LEFT_FRACTION = 0.35
_CROP_RIGHT_FRACTION = 1.0

_NUMBER_PATTERN = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")

EASYOCR_MODEL_DIR = os.environ.get("EASYOCR_MODEL_DIR", "/opt/easyocr-models")
EASYOCR_LANGUAGES = [lang.strip() for lang in os.environ.get("EASYOCR_LANGUAGES", "en").split(",") if lang.strip()]


class OcrReader(Protocol):
    def readtext(self, image: np.ndarray, detail: int = ...) -> list: ...


@lru_cache
def _get_reader() -> OcrReader:
    """Lazy singleton — loading EasyOCR's model is expensive, do it once.

    Reads only from the weights baked into the image at build time; no
    network access needed or attempted at runtime.
    """
    import easyocr  # deferred: heavy import (torch), only pay for it if used

    return easyocr.Reader(
        EASYOCR_LANGUAGES,
        model_storage_directory=EASYOCR_MODEL_DIR,
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


def _numbers_match(ocr_local: str, ocr_total: str, card_number: str | None, printed_total) -> bool:
    if not card_number:
        return False
    try:
        if int(ocr_local) != int(re.sub(r"\D", "", card_number) or -1):
            return False
    except ValueError:
        return False
    if printed_total in (None, ""):
        # Set total unknown locally — accept on the local number alone
        # rather than block disambiguation over missing metadata.
        return True
    try:
        return int(ocr_total) == int(printed_total)
    except (TypeError, ValueError):
        return True


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
    to returning the candidates for manual confirmation either way.
    """
    ocr_number = extract_number(image, reader=reader)
    if not ocr_number:
        return None
    match = _NUMBER_PATTERN.search(ocr_number)
    if not match:
        return None
    ocr_local, ocr_total = match.group(1), match.group(2)

    card_ids = [c.card_id for c in candidates]
    rows = (
        db.query(Card.id, Card.number, Card.set_id, Card.lang)
        .filter(Card.id.in_(card_ids))
        .all()
    )
    set_pairs = {(row.set_id, row.lang) for row in rows if row.set_id}
    printed_totals: dict[tuple, int | None] = {}
    if set_pairs:
        set_ids = {pair[0] for pair in set_pairs}
        set_rows = db.query(Set.tcg_set_id, Set.lang, Set.printed_total).filter(
            Set.tcg_set_id.in_(set_ids)
        ).all()
        printed_totals = {(row.tcg_set_id, row.lang): row.printed_total for row in set_rows}

    cards_by_id = {row.id: row for row in rows}
    matches = []
    for candidate in candidates:
        card = cards_by_id.get(candidate.card_id)
        if not card:
            continue
        printed_total = printed_totals.get((card.set_id, card.lang))
        if _numbers_match(ocr_local, ocr_total, card.number, printed_total):
            matches.append(candidate)

    if len(matches) == 1:
        return matches[0]
    return None
