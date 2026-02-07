from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.mobile_call_v1 import validate_execution_response_v1


def _base_resp(*, status: str, reason_id: str) -> dict:
    return {
        "v": "execution_response_v1",
        "request_id": "r1",
        "status": status,
        "reason_id": reason_id,
        "decision": {
            "intent": "send",
            "action": "SEND",
            "allowed": status == "allow",
            "context_hash": "a" * 64,
            "tva": {"allowed": status == "allow"},
            "eqc": {"allowed": status != "error"},
            "wsqk": {"allowed": status == "allow"},
            "nonce": {"consumed": status == "allow"},
            "timebox": {"valid": status != "error"},
        },
    }


def test_mobile_call_accepts_allow_shape() -> None:
    payload = _base_resp(status="allow", reason_id=ReasonId.OK_ALLOW.value)
    out = validate_execution_response_v1(payload=payload)
    assert out["status"] == "allow"


def test_mobile_call_rejects_unknown_fields() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    payload["extra"] = 1  # unknown
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)


def test_mobile_call_rejects_allow_without_ok_allow() -> None:
    payload = _base_resp(status="allow", reason_id=ReasonId.DENY_POLICY.value)
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)


def test_mobile_call_determinism_same_input_same_result() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    out1 = validate_execution_response_v1(payload=payload)
    out2 = validate_execution_response_v1(payload=payload)
    assert out1 == out2


# ---------------------------------------------------------------------
# D3 matrix regression locks
# ---------------------------------------------------------------------


def test_d3_deny_requires_deny_prefix_and_allowed_false() -> None:
    # deny but OK_* reason must fail
    payload = _base_resp(status="deny", reason_id=ReasonId.OK_ALLOW.value)
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)

    # deny but decision.allowed True must fail
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    payload["decision"]["allowed"] = True
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)


def test_d3_error_requires_err_prefix_and_allowed_false() -> None:
    # error but DENY_* reason must fail
    payload = _base_resp(status="error", reason_id=ReasonId.DENY_POLICY.value)
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)

    # error but decision.allowed True must fail
    payload = _base_resp(status="error", reason_id=ReasonId.ERR_INTERNAL.value)
    payload["decision"]["allowed"] = True
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)


def test_d3_deny_error_must_not_consume_nonce() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    payload["decision"]["nonce"]["consumed"] = True
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)

    payload = _base_resp(status="error", reason_id=ReasonId.ERR_INTERNAL.value)
    payload["decision"]["nonce"]["consumed"] = True
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)


def test_d3_allow_requires_nonce_consumed_and_timebox_valid() -> None:
    payload = _base_resp(status="allow", reason_id=ReasonId.OK_ALLOW.value)

    payload["decision"]["nonce"]["consumed"] = False
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)

    payload = _base_resp(status="allow", reason_id=ReasonId.OK_ALLOW.value)
    payload["decision"]["timebox"]["valid"] = False
    with pytest.raises(ValueError):
        validate_execution_response_v1(payload=payload)
