from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.response_v1 import build_execution_response_v1


def test_build_response_allow_happy_path_is_deterministic() -> None:
    r1 = build_execution_response_v1(
        request_id="req-1",
        intent="authorize",
        action="SEND",
        context_hash="a" * 64,
        status="allow",
        reason_id=ReasonId.OK_ALLOW,
        tva_allowed=True,
        eqc_allowed=True,
        wsqk_allowed=True,
        nonce_consumed=True,
        timebox_valid=True,
        artifacts={"executor_result": "EXECUTED"},
        metrics={"counters": {"OK_ALLOW": 1}},
    )
    r2 = build_execution_response_v1(
        request_id="req-1",
        intent="authorize",
        action="SEND",
        context_hash="a" * 64,
        status="allow",
        reason_id=ReasonId.OK_ALLOW,
        tva_allowed=True,
        eqc_allowed=True,
        wsqk_allowed=True,
        nonce_consumed=True,
        timebox_valid=True,
        artifacts={"executor_result": "EXECUTED"},
        metrics={"counters": {"OK_ALLOW": 1}},
    )

    assert r1 == r2
    assert r1["v"] == "execution_response_v1"
    assert r1["request_id"] == "req-1"
    assert r1["status"] == "allow"
    assert r1["reason_id"] == ReasonId.OK_ALLOW.value
    assert r1["decision"]["allowed"] is True
    assert r1["decision"]["context_hash"] == "a" * 64
    assert r1["artifacts"]["executor_result"] == "EXECUTED"


def test_build_response_deny_sets_allowed_false() -> None:
    r = build_execution_response_v1(
        request_id="req-2",
        intent="authorize",
        action="SEND",
        context_hash="b" * 64,
        status="deny",
        reason_id=ReasonId.DENY_SCHEMA_INVALID,
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=False,
        nonce_consumed=False,
        timebox_valid=False,
    )
    assert r["status"] == "deny"
    assert r["decision"]["allowed"] is False
    assert r["reason_id"] == ReasonId.DENY_SCHEMA_INVALID.value


def test_build_response_rejects_invalid_status() -> None:
    with pytest.raises(ValueError) as e:
        build_execution_response_v1(
            request_id="req-3",
            intent="authorize",
            action="SEND",
            context_hash="c" * 64,
            status="nope",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )
    assert "status must be one of" in str(e.value)


def test_allow_requires_ok_allow_reason() -> None:
    with pytest.raises(ValueError) as e:
        build_execution_response_v1(
            request_id="req-4",
            intent="authorize",
            action="SEND",
            context_hash="d" * 64,
            status="allow",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,  # not allowed on allow
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
        )
    assert "allow status requires ReasonId.OK_ALLOW" in str(e.value)


def test_optional_fields_must_be_dicts() -> None:
    with pytest.raises(ValueError) as e1:
        build_execution_response_v1(
            request_id="req-5",
            intent="authorize",
            action="SEND",
            context_hash="e" * 64,
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts="nope",  # type: ignore[arg-type]
        )
    assert "artifacts must be dict" in str(e1.value)

    with pytest.raises(ValueError) as e2:
        build_execution_response_v1(
            request_id="req-6",
            intent="authorize",
            action="SEND",
            context_hash="f" * 64,
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            metrics="nope",  # type: ignore[arg-type]
        )
    assert "metrics must be dict" in str(e2.value)


def test_required_fields_must_be_non_empty_strings() -> None:
    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="",
            intent="authorize",
            action="SEND",
            context_hash="a" * 64,
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )

    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="req",
            intent="",
            action="SEND",
            context_hash="a" * 64,
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )

    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="req",
            intent="authorize",
            action="",
            context_hash="a" * 64,
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )

    with pytest.raises(ValueError):
        build_execution_response_v1(
            request_id="req",
            intent="authorize",
            action="SEND",
            context_hash="",
            status="deny",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )
