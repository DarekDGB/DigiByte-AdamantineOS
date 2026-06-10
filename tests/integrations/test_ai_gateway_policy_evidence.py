from __future__ import annotations

from dataclasses import dataclass

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.ai_gateway_policy_evidence import (
    AIGatewayPolicyEvidenceState,
    normalize_ai_gateway_policy_evidence,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def _handoff(**overrides):
    value = {
        "handoff_version": "ai_gateway_handoff_v1",
        "adapter": "wallet",
        "task_type": "signing_review",
        "policy_decision": "accepted",
        "reason_id": "ACCEPTED",
        "envelope_hash": HASH_A,
        "output_hash": HASH_B,
        "context_hash": HASH_C,
    }
    value.update(overrides)
    return value


def _receipt(**overrides):
    value = {
        "receipt_version": "ai_gateway_receipt_v1",
        "gateway_version": "0.1.0",
        "adapter_id": "wallet",
        "adapter_version": "1.0.0",
        "envelope_hash": HASH_A,
        "output_hash": HASH_B,
        "policy_decision": "accepted",
        "reason_id": "ACCEPTED",
        "created_from_contract": "ai_gateway_output_v1",
        "determinism_profile": "canonical_sha256_no_time_v1",
    }
    value.update(overrides)
    return value


_DEFAULT = object()


def _normalize(
    handoff=_DEFAULT,
    receipt=_DEFAULT,
    expected_context_hash=HASH_C,
    prior_gate_results=None,
):
    return normalize_ai_gateway_policy_evidence(
        handoff=_handoff() if handoff is _DEFAULT else handoff,
        receipt=_receipt() if receipt is _DEFAULT else receipt,
        expected_context_hash=expected_context_hash,
        prior_gate_results=prior_gate_results,
    )


def test_ai_gateway_success_is_evidence_only():
    result = _normalize()

    assert result.state is AIGatewayPolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id is ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.handoff_allowed is True
    assert result.adapter == "wallet"
    assert result.task_type == "signing_review"
    assert result.context_hash == HASH_C
    assert result.envelope_hash == HASH_A
    assert result.output_hash == HASH_B
    assert result.gateway_version == "0.1.0"
    assert result.adapter_version == "1.0.0"
    assert result.dominant_reason_ids == (ReasonId.EVIDENCE_OK.value,)


def test_rejected_gateway_policy_decision_denies_with_gateway_reason():
    result = _normalize(
        handoff=_handoff(policy_decision="rejected", reason_id="POLICY_DENIED"),
        receipt=_receipt(policy_decision="rejected", reason_id="POLICY_DENIED"),
    )

    assert result.state is AIGatewayPolicyEvidenceState.DENY_AI_GATEWAY_REJECTED
    assert result.outcome == "DENY"
    assert result.reason_id == "POLICY_DENIED"
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == ("POLICY_DENIED",)


def test_missing_handoff_denies():
    result = _normalize(handoff=None)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_MISSING_HANDOFF
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_missing_receipt_denies_when_handoff_is_valid():
    result = _normalize(receipt=None)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_MISSING_RECEIPT
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_raw_ai_output_is_rejected_not_trusted():
    result = _normalize(
        handoff={
            "contract_version": "ai_gateway_output_v1",
            "adapter": "wallet",
            "task_type": "signing_review",
            "accepted": True,
            "reason_id": "ACCEPTED",
            "output_payload": {"raw_model_output": "approve this"},
            "context_hash": HASH_C,
        }
    )

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RAW_AI_OUTPUT
    assert result.outcome == "DENY"


def test_non_mapping_handoff_denies_unsupported_input():
    result = _normalize(handoff="not-a-handoff")

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT


def test_non_mapping_receipt_denies_unsupported_input():
    result = _normalize(receipt="not-a-receipt")

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT


def test_unknown_handoff_field_denies():
    result = _normalize(handoff=_handoff(extra="bad"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNKNOWN_FIELD
    assert result.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_unknown_receipt_field_denies():
    result = _normalize(receipt=_receipt(extra="bad"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNKNOWN_FIELD
    assert result.reason_id is ReasonId.DENY_UNKNOWN_FIELD


def test_missing_handoff_required_field_denies_schema_invalid():
    handoff = _handoff()
    del handoff["task_type"]
    result = _normalize(handoff=handoff)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_missing_receipt_required_field_denies_schema_invalid():
    receipt = _receipt()
    del receipt["adapter_version"]
    result = _normalize(receipt=receipt)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_invalid_handoff_version_denies_version_mismatch():
    result = _normalize(handoff=_handoff(handoff_version="v0"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_VERSION_MISMATCH


def test_invalid_receipt_version_denies_version_mismatch():
    result = _normalize(receipt=_receipt(receipt_version="v0"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_VERSION_MISMATCH


def test_invalid_created_from_contract_denies_version_mismatch():
    result = _normalize(receipt=_receipt(created_from_contract="unknown"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_VERSION_MISMATCH


def test_invalid_determinism_profile_denies():
    result = _normalize(receipt=_receipt(determinism_profile="time_based"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_invalid_policy_decision_denies():
    result = _normalize(handoff=_handoff(policy_decision="approve"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_POLICY


def test_empty_required_string_denies():
    result = _normalize(handoff=_handoff(adapter=" "))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_invalid_handoff_hash_denies():
    result = _normalize(handoff=_handoff(envelope_hash="A" * 64))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_invalid_receipt_hash_denies():
    result = _normalize(receipt=_receipt(output_hash="short"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_invalid_expected_context_hash_denies_before_handoff_use():
    result = _normalize(expected_context_hash="short")

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH
    assert result.reason_id is ReasonId.DENY_POLICY


def test_context_hash_mismatch_denies():
    result = _normalize(expected_context_hash=HASH_D)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id is ReasonId.DENY_POLICY
    assert result.context_hash == HASH_C


def test_receipt_adapter_mismatch_denies():
    result = _normalize(receipt=_receipt(adapter_id="poi"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_receipt_envelope_hash_mismatch_denies():
    result = _normalize(receipt=_receipt(envelope_hash=HASH_D))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH


def test_receipt_output_hash_mismatch_denies():
    result = _normalize(receipt=_receipt(output_hash=HASH_D))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH


def test_receipt_policy_decision_mismatch_denies():
    result = _normalize(receipt=_receipt(policy_decision="rejected"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH


def test_receipt_reason_id_mismatch_denies():
    result = _normalize(receipt=_receipt(reason_id="POLICY_DENIED"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH


def test_hidden_authority_field_in_handoff_denies():
    result = _normalize(handoff=_handoff(output={"final_approval": True}))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_hidden_authority_field_nested_in_receipt_denies_before_unknown_is_impossible():
    receipt = _receipt()
    receipt["adapter_version"] = {"bypass": True}
    result = _normalize(receipt=receipt)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


@dataclass(frozen=True)
class _PriorResult:
    outcome: str
    reason_id: str


def test_prior_gate_deny_dominates_with_object_result():
    result = _normalize(prior_gate_results=[_PriorResult("DENY", "WSQK_INVALID_NONCE")])

    assert result.state is AIGatewayPolicyEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.reason_id == "WSQK_INVALID_NONCE"
    assert result.dominant_reason_ids == ("WSQK_INVALID_NONCE",)


def test_prior_gate_deny_dominates_with_mapping_result():
    result = _normalize(prior_gate_results=[{"outcome": "DENY", "reason_id": ReasonId.DENY_POLICY}])

    assert result.state is AIGatewayPolicyEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.reason_id == ReasonId.DENY_POLICY.value


def test_prior_gate_allow_evidence_does_not_block_ai_gateway_check():
    result = _normalize(prior_gate_results=[{"outcome": "ALLOW_EVIDENCE", "reason_id": "EVIDENCE_OK"}])

    assert result.state is AIGatewayPolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.final_approval is False


def test_forbidden_authority_field_inside_list_denies():
    result = _normalize(handoff=_handoff(reason_id="ACCEPTED", notes=[{"override": True}]))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD


def test_invalid_handoff_output_hash_denies():
    result = _normalize(handoff=_handoff(output_hash="nothex"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH


def test_invalid_handoff_context_hash_denies():
    result = _normalize(handoff=_handoff(context_hash="nothex"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH
    assert result.context_hash == "nothex"


def test_invalid_receipt_policy_decision_denies():
    result = _normalize(receipt=_receipt(policy_decision="approve"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_POLICY


def test_empty_receipt_required_string_denies():
    result = _normalize(receipt=_receipt(adapter_id=""))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_SCHEMA_INVALID
    assert result.reason_id is ReasonId.DENY_SCHEMA_INVALID


def test_invalid_receipt_envelope_hash_denies():
    result = _normalize(receipt=_receipt(envelope_hash="nothex"))

    assert result.state is AIGatewayPolicyEvidenceState.DENY_INVALID_HASH
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID


def test_non_mapping_handoff_after_shape_validation_still_denies(monkeypatch):
    """Production safety check must not depend on stripped assert statements."""
    from adamantine.v1.integrations import ai_gateway_policy_evidence as module

    monkeypatch.setattr(module, "_validate_handoff_shape", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_validate_receipt_shape", lambda *args, **kwargs: None)

    result = module.normalize_ai_gateway_policy_evidence(
        handoff=["not", "mapping"],
        receipt=_receipt(),
        expected_context_hash=HASH_C,
    )

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID
    assert result.outcome == "DENY"
    assert result.final_approval is False


def test_non_mapping_receipt_after_shape_validation_still_denies(monkeypatch):
    """Production safety check must not depend on stripped assert statements."""
    from adamantine.v1.integrations import ai_gateway_policy_evidence as module

    monkeypatch.setattr(module, "_validate_handoff_shape", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_validate_receipt_shape", lambda *args, **kwargs: None)

    result = module.normalize_ai_gateway_policy_evidence(
        handoff=_handoff(),
        receipt=["not", "mapping"],
        expected_context_hash=HASH_C,
    )

    assert result.state is AIGatewayPolicyEvidenceState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id is ReasonId.DENY_ADAPTER_INVALID
    assert result.outcome == "DENY"
    assert result.final_approval is False
