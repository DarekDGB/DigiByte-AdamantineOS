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


COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")
REASON_BY_COMPONENT_DECISION = {
    "adn": {
        "ALLOW": "ADN_OK_COORDINATION_ALLOW",
        "ESCALATE": "ADN_ESCALATE_POLICY_REVIEW",
        "DENY": "ADN_DENY_DEFENSE_TRIGGERED",
        "ERROR": "ADN_ERROR_INVALID_VERDICT",
    },
    "dqsn": {
        "ALLOW": "DQSN_OK_NETWORK_ALLOW",
        "ESCALATE": "DQSN_ESCALATE_QUANTUM_SIGNAL",
        "DENY": "DQSN_DENY_NETWORK_RISK",
        "ERROR": "DQSN_ERROR_INVALID_VERDICT",
    },
    "guardian_wallet": {
        "ALLOW": "GW_OK_HEALTHY_ALLOW",
        "ESCALATE": "GW_ESCALATE_QID_REQUIRED",
        "DENY": "GW_DENY_POLICY_BLOCKED",
        "ERROR": "GW_ERROR_INVALID_VERDICT",
    },
    "qwg": {
        "ALLOW": "QWG_OK_POSTURE_ALLOW",
        "ESCALATE": "QWG_ESCALATE_QUANTUM_POSTURE",
        "DENY": "QWG_DENY_KEY_RISK",
        "ERROR": "QWG_ERROR_INVALID_VERDICT",
    },
    "sentinel_ai": {
        "ALLOW": "SNTL_OK_TELEMETRY_ALLOW",
        "ESCALATE": "SNTL_ESCALATE_THREAT_REVIEW",
        "DENY": "SNTL_DENY_THREAT_DETECTED",
        "ERROR": "SNTL_ERROR_AI_OUTPUT_UNTRUSTED",
    },
}
EVIDENCE_FAMILY_BY_COMPONENT = {
    "adn": "defense_signal",
    "dqsn": "network_observation",
    "guardian_wallet": "wallet_context",
    "qwg": "wallet_posture",
    "sentinel_ai": "telemetry",
}


def _classify(decisions: dict[str, str]) -> tuple[str, str, bool]:
    values = list(decisions.values())
    if "DENY" in values:
        return "DENY", "ORCH_DENY_DOMINATES", False
    if "ERROR" in values:
        return "DENY", "ORCH_ERROR_INVALID_COMPONENT_VERDICT", False
    if "ESCALATE" in values:
        return "HUMAN_REVIEW_REQUIRED", "ORCH_HUMAN_REVIEW_ESCALATE_PRESENT", False
    return "ALLOW", "ORCH_OK_ALL_COMPONENTS_ALLOW", True


def _component_verdicts(
    *,
    decisions: dict[str, str] | None = None,
    request_id: str = REQ,
    context_hash: str = CTX,
) -> list[dict[str, Any]]:
    merged = {component_id: "ALLOW" for component_id in COMPONENT_IDS}
    if decisions:
        merged.update(decisions)
    return [
        {
            "component_id": component_id,
            "contract_version": 3,
            "schema_version": "shield.verdict.v1",
            "request_id": request_id,
            "context_hash": context_hash,
            "decision": merged[component_id],
            "reason_ids": [REASON_BY_COMPONENT_DECISION[component_id][merged[component_id]]],
            "evidence_hash": "b" * 64,
            "evidence_families": [EVIDENCE_FAMILY_BY_COMPONENT[component_id]],
            "metadata": {},
            "fail_closed": True,
        }
        for component_id in COMPONENT_IDS
    ]


def _receipt(
    final_outcome: str = "ALLOW",
    *,
    request_id: str = REQ,
    context_hash: str = CTX,
    handoff_allowed: bool | None = None,
    component_verdicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decisions: dict[str, str] = {}
    if final_outcome == "DENY":
        decisions["guardian_wallet"] = "DENY"
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        decisions["guardian_wallet"] = "ESCALATE"
    if component_verdicts is None:
        component_verdicts = _component_verdicts(
            decisions=decisions,
            request_id=request_id,
            context_hash=context_hash,
        )
    component_decisions = {
        str(component["component_id"]): str(component.get("decision", "ALLOW"))
        for component in component_verdicts
        if isinstance(component, dict) and isinstance(component.get("component_id"), str)
    }
    outcome, reason, default_handoff = _classify(component_decisions or {"guardian_wallet": final_outcome})
    if handoff_allowed is None:
        handoff_allowed = default_handoff
    base: dict[str, Any] = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": request_id,
        "context_hash": context_hash,
        "component_verdicts": component_verdicts,
        "final_outcome": outcome,
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
    hidden_deny_receipt = _receipt("DENY")
    hidden_deny_receipt["final_outcome"] = "ALLOW"
    hidden_deny_receipt["dominant_reason_ids"] = ["ORCH_OK_ALL_COMPONENTS_ALLOW"]
    hidden_deny_receipt["adamantineos_handoff"] = {
        "handoff_allowed": True,
        "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
    }
    hidden_deny_receipt["receipt_hash"] = ""
    hidden_deny_receipt["receipt_hash"] = canonical_sha256(hidden_deny_receipt)

    result = run_shield_v3_adapter_harness(
        combined_context_payload=_context_payload(),
        shield_receipt=hidden_deny_receipt,
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
