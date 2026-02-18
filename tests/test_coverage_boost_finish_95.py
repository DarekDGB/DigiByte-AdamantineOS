from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.mobile_call_v1 import validate_execution_response_v1
from adamantine.v1.execution.response_v2 import build_execution_response_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


def _valid_execution_response_v1() -> dict:
    return {
        "v": "execution_response_v1",
        "request_id": "r1",
        "status": "deny",
        "reason_id": ReasonId.DENY_POLICY.value,
        "decision": {
            "intent": "sign_tx",
            "action": "sign",
            "allowed": False,
            "context_hash": "0" * 64,
            "tva": {"allowed": False},
            "eqc": {"allowed": False},
            "wsqk": {"allowed": False},
            "nonce": {"consumed": False},
            "timebox": {"valid": True},
        },
        "artifacts": {},
        "metrics": {},
    }


def test_mobile_call_v1_hits_all_missing_branches() -> None:
    # line 10: payload must be object
    with pytest.raises(ValueError, match="payload must be object"):
        validate_execution_response_v1(payload=[])  # type: ignore[arg-type]

    base = _valid_execution_response_v1()

    # line 17: require_str non-empty (v must be non-empty str)
    bad_v_empty = dict(base)
    bad_v_empty["v"] = "   "
    with pytest.raises(ValueError, match="v must be non-empty str"):
        validate_execution_response_v1(payload=bad_v_empty)

    # line 53: v must be execution_response_v1
    bad_v = dict(base)
    bad_v["v"] = "nope"
    with pytest.raises(ValueError, match="v must be execution_response_v1"):
        validate_execution_response_v1(payload=bad_v)

    # line 57: status must be one of allow/deny/error
    bad_status = dict(base)
    bad_status["status"] = "maybe"
    with pytest.raises(ValueError, match="status must be one of allow/deny/error"):
        validate_execution_response_v1(payload=bad_status)

    # lines 63-64: reason_id must be a known ReasonId
    bad_reason = dict(base)
    bad_reason["reason_id"] = "NOT_A_REAL_REASON"
    with pytest.raises(ValueError, match="reason_id must be a known ReasonId"):
        validate_execution_response_v1(payload=bad_reason)

    # line 79: context_hash must be 64-char hex string
    bad_ctx = dict(base)
    bad_dec = dict(base["decision"])
    bad_dec["context_hash"] = "abc"
    bad_ctx["decision"] = bad_dec
    with pytest.raises(ValueError, match="context_hash must be 64-char hex string"):
        validate_execution_response_v1(payload=bad_ctx)

    # line 24: require_bool (decision.allowed must be bool)
    bad_allowed_type = dict(base)
    bad_dec2 = dict(base["decision"])
    bad_dec2["allowed"] = "no"  # type: ignore[assignment]
    bad_allowed_type["decision"] = bad_dec2
    with pytest.raises(ValueError, match="allowed must be bool"):
        validate_execution_response_v1(payload=bad_allowed_type)

    # line 107: allow status requires decision.allowed == True
    bad_allow = dict(base)
    bad_allow["status"] = "allow"
    bad_allow["reason_id"] = ReasonId.OK_ALLOW.value
    bad_dec3 = dict(base["decision"])
    bad_dec3["allowed"] = False
    bad_dec3["nonce"] = {"consumed": True}
    bad_dec3["timebox"] = {"valid": True}
    bad_allow["decision"] = bad_dec3
    with pytest.raises(ValueError, match="allow status requires decision.allowed == True"):
        validate_execution_response_v1(payload=bad_allow)


def test_response_v2_hits_remaining_guard_lines() -> None:
    # lines 67/69/71: request_id/intent/action validation raises
    with pytest.raises(ValueError, match="request_id must be non-empty str"):
        build_execution_response_v2(
            request_id="",
            intent="i",
            action="a",
            context_hash="0" * 64,
            status="deny",
            reason_id=ReasonId.DENY_POLICY,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="mem",
            nonce_value="n",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode="strict",
            override_allowed=False,
            policy_reason_id=ReasonId.DENY_POLICY,
            artifacts={},
        )

    with pytest.raises(ValueError, match="intent must be non-empty str"):
        build_execution_response_v2(
            request_id="r",
            intent="",
            action="a",
            context_hash="0" * 64,
            status="deny",
            reason_id=ReasonId.DENY_POLICY,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="mem",
            nonce_value="n",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode="strict",
            override_allowed=False,
            policy_reason_id=ReasonId.DENY_POLICY,
            artifacts={},
        )

    with pytest.raises(ValueError, match="action must be non-empty str"):
        build_execution_response_v2(
            request_id="r",
            intent="i",
            action="",
            context_hash="0" * 64,
            status="deny",
            reason_id=ReasonId.DENY_POLICY,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="mem",
            nonce_value="n",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode="strict",
            override_allowed=False,
            policy_reason_id=ReasonId.DENY_POLICY,
            artifacts={},
        )

    # line 79: protection_mode must be one of...
    with pytest.raises(ValueError, match="protection_mode must be one of"):
        build_execution_response_v2(
            request_id="r",
            intent="i",
            action="a",
            context_hash="0" * 64,
            status="deny",
            reason_id=ReasonId.DENY_POLICY,
            protection_mode="weird",  # type: ignore[arg-type]
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            issued_at=0,
            expires_at=0,
            max_skew_seconds=0,
            timebox_valid=True,
            nonce_store="mem",
            nonce_value="n",
            nonce_consumed=False,
            qid_present=False,
            qid_valid=False,
            shield_present=False,
            shield_valid=False,
            oracle_present=False,
            oracle_valid=False,
            policy_mode="strict",
            override_allowed=False,
            policy_reason_id=ReasonId.DENY_POLICY,
            artifacts={},
        )


def test_risk_policy_hits_policy_pack_type_guard() -> None:
    # line 61: policy_pack must be PolicyPack or None
    with pytest.raises(ValueError, match="policy_pack must be PolicyPack or None"):
        RiskPolicy(policy_pack=object()).validate()  # type: ignore[arg-type]
