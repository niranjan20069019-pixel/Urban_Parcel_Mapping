"""Test confidence engine."""
import pytest
from app.services.confidence_service import _DEFAULT_WEIGHTS, ConfidenceFactor


def test_confidence_weights_sum_to_one():
    assert abs(sum(_DEFAULT_WEIGHTS.values()) - 1.0) < 0.01


def test_confidence_factor_fields():
    f = ConfidenceFactor(name="test", score=0.8, weight=0.5, details={"k": "v"})
    assert f.name == "test"
    assert f.score == 0.8
    assert f.weight == 0.5
    assert f.details == {"k": "v"}
