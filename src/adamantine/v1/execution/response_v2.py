from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Literal

from adamantine.v1.contracts.reason_ids import ReasonId


ProtectionMode = Literal["legacy", "minimal", "full"]


_EPOCH_ISO_Z = "1970-01-01T00:00:00Z"


def _iso_z_from_unix_seconds(sec: int) -> str:
    """Deterministic RFC3339 UTC format with 'Z'.

    Fail closed to the Unix epoch for integers outside the platform/date
    range so response construction stays total for every caller-supplied int.
    """
    try:
        dt = datetime.fromtimestamp(int(sec), tz=timezone.utc).replace(microsecond=0)
    except (OverflowError, OSError, ValueError):
        return _EPOCH_ISO_Z
    return dt.isoformat().replace("+00:00", "Z")


def build_execution_response_v2(
    *,
    request_id: str,
    intent: str,
    action: str,
    context_hash: str,
    status: str,
    reason_id: ReasonId,
    protection_mode: ProtectionMode,
    # Gates
    tva_allowed: bool,
    eqc_allowed: bool,
    wsqk_allowed: bool,
    # Timebox + nonce (echo + evaluation)
    issued_at: int,
    expires_at: int,
    max_skew_seconds: int,
    timebox_valid: bool,
    nonce_store: str,
    nonce_value: str,
    nonce_consumed: bool,
    # Evidence summaries
    qid_present: bool,
    qid_valid: bool,
    shield_present: bool,
    shield_valid: bool,
    oracle_present: bool,
    oracle_valid: bool,
    # Policy summary
    policy_mode: str,
    override_allowed: bool,
    policy_reason_id: ReasonId,
    artifacts: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic builder for execution_response_v2.

    Contract invariants:
    - status Ã¢ÂÂ {"allow","deny","error"}
    - status=="allow" => decision.allowed==True and reason_id==OK_ALLOW
    - status in {"deny","error"} => decision.allowed==False
    - protection_mode Ã¢ÂÂ {"legacy","minimal","full"}
    - response shape is fixed; no unknown keys are inserted
    - no nondeterminism: no environment reads, no random ids, no clocks (caller injects times)
    """
    if not isinstance(request_id, str) or request_id == "":
        raise ValueError("request_id must be non-empty str")
    if not isinstance(intent, str) or intent == "":
        raise ValueError("intent must be non-empty str")
    if not isinstance(action, str) or action == "":
        raise ValueError("action must be non-empty str")
    if not isinstance(context_hash, str) or len(context_hash) != 64:
        raise ValueError("context_hash must be 64-hex str")

    if status not in {"allow", "deny", "error"}:
        raise ValueError("status must be one of: allow, deny, error")

    if protection_mode not in {"legacy", "minimal", "full"}:
        raise ValueError("protection_mode must be one of: legacy, minimal, full")

    if status == "allow" and reason_id is not ReasonId.OK_ALLOW:
        raise ValueError("allow status requires ReasonId.OK_ALLOW")

    allowed = status == "allow"
    gate_reason = ReasonId.OK_ALLOW if allowed else reason_id

    issued_at_s = _iso_z_from_unix_seconds(issued_at) if isinstance(issued_at, int) else _EPOCH_ISO_Z
    expires_at_s = _iso_z_from_unix_seconds(expires_at) if isinstance(expires_at, int) else _EPOCH_ISO_Z

    decision: Dict[str, Any] = {
        "intent": intent,
        "action": action,
        "allowed": allowed,
        "protection_mode": protection_mode,
        "gates": {
            "tva": {
                "allowed": bool(tva_allowed),
                "reason_id": (ReasonId.OK_ALLOW if tva_allowed else gate_reason).value,
            },
            "eqc": {
                "allowed": bool(eqc_allowed),
                "reason_id": (ReasonId.OK_ALLOW if eqc_allowed else gate_reason).value,
            },
            "wsqk": {
                "allowed": bool(wsqk_allowed),
                "reason_id": (ReasonId.OK_ALLOW if wsqk_allowed else gate_reason).value,
            },
        },
        "timebox": {
            "valid": bool(timebox_valid),
            "issued_at": issued_at_s,
            "expires_at": expires_at_s,
            "max_skew_seconds": int(max_skew_seconds),
            "reason_id": (ReasonId.OK_ALLOW if timebox_valid else gate_reason).value,
        },
        "nonce": {
            "consumed": bool(nonce_consumed),
            "store": nonce_store if isinstance(nonce_store, str) and nonce_store else "unknown",
            "value": nonce_value if isinstance(nonce_value, str) and nonce_value else "unknown",
            "reason_id": (ReasonId.OK_ALLOW if nonce_consumed else gate_reason).value,
        },
        "evidence": {
            "qid": {
                "present": bool(qid_present),
                "valid": bool(qid_valid),
                "reason_id": (ReasonId.OK_ALLOW if qid_valid else gate_reason).value,
            },
            "shield": {
                "present": bool(shield_present),
                "valid": bool(shield_valid),
                "reason_id": (ReasonId.OK_ALLOW if shield_valid else gate_reason).value,
            },
            "oracle": {
                "present": bool(oracle_present),
                "valid": bool(oracle_valid),
                "reason_id": (ReasonId.OK_ALLOW if oracle_valid else gate_reason).value,
            },
        },
        "policy": {
            "mode": policy_mode,
            "override_allowed": bool(override_allowed),
            "reason_id": policy_reason_id.value,
        },
    }

    resp: Dict[str, Any] = {
        "v": "execution_response_v2",
        "request_id": request_id,
        "status": status,
        "reason_id": reason_id.value,
        "context_hash": context_hash,
        "decision": decision,
    }

    if artifacts is not None:
        if not isinstance(artifacts, dict):
            raise ValueError("artifacts must be dict if provided")
        resp["artifacts"] = artifacts

    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be dict if provided")
        resp["metrics"] = metrics

    return resp
