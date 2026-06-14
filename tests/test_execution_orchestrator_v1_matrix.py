from __future__ import annotations

from typing import Any

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.orchestrator_v1 import orchestrate_execution_v1
from adamantine.v1.policy.risk_policy import RiskPolicy


def _qid_payload(*, issued_at: int, expires_at: int, context_hash: str | None = None) -> dict[str, Any]:
    return {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "context_hash": context_hash,
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }


def _risk_payload(*, context_hash: str, generated_at: int, overall_score: int, reason_ids: list[str]) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": context_hash,
        "generated_at": generated_at,
        "overall_score": overall_score,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": reason_ids}],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }


def _envelope_base(*, fields: dict[str, str]) -> dict[str, Any]:
    # These timestamps MUST match the deterministic test `now` used elsewhere.
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

    # Parsed ints for WSQK proof binding to timebox
    issued_at = 1706990400
    expires_at = 1706990460

    nonce = "nonce-1"
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=fields)

    return {
        "v": "execution_request_v1",
        "request_id": "req-1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": "SEND",
            "fields": fields,
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "proofs": {
                "wsqk": {
                    "wallet_id": "w1",
                    "action": "SEND",
                    "context_hash": ctx_hash,
                    # MUST bind to envelope timebox ints, not `now`
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": nonce,
                }
            },
        },
        "timebox": {"issued_at": issued_iso, "expires_at": expires_iso},
        "nonce": {"value": nonce, "store": "tva", "mode": "single_use"},
        "payload": {"ui_confirmed": True},
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def _allow_payload(now: int) -> dict[str, Any]:
    fields = {"amount": "10", "to": "DGB1"}
    env = _envelope_base(fields=fields)
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=fields)

    env["payload"] = {
        "ui_confirmed": True,
        "evidence": {
            "qid": _qid_payload(issued_at=now - 50, expires_at=now + 50, context_hash=ctx_hash),
            "risk": _risk_payload(context_hash=ctx_hash, generated_at=now - 10, overall_score=95, reason_ids=["ok"]),
        },
    }
    return env


def _deny_payload_low_score(now: int) -> dict[str, Any]:
    fields = {"amount": "10", "to": "DGB1"}
    env = _envelope_base(fields=fields)
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=fields)

    env["payload"] = {
        "ui_confirmed": True,
        "evidence": {
            "qid": _qid_payload(issued_at=now - 50, expires_at=now + 50, context_hash=ctx_hash),
            "risk": _risk_payload(context_hash=ctx_hash, generated_at=now - 10, overall_score=10, reason_ids=["ok"]),
        },
    }
    return env


def _d(decision: dict[str, Any], *path: str) -> Any:
    cur: Any = decision
    for k in path:
        cur = cur[k]
    return cur


def test_matrix_allow_flags_and_reason() -> None:
    now = 1706990400
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    policy = RiskPolicy(min_overall_score=85, policy_pack=PolicyPack())

    resp = orchestrate_execution_v1(
        payload=_allow_payload(now),
        now=now,
        executor=executor,
        nonce_store=store,
        policy=policy,
    )

    assert resp["status"] == "allow"
    assert resp["reason_id"] == ReasonId.OK_ALLOW.value

    decision = resp["decision"]
    assert _d(decision, "eqc", "allowed") is True
    assert _d(decision, "wsqk", "allowed") is True
    assert _d(decision, "tva", "allowed") is True
    assert _d(decision, "nonce", "consumed") is True
    assert executor.called is True


def test_matrix_deny_flags_and_reason() -> None:
    now = 1706990400
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    policy = RiskPolicy(min_overall_score=85, policy_pack=PolicyPack())

    resp = orchestrate_execution_v1(
        payload=_deny_payload_low_score(now),
        now=now,
        executor=executor,
        nonce_store=store,
        policy=policy,
    )

    assert resp["status"] in {"deny", "error"}
    assert resp["reason_id"] != ReasonId.OK_ALLOW.value

    decision = resp["decision"]
    assert _d(decision, "eqc", "allowed") is False
    assert _d(decision, "wsqk", "allowed") is False
    assert _d(decision, "tva", "allowed") is False
    assert _d(decision, "nonce", "consumed") is False
    assert executor.called is False


def test_matrix_error_flags_and_reason() -> None:
    now = 1706990400
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    resp = orchestrate_execution_v1(payload={}, now=now, executor=executor, nonce_store=store)

    assert resp["status"] == "error"
    assert resp["reason_id"] != ReasonId.OK_ALLOW.value

    decision = resp["decision"]
    assert _d(decision, "eqc", "allowed") is False
    assert _d(decision, "wsqk", "allowed") is False
    assert _d(decision, "tva", "allowed") is False
    assert _d(decision, "nonce", "consumed") is False
    assert executor.called is False


def test_matrix_determinism_same_input_same_output() -> None:
    now = 1706990400
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = RiskPolicy(min_overall_score=85, policy_pack=PolicyPack())
    payload = _deny_payload_low_score(now)

    r1 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    r2 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)

    assert r1 == r2
