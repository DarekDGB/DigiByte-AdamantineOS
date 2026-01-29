import pytest

from adamantine.v1.policy.risk_policy import RiskPolicy


def test_default_policy_is_valid() -> None:
    p = RiskPolicy()
    p.validate()
    assert p.min_overall_score == 85


def test_policy_rejects_out_of_range_score() -> None:
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score=-1).validate()
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score=101).validate()
