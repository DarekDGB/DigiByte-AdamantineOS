from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.policy.risk_policy import RiskPolicy


def test_policy_pack_validate_rejects_negative_threshold() -> None:
    p = PolicyPack(min_overall_score=-1)
    with pytest.raises(ValueError):
        p.validate()


def test_policy_pack_validate_rejects_threshold_over_100() -> None:
    p = PolicyPack(min_overall_score=101)
    with pytest.raises(ValueError):
        p.validate()


def test_risk_policy_effective_external_reason_map_none_when_no_pack() -> None:
    rp = RiskPolicy(policy_pack=None)
    assert rp.effective_external_reason_map() is None


def test_risk_policy_effective_allowed_reason_ids_defaults_to_ok_when_no_pack() -> None:
    rp = RiskPolicy(policy_pack=None)
    assert tuple(rp.effective_allowed_external_reason_ids()) == ("ok",)
