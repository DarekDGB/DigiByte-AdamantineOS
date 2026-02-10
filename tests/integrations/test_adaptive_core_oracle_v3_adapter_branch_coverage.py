from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.obs.metrics import InMemoryMetrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def _reason_map() -> ExternalReasonMap:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )
    m.validate()
    return m


def _policy() -> RiskPolicy:
    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("AC_OK",),
        external_reason_map=_reason_map(),
    )
    pack.validate()
    return RiskPolicy(min_overall_score=85, policy_pack=pack)


def _payload() -> dict:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "generated_at": 120,
        "overall_score": 95,
        "signals": [
            {"source": "ac_model", "severity": 10, "reason_ids": ["AC_OK"]},
        ],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def test_oracle_v3_adapter_metrics_inc_path_is_hit() -> None:
    m = InMemoryMetrics()
    with pytest.raises(AdapterError):
        parse_adaptive_core_oracle_v3(
            payload=_payload(),
            now="nope",  # type: ignore[arg-type]
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
            metrics=m,
        )
    assert sum(m.snapshot().values()) >= 1


def test_oracle_v3_adapter_rejects_expected_context_hash_blank() -> None:
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=_payload(),
            now=200,
            expected_context_hash="",
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_adapter_rejects_payload_not_mapping() -> None:
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload="nope",  # type: ignore[arg-type]
            now=200,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_adapter_rejects_context_hash_missing_or_empty() -> None:
    p = _payload()
    p["context_hash"] = ""
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=200,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_adapter_rejects_issued_at_expires_at_not_int() -> None:
    p = _payload()
    p["issued_at"] = "100"
    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=p,
            now=200,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            policy=_policy(),
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_adapter_contract_validation_failure_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # The adapter has a defensive try/except around out.validate(now=...).
    # Under normal conditions, parse_risk_report() already validated the report, so out.validate should succeed.
    # To cover the defensive branch deterministically, we patch RiskReport.validate to raise.
    from adamantine.v1.contracts import risk as risk_mod

    original = risk_mod.RiskReport.validate

    def boom(self, *, now: int) -> None:  # type: ignore[override]
        raise ValueError("boom")

    monkeypatch.setattr(risk_mod.RiskReport, "validate", boom, raising=True)

    try:
        with pytest.raises(AdapterError) as e:
            parse_adaptive_core_oracle_v3(
                payload=_payload(),
                now=200,
                expected_context_hash="a" * 64,
                reason_map=_reason_map(),
                policy=_policy(),
            )
        assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT
    finally:
        monkeypatch.setattr(risk_mod.RiskReport, "validate", original, raising=True)
