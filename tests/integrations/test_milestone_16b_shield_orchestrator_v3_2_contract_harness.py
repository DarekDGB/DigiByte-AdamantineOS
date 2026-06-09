from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations import verify_shield_orchestrator_receipt
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import ShieldReceiptVerificationState
from adamantine.v1.policy.final_policy_engine import (
    FinalPolicyEngineState,
    LocalPolicyGateResult,
    evaluate_final_policy_engine,
)

CTX = "a" * 64
REQ = "req-milestone-16b-v3-2-contract"
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "shield_v3_integration"
    / "orchestrator_v3_2_receipt"
    / "allow_receipt.json"
)


@dataclass(frozen=True)
class Evidence:
    state: str = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    outcome: str = "ALLOW_EVIDENCE"
    reason_id: ReasonId | str = ReasonId.EVIDENCE_OK
    accepted_as_evidence: bool = True
    final_approval: bool = False
    handoff_allowed: bool = True
    dominant_reason_ids: tuple[str, ...] = (ReasonId.EVIDENCE_OK.value,)
    final_outcome: str | None = None


def _load_receipt() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def _allow_gate(name: str) -> LocalPolicyGateResult:
    return LocalPolicyGateResult(name, True, ReasonId.EVIDENCE_OK)


def _run_final_engine(*, shield: Any, **overrides: Any):
    args: dict[str, Any] = {
        "shield": shield,
        "wsqk_v2": Evidence(),
        "qid": Evidence(),
        "adaptive_core": Evidence(),
        "ai_gateway": Evidence(),
        "replay": _allow_gate("replay"),
        "wallet_policy": _allow_gate("wallet_policy"),
        "human": _allow_gate("human"),
    }
    args.update(overrides)
    return evaluate_final_policy_engine(**args)


def _rehash(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(receipt)
    receipt["receipt_hash"] = ""
    receipt["receipt_hash"] = canonical_sha256(receipt)
    return receipt


def test_milestone_16b_accepts_real_v3_2_orchestrator_receipt_as_evidence_only() -> None:
    receipt = _load_receipt()

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.verified is True
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.handoff_allowed is True
    assert result.dominant_reason_ids == ("ORCH_OK_ALL_COMPONENTS_ALLOW",)


def test_milestone_16b_policy_engine_keeps_adamantineos_as_final_boundary() -> None:
    shield = verify_shield_orchestrator_receipt(
        _load_receipt(),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    result = _run_final_engine(shield=shield)

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


def test_milestone_16b_shield_allow_alone_is_not_final_approval() -> None:
    shield = verify_shield_orchestrator_receipt(
        _load_receipt(),
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    result = _run_final_engine(shield=shield, wsqk_v2=None)

    assert result.state == FinalPolicyEngineState.DENY_MISSING_EVIDENCE
    assert result.stopped_at == "wsqk_v2"
    assert result.final_approval is False
    assert result.dominant_reason_ids == ("MISSING_EVIDENCE:wsqk_v2",)


def test_milestone_16b_rejects_raw_v3_2_component_verdict_bypass() -> None:
    receipt = _load_receipt()
    raw_component = receipt["component_verdicts"][0]

    result = verify_shield_orchestrator_receipt(
        raw_component,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16b_context_mismatch_fails_closed() -> None:
    result = verify_shield_orchestrator_receipt(
        _load_receipt(),
        expected_context_hash="c" * 64,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16b_receipt_hash_mismatch_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["receipt_hash"] = "c" * 64

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16b_unknown_authority_inside_metadata_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["metadata"] = {"final_approval": True}
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16b_import_failure_shape_never_becomes_allow() -> None:
    result = verify_shield_orchestrator_receipt(
        {"import_error": "shield_orchestrator.v3.contracts.v3_2_receipt unavailable"},
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16b_nested_authority_list_inside_metadata_fails_closed() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["metadata"] = {"nested": [{"force_allow": True}]}
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS


def test_milestone_16b_escalate_component_cannot_hide_under_allow() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["decision"] = "ESCALATE"
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.dominant_reason_ids == ("DENY_MUST_DOMINATE",)


def test_milestone_16b_error_component_must_resolve_to_deny() -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0]["decision"] = "ERROR"
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS
    assert result.dominant_reason_ids == ("DENY_MUST_DOMINATE",)


def test_milestone_16b_rejects_duplicate_v3_2_evidence_families() -> None:
    receipt = _load_receipt()
    family = receipt["component_verdicts"][0]["evidence_families"][0]
    receipt["component_verdicts"][0]["evidence_families"] = [family, family]
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.dominant_reason_ids == ("COMPONENT_VERDICTS_INVALID",)


import pytest


@pytest.mark.parametrize(
    "field,value",
    [
        ("component_id", " "),
        ("contract_version", 4),
        ("schema_version", "shield.verdict.v2"),
        ("request_id", "wrong-request"),
        ("context_hash", "bad"),
        ("context_hash", "g" * 64),
        ("decision", "MAYBE"),
        ("reason_ids", []),
        ("evidence_hash", "bad"),
        ("evidence_hash", "g" * 64),
        ("evidence_families", []),
        ("metadata", []),
        ("fail_closed", False),
    ],
)
def test_milestone_16b_rejects_malformed_v3_2_component_fields(field: str, value: Any) -> None:
    receipt = _load_receipt()
    receipt["component_verdicts"][0][field] = value
    receipt = _rehash(receipt)

    result = verify_shield_orchestrator_receipt(
        receipt,
        expected_context_hash=CTX,
        expected_request_id=REQ,
    )

    assert result.state == ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
