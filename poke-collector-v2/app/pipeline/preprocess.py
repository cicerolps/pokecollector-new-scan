"""OpenCV pre-processing (Fase 3): find the card in a photo, straighten it,
and normalize lighting so hashing sees a consistent, reference-like image.

PROJECT_SPEC.md section 3.1:
  - contour detection + perspective warp to a standardized frontal image
  - CLAHE lighting normalization (helps with holo/reflective cards)
  - orientation is NOT decided here (see pipeline/hash_matcher.four_rotations
    and match_with_rotations) — a photo can be taken at any rotation, so the
    hash-matching step tries all 4 and keeps the best-scoring one.
"""
from __future__ import annotations

import cv2
import numpy as np

# Fraction of the full image area a candidate contour must cover to be
# considered "the card" rather than noise/background clutter.
_MIN_CONTOUR_AREA_FRACTION = 0.15

# A Pokemon card is ~2.5x3.5in — reject 4-point contours that don't
# roughly match that ratio (checked both ways since we don't know
# orientation yet). Found live: without this, a busy card illustration
# with no photographed background at all (i.e. an already-cropped
# reference image) can have a strong internal edge — e.g. part of the
# artwork — that Canny/approxPolyDP mistakes for "the card", producing a
# wrong, non-card-shaped crop instead of falling back to the whole frame.
_CARD_ASPECT_RATIO = 2.5 / 3.5
_ASPECT_RATIO_TOLERANCE = 0.18


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = points.sum(axis=1)
    rect[0] = points[np.argmin(s)]
    rect[2] = points[np.argmax(s)]
    diff = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diff)]
    rect[3] = points[np.argmax(diff)]
    return rect


def _is_card_shaped(contour: np.ndarray) -> bool:
    (_, (w, h), _) = cv2.minAreaRect(contour)
    if w <= 0 or h <= 0:
        return False
    ratio = min(w, h) / max(w, h)
    return abs(ratio - _CARD_ASPECT_RATIO) <= _ASPECT_RATIO_TOLERANCE


def find_card_corners(image: np.ndarray) -> np.ndarray | None:
    """Best-guess 4 corners of the card rectangle, or None if not confident.

    Caller should fall back to treating the whole frame as the card (i.e.
    the user already cropped it) when this returns None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image.shape[0] * image.shape[1]
    best_quad: np.ndarray | None = None
    best_area = 0.0

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        area = cv2.contourArea(contour)
        if area < image_area * _MIN_CONTOUR_AREA_FRACTION:
            continue
        if not _is_card_shaped(contour):
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and area > best_area:
            best_quad = approx.reshape(4, 2).astype("float32")
            best_area = area

    return best_quad


def warp_card(image: np.ndarray, corners: np.ndarray, output_size: tuple[int, int]) -> np.ndarray:
    """Perspective-correct the quadrilateral in `corners` to a flat rectangle."""
    rect = _order_corners(corners)
    width, height = output_size
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image, matrix, (width, height))


def normalize_lighting(image: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel (LAB space) — tones down holo/glare hotspots
    without blowing out the rest of the image the way global histogram
    equalization would.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def preprocess_image(
    image_bytes: bytes, output_size: tuple[int, int] = (600, 825)
) -> np.ndarray:
    """Decode a photo and return a normalized, upright-ish BGR card image.

    Falls back to treating the whole frame as the card (resized to
    output_size) when no confident quadrilateral is found — e.g. the client
    already sent a tightly cropped photo, or lighting/background made
    contour detection fail (PROJECT_SPEC.md section 11's manual-crop
    fallback is a client concern; this is the server-side equivalent).
    """
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes")

    corners = find_card_corners(image)
    if corners is not None:
        warped = warp_card(image, corners, output_size)
    else:
        warped = cv2.resize(image, output_size, interpolation=cv2.INTER_AREA)

    return normalize_lighting(warped)


def four_rotations(image: np.ndarray) -> list[np.ndarray]:
    """The 0/90/180/270 rotations of a normalized card image.

    A perspective-corrected card can still be upside down or on its side —
    contour detection finds the rectangle, not which edge is "up"
    (PROJECT_SPEC.md 3.1). Matching tries all four.
    """
    return [
        image,
        cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(image, cv2.ROTATE_180),
        cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
