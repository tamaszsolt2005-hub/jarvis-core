import pytest

from scoring_core import calculate_weighted_score


def test_shared_scoring_core_calculates_weighted_score():
    assert calculate_weighted_score({"fit": 80, "confidence": 60}, {"fit": 0.75, "confidence": 0.25}) == 75.0


def test_shared_scoring_core_returns_none_for_missing_dimension():
    assert calculate_weighted_score({"fit": 80, "confidence": None}, {"fit": 0.75, "confidence": 0.25}) is None


def test_shared_scoring_core_supports_reverse_scored_dimensions():
    assert calculate_weighted_score({"benefit": 80, "risk": 20}, {"benefit": 0.75, "risk": 0.25}, reverse_scored=("risk",)) == 80.0


@pytest.mark.parametrize("value", [-1, 101, True, "90"])
def test_shared_scoring_core_rejects_invalid_scores(value):
    with pytest.raises(ValueError):
        calculate_weighted_score({"fit": value}, {"fit": 1.0})


def test_shared_scoring_core_requires_weights_to_sum_to_one():
    with pytest.raises(ValueError):
        calculate_weighted_score({"fit": 80}, {"fit": 0.8})
