from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adamantine.v1.contracts.combined_context_hash import EXPECTED_VALID_HASH
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations.shield_v3_adapter_harness import (
    ShieldV3AdapterHarnessState,
    run_shield_v3_adapter_harness,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "shield_v3_integration" / "combined_context_hash"
CTX = EXPECTED_VALID_HASH
REQ = "req-000001"


def _context_payload(name: str = "valid_combined_context_hash_v1.json") -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _receipt(
    final_outcome: str = "ALLOW",
    *,
    request_id: str = REQ,
    context_hash: str = CTX,
    handoff_allowed: bool | None = None,
    component_verdicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if handoff_allowed is None:
        handoff_allowed = final_outcome == "ALLOW"
    reason = {
        "ALLOW": "ORCH_OK_ALL_COMPONENTS_ALLOW",
        "DENY": "ORCH_DENY_DOMINATES",
        "HUMAN_REVIEW_REQUIRED": "ORCH_HUMAN_REVIEW_REQUIRED",
    }[final_outcome]
    if component_verdicts is None:
        component_verdicts = [
            {
                "component_id": "shield_orchestrator_fixture",
                "verdict": final_outcome,
                "reason_ids": [reason],
            }
        ]
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": component_verdicts,
        "final_outcome": final_outcome,
        "dominant_reason_ids": [reason],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": handoff_allowed,
            "handoff_reason": reason,
        },
        "fail_closed": True,
    }
    base["receipt_hash"] = canonical_sha256(base)
    return base


def test_level_2_harness_accepts_allow_as_evidence_only_continue_checks() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW"),
    )

    assert result.state == ShieldV3AdapterHarnessState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "ALLOW"
    assert result.handoff_allowed is True
    assert result.verification is not None
    assert result.adapter is not None
    assert result.verification.final_approval is False
    assert result.adapter.final_approval is False


def test_level_2_harness_maps_deny_to_block_with_deny_dominance() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("DENY"),
    )

    assert result.state == ShieldV3AdapterHarnessState.DENY_DOMINATES_BLOCK
    assert result.reason_id == ReasonId.DENY_POLICY
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "DENY"
    assert result.handoff_allowed is False
    assert result.dominant_reason_ids == ("ORCH_DENY_DOMINATES",)


def test_level_2_harness_maps_human_review_to_review_required() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("HUMAN_REVIEW_REQUIRED"),
    )

    assert result.state == ShieldV3AdapterHarnessState.HUMAN_REVIEW_REQUIRED
    assert result.reason_id == ReasonId.DENY_AUTHORITY_INSUFFICIENT
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.final_outcome == "HUMAN_REVIEW_REQUIRED"
    assert result.handoff_allowed is False


def test_level_2_harness_rejects_invalid_combined_context_before_receipt_use() -> None:
    invalid_context = _context_payload()
    invalid_context["timestamp"] = "2026-06-08T00:00:00Z"

    result = run_shield_v3_adapter_harness(
        combined_context_payload=invalid_context,
        shield_receipt=_receipt("ALLOW"),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_CONTEXT_CONTRACT
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.context_hash is None
    assert result.verification is None
    assert result.adapter is None
    assert result.dominant_reason_ids[0].startswith("COMBINED_CONTEXT_HASH_CONTRACT_REJECTED:")


def test_level_2_harness_rejects_receipt_context_mismatch_fail_closed() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW", context_hash="b" * 64),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    assert result.context_hash == CTX
    assert result.request_id == REQ
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.dominant_reason_ids == ("REJECTED_CONTEXT_MISMATCH",)
    assert result.verification is not None
    assert result.verification.accepted_as_evidence is False
    assert result.adapter is None


def test_level_2_harness_rejects_request_mismatch_to_stop_receipt_reuse() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW", request_id="req-reused"),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("REJECTED_REQUEST_MISMATCH",)
    assert result.final_approval is False


def test_level_2_harness_rejects_injected_replay_risk_without_global_state() -> None:
    receipt = _receipt("ALLOW")

    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=receipt,
        rejected_receipt_hashes=(receipt["receipt_hash"],),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_SHIELD_STALE
    assert result.dominant_reason_ids == ("REJECTED_REPLAY_RISK",)
    assert result.final_approval is False


def test_level_2_harness_rejects_tampered_receipt_before_adapter_mapping() -> None:
    receipt = _receipt("ALLOW")
    receipt["receipt_hash"] = "c" * 64

    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=receipt,
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("REJECTED_TAMPERED_RECEIPT",)
    assert result.final_approval is False
    assert result.adapter is None


def test_level_2_harness_rejects_raw_component_verdict_bypass() -> None:
    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt={"schema_version": "shield.verdict.v1", "decision": "ALLOW"},
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("REJECTED_RAW_COMPONENT_BYPASS",)
    assert result.final_approval is False


def test_level_2_harness_rejects_component_deny_hidden_under_final_allow() -> None:
    hidden_deny = [
        {
            "component_id": "shield_orchestrator_fixture",
            "verdict": "DENY",
            "reason_ids": ["GUARDIAN_DENY"],
        }
    ]

    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW", component_verdicts=hidden_deny),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_RECEIPT_VERIFICATION
    assert result.reason_id == ReasonId.EQC_CONFLICTING_EVIDENCE
    assert result.dominant_reason_ids == ("REJECTED_AUTHORITY_BYPASS",)
    assert result.final_approval is False


def test_level_2_harness_private_request_id_helper_returns_none_for_non_mapping() -> None:
    from adamantine.v1.integrations.shield_v3_adapter_harness import _request_id_from_context

    assert _request_id_from_context(["not", "context"]) is None


def test_level_2_harness_rejects_adapter_mapping_failure_after_verified_receipt(monkeypatch) -> None:
    from adamantine.v1.integrations import shield_v3_adapter_harness as harness
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
        ShieldReceiptAdapterResult,
        ShieldReceiptAdapterState,
    )

    def rejected_adapter(*args: object, **kwargs: object) -> ShieldReceiptAdapterResult:
        return ShieldReceiptAdapterResult(
            state=ShieldReceiptAdapterState.SHIELD_REJECTED_INVALID_RECEIPT,
            adapter_reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            accepted_as_evidence=False,
            final_approval=False,
            final_outcome=None,
            dominant_reason_ids=("ADAPTER_REJECTED",),
            context_hash=CTX,
            handoff_allowed=False,
            receipt=None,
        )

    monkeypatch.setattr(harness, "adapt_shield_orchestrator_receipt", rejected_adapter)

    result = harness.run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW"),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_ADAPTER_MAPPING
    assert result.reason_id == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert result.dominant_reason_ids == ("SHIELD_REJECTED_INVALID_RECEIPT",)
    assert result.final_approval is False
    assert result.verification is not None
    assert result.adapter is not None


def test_level_2_harness_rejects_verifier_adapter_state_mismatch(monkeypatch) -> None:
    from adamantine.v1.integrations import shield_v3_adapter_harness as harness
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
        ShieldReceiptAdapterResult,
        ShieldReceiptAdapterState,
    )

    def mismatched_adapter(*args: object, **kwargs: object) -> ShieldReceiptAdapterResult:
        return ShieldReceiptAdapterResult(
            state=ShieldReceiptAdapterState.SHIELD_BLOCK_DENY_DOMINATES,
            adapter_reason_id=ReasonId.DENY_POLICY,
            accepted_as_evidence=True,
            final_approval=False,
            final_outcome="DENY",
            dominant_reason_ids=("ORCH_DENY_DOMINATES",),
            context_hash=CTX,
            handoff_allowed=False,
            receipt=_receipt("DENY"),
        )

    monkeypatch.setattr(harness, "adapt_shield_orchestrator_receipt", mismatched_adapter)

    result = harness.run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW"),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_BOUNDARY_INCONSISTENCY
    assert result.reason_id == ReasonId.EQC_CONFLICTING_EVIDENCE
    assert result.dominant_reason_ids == ("VERIFIER_ADAPTER_STATE_MISMATCH",)
    assert result.final_approval is False


def test_level_2_harness_rejects_any_adapter_final_approval_bug(monkeypatch) -> None:
    from adamantine.v1.integrations import shield_v3_adapter_harness as harness
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
        ShieldReceiptAdapterResult,
        ShieldReceiptAdapterState,
    )

    def bad_adapter(*args: object, **kwargs: object) -> ShieldReceiptAdapterResult:
        return ShieldReceiptAdapterResult(
            state=ShieldReceiptAdapterState.SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS,
            adapter_reason_id=ReasonId.EVIDENCE_OK,
            accepted_as_evidence=True,
            final_approval=True,
            final_outcome="ALLOW",
            dominant_reason_ids=("ORCH_OK_ALL_COMPONENTS_ALLOW",),
            context_hash=CTX,
            handoff_allowed=True,
            receipt=_receipt("ALLOW"),
        )

    monkeypatch.setattr(harness, "adapt_shield_orchestrator_receipt", bad_adapter)

    result = harness.run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=_receipt("ALLOW"),
    )

    assert result.state == ShieldV3AdapterHarnessState.REJECTED_BOUNDARY_INCONSISTENCY
    assert result.reason_id == ReasonId.EQC_CONFLICTING_EVIDENCE
    assert result.dominant_reason_ids == ("SHIELD_EVIDENCE_CANNOT_GRANT_FINAL_APPROVAL",)
    assert result.final_approval is False


def test_level_2_harness_adapter_state_match_helper_rejects_unverified_state() -> None:
    from adamantine.v1.integrations.shield_orchestrator_receipt_adapter import (
        ShieldReceiptAdapterResult,
        ShieldReceiptAdapterState,
    )
    from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import (
        ShieldReceiptVerificationResult,
        ShieldReceiptVerificationState,
    )
    from adamantine.v1.integrations.shield_v3_adapter_harness import _adapter_state_matches_verifier

    verification = ShieldReceiptVerificationResult(
        state=ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT,
        reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
        verified=False,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        context_hash=CTX,
        request_id=REQ,
        receipt_hash="d" * 64,
        handoff_allowed=False,
        dominant_reason_ids=("REJECTED_INVALID_RECEIPT",),
        receipt=None,
    )
    adapter = ShieldReceiptAdapterResult(
        state=ShieldReceiptAdapterState.SHIELD_EVIDENCE_ACCEPTED_CONTINUE_CHECKS,
        adapter_reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        final_outcome="ALLOW",
        dominant_reason_ids=("ORCH_OK_ALL_COMPONENTS_ALLOW",),
        context_hash=CTX,
        handoff_allowed=True,
        receipt=_receipt("ALLOW"),
    )

    assert _adapter_state_matches_verifier(verification, adapter) is False
