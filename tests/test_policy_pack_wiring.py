from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


def test_policy_pack_allowlist_allows_new_reason_when_explicitly_listed() -> None:
    now = 200
    expected_hash = "a" * 64

    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 190,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["NEW_REASON"]}],
    }

    # PolicyPack must include both allowlist AND mapping for every allowlisted external reason id.
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("ok", "NEW_REASON"),
        external_reason_map=ExternalReasonMap(
            entries=(
                ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
                ExternalReasonMapEntry(external_id="NEW_REASON", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            )
        ),
    )
    policy = RiskPolicy(min_overall_score=85, policy_pack=pack)

    rpt = parse_risk_report(
        payload=payload,
        now=now,
        expected_context_hash=expected_hash,
        policy=policy,
    )
    assert rpt.context_hash == expected_hash


def test_policy_pack_mismatch_is_rejected_by_risk_policy_validate() -> None:
    pack = PolicyPack(
        min_overall_score=90,
        allowed_external_reason_ids=("ok",),
        external_reason_map=ExternalReasonMap(
            entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
        ),
    )
    policy = RiskPolicy(min_overall_score=85, policy_pack=pack)

    with pytest.raises(ValueError):
        policy.validate()


def test_default_policy_pack_behavior_still_denies_unknown_reason() -> None:
    now = 200
    expected_hash = "a" * 64

    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 190,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["NEW_REASON"]}],
    }

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash=expected_hash,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )

    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON
