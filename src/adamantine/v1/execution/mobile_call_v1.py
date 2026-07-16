from __future__ import annotations

from typing import Any, Mapping, cast

from adamantine.v1.contracts.reason_ids import ReasonId

_DENY_REASON_PREFIXES = ("DENY_", "TVA_", "EQC_")


def _require_mapping(obj: Any) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise ValueError("payload must be object")
    return cast(Mapping[str, Any], obj)


def _require_str(m: Mapping[str, Any], key: str) -> str:
    v = m.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{key} must be non-empty str")
    return v


def _require_bool(m: Mapping[str, Any], key: str) -> bool:
    v = m.get(key)
    if not isinstance(v, bool):
        raise ValueError(f"{key} must be bool")
    return v


def _deny_unknown_keys(m: Mapping[str, Any], *, allowed: set[str], name: str) -> None:
    unknown = set(m.keys()) - allowed
    if unknown:
        raise ValueError(f"{name} contains unknown fields: {sorted(unknown)}")


def validate_execution_response_v1(*, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """
    Contract validator for mobile consumers.

    - deny-by-default (unknown fields rejected)
    - fail-closed (raises ValueError)
    - validates the *shape* + key invariants only
    - D3: locks status <-> reason_id semantics + nonce/timebox safety invariants
    """
    top = _require_mapping(payload)

    _deny_unknown_keys(
        top,
        allowed={"v", "request_id", "status", "reason_id", "decision", "artifacts", "metrics"},
        name="execution_response_v1",
    )

    v = _require_str(top, "v")
    if v != "execution_response_v1":
        raise ValueError("v must be execution_response_v1")

    status = _require_str(top, "status")
    if status not in {"allow", "deny", "error"}:
        raise ValueError("status must be one of allow/deny/error")

    reason_id = _require_str(top, "reason_id")
    # Must be a known ReasonId string
    try:
        ReasonId(reason_id)
    except Exception as e:
        raise ValueError("reason_id must be a known ReasonId") from e

    decision = _require_mapping(top.get("decision"))
    _deny_unknown_keys(
        decision,
        allowed={"intent", "action", "allowed", "context_hash", "tva", "eqc", "wsqk", "nonce", "timebox"},
        name="decision",
    )

    _require_str(decision, "intent")
    _require_str(decision, "action")
    allowed = _require_bool(decision, "allowed")

    ctx_hash = _require_str(decision, "context_hash")
    if len(ctx_hash) != 64:
        raise ValueError("context_hash must be 64-char hex string")

    tva = _require_mapping(decision.get("tva"))
    eqc = _require_mapping(decision.get("eqc"))
    wsqk = _require_mapping(decision.get("wsqk"))
    nonce = _require_mapping(decision.get("nonce"))
    timebox = _require_mapping(decision.get("timebox"))

    _deny_unknown_keys(tva, allowed={"allowed"}, name="decision.tva")
    _deny_unknown_keys(eqc, allowed={"allowed"}, name="decision.eqc")
    _deny_unknown_keys(wsqk, allowed={"allowed"}, name="decision.wsqk")
    _deny_unknown_keys(nonce, allowed={"consumed"}, name="decision.nonce")
    _deny_unknown_keys(timebox, allowed={"valid"}, name="decision.timebox")

    _require_bool(tva, "allowed")
    _require_bool(eqc, "allowed")
    _require_bool(wsqk, "allowed")

    nonce_consumed = _require_bool(nonce, "consumed")
    timebox_valid = _require_bool(timebox, "valid")

    # ---------------------------------------------------------------------
    # D2 invariant (existing): allow => OK_ALLOW + decision.allowed True
    # ---------------------------------------------------------------------
    if status == "allow":
        if reason_id != ReasonId.OK_ALLOW.value:
            raise ValueError("allow status requires reason_id == OK_ALLOW")
        if allowed is not True:
            raise ValueError("allow status requires decision.allowed == True")

    # ---------------------------------------------------------------------
    # D3 locks: status <-> reason_id semantics + nonce/timebox safety invariants
    # ---------------------------------------------------------------------
    if status == "deny":
        if not reason_id.startswith(_DENY_REASON_PREFIXES):
            raise ValueError("deny status requires DENY_, TVA_, or EQC_ reason_id prefix")
        if allowed is not False:
            raise ValueError("deny status requires decision.allowed == False")
        if nonce_consumed is True:
            raise ValueError("deny must not consume nonce")

    if status == "error":
        if not reason_id.startswith("ERR_"):
            raise ValueError("error status requires reason_id starting with ERR_")
        if allowed is not False:
            raise ValueError("error status requires decision.allowed == False")
        if nonce_consumed is True:
            raise ValueError("error must not consume nonce")

    if status == "allow":
        if nonce_consumed is not True:
            raise ValueError("allow must consume nonce")
        if timebox_valid is not True:
            raise ValueError("allow requires timebox.valid == True")

    return top
