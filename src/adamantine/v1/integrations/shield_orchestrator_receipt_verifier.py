from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield_orchestrator_receipt import (
    ALLOWED_FINAL_OUTCOMES,
    reject_direct_component_verdict,
    validate_shield_orchestrator_receipt,
)


class ShieldReceiptVerificationState(str, Enum):
    """Stable AdamantineOS Shield Orchestrator receipt verification states."""

    VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS = "VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS"
    VERIFIED_DENY_DOMINATES = "VERIFIED_DENY_DOMINATES"
    VERIFIED_HUMAN_REVIEW_REQUIRED = "VERIFIED_HUMAN_REVIEW_REQUIRED"
    REJECTED_INVALID_RECEIPT = "REJECTED_INVALID_RECEIPT"
    REJECTED_CONTEXT_MISMATCH = "REJECTED_CONTEXT_MISMATCH"
    REJECTED_REQUEST_MISMATCH = "REJECTED_REQUEST_MISMATCH"
    REJECTED_TAMPERED_RECEIPT = "REJECTED_TAMPERED_RECEIPT"
    REJECTED_RAW_COMPONENT_BYPASS = "REJECTED_RAW_COMPONENT_BYPASS"
    REJECTED_AUTHORITY_BYPASS = "REJECTED_AUTHORITY_BYPASS"
    REJECTED_REPLAY_RISK = "REJECTED_REPLAY_RISK"


@dataclass(frozen=True)
class ShieldReceiptVerificationResult:
    """Fail-closed verification result for external Shield Orchestrator evidence."""

    state: ShieldReceiptVerificationState
    reason_id: ReasonId
    verified: bool
    accepted_as_evidence: bool
    final_approval: bool
    final_outcome: str | None
    context_hash: str | None
    request_id: str | None
    receipt_hash: str | None
    handoff_allowed: bool
    dominant_reason_ids: tuple[str, ...]
    receipt: Mapping[str, Any] | None = None


_LEGACY_COMPONENT_KEYS = frozenset({"component_id", "verdict", "reason_ids"})
_V3_2_COMPONENT_KEYS = frozenset({
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
})
_V3_2_COMPONENT_DECISIONS = frozenset({"ALLOW", "ESCALATE", "DENY", "ERROR", "SKIPPED"})
_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "allow",
        "approved",
        "authority",
        "auto_approve",
        "broadcast",
        "bypass",
        "can_sign",
        "decision",
        "execute",
        "final_approval",
        "force_allow",
        "human_approved",
        "override",
        "sign",
        "trusted",
    }
)


def _string_or_none(payload: Any, key: str) -> str | None:
    if isinstance(payload, Mapping) and isinstance(payload.get(key), str):
        return str(payload[key])
    return None


def _rejected(
    *,
    state: ShieldReceiptVerificationState,
    reason_id: ReasonId,
    payload: Any,
    dominant_reason: str | None = None,
) -> ShieldReceiptVerificationResult:
    return ShieldReceiptVerificationResult(
        state=state,
        reason_id=reason_id,
        verified=False,
        accepted_as_evidence=False,
        final_approval=False,
        final_outcome=None,
        context_hash=_string_or_none(payload, "context_hash"),
        request_id=_string_or_none(payload, "request_id"),
        receipt_hash=_string_or_none(payload, "receipt_hash"),
        handoff_allowed=False,
        dominant_reason_ids=(dominant_reason or state.value,),
        receipt=None,
    )


def _classify_base_error(exc: ValueError) -> tuple[ShieldReceiptVerificationState, ReasonId]:
    message = str(exc).lower()
    if "direct shield component" in message:
        return ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    if "context mismatch" in message:
        return ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH, ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH
    if "hash mismatch" in message:
        return ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE
    return ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT, ReasonId.EQC_INVALID_SHIELD_BUNDLE


def _contains_authority_bypass(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(set(value.keys()) & _FORBIDDEN_AUTHORITY_KEYS) or any(_contains_authority_bypass(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_authority_bypass(item) for item in value)
    return False


def _component_contains_unknown_authority_field(component: Any) -> bool:
    if not isinstance(component, Mapping):
        return False
    keys = set(component.keys())
    allowed_contract_keys = _LEGACY_COMPONENT_KEYS | _V3_2_COMPONENT_KEYS
    unknown_keys = keys - allowed_contract_keys
    if unknown_keys & _FORBIDDEN_AUTHORITY_KEYS:
        return True
    metadata = component.get("metadata")
    return _contains_authority_bypass(metadata)


def _is_hash(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _has_non_empty_string_list(value: Any, *, unique: bool = False) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return False
    return not unique or len(set(value)) == len(value)


def _validate_legacy_component_verdict(component: Mapping[str, Any]) -> bool:
    if set(component.keys()) != _LEGACY_COMPONENT_KEYS:
        return False
    if not isinstance(component["component_id"], str) or not component["component_id"].strip():
        return False
    if component["verdict"] not in ALLOWED_FINAL_OUTCOMES:
        return False
    return _has_non_empty_string_list(component["reason_ids"])


def _validate_v3_2_component_verdict(component: Mapping[str, Any], *, receipt: Mapping[str, Any]) -> bool:
    if set(component.keys()) != _V3_2_COMPONENT_KEYS:
        return False
    if not isinstance(component["component_id"], str) or not component["component_id"].strip():
        return False
    if component["contract_version"] != 3:
        return False
    if component["schema_version"] != "shield.verdict.v1":
        return False
    if component["request_id"] != receipt.get("request_id"):
        return False
    if component["context_hash"] != receipt.get("context_hash") or not _is_hash(component["context_hash"]):
        return False
    if component["decision"] not in _V3_2_COMPONENT_DECISIONS:
        return False
    if not _has_non_empty_string_list(component["reason_ids"]):
        return False
    if not _is_hash(component["evidence_hash"]):
        return False
    if not _has_non_empty_string_list(component["evidence_families"], unique=True):
        return False
    if not isinstance(component["metadata"], Mapping):
        return False
    if component["fail_closed"] is not True:
        return False
    return True


def _validate_component_verdicts(receipt: Mapping[str, Any]) -> bool:
    components = receipt.get("component_verdicts")
    if not isinstance(components, list) or not components:
        return False
    for component in components:
        if not isinstance(component, Mapping):
            return False
        if _validate_legacy_component_verdict(component):
            continue
        if _validate_v3_2_component_verdict(component, receipt=receipt):
            continue
        return False
    return True


def _component_decision(component: Mapping[str, Any]) -> str:
    if "decision" in component:
        return str(component["decision"])
    return str(component["verdict"])


def _deny_dominates(receipt: Mapping[str, Any]) -> bool:
    components = receipt["component_verdicts"]
    decisions = [_component_decision(component) for component in components]
    if any(decision in {"DENY", "ERROR"} for decision in decisions):
        return receipt["final_outcome"] == "DENY"
    if "ESCALATE" in decisions:
        return receipt["final_outcome"] == "HUMAN_REVIEW_REQUIRED"
    return True


def verify_shield_orchestrator_receipt(
    receipt: Any,
    *,
    expected_context_hash: str,
    expected_request_id: str,
    rejected_receipt_hashes: Iterable[str] = (),
) -> ShieldReceiptVerificationResult:
    """Verify external Shield Orchestrator evidence without importing live Shield code.

    This boundary treats Shield output as evidence only. Even a verified ALLOW never
    becomes AdamantineOS final approval; it can only continue to later checks.
    Replay state is injected by the caller so the verifier remains deterministic and
    has no hidden global authority.
    """

    try:
        reject_direct_component_verdict(receipt)
        valid = validate_shield_orchestrator_receipt(receipt, expected_context_hash=expected_context_hash)
    except ValueError as exc:
        state, reason_id = _classify_base_error(exc)
        return _rejected(state=state, reason_id=reason_id, payload=receipt)

    if not isinstance(expected_request_id, str) or not expected_request_id.strip():
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
            dominant_reason="EXPECTED_REQUEST_ID_INVALID",
        )

    if valid["request_id"] != expected_request_id:
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_REQUEST_MISMATCH,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
        )

    receipt_hash = str(valid["receipt_hash"])
    if receipt_hash in set(rejected_receipt_hashes):
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_REPLAY_RISK,
            reason_id=ReasonId.EQC_SHIELD_STALE,
            payload=valid,
        )

    if any(_component_contains_unknown_authority_field(component) for component in valid["component_verdicts"]):
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
        )

    if not _validate_component_verdicts(valid):
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_INVALID_RECEIPT,
            reason_id=ReasonId.EQC_INVALID_SHIELD_BUNDLE,
            payload=valid,
            dominant_reason="COMPONENT_VERDICTS_INVALID",
        )

    if not _deny_dominates(valid):
        return _rejected(
            state=ShieldReceiptVerificationState.REJECTED_AUTHORITY_BYPASS,
            reason_id=ReasonId.EQC_CONFLICTING_EVIDENCE,
            payload=valid,
            dominant_reason="DENY_MUST_DOMINATE",
        )

    final_outcome = str(valid["final_outcome"])
    handoff_allowed = bool(valid["adamantineos_handoff"]["handoff_allowed"])
    dominant_reason_ids = tuple(str(reason_id) for reason_id in valid["dominant_reason_ids"])

    if final_outcome == "DENY":
        state = ShieldReceiptVerificationState.VERIFIED_DENY_DOMINATES
        reason_id = ReasonId.DENY_POLICY
    elif final_outcome == "HUMAN_REVIEW_REQUIRED":
        state = ShieldReceiptVerificationState.VERIFIED_HUMAN_REVIEW_REQUIRED
        reason_id = ReasonId.DENY_AUTHORITY_INSUFFICIENT
    else:
        state = ShieldReceiptVerificationState.VERIFIED_ALLOW_EVIDENCE_CONTINUE_CHECKS
        reason_id = ReasonId.EVIDENCE_OK

    return ShieldReceiptVerificationResult(
        state=state,
        reason_id=reason_id,
        verified=True,
        accepted_as_evidence=True,
        final_approval=False,
        final_outcome=final_outcome,
        context_hash=str(valid["context_hash"]),
        request_id=str(valid["request_id"]),
        receipt_hash=receipt_hash,
        handoff_allowed=handoff_allowed,
        dominant_reason_ids=dominant_reason_ids,
        receipt=valid,
    )
