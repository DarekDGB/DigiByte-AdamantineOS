from __future__ import annotations

import pytest

from adamantine.v1.policy.risk_policy import RiskPolicy


def test_risk_policy_validate_rejects_invalid_min_overall_score_type() -> None:
    rp = RiskPolicy(min_overall_score="85")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        rp.validate()
