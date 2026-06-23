from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)

CTX = "a" * 64
REQUIRED_ALGORITHMS = ("classical-ed25519", "ml-dsa")
COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")


@dataclass(frozen=True)
class Evidence:
    state: str = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    outcome: str = "ALLOW_EVIDENCE"
    reason_id: ReasonId | str = ReasonId.EVIDENCE_OK
    accepted_as_evidence: bool = True
    verified: bool = True
    final_approval: bool = False
    handoff_allowed: bool = True
    context_hash: str = CTX
    dominant_reason_ids: tuple[str, ...] = (ReasonId.EVIDENCE_OK.value,)
    final_outcome: str | None = "ALLOW"
    receipt: Mapping[str, Any] | None = None
    verification_summary: Mapping[str, Any] | None = None


def allow_gates() -> dict[str, LocalPolicyGateResult]:
    return {
        "replay": LocalPolicyGateResult("replay", True, ReasonId.EVIDENCE_OK),
        "wallet_policy": LocalPolicyGateResult("wallet_policy", True, ReasonId.EVIDENCE_OK),
        "human": LocalPolicyGateResult("human", True, ReasonId.EVIDENCE_OK),
    }


def generic_evidence() -> Evidence:
    return Evidence(receipt=None, verification_summary=None)


def v4_receipt(*, schema_version: str = "shield.receipt.v2", contract_version: int = 4) -> dict[str, Any]:
    return {"schema_version": schema_version, "contract_version": contract_version}


def algorithm_summary(*, algorithms: tuple[str, ...] = REQUIRED_ALGORITHMS) -> dict[str, Any]:
    return {"verified_algorithms": list(algorithms)}


def component_summaries(
    *,
    components: tuple[str, ...] = COMPONENT_IDS,
    algorithms: tuple[str, ...] = REQUIRED_ALGORITHMS,
) -> list[dict[str, Any]]:
    return [{"component_id": component_id, "verified_algorithms": list(algorithms)} for component_id in components]


def v4_summary(
    *,
    policy_version: str = "policy.v1",
    orchestrator: Mapping[str, Any] | None = None,
    components: Any | None = None,
) -> dict[str, Any]:
    return {
        "policy_version": policy_version,
        "orchestrator": algorithm_summary() if orchestrator is None else orchestrator,
        "components": component_summaries() if components is None else components,
    }


def v4_shield_evidence(**overrides: Any) -> Evidence:
    fields: dict[str, Any] = {"receipt": v4_receipt(), "verification_summary": v4_summary()}
    fields.update(overrides)
    return Evidence(**fields)


def run_engine(*, shield: Any, shield_v4_required: bool | object = True):
    gates = allow_gates()
    return evaluate_final_policy_engine(
        shield=shield,
        wsqk_v2=generic_evidence(),
        qid=generic_evidence(),
        adaptive_core=generic_evidence(),
        ai_gateway=generic_evidence(),
        expected_context_hash=CTX,
        shield_v4_required=shield_v4_required,  # type: ignore[arg-type]
        **gates,
    )


def assert_shield_v4_required_denial(result, dominant_reason: str) -> None:
    assert result.state == FinalPolicyEngineState.DENY_SHIELD_V4_REQUIRED
    assert result.outcome == "DENY"
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.stopped_at == "shield"
    assert result.evaluation_order == ("shield",)
    assert result.dominant_reason_ids == (dominant_reason,)
    assert result.final_approval is False


def test_shield_v4_required_accepts_verified_v4_receipt_before_local_gates() -> None:
    result = run_engine(shield=v4_shield_evidence())

    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION
    assert result.final_approval is True
    assert result.evaluation_order == (
        "shield",
        "wsqk_v2",
        "qid",
        "adaptive_core",
        "ai_gateway",
        "replay",
        "wallet_policy",
        "human",
        "final_adamantineos_decision",
    )


def test_shield_v4_required_rejects_invalid_mode_shape_before_evidence() -> None:
    result = run_engine(shield=v4_shield_evidence(), shield_v4_required="yes")

    assert result.state == FinalPolicyEngineState.DENY_SHIELD_V4_REQUIRED
    assert result.stopped_at == "shield_v4_required"
    assert result.evaluation_order == ("shield_v4_required",)
    assert result.dominant_reason_ids == ("SHIELD_V4_REQUIRED_MODE_INVALID",)


def test_shield_v4_required_rejects_unverified_result() -> None:
    result = run_engine(shield=v4_shield_evidence(verified=False))

    assert_shield_v4_required_denial(result, "SHIELD_V4_VERIFIED_RESULT_REQUIRED")


def test_shield_v4_required_rejects_missing_v4_receipt() -> None:
    result = run_engine(shield=Evidence(receipt=None, verification_summary=v4_summary()))

    assert_shield_v4_required_denial(result, "SHIELD_V4_RECEIPT_REQUIRED")


def test_shield_v4_required_rejects_v3_downgrade_receipt() -> None:
    result = run_engine(shield=v4_shield_evidence(receipt=v4_receipt(schema_version="shield.receipt.v1", contract_version=3)))

    assert_shield_v4_required_denial(result, "SHIELD_V4_DOWNGRADE_REJECTED")


def test_shield_v4_required_rejects_missing_verification_summary() -> None:
    result = run_engine(shield=Evidence(receipt=v4_receipt(), verification_summary=None))

    assert_shield_v4_required_denial(result, "SHIELD_V4_VERIFICATION_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_weak_policy() -> None:
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(policy_version="policy.weak")))

    assert_shield_v4_required_denial(result, "SHIELD_V4_POLICY_REQUIRED")


def test_shield_v4_required_rejects_missing_orchestrator_algorithm() -> None:
    weak_orchestrator = algorithm_summary(algorithms=("classical-ed25519",))
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(orchestrator=weak_orchestrator)))

    assert_shield_v4_required_denial(result, "SHIELD_V4_ORCHESTRATOR_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_non_mapping_orchestrator_summary() -> None:
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(orchestrator=[])))

    assert_shield_v4_required_denial(result, "SHIELD_V4_ORCHESTRATOR_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_missing_component_signature_summary() -> None:
    missing_component = component_summaries(components=("adn", "dqsn", "guardian_wallet", "qwg"))
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(components=missing_component)))

    assert_shield_v4_required_denial(result, "SHIELD_V4_COMPONENT_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_component_summary_without_required_algorithms() -> None:
    weak_components = component_summaries(algorithms=("classical-ed25519",))
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(components=weak_components)))

    assert_shield_v4_required_denial(result, "SHIELD_V4_COMPONENT_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_malformed_component_summary_collection() -> None:
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(components="not-a-list")))

    assert_shield_v4_required_denial(result, "SHIELD_V4_COMPONENT_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_rejects_component_without_string_id() -> None:
    bad_components = component_summaries()
    bad_components[0] = {"component_id": 123, "verified_algorithms": list(REQUIRED_ALGORITHMS)}
    result = run_engine(shield=v4_shield_evidence(verification_summary=v4_summary(components=bad_components)))

    assert_shield_v4_required_denial(result, "SHIELD_V4_COMPONENT_SIGNATURE_SUMMARY_REQUIRED")


def test_shield_v4_required_keeps_specific_rejected_verifier_reason() -> None:
    rejected = Evidence(
        verified=False,
        accepted_as_evidence=False,
        handoff_allowed=False,
        reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
        dominant_reason_ids=("SHIELD_V4_DOWNGRADE_REJECTED",),
    )
    result = run_engine(shield=rejected)

    assert result.state == FinalPolicyEngineState.DENY_EVIDENCE_REJECTED
    assert result.stopped_at == "shield"
    assert result.dominant_reason_ids == (ReasonId.UNKNOWN_EXTERNAL_REASON.value,)


def test_default_mode_still_allows_legacy_normalized_shield_evidence() -> None:
    result = run_engine(shield=generic_evidence(), shield_v4_required=False)

    assert result.state == FinalPolicyEngineState.ALLOW_FINAL_ADAMANTINEOS_DECISION
    assert result.final_approval is True
