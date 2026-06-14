from __future__ import annotations

import hashlib
import json
from typing import Any

RECEIPT_SCHEMA_VERSION = "shield.receipt.v1"
CONTRACT_VERSION = 3
ALLOWED_FINAL_OUTCOMES = ("ALLOW", "DENY", "HUMAN_REVIEW_REQUIRED")
REQUIRED_RECEIPT_FIELDS = frozenset({
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
})


class ShieldReceiptError(ValueError):
    """Fail-closed base error for Shield Orchestrator receipt validation."""


class DirectComponentVerdictError(ShieldReceiptError):
    """A raw Shield component verdict attempted to bypass the Orchestrator receipt."""


class ShieldReceiptContextMismatchError(ShieldReceiptError):
    """The receipt context hash does not match the expected AdamantineOS context."""


class ShieldReceiptHashMismatchError(ShieldReceiptError):
    """The receipt hash does not match the canonical receipt body."""


def canonical_json(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require_hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64-character sha256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be sha256 hex") from exc
    return value.lower()


def reject_direct_component_verdict(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Shield payload must be dict")
    if payload.get("schema_version") == "shield.verdict.v1" or "decision" in payload:
        raise DirectComponentVerdictError("AdamantineOS rejects direct Shield component verdicts; Orchestrator receipt required")


def validate_shield_orchestrator_receipt(receipt: dict[str, Any], *, expected_context_hash: str) -> dict[str, Any]:
    reject_direct_component_verdict(receipt)
    if set(receipt.keys()) != REQUIRED_RECEIPT_FIELDS:
        raise ValueError("Shield receipt fields must match required schema")
    if receipt["schema_version"] != RECEIPT_SCHEMA_VERSION:
        raise ValueError("unknown Shield receipt schema")
    if receipt["contract_version"] != CONTRACT_VERSION:
        raise ValueError("unsupported Shield contract version")
    if receipt["fail_closed"] is not True:
        raise ValueError("Shield receipt must be fail_closed")
    if _require_hash(receipt["context_hash"], field="context_hash") != _require_hash(expected_context_hash, field="expected_context_hash"):
        raise ShieldReceiptContextMismatchError("Shield receipt context mismatch")
    if receipt["final_outcome"] not in ALLOWED_FINAL_OUTCOMES:
        raise ValueError("unsupported Shield final outcome")
    if not isinstance(receipt["component_verdicts"], list) or not receipt["component_verdicts"]:
        raise ValueError("Shield receipt must contain component verdicts")
    if not isinstance(receipt["dominant_reason_ids"], list) or not receipt["dominant_reason_ids"]:
        raise ValueError("Shield receipt must contain dominant reason IDs")
    handoff = receipt["adamantineos_handoff"]
    if not isinstance(handoff, dict) or set(handoff.keys()) != {"handoff_allowed", "handoff_reason"}:
        raise ValueError("Shield receipt handoff must be canonical")
    if not isinstance(handoff["handoff_allowed"], bool) or not isinstance(handoff["handoff_reason"], str) or not handoff["handoff_reason"].strip():
        raise ValueError("Shield receipt handoff values are invalid")
    without_hash = dict(receipt)
    received_hash = _require_hash(without_hash["receipt_hash"], field="receipt_hash")
    without_hash["receipt_hash"] = ""
    if canonical_sha256(without_hash) != received_hash:
        raise ShieldReceiptHashMismatchError("Shield receipt hash mismatch")
    if receipt["final_outcome"] == "DENY" and handoff["handoff_allowed"] is True:
        raise ValueError("Shield DENY cannot allow AdamantineOS handoff")
    if receipt["final_outcome"] == "HUMAN_REVIEW_REQUIRED" and handoff["handoff_allowed"] is True:
        raise ValueError("Shield human review cannot allow autonomous AdamantineOS handoff")
    return dict(receipt)
