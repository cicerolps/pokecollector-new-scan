from app.config import Settings
from app.db.models import CardHash
from app.pipeline import hash_matcher


def test_hamming_distance_identical_hashes_is_zero():
    assert hash_matcher._hamming("ffff0000ffff0000", "ffff0000ffff0000") == 0


def test_hamming_distance_missing_hash_is_treated_as_max():
    assert hash_matcher._hamming(None, "ffff0000ffff0000") == 64


def test_search_candidates_ranks_exact_match_first(db_session):
    db_session.add_all(
        [
            CardHash(
                card_id="exact",
                phash="ffff0000ffff0000",
                dhash="0000ffff0000ffff",
                whash="f0f0f0f0f0f0f0f0",
            ),
            CardHash(
                card_id="far",
                phash="0000000000000000",
                dhash="ffffffffffffffff",
                whash="0000000000000000",
            ),
        ]
    )
    db_session.commit()

    hashes = {
        "phash": "ffff0000ffff0000",
        "dhash": "0000ffff0000ffff",
        "whash": "f0f0f0f0f0f0f0f0",
    }
    candidates = hash_matcher.search_candidates(db_session, hashes, top_n=5)

    assert candidates[0].card_id == "exact"
    assert candidates[0].combined_distance == 0
    assert candidates[1].card_id == "far"


def test_search_candidates_respects_top_n(db_session):
    db_session.add_all(
        CardHash(card_id=f"c{i}", phash="0" * 16, dhash="0" * 16, whash="0" * 16)
        for i in range(10)
    )
    db_session.commit()

    candidates = hash_matcher.search_candidates(
        db_session, {"phash": "0" * 16, "dhash": "0" * 16, "whash": "0" * 16}, top_n=3
    )
    assert len(candidates) == 3


def test_evaluate_confidence_confident_when_gap_large():
    settings = Settings(hash_confidence_gap=10, hash_no_match_distance=60)
    candidates = [
        hash_matcher.Candidate("a", 2, 2, 2),  # combined 6
        hash_matcher.Candidate("b", 20, 20, 20),  # combined 60, gap 54
    ]
    assert hash_matcher.evaluate_confidence(candidates, settings=settings) == "confident"


def test_evaluate_confidence_ambiguous_when_gap_small():
    settings = Settings(hash_confidence_gap=10, hash_no_match_distance=60)
    candidates = [
        hash_matcher.Candidate("a", 2, 2, 2),  # combined 6
        hash_matcher.Candidate("b", 3, 3, 3),  # combined 9, gap 3
    ]
    assert hash_matcher.evaluate_confidence(candidates, settings=settings) == "ambiguous"


def test_evaluate_confidence_single_candidate_is_confident():
    settings = Settings(hash_confidence_gap=10, hash_no_match_distance=60)
    candidates = [hash_matcher.Candidate("a", 2, 2, 2)]
    assert hash_matcher.evaluate_confidence(candidates, settings=settings) == "confident"


def test_evaluate_confidence_no_match_when_top_candidate_too_far():
    settings = Settings(hash_confidence_gap=10, hash_no_match_distance=60)
    candidates = [hash_matcher.Candidate("a", 30, 30, 30)]  # combined 90 >= 60
    assert hash_matcher.evaluate_confidence(candidates, settings=settings) == "no_match"


def test_evaluate_confidence_empty_candidates_is_no_match():
    assert hash_matcher.evaluate_confidence([], settings=Settings()) == "no_match"
