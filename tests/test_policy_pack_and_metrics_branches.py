from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.obs.metrics import Metrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def test_metrics_inc_ignores_empty_reason_id() -> None:
    m = Metrics()
    m.inc("")  # should be ignored
    assert m.snapshot() == {}


def test_risk_policy_rejects_non_policy_pack_type() -> None:
    p = RiskPolicy(policy_pack="nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        p.validate()


def test_risk_policy_effective_external_reason_map_none_when_no_pack() -> None:
    p = RiskPolicy(policy_pack=None)
    assert p.effective_external_reason_map() is None


def test_policy_pack_rejects_external_reason_map_wrong_type() -> None:
    pack = PolicyPack(external_reason_map="nope")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pack.validate()
