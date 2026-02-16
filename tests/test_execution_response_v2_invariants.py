from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.response_v2 import build_execution_response_v2


def _base_kwargs() -> dict:
    return dict(
        request_id="req",
        intent="authorize",
        action="send",
        context_hash="0" * 64,
        status="deny",
        reason_id=ReasonId.DENY_POLICY,
        protection_mode="full",
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=False,
        issued_at=0,
        expires_at=0,
        max_skew_seconds=0,
        timebox_valid=True,
        nonce_store="tva",
        nonce_value="n1",
        nonce_consumed=False,
        qid_present=True,
        qid_valid=True,
        shield_present=True,
        shield_valid=True,
        oracle_present=True,
        oracle_valid=True,
        policy_mode="STRICT_FAIL_CLOSED",
        override_allowed=False,
        policy_reason_id=ReasonId.DENY_POLICY,
    )


def test_allow_requires_ok_allow_reason() -> None:
    kw = _base_kwargs()
    kw["status"] = "allow"
    kw["reason_id"] = ReasonId.DENY_POLICY
    with pytest.raises(ValueError):
        build_execution_response_v2(**kw)  # type: ignore[arg-type]


def test_invalid_context_hash_rejected() -> None:
    kw = _base_kwargs()
    kw["context_hash"] = "abc"
    with pytest.raises(ValueError):
        build_execution_response_v2(**kw)  # type: ignore[arg-type]


def test_unknown_status_rejected() -> None:
    kw = _base_kwargs()
    kw["status"] = "maybe"
    with pytest.raises(ValueError):
        build_execution_response_v2(**kw)  # type: ignore[arg-type]


def test_artifacts_and_metrics_must_be_dict_when_present() -> None:
    kw = _base_kwargs()
    kw["artifacts"] = {"k": "v"}
    kw["metrics"] = {"m": 1}
    resp = build_execution_response_v2(**kw)  # type: ignore[arg-type]
    assert resp["artifacts"]["k"] == "v"
    assert resp["metrics"]["m"] == 1

    kw2 = _base_kwargs()
    kw2["artifacts"] = ["nope"]  # type: ignore[assignment]
    with pytest.raises(ValueError):
        build_execution_response_v2(**kw2)  # type: ignore[arg-type]

    kw3 = _base_kwargs()
    kw3["metrics"] = ["nope"]  # type: ignore[assignment]
    with pytest.raises(ValueError):
        build_execution_response_v2(**kw3)  # type: ignore[arg-type]
