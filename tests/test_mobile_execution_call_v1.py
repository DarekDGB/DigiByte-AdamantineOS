from __future__ import annotations

import hashlib
import json

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.mobile_call_v1 import validate_execution_response_v1


def _canon_json_bytes(obj: object) -> bytes:
    """
    Deterministic canonical JSON encoding for boundary determinism proofs.

    - sort_keys=True removes any dict insertion-order influence
    - separators=(',', ':') removes whitespace variability
    - ensure_ascii=True makes encoding stable across environments
    """
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s.encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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


# ---------------------------------------------------------------------
# D4 determinism proof (byte-identical canonical response encoding)
# ---------------------------------------------------------------------


def test_d4_replay_produces_byte_identical_canonical_response() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)

    out1 = validate_execution_response_v1(payload=payload)
    out2 = validate_execution_response_v1(payload=payload)

    b1 = _canon_json_bytes(out1)
    b2 = _canon_json_bytes(out2)

    assert b1 == b2
    assert _sha256_hex(b1) == _sha256_hex(b2)


def test_d4_snapshot_hash_regression_lock() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    out = validate_execution_response_v1(payload=payload)

    digest = _sha256_hex(_canon_json_bytes(out))

    # If this changes, determinism/semantics may have drifted.
    # Update only with intent (and treat as a contract bump signal).
    assert digest == "d3ea98c2f752ac035c378d868ca0bf34346933601c87c2ae9e3ce6e657026f56"


def test_d4_single_field_change_changes_hash() -> None:
    payload = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    out = validate_execution_response_v1(payload=payload)
    h1 = _sha256_hex(_canon_json_bytes(out))

    payload2 = _base_resp(status="deny", reason_id=ReasonId.DENY_POLICY.value)
    payload2["decision"]["context_hash"] = ("a" * 63) + "b"  # 1-byte change
    out2 = validate_execution_response_v1(payload=payload2)
    h2 = _sha256_hex(_canon_json_bytes(out2))

    assert h1 != h2
