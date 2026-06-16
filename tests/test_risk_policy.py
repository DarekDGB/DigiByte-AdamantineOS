import pytest

from adamantine.v1.policy.risk_policy import RiskPolicy, ResilienceMode, ShieldRuntimeBoundary, UnknownReasonMode


def test_default_policy_is_valid() -> None:
    p = RiskPolicy()
    p.validate()
    assert p.min_overall_score == 85
    assert p.unknown_reason_mode is UnknownReasonMode.DENY_EXPLICIT
    assert p.resilience_mode is ResilienceMode.STRICT_FAIL_CLOSED
    assert p.shield_runtime_boundary is ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2


def test_policy_rejects_out_of_range_score() -> None:
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score=-1).validate()
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score=101).validate()


def test_policy_accepts_explicit_modes() -> None:
    p = RiskPolicy(
        min_overall_score=90,
        unknown_reason_mode=UnknownReasonMode.DENY_EXPLICIT,
        resilience_mode=ResilienceMode.STRICT_FAIL_CLOSED,
    )
    p.validate()
