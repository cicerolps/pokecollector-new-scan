"""Tests for OpenCV pre-processing using synthetic images.

No real card photos needed to validate the geometry: a filled quadrilateral
on a plain background exercises contour detection + perspective warp the
same way a photographed card against a table would.
"""
import cv2
import numpy as np

from app.pipeline.preprocess import find_card_corners, four_rotations, preprocess_image


def _synthetic_photo(corners, canvas_size=(1000, 800), fill_color=(40, 120, 200)):
    canvas = np.full((canvas_size[1], canvas_size[0], 3), 230, dtype=np.uint8)
    cv2.fillConvexPoly(canvas, np.array(corners, dtype=np.int32), fill_color)
    return canvas


def _encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()


def test_find_card_corners_detects_a_rectangle():
    corners = [(200, 100), (700, 100), (700, 700), (200, 700)]
    found = find_card_corners(_synthetic_photo(corners))
    assert found is not None
    assert found.shape == (4, 2)


def test_find_card_corners_returns_none_without_a_shape():
    blank = np.full((400, 400, 3), 230, dtype=np.uint8)
    assert find_card_corners(blank) is None


def test_find_card_corners_rejects_non_card_shaped_internal_contour():
    """Regression: found live against a real reference image (no
    photographed background at all — the whole frame IS the card) where a
    high-contrast region within the artwork itself formed a clean 4-point
    contour that passed the area threshold but had nothing like a card's
    aspect ratio. Before this check it got accepted as "the card" and
    warped into a wrong, unrelated-looking crop.
    """
    canvas = np.full((1000, 800, 3), 230, dtype=np.uint8)
    banner = np.array([(50, 400), (750, 400), (750, 600), (50, 600)], dtype=np.int32)
    cv2.fillConvexPoly(canvas, banner, (10, 10, 10))
    assert find_card_corners(canvas) is None


def test_preprocess_image_isolates_the_card_region():
    fill_color = (40, 120, 200)  # BGR
    corners = [(220, 90), (710, 130), (680, 690), (190, 660)]  # slightly skewed
    png_bytes = _encode_png(_synthetic_photo(corners, fill_color=fill_color))

    output_size = (300, 420)
    normalized = preprocess_image(png_bytes, output_size=output_size)

    assert normalized.shape[:2] == (output_size[1], output_size[0])
    center = normalized[output_size[1] // 2, output_size[0] // 2].astype(int)
    background = np.array([230, 230, 230])
    assert np.linalg.norm(center - background) > 30, "expected card color at center, not background"


def test_preprocess_image_falls_back_when_no_contour_found():
    flat = np.full((400, 300, 3), 100, dtype=np.uint8)
    png_bytes = _encode_png(flat)
    normalized = preprocess_image(png_bytes, output_size=(150, 200))
    assert normalized.shape[:2] == (200, 150)


def test_preprocess_image_rejects_undecodable_bytes():
    import pytest

    with pytest.raises(ValueError):
        preprocess_image(b"not an image", output_size=(100, 140))


def test_four_rotations_returns_four_shapes():
    image = np.zeros((100, 60, 3), dtype=np.uint8)
    rotations = four_rotations(image)
    assert len(rotations) == 4
    assert rotations[0].shape == (100, 60, 3)
    assert rotations[1].shape == (60, 100, 3)
    assert rotations[2].shape == (100, 60, 3)
    assert rotations[3].shape == (60, 100, 3)
