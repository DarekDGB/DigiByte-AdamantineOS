from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.integrations.adaptive_core_policy_evidence import (
    AdaptiveCorePolicyEvidenceState,
    normalize_adaptive_core_policy_evidence,
)
from adamantine.v1.policy.risk_policy import RiskPolicy


CTX = "a" * 64
NOW = 1_000


def _reason_map():
    return PolicyPack().external_reason_map


def _risk_payload(*, score: int = 90, context_hash: str = CTX):
    return {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": context_hash,
        "generated_at": 900,
        "overall_score": score,
        "signals": [{"source": "adaptive-core", "severity": 5, "reason_ids": ["ok"]}],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }


def _oracle_payload(*, score: int = 90, context_hash: str = CTX):
    payload = _risk_payload(score=score, context_hash=context_hash)
    payload.update(
        {
            "ac_iface_version": "adaptive_core_oracle_v3",
            "issued_at": 880,
            "expires_at": 1_100,
            "oracle_version": "ac-oracle-v3",
        }
    )
    return payload


def _report(*, score: int = 90, context_hash: str = CTX) -> RiskReport:
    return RiskReport(
        context_hash=context_hash,
        signals=(RiskSignal(source="adaptive-core", severity=5, reason_ids=(ReasonId.EVIDENCE_OK.value,)),),
        overall_score=score,
        generated_at=900,
        oracle_version="ac-v0",
        external_source_id="rpt-1",
    )


def test_normalizes_valid_risk_payload_as_evidence_only() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id is ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.handoff_allowed is True
    assert result.context_hash == CTX
    assert result.overall_score == 90
    assert result.min_overall_score == 85
    assert result.report is not None
    assert result.oracle is None


def test_normalizes_valid_oracle_v3_payload_without_reimplementing_parser() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _oracle_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.final_approval is False
    assert result.issued_at == 880
    assert result.expires_at == 1_100
    assert result.oracle is not None
    assert result.report is result.oracle.report


def test_consumes_already_parsed_risk_report_cleanly() -> None:
    report = _report(score=91)

    result = normalize_adaptive_core_policy_evidence(
        report,
        now=NOW,
        expected_context_hash=CTX,
        policy=RiskPolicy(min_overall_score=90),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.report is report
    assert result.overall_score == 91
    assert result.min_overall_score == 90


def test_consumes_already_parsed_oracle_cleanly() -> None:
    report = _report(score=95)
    oracle = AdaptiveCoreOracleV3(context_hash=CTX, issued_at=880, expires_at=1_100, report=report)

    result = normalize_adaptive_core_policy_evidence(
        oracle,
        now=NOW,
        expected_context_hash=CTX,
        policy=RiskPolicy(min_overall_score=90),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.oracle is oracle
    assert result.report is report
    assert result.issued_at == 880
    assert result.expires_at == 1_100


def test_score_below_threshold_denies_with_explicit_reason() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(score=84),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_SCORE_BELOW_THRESHOLD
    assert result.outcome == "DENY"
    assert result.reason_id is ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == (ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value,)


def test_adapter_failure_becomes_structured_deny_reason_id() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(context_hash="b" * 64),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH
    assert result.outcome == "DENY"


def test_unknown_external_reason_stays_fail_closed_through_existing_adapter() -> None:
    payload = _risk_payload()
    payload["signals"] = [{"source": "adaptive-core", "severity": 5, "reason_ids": ["new-risk"]}]

    result = normalize_adaptive_core_policy_evidence(
        payload,
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_hidden_authority_field_denies_before_adapter_use() -> None:
    payload = _risk_payload()
    payload["final_approval"] = True

    result = normalize_adaptive_core_policy_evidence(
        payload,
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID
    assert result.report is None


def test_unsupported_input_denies() -> None:
    result = normalize_adaptive_core_policy_evidence(
        ["not", "a", "report"],
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_already_parsed_report_context_mismatch_denies() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _report(context_hash="b" * 64),
        now=NOW,
        expected_context_hash=CTX,
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id is ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH


@dataclass(frozen=True)
class _PriorResult:
    outcome: str
    reason_id: ReasonId


def test_prior_gate_deny_dominates_before_adaptive_core_evaluation() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
        prior_gate_results=[_PriorResult(outcome="DENY", reason_id=ReasonId.DENY_WSQK)],
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.reason_id == ReasonId.DENY_WSQK.value
    assert result.dominant_reason_ids == (ReasonId.DENY_WSQK.value,)
    assert result.report is None


def test_prior_gate_mapping_deny_dominates() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
        prior_gate_results=[{"outcome": "DENY", "reason_id": ReasonId.DENY_EQC}],
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.dominant_reason_ids == (ReasonId.DENY_EQC.value,)


def test_invalid_policy_denies_without_adapter_rewrite() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
        policy=RiskPolicy(min_overall_score=101),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_POLICY_INVALID
    assert result.reason_id is ReasonId.DENY_POLICY


def test_invalid_already_parsed_report_denies() -> None:
    report = RiskReport(
        context_hash=CTX,
        signals=(RiskSignal(source="adaptive-core", severity=5, reason_ids=(ReasonId.EVIDENCE_OK.value,)),),
        overall_score=90,
        generated_at=NOW + 1,
    )

    result = normalize_adaptive_core_policy_evidence(
        report,
        now=NOW,
        expected_context_hash=CTX,
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_invalid_already_parsed_oracle_denies() -> None:
    oracle = AdaptiveCoreOracleV3(
        context_hash=CTX,
        issued_at=1_100,
        expires_at=1_000,
        report=_report(score=90),
    )

    result = normalize_adaptive_core_policy_evidence(
        oracle,
        now=NOW,
        expected_context_hash=CTX,
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_oracle_v3_unknown_field_denies_through_existing_adapter() -> None:
    payload = _oracle_payload()
    payload["unknown"] = "deny"

    result = normalize_adaptive_core_policy_evidence(
        payload,
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED
    assert result.reason_id is ReasonId.EQC_INVALID_RISK_REPORT


def test_nested_hidden_authority_field_denies() -> None:
    payload = _risk_payload()
    payload["nested"] = {"override": True}

    result = normalize_adaptive_core_policy_evidence(
        payload,
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_non_risk_policy_object_denies() -> None:
    result = normalize_adaptive_core_policy_evidence(
        _risk_payload(),
        now=NOW,
        expected_context_hash=CTX,
        reason_map=_reason_map(),
        policy=object(),  # type: ignore[arg-type]
    )

    assert result.state is AdaptiveCorePolicyEvidenceState.DENY_POLICY_INVALID
    assert result.reason_id is ReasonId.DENY_POLICY
