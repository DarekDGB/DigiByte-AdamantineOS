from __future__ import annotations

import json
from pathlib import Path

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.ai_gateway_policy_evidence import (
    AIGatewayPolicyEvidenceState,
    normalize_ai_gateway_policy_evidence,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "ai_gateway_external_baseline"
    / "ai_gateway_adamantine_evidence_v1.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def _normalize(evidence: dict):
    return normalize_ai_gateway_policy_evidence(
        handoff=evidence["handoff"],
        receipt=evidence["receipt"],
        expected_context_hash=evidence["expected_context_hash"],
    )


def test_16f_external_ai_gateway_adamantine_evidence_accepts_as_evidence_only() -> None:
    evidence = _fixture()

    result = _normalize(evidence)

    assert evidence["evidence_version"] == "adamantine_ai_gateway_evidence_v1"
    assert evidence["source"] == "adamantine-ai-gateway"
    assert evidence["evidence_role"] == "evidence_only"
    assert result.state is AIGatewayPolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id is ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.handoff_allowed is True


def test_16f_ai_gateway_evidence_rejected_decision_denies() -> None:
    evidence = _fixture()
    evidence["handoff"]["policy_decision"] = "rejected"
    evidence["handoff"]["reason_id"] = "POLICY_DENIED"
    evidence["receipt"]["policy_decision"] = "rejected"
    evidence["receipt"]["reason_id"] = "POLICY_DENIED"

    result = _normalize(evidence)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_AI_GATEWAY_REJECTED
    assert result.outcome == "DENY"
    assert result.final_approval is False


def test_16f_ai_gateway_evidence_context_hash_mismatch_denies() -> None:
    evidence = _fixture()
    evidence["expected_context_hash"] = "d" * 64

    result = _normalize(evidence)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH
    assert result.final_approval is False


def test_16f_ai_gateway_evidence_receipt_mismatch_denies() -> None:
    evidence = _fixture()
    evidence["receipt"]["output_hash"] = "d" * 64

    result = _normalize(evidence)

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RECEIPT_MISMATCH
    assert result.final_approval is False


def test_16f_ai_gateway_raw_output_bypass_still_rejects() -> None:
    evidence = _fixture()
    raw_output = {
        "contract_version": "ai_gateway_output_v1",
        "adapter": "wallet",
        "task_type": "signing_review",
        "accepted": True,
        "reason_id": "ACCEPTED",
        "output_payload": {"raw_model_output": "approve execution"},
        "context_hash": evidence["expected_context_hash"],
    }

    result = normalize_ai_gateway_policy_evidence(
        handoff=raw_output,
        receipt=evidence["receipt"],
        expected_context_hash=evidence["expected_context_hash"],
    )

    assert result.state is AIGatewayPolicyEvidenceState.DENY_RAW_AI_OUTPUT
    assert result.final_approval is False


def test_16f_ai_gateway_hidden_authority_field_denies() -> None:
    evidence = _fixture()
    evidence["handoff"]["final_approval"] = True

    result = _normalize(evidence)

    assert result.state in {
        AIGatewayPolicyEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
        AIGatewayPolicyEvidenceState.DENY_UNKNOWN_FIELD,
    }
    assert result.final_approval is False
