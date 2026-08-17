import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Card
from app.pipeline import ocr_disambiguator
from app.pipeline.hash_matcher import Candidate


class _FakeReader:
    def __init__(self, text: str):
        self._text = text

    def readtext(self, image, detail=0):
        return [self._text]


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_crop_number_region_is_smaller_than_the_full_image():
    image = np.zeros((1000, 800, 3), dtype=np.uint8)
    crop = ocr_disambiguator.crop_number_region(image)
    assert crop.shape[0] < image.shape[0]
    assert crop.shape[1] < image.shape[1]


def test_extract_number_parses_slash_format_amid_noise():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    reader = _FakeReader("Some noise 025/198 more noise")
    assert ocr_disambiguator.extract_number(image, reader=reader) == "025/198"


def test_extract_number_returns_none_without_a_match():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    reader = _FakeReader("no number here")
    assert ocr_disambiguator.extract_number(image, reader=reader) is None


def test_disambiguate_picks_the_uniquely_matching_candidate(db_session):
    db_session.add_all(
        [
            Card(id="a", source_api="tcgdex", name="A", set_id="s", set_name="S", number="25/198"),
            Card(id="b", source_api="tcgdex", name="B", set_id="s", set_name="S", number="99/198"),
        ]
    )
    db_session.commit()

    candidates = [Candidate("a", 5, 5, 5), Candidate("b", 6, 6, 6)]
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    reader = _FakeReader("25/198")

    result = ocr_disambiguator.disambiguate(db_session, image, candidates, reader=reader)
    assert result is not None
    assert result.card_id == "a"


def test_disambiguate_returns_none_when_ocr_finds_nothing(db_session):
    candidates = [Candidate("a", 5, 5, 5)]
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    reader = _FakeReader("garbage")

    assert ocr_disambiguator.disambiguate(db_session, image, candidates, reader=reader) is None


def test_disambiguate_returns_none_when_no_candidate_matches(db_session):
    db_session.add(Card(id="a", source_api="tcgdex", name="A", set_id="s", set_name="S", number="25/198"))
    db_session.commit()

    candidates = [Candidate("a", 5, 5, 5)]
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    reader = _FakeReader("999/999")

    assert ocr_disambiguator.disambiguate(db_session, image, candidates, reader=reader) is None
