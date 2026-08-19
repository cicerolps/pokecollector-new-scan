"""EasyOCR-based key-field extraction for the local card scanner.

Reads the small text regions that actually identify a printing — collector
number/total (bottom strip), illustrator + set code (bottom-left corner),
and the card name (title band) — instead of relying on hash comparison
alone. These fields feed services/card_scan_resolver.py's deterministic
scoring pass, which narrows/ranks the hash-matcher's candidate list before
falling back to a pure hash-distance decision when OCR comes up empty
(faded ink, glare, an unfamiliar layout, etc).
"""
from __future__ import annotations

import difflib
import os
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

_NUMBER_CROP = (0.88, 1.0, 0.35, 1.0)  # top, bottom, left, right fractions
_ARTIST_SET_CROP = (0.88, 1.0, 0.0, 0.35)  # bottom-left corner, complements _NUMBER_CROP
_NAME_CROP = (0.03, 0.16, 0.05, 0.90)  # title band, avoiding a Pokemon's HP in the top-right

_NUMBER_PATTERN = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})")
_ARTIST_PATTERN = re.compile(r"illus\.?\s*([a-z][a-z .'\-]{1,30})", re.IGNORECASE)
_SET_CODE_PATTERN = re.compile(r"\b[a-z]{2,6}\b", re.IGNORECASE)

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


def _crop(image: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    top_f, bottom_f, left_f, right_f = region
    return image[int(height * top_f):int(height * bottom_f), int(width * left_f):int(width * right_f)]


def _read_text(image: np.ndarray, region: tuple[float, float, float, float], *, reader: OcrReader) -> str:
    results = reader.readtext(_crop(image, region), detail=0)
    return " ".join(results)


def extract_number_and_total(text: str) -> tuple[str | None, str | None]:
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def extract_artist(text: str) -> str | None:
    match = _ARTIST_PATTERN.search(text)
    if not match:
        return None
    return match.group(1).strip(" .")


def extract_set_code(text: str, *, exclude: str | None = None) -> str | None:
    """Best-effort short alpha token near the number/illustrator credit —
    treated as a soft bonus signal only (see score_candidate), since a
    2-6 letter OCR read is easy to get wrong and not every printing shows
    one as plain text in the first place."""
    excluded = {"illus"}
    if exclude:
        excluded.add(exclude.split()[0].lower())
    for token in _SET_CODE_PATTERN.findall(text):
        if token.lower() not in excluded:
            return token.upper()
    return None


def extract_number(image: np.ndarray, *, reader: OcrReader | None = None) -> str | None:
    """OCR the number crop and return a normalized "N/N" string, or None.

    Kept as its own entry point for callers that only need the number
    (scripts, tests) without paying for the name/artist crops too.
    """
    reader = reader or _get_reader()
    text = _read_text(image, _NUMBER_CROP, reader=reader)
    local, total = extract_number_and_total(text)
    if local is None:
        return None
    return f"{local}/{total}"


def extract_fields(image: np.ndarray, *, reader: OcrReader | None = None) -> dict[str, str | None]:
    """Best-effort read of every field the resolver's scoring pass uses.

    Every field is independently nullable — a card with glare over the
    artist credit but a clean number is still worth reading. Two OCR calls
    total (name band, bottom-left strip); the number crop is unchanged from
    the original single-purpose implementation.
    """
    reader = reader or _get_reader()

    name_text = _read_text(image, _NAME_CROP, reader=reader)
    number_text = _read_text(image, _NUMBER_CROP, reader=reader)
    bottom_left_text = _read_text(image, _ARTIST_SET_CROP, reader=reader)

    local, total = extract_number_and_total(number_text)
    artist = extract_artist(bottom_left_text)
    set_code = extract_set_code(bottom_left_text, exclude=artist)

    return {
        "name": name_text.strip() or None,
        "number": local,
        "total": total,
        "artist": artist,
        "set_code": set_code,
    }


def _normalize_for_similarity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def name_similarity(a: str | None, b: str | None) -> float:
    """0.0-1.0 similarity, tolerant of OCR noise (case, punctuation,
    apostrophes) — exact string equality is not realistic for OCR output."""
    if not a or not b:
        return 0.0
    norm_a, norm_b = _normalize_for_similarity(a), _normalize_for_similarity(b)
    if not norm_a or not norm_b:
        return 0.0
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def numbers_match(ocr_local: str, ocr_total: str | None, card_number: str | None, printed_total) -> bool:
    if not card_number:
        return False
    try:
        if int(ocr_local) != int(re.sub(r"\D", "", card_number) or -1):
            return False
    except ValueError:
        return False
    if not ocr_total or printed_total in (None, ""):
        # Set total unknown locally, or not read from the card — accept on
        # the local number alone rather than block on missing metadata.
        return True
    try:
        return int(ocr_total) == int(printed_total)
    except (TypeError, ValueError):
        return True
