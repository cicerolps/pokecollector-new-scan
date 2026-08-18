import cv2
import numpy as np

from app.db.models import Card, CardHash


def _synthetic_card_png() -> bytes:
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    corners = np.array([(220, 90), (710, 130), (680, 690), (190, 660)], dtype=np.int32)
    cv2.fillConvexPoly(canvas, corners, (40, 120, 200))
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


def test_scan_endpoint_returns_no_match_on_empty_catalog(client):
    response = client.post(
        "/api/v1/scan",
        files={"image": ("photo.png", _synthetic_card_png(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_match"
    assert body["card_id"] is None
    assert body["candidates"] == []
    assert body["scan_log_id"] is not None


def test_scan_endpoint_rejects_empty_upload(client):
    response = client.post(
        "/api/v1/scan",
        files={"image": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400


def test_scan_endpoint_rejects_undecodable_image(client):
    response = client.post(
        "/api/v1/scan",
        files={"image": ("not-an-image.png", b"this is not a png", "image/png")},
    )
    assert response.status_code == 400


def test_scan_confirm_updates_the_scan_log(client, db_session):
    db_session.add(
        Card(id="a", source_api="tcgdex", name="A", set_id="s", set_name="S", number="1/1")
    )
    db_session.commit()

    scan_response = client.post(
        "/api/v1/scan",
        files={"image": ("photo.png", _synthetic_card_png(), "image/png")},
    )
    scan_log_id = scan_response.json()["scan_log_id"]

    confirm_response = client.post(
        "/api/v1/scan/confirm",
        json={"scan_log_id": scan_log_id, "card_id": "a"},
    )

    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["scan_log_id"] == scan_log_id
    assert body["card"]["id"] == "a"


def test_scan_confirm_404s_on_unknown_scan_log(client):
    response = client.post(
        "/api/v1/scan/confirm", json={"scan_log_id": 999999, "card_id": "a"}
    )
    assert response.status_code == 404


def test_scan_confirm_404s_on_unknown_card(client, db_session):
    scan_response = client.post(
        "/api/v1/scan",
        files={"image": ("photo.png", _synthetic_card_png(), "image/png")},
    )
    scan_log_id = scan_response.json()["scan_log_id"]

    response = client.post(
        "/api/v1/scan/confirm",
        json={"scan_log_id": scan_log_id, "card_id": "does-not-exist"},
    )
    assert response.status_code == 404
