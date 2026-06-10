from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_HIGH_RISK", internal_reason_id=ReasonId.DENY_EQC.value),
        )
    )


def _policy() -> RiskPolicy:
    # RiskPolicy enforces allowlist via PolicyPack (strict deny-by-default).
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("AC_HIGH_RISK", "AC_OK", "ok"),
        external_reason_map=_reason_map(),
    )
    return RiskPolicy(min_overall_score=85, policy_pack=pack)


def _payload() -> dict:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "generated_at": 120,
        "overall_score": 73,
        "signals": [
            {"source": "ac_model", "severity": 73, "reason_ids": ["AC_HIGH_RISK"]},
        ],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def test_oracle_v3_accepts_valid_payload() -> None:
    out = parse_adaptive_core_oracle_v3(
        payload=_payload(),
        now=150,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        policy=_policy(),
    )
    assert out.context_hash == "a" * 64
    assert out.report.overall_score == 73


def test_oracle_v3_rejects_unknown_fields() -> None:
    p = _payload()
    p["extra"] = 1
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_rejects_version_mismatch() -> None:
    p = _payload()
    p["ac_iface_version"] = "nope"
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.DENY_VERSION_MISMATCH


def test_oracle_v3_rejects_context_hash_mismatch() -> None:
    p = _payload()
    p["context_hash"] = "b" * 64
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH


def test_oracle_v3_rejects_invalid_time_window() -> None:
    p = _payload()
    p["issued_at"] = 200
    p["expires_at"] = 100
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_rejects_unknown_external_reason() -> None:
    p = _payload()
    p["signals"][0]["reason_ids"] = ["UNKNOWN"]
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_oracle_v3_determinism_replay() -> None:
    p = _payload()
    out1 = parse_adaptive_core_oracle_v3(
        payload=p,
        now=150,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        policy=_policy(),
    )
    out2 = parse_adaptive_core_oracle_v3(
        payload=p,
        now=150,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        policy=_policy(),
    )
    assert out1 == out2


def test_oracle_v3_rejects_non_canonical_context_hash_format() -> None:
    p = _payload()
    p["context_hash"] = "A" * 64
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=150,
            expected_context_hash="A" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_rejects_not_yet_valid_or_expired_window() -> None:
    future = _payload()
    future["issued_at"] = 151
    future["expires_at"] = 200
    future["generated_at"] = 150
    with pytest.raises(AdapterError) as future_error:
        parse_adaptive_core_oracle_v3(
            payload=future,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert future_error.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT

    expired = _payload()
    expired["issued_at"] = 100
    expired["expires_at"] = 149
    expired["generated_at"] = 120
    with pytest.raises(AdapterError) as expired_error:
        parse_adaptive_core_oracle_v3(
            payload=expired,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert expired_error.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT
