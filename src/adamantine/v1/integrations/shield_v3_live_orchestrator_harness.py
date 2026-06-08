from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Mapping

from adamantine.v1.contracts.combined_context_hash import (
    CombinedContextHashError,
    compute_combined_context_hash,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import canonical_sha256
from adamantine.v1.integrations.shield_v3_adapter_harness import (
    ShieldV3AdapterHarnessResult,
    ShieldV3AdapterHarnessState,
    run_shield_v3_adapter_harness,
)

LiveReceiptBuilder = Callable[..., Mapping[str, Any]]


class ShieldV3LiveOrchestratorHarnessState(str, Enum):
    """Stable Level 3 live Shield Orchestrator boundary states."""

    LIVE_ALLOW_EVIDENCE_CONTINUE_CHECKS = "LIVE_ALLOW_EVIDENCE_CONTINUE_CHECKS"
    LIVE_DENY_DOMINATES_BLOCK = "LIVE_DENY_DOMINATES_BLOCK"
    LIVE_HUMAN_REVIEW_REQUIRED = "LIVE_HUMAN_REVIEW_REQUIRED"
    REJECTED_CONTEXT_CONTRACT = "REJECTED_CONTEXT_CONTRACT"
    REJECTED_ORCHESTRATOR_UNAVAILABLE = "REJECTED_ORCHESTRATOR_UNAVAILABLE"
    REJECTED_ORCHESTRATOR_EXCEPTION = "REJECTED_ORCHESTRATOR_EXCEPTION"
    REJECTED_LIVE_RECEIPT_SHAPE = "REJECTED_LIVE_RECEIPT_SHAPE"
    REJECTED_LIVE_RECEIPT_TAMPERED = "REJECTED_LIVE_RECEIPT_TAMPERED"
    REJECTED_AUTHORITY_BYPASS = "REJECTED_AUTHORITY_BYPASS"
    REJECTED_ADAPTER_HARNESS = "REJECTED_ADAPTER_HARNESS"


@dataclass(frozen=True)
class ShieldV3LiveOrchestratorHarnessResult:
    """Deterministic Level 3 harness result for a live Orchestrator receipt boundary.

    The harness accepts a caller-injected Shield Orchestrator receipt builder. It
    intentionally does not import Shield repositories on its own, does not call
    individual Shield components, and never grants final AdamantineOS approval.
    """

    state: ShieldV3LiveOrchestratorHarnessState
    reason_id: ReasonId
    context_hash: str | None
    request_id: str | None
    accepted_as_evidence: bool
    final_approval: bool
    final_outcome: str | None
    handoff_allowed: bool
    dominant_reason_ids: tuple[str, ...]
    source_receipt_hash: str | None = None
    normalized_receipt_hash: str | None = None
    adapter_harness: ShieldV3AdapterHarnessResult | None = None


_LIVE_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_version",
        "request_id",
        "context_hash",
        "component_verdicts",
        "final_outcome",
        "dominant_reason_ids",
        "receipt_hash",
        "adamantineos_handoff",
        "fail_closed",
    }
)

_LIVE_COMPONENT_FIELDS = frozenset(
    {
        "component_id",
        "contract_version",
        "schema_version",
        "request_id",
        "context_hash",
        "decision",
        "reason_ids",
        "evidence_hash",
        "evidence_families",
        "metadata",
        "fail_closed",
    }
)

_SUPPORTED_LIVE_DECISIONS = frozenset({"ALLOW", "ESCALATE", "DENY", "ERROR", "SKIPPED"})
_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "allow",
        "approved",
        "authority",
        "auto_approve",
        "broadcast",
        "bypass",
        "can_sign",
        "decision_override",
        "execute",
        "final_approval",
        "force_allow",
        "human_approved",
        "override",
        "sign",
        "trusted",
    }
)


def _request_id_from_context(context_payload: Any) -> str | None:
    if isinstance(context_payload, Mapping) and isinstance(context_payload.get("request_id"), str):
        return str(context_payload["request_id"])
    return None


def _rejected(
    *,
    state: ShieldV3LiveOrchestratorHarnessState,
    reason_id: ReasonId,
    context_hash: str | None,
    request_id: str | None,
    dominant_reason: str,
    source_receipt_hash: str | None = None,
    normalized_receipt_hash: str | None = None,
    adapter_harness: ShieldV3AdapterHarnessResult | None = None,
) -> ShieldV3LiveOrchestratorHarnessResult:
    return ShieldV3LiveOrchestratorHarnessResult(
        state=state,
        reason_id=reason_id,
        context_hash=context_hash,
        request_id=request_id,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        handoff_allowed=False,
        dominant_reason_ids=(dominant_reason,),
        source_receipt_hash=source_receipt_hash,
        normalized_receipt_hash=normalized_receipt_hash,
        adapter_harness=adapter_harness,
    )


def _require_hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64-character sha256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be sha256 hex") from exc
    return value.lower()


def _contains_authority_bypass(value: Any) -> bool:
    if isinstance(value, Mapping):
        if set(value.keys()) & _FORBIDDEN_AUTHORITY_KEYS:
            return True
        return any(_contains_authority_bypass(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_authority_bypass(item) for item in value)
    return False


def _verify_source_receipt_hash(receipt: Mapping[str, Any]) -> str:
    source_hash = _require_hash(receipt.get("receipt_hash"), field="receipt_hash")
    without_hash = dict(receipt)
    without_hash["receipt_hash"] = ""
    if canonical_sha256(without_hash) != source_hash:
        raise ValueError("live receipt hash mismatch")
    return source_hash


def _decision_to_internal_verdict(decision: str) -> str:
    if decision == "ALLOW":
        return "ALLOW"
    if decision in {"DENY", "ERROR"}:
        return "DENY"
    if decision == "ESCALATE":
        return "HUMAN_REVIEW_REQUIRED"
    raise ValueError("unsupported live component decision for AdamantineOS handoff")


def _normalize_live_component(component: Any, *, expected_context_hash: str, expected_request_id: str) -> dict[str, Any]:
    if not isinstance(component, Mapping):
        raise ValueError("live component verdict must be object")
    if set(component.keys()) != _LIVE_COMPONENT_FIELDS:
        raise ValueError("live component verdict fields must match Shield v3.2.0 schema")
    if component["schema_version"] != "shield.verdict.v1":
        raise ValueError("live component schema mismatch")
    if component["contract_version"] != 3:
        raise ValueError("live component contract mismatch")
    if component["fail_closed"] is not True:
        raise ValueError("live component must be fail_closed")
    if component["request_id"] != expected_request_id:
        raise ValueError("live component request mismatch")
    if _require_hash(component["context_hash"], field="component.context_hash") != expected_context_hash:
        raise ValueError("live component context mismatch")
    component_id = component["component_id"]
    if not isinstance(component_id, str) or not component_id.strip():
        raise ValueError("live component_id invalid")
    decision = component["decision"]
    if decision not in _SUPPORTED_LIVE_DECISIONS:
        raise ValueError("live component decision unsupported")
    if not isinstance(component["reason_ids"], list) or not component["reason_ids"]:
        raise ValueError("live component reason_ids invalid")
    if any(not isinstance(reason_id, str) or not reason_id.strip() for reason_id in component["reason_ids"]):
        raise ValueError("live component reason_id invalid")
    _require_hash(component["evidence_hash"], field="component.evidence_hash")
    if not isinstance(component["evidence_families"], list) or not component["evidence_families"]:
        raise ValueError("live component evidence_families invalid")
    if not isinstance(component["metadata"], Mapping):
        raise ValueError("live component metadata invalid")

    return {
        "component_id": str(component_id),
        "verdict": _decision_to_internal_verdict(str(decision)),
        "reason_ids": [str(reason_id) for reason_id in component["reason_ids"]],
    }


def normalize_live_orchestrator_receipt(
    receipt: Any,
    *,
    expected_context_hash: str,
    expected_request_id: str,
) -> tuple[dict[str, Any], str]:
    """Normalize a Shield Orchestrator v3.2.0 receipt into AdamantineOS evidence shape."""

    if not isinstance(receipt, Mapping):
        raise ValueError("live Shield receipt must be object")
    if set(receipt.keys()) != _LIVE_RECEIPT_FIELDS:
        raise ValueError("live Shield receipt fields must match required schema")
    if _contains_authority_bypass(receipt):
        raise ValueError("live Shield receipt contains authority bypass material")
    if receipt["schema_version"] != "shield.receipt.v1":
        raise ValueError("live Shield receipt schema mismatch")
    if receipt["contract_version"] != 3:
        raise ValueError("live Shield receipt contract mismatch")
    if receipt["fail_closed"] is not True:
        raise ValueError("live Shield receipt must be fail_closed")
    if receipt["request_id"] != expected_request_id:
        raise ValueError("live Shield receipt request mismatch")
    if _require_hash(receipt["context_hash"], field="context_hash") != _require_hash(expected_context_hash, field="expected_context_hash"):
        raise ValueError("live Shield receipt context mismatch")
    if receipt["final_outcome"] not in {"ALLOW", "DENY", "HUMAN_REVIEW_REQUIRED"}:
        raise ValueError("live Shield receipt final outcome unsupported")
    if not isinstance(receipt["component_verdicts"], list) or not receipt["component_verdicts"]:
        raise ValueError("live Shield receipt component verdicts invalid")
    if not isinstance(receipt["dominant_reason_ids"], list) or not receipt["dominant_reason_ids"]:
        raise ValueError("live Shield receipt dominant reason ids invalid")
    handoff = receipt["adamantineos_handoff"]
    if not isinstance(handoff, Mapping) or set(handoff.keys()) != {"handoff_allowed", "handoff_reason"}:
        raise ValueError("live Shield receipt handoff invalid")
    if not isinstance(handoff["handoff_allowed"], bool) or not isinstance(handoff["handoff_reason"], str) or not handoff["handoff_reason"].strip():
        raise ValueError("live Shield receipt handoff values invalid")

    source_receipt_hash = _verify_source_receipt_hash(receipt)
    normalized_components = [
        _normalize_live_component(
            component,
            expected_context_hash=expected_context_hash,
            expected_request_id=expected_request_id,
        )
        for component in receipt["component_verdicts"]
    ]

    normalized = {
        "schema_version": "shield.receipt.v1",
        "contract_version": 3,
        "request_id": expected_request_id,
        "context_hash": expected_context_hash,
        "component_verdicts": normalized_components,
        "final_outcome": str(receipt["final_outcome"]),
        "dominant_reason_ids": [str(reason_id) for reason_id in receipt["dominant_reason_ids"]],
        "receipt_hash": "",
        "adamantineos_handoff": {
            "handoff_allowed": bool(handoff["handoff_allowed"]),
            "handoff_reason": str(handoff["handoff_reason"]),
        },
        "fail_closed": True,
    }
    normalized["receipt_hash"] = canonical_sha256(normalized)
    return normalized, source_receipt_hash


def _state_from_adapter(adapter_result: ShieldV3AdapterHarnessResult) -> ShieldV3LiveOrchestratorHarnessState:
    if adapter_result.state == ShieldV3AdapterHarnessState.ALLOW_EVIDENCE_CONTINUE_CHECKS:
        return ShieldV3LiveOrchestratorHarnessState.LIVE_ALLOW_EVIDENCE_CONTINUE_CHECKS
    if adapter_result.state == ShieldV3AdapterHarnessState.DENY_DOMINATES_BLOCK:
        return ShieldV3LiveOrchestratorHarnessState.LIVE_DENY_DOMINATES_BLOCK
    if adapter_result.state == ShieldV3AdapterHarnessState.HUMAN_REVIEW_REQUIRED:
        return ShieldV3LiveOrchestratorHarnessState.LIVE_HUMAN_REVIEW_REQUIRED
    return ShieldV3LiveOrchestratorHarnessState.REJECTED_ADAPTER_HARNESS


def run_shield_v3_live_orchestrator_harness(
    *,
    combined_context_payload: Any,
    live_receipt_builder: LiveReceiptBuilder | None,
    component_verdicts: list[Mapping[str, Any]],
    rejected_receipt_hashes: Iterable[str] = (),
) -> ShieldV3LiveOrchestratorHarnessResult:
    """Run the Level 3 live Shield Orchestrator boundary through AdamantineOS.

    The live boundary is injected by the caller as a receipt builder compatible
    with Shield Orchestrator v3.2.0's `build_receipt(request_id, context_hash,
    component_verdicts)` contract. This keeps AdamantineOS CI deterministic and
    prevents an unbounded multi-repo integration from starting accidentally.
    """

    request_id = _request_id_from_context(combined_context_payload)
    try:
        context_hash = compute_combined_context_hash(combined_context_payload)
    except CombinedContextHashError as exc:
        return _rejected(
            state=ShieldV3LiveOrchestratorHarnessState.REJECTED_CONTEXT_CONTRACT,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            context_hash=None,
            request_id=request_id,
            dominant_reason=f"COMBINED_CONTEXT_HASH_CONTRACT_REJECTED:{exc}",
        )

    if live_receipt_builder is None or not callable(live_receipt_builder):
        return _rejected(
            state=ShieldV3LiveOrchestratorHarnessState.REJECTED_ORCHESTRATOR_UNAVAILABLE,
            reason_id=ReasonId.DENY_ADAPTER_UNAVAILABLE,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason="LIVE_ORCHESTRATOR_BUILDER_REQUIRED",
        )

    try:
        live_receipt = live_receipt_builder(
            request_id=str(combined_context_payload["request_id"]),
            context_hash=context_hash,
            component_verdicts=component_verdicts,
        )
    except Exception as exc:
        return _rejected(
            state=ShieldV3LiveOrchestratorHarnessState.REJECTED_ORCHESTRATOR_EXCEPTION,
            reason_id=ReasonId.DENY_ADAPTER_UNAVAILABLE,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason=f"LIVE_ORCHESTRATOR_EXCEPTION:{type(exc).__name__}",
        )

    try:
        normalized_receipt, source_receipt_hash = normalize_live_orchestrator_receipt(
            live_receipt,
            expected_context_hash=context_hash,
            expected_request_id=str(combined_context_payload["request_id"]),
        )
    except ValueError as exc:
        state = ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_TAMPERED if "hash mismatch" in str(exc).lower() else ShieldV3LiveOrchestratorHarnessState.REJECTED_LIVE_RECEIPT_SHAPE
        if "authority bypass" in str(exc).lower():
            state = ShieldV3LiveOrchestratorHarnessState.REJECTED_AUTHORITY_BYPASS
        return _rejected(
            state=state,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason=f"LIVE_RECEIPT_REJECTED:{exc}",
        )

    adapter_result = run_shield_v3_adapter_harness(
        combined_context_payload=combined_context_payload,
        shield_receipt=normalized_receipt,
        rejected_receipt_hashes=rejected_receipt_hashes,
    )
    state = _state_from_adapter(adapter_result)
    if state == ShieldV3LiveOrchestratorHarnessState.REJECTED_ADAPTER_HARNESS:
        return _rejected(
            state=state,
            reason_id=adapter_result.reason_id,
            context_hash=context_hash,
            request_id=request_id,
            dominant_reason=adapter_result.state.value,
            source_receipt_hash=source_receipt_hash,
            normalized_receipt_hash=normalized_receipt["receipt_hash"],
            adapter_harness=adapter_result,
        )

    return ShieldV3LiveOrchestratorHarnessResult(
        state=state,
        reason_id=adapter_result.reason_id,
        context_hash=context_hash,
        request_id=request_id,
        accepted_as_evidence=adapter_result.accepted_as_evidence,
        final_approval=False,
        final_outcome=adapter_result.final_outcome,
        handoff_allowed=adapter_result.handoff_allowed,
        dominant_reason_ids=adapter_result.dominant_reason_ids,
        source_receipt_hash=source_receipt_hash,
        normalized_receipt_hash=normalized_receipt["receipt_hash"],
        adapter_harness=adapter_result,
    )
