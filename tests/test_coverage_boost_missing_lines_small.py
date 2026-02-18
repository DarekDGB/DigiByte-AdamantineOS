from __future__ import annotations

from pathlib import Path

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.fixture_harness import (
    _fixture_dir,
    run_all,
    verify_manifest_strict_v1_3_0,
)
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.execution.response_v2 import build_execution_response_v2
from adamantine.v1.obs.metrics import InMemoryMetrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def _base_env_v1() -> dict:
    # now=1000 must be inside issued/expires (with max_skew=0)
    return {
        "v": "execution_request_v1",
        "request_id": "r1",
        "intent": "sign_tx",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "a1",
            "session_id": "s1",
            "action": "sign",
            "fields": {"ok": "v"},
        },
        "authority": {"class": "user", "scope": {"wallet_id": "w1"}},
        "timebox": {
            "issued_at": "1970-01-01T00:10:00+00:00",   # 600
            "expires_at": "1970-01-01T00:20:00+00:00",  # 1200
        },
        "nonce": {"value": "n1", "store": "mem", "mode": "single_use"},
        "payload": {"tx": "abc"},
    }


def test_adaptive_core_oracle_v3_rejects_blank_context_hash() -> None:
    rr = RiskReport(context_hash="x", signals=(), overall_score=0, generated_at=1)
    o = AdaptiveCoreOracleV3(context_hash="   ", issued_at=0, expires_at=1, report=rr)
    with pytest.raises(ValueError, match="context_hash must be non-empty str"):
        o.validate(now=10)


def test_policy_pack_rejects_bad_external_reason_map_type() -> None:
    p = PolicyPack(external_reason_map=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="external_reason_map must be ExternalReasonMap"):
        p.validate()


def test_inmemory_metrics_ignores_empty_reason_id() -> None:
    m = InMemoryMetrics()
    m.inc("")       # covers early-return branch
    m.inc("   ")    # covers strip->empty branch
    assert m.snapshot() == {}


def test_risk_policy_rejects_non_bool_latches() -> None:
    with pytest.raises(ValueError, match="require_protected_call must be bool"):
        RiskPolicy(require_protected_call="yes").validate()  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="require_full_mode must be bool"):
        RiskPolicy(require_full_mode="yes").validate()  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="require_qid_replay_proof must be bool"):
        RiskPolicy(require_qid_replay_proof="yes").validate()  # type: ignore[arg-type]


def test_response_v1_rejects_invalid_protection_mode() -> None:
    with pytest.raises(ValueError, match="protection_mode must be one of"):
        build_execution_response_v1(
            request_id="r",
            intent="i",
            action="a",
            context_hash="h",
            status="deny",
            reason_id=ReasonId.DENY_POLICY,
            protection_mode="weird",  # type: ignore[arg-type]
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=True,
        )


def test_response_v2_covers_wsqt_timebox_and_nonce_unknown_fallbacks() -> None:
    # Covers missing lines inside response_v2:
    # - wsqk gate reason_id path when wsqk_allowed=True
    # - timebox valid path
    # - nonce.store fallback to "unknown" when empty string
    resp = build_execution_response_v2(
        request_id="r",
        intent="i",
        action="a",
        context_hash="0" * 64,
        status="deny",
        reason_id=ReasonId.DENY_POLICY,
        protection_mode="full",
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=True,           # important: flips wsqk gate reason_id to OK_ALLOW
        issued_at=0,
        expires_at=0,
        max_skew_seconds=0,
        timebox_valid=True,          # flips timebox reason_id to OK_ALLOW
        nonce_store="",              # forces "unknown"
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
    assert resp["decision"]["gates"]["wsqk"]["reason_id"] == ReasonId.OK_ALLOW.value
    assert resp["decision"]["timebox"]["reason_id"] == ReasonId.OK_ALLOW.value
    assert resp["decision"]["nonce"]["store"] == "unknown"


def test_envelope_v1_covers_fail_branches_with_metrics() -> None:
    m = InMemoryMetrics()

    # line 129: now must be int
    with pytest.raises(EnvelopeError) as e1:
        parse_execution_request_envelope_v1(payload=_base_env_v1(), now="x", metrics=m)  # type: ignore[arg-type]
    assert e1.value.reason_id is ReasonId.DENY_SCHEMA_INVALID

    # line 57: envelope must be object
    with pytest.raises(EnvelopeError) as e2:
        parse_execution_request_envelope_v1(payload=[], now=1000, metrics=m)  # type: ignore[arg-type]
    assert e2.value.reason_id is ReasonId.DENY_SCHEMA_INVALID

    # line 81: require_nonempty_str (e.g. request_id empty)
    bad = _base_env_v1()
    bad["request_id"] = ""
    with pytest.raises(EnvelopeError) as e3:
        parse_execution_request_envelope_v1(payload=bad, now=1000, metrics=m)
    assert e3.value.reason_id is ReasonId.DENY_SCHEMA_INVALID

    # line 171: context.fields key must be non-empty str
    bad2 = _base_env_v1()
    bad2["context"]["fields"] = {"": "v"}  # invalid key
    with pytest.raises(EnvelopeError) as e4:
        parse_execution_request_envelope_v1(payload=bad2, now=1000, metrics=m)
    assert e4.value.reason_id is ReasonId.DENY_SCHEMA_INVALID

    # also ensures metrics path was executed (we don't assert exact counts to avoid brittleness)
    snap = m.snapshot()
    assert isinstance(snap, dict)
    assert len(snap) > 0


def test_fixture_harness_covers_wrapper_and_non_json_skip() -> None:
    # covers line 157 wrapper
    verify_manifest_strict_v1_3_0()

    # covers line 184 "continue" for non-json files
    base: Path = _fixture_dir("v1_3_0")
    tmp = base / "zzz_temp_non_json_file.txt"
    try:
        tmp.write_text("x", encoding="utf-8")
        out = run_all("v1_3_0", now=1000)
        assert isinstance(out, dict)
    finally:
        if tmp.exists():
            tmp.unlink()
