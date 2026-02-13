from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.response_v1 import build_execution_response_v1


def test_build_allow_requires_ok_allow() -> None:
    resp = build_execution_response_v1(
        request_id="req_1",
        intent="authorize",
        action="send",
        context_hash="a" * 64,
        status="allow",
        reason_id=ReasonId.OK_ALLOW,
        protection_mode="full",
        tva_allowed=True,
        eqc_allowed=True,
        wsqk_allowed=True,
        nonce_consumed=True,
        timebox_valid=True,
    )
    assert resp["v"] == "execution_response_v1"
    assert resp["status"] == "allow"
    assert resp["reason_id"] == "OK_ALLOW"
    assert resp["decision"]["allowed"] is True


def test_build_deny_forces_allowed_false() -> None:
    resp = build_execution_response_v1(
        request_id="req_2",
        intent="authorize",
        action="send",
        context_hash="b" * 64,
        status="deny",
        reason_id=ReasonId.DENY_NONCE_REPLAY,
        protection_mode="full",
        tva_allowed=False,
        eqc_allowed=True,
        wsqk_allowed=True,
        nonce_consumed=False,
        timebox_valid=True,
    )
    assert resp["status"] == "deny"
    assert resp["decision"]["allowed"] is False
    assert resp["reason_id"] == "DENY_NONCE_REPLAY"


def test_build_error_forces_allowed_false() -> None:
    resp = build_execution_response_v1(
        request_id="req_3",
        intent="authorize",
        action="send",
        context_hash="c" * 64,
        status="error",
        reason_id=ReasonId.ERR_INTERNAL,
        protection_mode="legacy",
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=False,
        nonce_consumed=False,
        timebox_valid=False,
    )
    assert resp["status"] == "error"
    assert resp["decision"]["allowed"] is False
    assert resp["reason_id"] == "ERR_INTERNAL"


def test_reject_invalid_status() -> None:
    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="req_4",
            intent="authorize",
            action="send",
            context_hash="d" * 64,
            status="ok",  # invalid
            reason_id=ReasonId.OK_ALLOW,
            protection_mode="full",
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
        )


def test_allow_rejects_non_ok_reason() -> None:
    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="req_5",
            intent="authorize",
            action="send",
            context_hash="e" * 64,
            status="allow",
            reason_id=ReasonId.DENY_POLICY,  # not allowed for allow status
            protection_mode="full",
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
        )
