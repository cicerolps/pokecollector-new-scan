import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import get_db
from app.main import app


def _synthetic_card_png() -> bytes:
    canvas = np.full((800, 900, 3), 230, dtype=np.uint8)
    corners = np.array([(220, 90), (710, 130), (680, 690), (190, 660)], dtype=np.int32)
    cv2.fillConvexPoly(canvas, corners, (40, 120, 200))
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
