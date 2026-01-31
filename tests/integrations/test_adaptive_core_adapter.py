import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


def test_parse_risk_report_accepts_valid_payload() -> None:
    now = 150
    expected_hash = "a" * 64
    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 140,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"], "extra": "ignored"}],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }
    rpt = parse_risk_report(
        payload=payload,
        now=now,
        expected_context_hash=expected_hash,
        reason_map=PolicyPack().external_reason_map,
        policy=RiskPolicy(),
    )
    assert rpt.context_hash == expected_hash
    assert rpt.overall_score == 90


def test_parse_risk_report_denies_context_hash_mismatch() -> None:
    now = 150
    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": "b" * 64,
        "generated_at": 140,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
    }
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=payload,
            now=now,
            expected_context_hash="a" * 64,
            reason_map=PolicyPack().external_reason_map,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id is ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH


def test_parse_risk_report_denies_unknown_reason_id() -> None:
    now = 150
    expected_hash = "a" * 64
    payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": expected_hash,
        "generated_at": 140,
        "overall_score": 90,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["SOMETHING_NEW"]}],
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
