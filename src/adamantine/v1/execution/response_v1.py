from __future__ import annotations

from typing import Any, Dict, Optional

from adamantine.v1.contracts.reason_ids import ReasonId


def build_execution_response_v1(
    *,
    request_id: str,
    intent: str,
    action: str,
    context_hash: str,
    status: str,
    reason_id: ReasonId,
    tva_allowed: bool,
    eqc_allowed: bool,
    wsqk_allowed: bool,
    nonce_consumed: bool,
    timebox_valid: bool,
    artifacts: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministic builder for execution_response_v1.

    Rules (contract-locked):
    - status ∈ {"allow","deny","error"}
    - status=="allow" => allowed==True and reason_id==OK_ALLOW
    - status in {"deny","error"} => allowed==False
    - No nondeterministic fields are inserted (no timestamps, no random ids)
    - Unknown keys are not added (shape is fixed)
    """
    if not isinstance(request_id, str) or request_id == "":
        raise ValueError("request_id must be non-empty str")
    if not isinstance(intent, str) or intent == "":
        raise ValueError("intent must be non-empty str")
    if not isinstance(action, str) or action == "":
        raise ValueError("action must be non-empty str")
    if not isinstance(context_hash, str) or context_hash == "":
        raise ValueError("context_hash must be non-empty str")

    if status not in {"allow", "deny", "error"}:
        raise ValueError("status must be one of: allow, deny, error")

    if status == "allow" and reason_id is not ReasonId.OK_ALLOW:
        raise ValueError("allow status requires ReasonId.OK_ALLOW")

    allowed = status == "allow"

    decision: Dict[str, Any] = {
        "intent": intent,
        "action": action,
        "allowed": allowed,
        "tva": {"allowed": bool(tva_allowed)},
        "eqc": {"allowed": bool(eqc_allowed)},
        "wsqk": {"allowed": bool(wsqk_allowed)},
        "nonce": {"consumed": bool(nonce_consumed)},
        "timebox": {"valid": bool(timebox_valid)},
        "context_hash": context_hash,
    }

    resp: Dict[str, Any] = {
        "v": "execution_response_v1",
        "request_id": request_id,
        "status": status,
        "reason_id": reason_id.value,
        "decision": decision,
    }

    # Optional fields (still deterministic if provided deterministically)
    if artifacts is not None:
        if not isinstance(artifacts, dict):
            raise ValueError("artifacts must be dict if provided")
        resp["artifacts"] = artifacts

    if metrics is not None:
        if not isinstance(metrics, dict):
            raise ValueError("metrics must be dict if provided")
        resp["metrics"] = metrics

    return resp
