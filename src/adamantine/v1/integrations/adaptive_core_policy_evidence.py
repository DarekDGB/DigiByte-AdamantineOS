from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.external_reason_registry import ExternalReasonRegistryV1
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport
from adamantine.v1.contracts.shield import ExternalReasonMap
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


class AdaptiveCorePolicyEvidenceState(str, Enum):
    """Stable Adaptive Core policy evidence states.

    Adaptive Core is advisory evidence only. It can continue checks or deny, but
    it can never grant final AdamantineOS approval by itself.
    """

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_ADAPTIVE_CORE_REJECTED = "DENY_ADAPTIVE_CORE_REJECTED"
    DENY_UNSUPPORTED_INPUT = "DENY_UNSUPPORTED_INPUT"
    DENY_SCORE_BELOW_THRESHOLD = "DENY_SCORE_BELOW_THRESHOLD"
    DENY_CONTEXT_HASH_MISMATCH = "DENY_CONTEXT_HASH_MISMATCH"
    DENY_EARLIER_GATE_DENIED = "DENY_EARLIER_GATE_DENIED"
    DENY_HIDDEN_AUTHORITY_FIELD = "DENY_HIDDEN_AUTHORITY_FIELD"
    DENY_POLICY_INVALID = "DENY_POLICY_INVALID"


@dataclass(frozen=True)
class AdaptiveCorePolicyEvidenceResult:
    """Normalized Adaptive Core evidence for the future policy engine."""

    source: str
    state: AdaptiveCorePolicyEvidenceState
    outcome: str
    reason_id: ReasonId | str
    accepted_as_evidence: bool
    final_approval: bool
    handoff_allowed: bool
    context_hash: str | None
    overall_score: int | None
    min_overall_score: int | None
    generated_at: int | None
    issued_at: int | None
    expires_at: int | None
    oracle_version: str | None
    external_source_id: str | None
    dominant_reason_ids: tuple[str, ...]
    report: RiskReport | None = None
    oracle: AdaptiveCoreOracleV3 | None = None


def _reason_text(reason_id: ReasonId | str) -> str:
    return reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)


def _deny(
    *,
    state: AdaptiveCorePolicyEvidenceState,
    reason_id: ReasonId | str,
    context_hash: str | None = None,
    overall_score: int | None = None,
    min_overall_score: int | None = None,
    generated_at: int | None = None,
    issued_at: int | None = None,
    expires_at: int | None = None,
    oracle_version: str | None = None,
    external_source_id: str | None = None,
    dominant_reason_ids: tuple[str, ...] | None = None,
    report: RiskReport | None = None,
    oracle: AdaptiveCoreOracleV3 | None = None,
) -> AdaptiveCorePolicyEvidenceResult:
    reason = _reason_text(reason_id)
    return AdaptiveCorePolicyEvidenceResult(
        source="adaptive_core",
        state=state,
        outcome="DENY",
        reason_id=reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        handoff_allowed=False,
        context_hash=context_hash,
        overall_score=overall_score,
        min_overall_score=min_overall_score,
        generated_at=generated_at,
        issued_at=issued_at,
        expires_at=expires_at,
        oracle_version=oracle_version,
        external_source_id=external_source_id,
        dominant_reason_ids=dominant_reason_ids or (reason,),
        report=report,
        oracle=oracle,
    )


def _contains_forbidden_authority_field(value: Any) -> bool:
    forbidden = {
        "allow",
        "approve",
        "approved",
        "authority",
        "authorization",
        "bypass",
        "final_approval",
        "grant_execution",
        "handoff_allowed",
        "override",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in forbidden:
                return True
            if _contains_forbidden_authority_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_authority_field(item) for item in value)
    return False


def _normalize_policy(policy: RiskPolicy | None) -> RiskPolicy | AdaptiveCorePolicyEvidenceResult:
    selected = policy or RiskPolicy()
    if not isinstance(selected, RiskPolicy):
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_POLICY_INVALID,
            reason_id=ReasonId.DENY_POLICY,
        )
    try:
        selected.validate()
    except ValueError:
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_POLICY_INVALID,
            reason_id=ReasonId.DENY_POLICY,
        )
    return selected


def _report_from_input(
    adaptive_core_input: Any,
    *,
    now: int,
    expected_context_hash: str,
    reason_map: ExternalReasonMap | None,
    reason_registry: ExternalReasonRegistryV1 | None,
    policy: RiskPolicy,
) -> tuple[RiskReport, AdaptiveCoreOracleV3 | None] | AdaptiveCorePolicyEvidenceResult:
    if isinstance(adaptive_core_input, AdaptiveCoreOracleV3):
        try:
            adaptive_core_input.validate(now=now)
        except ValueError:
            return _deny(
                state=AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED,
                reason_id=ReasonId.EQC_INVALID_RISK_REPORT,
            )
        return adaptive_core_input.report, adaptive_core_input

    if isinstance(adaptive_core_input, RiskReport):
        try:
            adaptive_core_input.validate(now=now)
        except ValueError:
            return _deny(
                state=AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED,
                reason_id=ReasonId.EQC_INVALID_RISK_REPORT,
            )
        return adaptive_core_input, None

    if isinstance(adaptive_core_input, Mapping):
        iface = adaptive_core_input.get("ac_iface_version")
        try:
            if iface == "adaptive_core_oracle_v3":
                oracle = parse_adaptive_core_oracle_v3(
                    payload=adaptive_core_input,
                    now=now,
                    expected_context_hash=expected_context_hash,
                    reason_map=reason_map,
                    reason_registry=reason_registry,
                    policy=policy,
                )
                return oracle.report, oracle
            report = parse_risk_report(
                payload=adaptive_core_input,
                now=now,
                expected_context_hash=expected_context_hash,
                reason_map=reason_map,
                reason_registry=reason_registry,
                policy=policy,
            )
            return report, None
        except AdapterError as exc:
            return _deny(
                state=AdaptiveCorePolicyEvidenceState.DENY_ADAPTIVE_CORE_REJECTED,
                reason_id=exc.reason_id,
            )

    return _deny(
        state=AdaptiveCorePolicyEvidenceState.DENY_UNSUPPORTED_INPUT,
        reason_id=ReasonId.EQC_INVALID_RISK_REPORT,
    )


def _extract_earlier_denies(prior_gate_results: Sequence[Any] | None) -> tuple[str, ...]:
    if prior_gate_results is None:
        return ()
    denies: list[str] = []
    for result in prior_gate_results:
        outcome = getattr(result, "outcome", None)
        reason_id = getattr(result, "reason_id", None)
        if isinstance(result, Mapping):
            outcome = result.get("outcome", outcome)
            reason_id = result.get("reason_id", reason_id)
        if outcome == "DENY":
            denies.append(_reason_text(reason_id or ReasonId.DENY_POLICY))
    return tuple(denies)


def normalize_adaptive_core_policy_evidence(
    adaptive_core_input: Any,
    *,
    now: int,
    expected_context_hash: str,
    reason_map: ExternalReasonMap | None = None,
    reason_registry: ExternalReasonRegistryV1 | None = None,
    policy: RiskPolicy | None = None,
    prior_gate_results: Sequence[Any] | None = None,
) -> AdaptiveCorePolicyEvidenceResult:
    """Normalize Adaptive Core evidence for policy-engine consumption.

    This is a thin translator boundary. It consumes existing Adaptive Core
    adapter outputs or calls the existing adapter functions for raw payloads. It
    does not duplicate parser logic and it never treats Adaptive Core as final
    approval authority.
    """

    earlier_denies = _extract_earlier_denies(prior_gate_results)
    if earlier_denies:
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_EARLIER_GATE_DENIED,
            reason_id=earlier_denies[0],
            dominant_reason_ids=earlier_denies,
        )

    selected_policy = _normalize_policy(policy)
    if isinstance(selected_policy, AdaptiveCorePolicyEvidenceResult):
        return selected_policy

    if _contains_forbidden_authority_field(adaptive_core_input):
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            min_overall_score=selected_policy.min_overall_score,
        )

    normalized = _report_from_input(
        adaptive_core_input,
        now=now,
        expected_context_hash=expected_context_hash,
        reason_map=reason_map,
        reason_registry=reason_registry,
        policy=selected_policy,
    )
    if isinstance(normalized, AdaptiveCorePolicyEvidenceResult):
        return normalized

    report, oracle = normalized
    issued_at = oracle.issued_at if oracle is not None else None
    expires_at = oracle.expires_at if oracle is not None else None

    if report.context_hash != expected_context_hash:
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
            reason_id=ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH,
            context_hash=report.context_hash,
            overall_score=report.overall_score,
            min_overall_score=selected_policy.min_overall_score,
            generated_at=report.generated_at,
            issued_at=issued_at,
            expires_at=expires_at,
            oracle_version=report.oracle_version,
            external_source_id=report.external_source_id,
            report=report,
            oracle=oracle,
        )

    if report.overall_score < selected_policy.min_overall_score:
        return _deny(
            state=AdaptiveCorePolicyEvidenceState.DENY_SCORE_BELOW_THRESHOLD,
            reason_id=ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD,
            context_hash=report.context_hash,
            overall_score=report.overall_score,
            min_overall_score=selected_policy.min_overall_score,
            generated_at=report.generated_at,
            issued_at=issued_at,
            expires_at=expires_at,
            oracle_version=report.oracle_version,
            external_source_id=report.external_source_id,
            report=report,
            oracle=oracle,
        )

    return AdaptiveCorePolicyEvidenceResult(
        source="adaptive_core",
        state=AdaptiveCorePolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
        outcome="ALLOW_EVIDENCE",
        reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        handoff_allowed=True,
        context_hash=report.context_hash,
        overall_score=report.overall_score,
        min_overall_score=selected_policy.min_overall_score,
        generated_at=report.generated_at,
        issued_at=issued_at,
        expires_at=expires_at,
        oracle_version=report.oracle_version,
        external_source_id=report.external_source_id,
        dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
        report=report,
        oracle=oracle,
    )
