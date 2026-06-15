from __future__ import annotations

import hashlib
import json
from typing import Any

RECEIPT_SCHEMA_VERSION = "shield.receipt.v1"
VERDICT_SCHEMA_VERSION = "shield.verdict.v1"
CONTRACT_VERSION = 3
ALLOWED_FINAL_OUTCOMES = ("ALLOW", "DENY", "HUMAN_REVIEW_REQUIRED")
SUPPORTED_COMPONENT_IDS = ("adn", "dqsn", "guardian_wallet", "qwg", "sentinel_ai")
SUPPORTED_COMPONENT_DECISIONS = ("ALLOW", "ESCALATE", "DENY", "ERROR", "SKIPPED")
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
REQUIRED_VERDICT_FIELDS = frozenset({
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
COMPONENT_REASON_IDS = {
    "guardian_wallet": frozenset({
        "GW_OK_HEALTHY_ALLOW",
        "GW_ESCALATE_QID_REQUIRED",
        "GW_DENY_POLICY_BLOCKED",
        "GW_ERROR_INVALID_VERDICT",
        "GW_ERROR_CONTEXT_HASH_MISMATCH",
    }),
    "adn": frozenset({
        "ADN_OK_COORDINATION_ALLOW",
        "ADN_ESCALATE_POLICY_REVIEW",
        "ADN_DENY_DEFENSE_TRIGGERED",
        "ADN_ERROR_INVALID_VERDICT",
        "ADN_ERROR_CONTEXT_HASH_MISMATCH",
    }),
    "sentinel_ai": frozenset({
        "SNTL_OK_TELEMETRY_ALLOW",
        "SNTL_ESCALATE_THREAT_REVIEW",
        "SNTL_DENY_THREAT_DETECTED",
        "SNTL_ERROR_AI_OUTPUT_UNTRUSTED",
        "SNTL_ERROR_CONTEXT_HASH_MISMATCH",
    }),
    "dqsn": frozenset({
        "DQSN_OK_NETWORK_ALLOW",
        "DQSN_ESCALATE_QUANTUM_SIGNAL",
        "DQSN_DENY_NETWORK_RISK",
        "DQSN_ERROR_INVALID_VERDICT",
        "DQSN_ERROR_CONTEXT_HASH_MISMATCH",
    }),
    "qwg": frozenset({
        "QWG_OK_POSTURE_ALLOW",
        "QWG_ESCALATE_QUANTUM_POSTURE",
        "QWG_DENY_KEY_RISK",
        "QWG_ERROR_INVALID_VERDICT",
        "QWG_ERROR_CONTEXT_HASH_MISMATCH",
    }),
}
COMPONENT_EVIDENCE_FAMILIES = {
    "guardian_wallet": frozenset({
        "wallet_context",
        "transaction_context",
        "qid_auth_context",
        "sentinel_signal",
        "device_signal",
    }),
    "adn": frozenset({"defense_signal", "policy_context", "coordination_state"}),
    "sentinel_ai": frozenset({
        "telemetry",
        "monitor_signal",
        "threat_observation",
        "adaptive_core_bridge_event",
    }),
    "dqsn": frozenset({"network_observation", "quantum_signal", "node_state", "aggregate_signal"}),
    "qwg": frozenset({"wallet_posture", "quantum_risk_context", "key_age_context", "dormancy_context"}),
}
FORBIDDEN_METADATA_AUTHORITY_KEYS = frozenset({
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
})


class ShieldReceiptError(ValueError):
    """Fail-closed base error for Shield Orchestrator receipt validation."""


class DirectComponentVerdictError(ShieldReceiptError):
    """A raw Shield component verdict attempted to bypass the Orchestrator receipt."""


class ShieldReceiptContextMismatchError(ShieldReceiptError):
    """The receipt context hash does not match the expected AdamantineOS context."""


class ShieldReceiptHashMismatchError(ShieldReceiptError):
    """The receipt hash does not match the canonical receipt body."""


class ShieldReceiptAuthorityBypassError(ShieldReceiptError):
    """The receipt tries to carry execution authority through Shield evidence."""


class ShieldReceiptOutcomeMismatchError(ShieldReceiptError):
    """The receipt final outcome does not match its component verdict decisions."""


class ShieldReceiptComponentVerdictError(ShieldReceiptError):
    """An embedded Shield v3.2 component verdict is malformed or incomplete."""


def canonical_json(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require_hash(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be 64-character sha256 hex")
    if value != value.lower():
        raise ValueError(f"{field} must be lowercase sha256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be sha256 hex") from exc
    return value


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty str")
    return value.strip()


def _contains_forbidden_metadata_authority(value: Any) -> bool:
    if isinstance(value, dict):
        if set(value) & FORBIDDEN_METADATA_AUTHORITY_KEYS:
            return True
        return any(_contains_forbidden_metadata_authority(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_metadata_authority(item) for item in value)
    return False


def validate_component_verdict(
    verdict: dict[str, Any],
    *,
    expected_context_hash: str,
    expected_request_id: str,
) -> dict[str, Any]:
    """Validate one Shield v3.2 component verdict embedded in an Orchestrator receipt.

    AdamantineOS does not accept legacy component verdict summaries as Shield
    evidence. Each embedded component verdict must match the v3.2 Shield
    Orchestrator contract exactly, bind to the receipt request/context, and
    contain no metadata authority that could bypass AdamantineOS final policy.
    """

    if not isinstance(verdict, dict):
        raise ValueError("Shield component verdict must be dict")
    if set(verdict.keys()) != REQUIRED_VERDICT_FIELDS:
        raise ValueError("Shield component verdict fields must match v3.2 schema")
    component_id = _require_non_empty_str(verdict["component_id"], field="component_id")
    if component_id not in SUPPORTED_COMPONENT_IDS:
        raise ValueError("unknown Shield component_id")
    if verdict["contract_version"] != CONTRACT_VERSION:
        raise ValueError("Shield component contract_version mismatch")
    if verdict["schema_version"] != VERDICT_SCHEMA_VERSION:
        raise ValueError("Shield component schema_version mismatch")
    if verdict["fail_closed"] is not True:
        raise ValueError("Shield component verdict must be fail_closed")
    if _require_non_empty_str(verdict["request_id"], field="request_id") != _require_non_empty_str(
        expected_request_id,
        field="expected_request_id",
    ):
        raise ValueError("Shield component request_id mismatch")
    if _require_hash(verdict["context_hash"], field="context_hash") != _require_hash(
        expected_context_hash,
        field="expected_context_hash",
    ):
        raise ValueError("Shield component context_hash mismatch")
    decision = _require_non_empty_str(verdict["decision"], field="decision")
    if decision not in SUPPORTED_COMPONENT_DECISIONS:
        raise ValueError("unsupported Shield component decision")
    if decision == "SKIPPED":
        raise ValueError("SKIPPED Shield component verdict cannot be accepted as evidence")
    if not isinstance(verdict["reason_ids"], list) or not verdict["reason_ids"]:
        raise ValueError("Shield component reason_ids must be non-empty list")
    allowed_reason_ids = COMPONENT_REASON_IDS[component_id]
    for reason_id in verdict["reason_ids"]:
        clean_reason_id = _require_non_empty_str(reason_id, field="reason_id")
        if clean_reason_id not in allowed_reason_ids:
            raise ValueError("unknown Shield component reason_id")
    _require_hash(verdict["evidence_hash"], field="evidence_hash")
    if not isinstance(verdict["evidence_families"], list) or not verdict["evidence_families"]:
        raise ValueError("Shield component evidence_families must be non-empty list")
    if len(set(verdict["evidence_families"])) != len(verdict["evidence_families"]):
        raise ValueError("duplicated Shield component evidence family")
    allowed_evidence_families = COMPONENT_EVIDENCE_FAMILIES[component_id]
    for evidence_family in verdict["evidence_families"]:
        clean_evidence_family = _require_non_empty_str(evidence_family, field="evidence_family")
        if clean_evidence_family not in allowed_evidence_families:
            raise ValueError("unknown Shield component evidence family")
    if not isinstance(verdict["metadata"], dict):
        raise ValueError("Shield component metadata must be dict")
    if _contains_forbidden_metadata_authority(verdict["metadata"]):
        raise ShieldReceiptAuthorityBypassError("Shield component metadata contains forbidden authority field")
    return dict(verdict)


def _validate_component_verdicts(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    verdicts = receipt["component_verdicts"]
    checked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for verdict in verdicts:
        try:
            valid = validate_component_verdict(
                verdict,
                expected_context_hash=receipt["context_hash"],
                expected_request_id=receipt["request_id"],
            )
        except ShieldReceiptAuthorityBypassError:
            raise
        except ValueError as exc:
            raise ShieldReceiptComponentVerdictError("Shield component verdict invalid") from exc
        component_id = str(valid["component_id"])
        if component_id in seen:
            raise ShieldReceiptComponentVerdictError("duplicated Shield component verdict")
        seen.add(component_id)
        checked.append(valid)
    if seen != set(SUPPORTED_COMPONENT_IDS):
        raise ShieldReceiptComponentVerdictError("Shield receipt missing required v3.2 component verdict")
    if [item["component_id"] for item in checked] != sorted(SUPPORTED_COMPONENT_IDS):
        raise ShieldReceiptComponentVerdictError("Shield receipt component verdicts must be canonical v3.2 order")
    return checked


def _classify_component_verdicts(verdicts: list[dict[str, Any]]) -> tuple[str, list[str], dict[str, Any]]:
    decisions = [str(verdict["decision"]) for verdict in verdicts]
    if "DENY" in decisions:
        return "DENY", ["ORCH_DENY_DOMINATES"], {"handoff_allowed": False, "handoff_reason": "ORCH_DENY_DOMINATES"}
    if "ERROR" in decisions:
        return "DENY", ["ORCH_ERROR_INVALID_COMPONENT_VERDICT"], {
            "handoff_allowed": False,
            "handoff_reason": "ORCH_ERROR_INVALID_COMPONENT_VERDICT",
        }
    if "ESCALATE" in decisions:
        return "HUMAN_REVIEW_REQUIRED", ["ORCH_HUMAN_REVIEW_ESCALATE_PRESENT"], {
            "handoff_allowed": False,
            "handoff_reason": "ORCH_HUMAN_REVIEW_ESCALATE_PRESENT",
        }
    return "ALLOW", ["ORCH_OK_ALL_COMPONENTS_ALLOW"], {
        "handoff_allowed": True,
        "handoff_reason": "ORCH_OK_ALL_COMPONENTS_ALLOW",
    }


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
    component_verdicts = _validate_component_verdicts(receipt)
    if not isinstance(receipt["dominant_reason_ids"], list) or not receipt["dominant_reason_ids"]:
        raise ValueError("Shield receipt must contain dominant reason IDs")
    handoff = receipt["adamantineos_handoff"]
    if not isinstance(handoff, dict) or set(handoff.keys()) != {"handoff_allowed", "handoff_reason"}:
        raise ValueError("Shield receipt handoff must be canonical")
    if not isinstance(handoff["handoff_allowed"], bool) or not isinstance(handoff["handoff_reason"], str) or not handoff["handoff_reason"].strip():
        raise ValueError("Shield receipt handoff values are invalid")
    expected_outcome, expected_reasons, expected_handoff = _classify_component_verdicts(component_verdicts)
    if receipt["final_outcome"] != expected_outcome:
        raise ShieldReceiptOutcomeMismatchError("Shield receipt final_outcome does not match v3.2 component decisions")
    if receipt["dominant_reason_ids"] != expected_reasons:
        raise ShieldReceiptOutcomeMismatchError("Shield receipt dominant_reason_ids do not match v3.2 component decisions")
    if receipt["adamantineos_handoff"] != expected_handoff:
        raise ShieldReceiptOutcomeMismatchError("Shield receipt handoff does not match v3.2 component decisions")
    without_hash = dict(receipt)
    received_hash = _require_hash(without_hash["receipt_hash"], field="receipt_hash")
    without_hash["receipt_hash"] = ""
    if canonical_sha256(without_hash) != received_hash:
        raise ShieldReceiptHashMismatchError("Shield receipt hash mismatch")
    return dict(receipt)
