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


def _risk_payload(*, context_hash: str, generated_at: int, overall_score: int) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": context_hash,
        "generated_at": generated_at,
        "overall_score": overall_score,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }


def _allow_payload(now: int, nonce: str) -> dict[str, Any]:
    fields = {"amount": "10", "to": "DGB1"}
    wallet_id = "w1"
    action = "SEND"

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    # Envelope timebox is parsed into ints:
    issued_at = 1706990400
    expires_at = 1706990460

    qid = _qid_payload(issued_at=now - 30, expires_at=now + 30, context_hash=ctx_hash)
    risk = _risk_payload(context_hash=ctx_hash, generated_at=now - 5, overall_score=95)

    return {
        "v": "execution_request_v1",
        "request_id": "req-c5-replay",
        "intent": "authorize",
        "context": {
            "wallet_id": wallet_id,
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": action,
            "fields": fields,
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "proofs": {
                "wsqk": {
                    "wallet_id": wallet_id,
                    "action": action,
                    "context_hash": ctx_hash,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                    "nonce": nonce,
                }
            },
        },
        "timebox": {"issued_at": "2024-02-03T20:00:00Z", "expires_at": "2024-02-03T20:01:00Z"},
        "nonce": {"value": nonce, "store": "tva", "mode": "single_use"},
        "payload": {
            "ui_confirmed": True,
            "evidence": {"qid": qid, "risk": risk},
            "qid": qid,
            "risk": risk,
        },
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def test_orchestrator_replay_nonce_denied_and_executor_called_once() -> None:
    now = 1706990400

    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = RiskPolicy(min_overall_score=85, policy_pack=PolicyPack())

    payload = _allow_payload(now=now, nonce="nonce-c5-replay")

    # First execution -> allow
    r1 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    assert r1["status"] == "allow"
    assert r1["reason_id"] == ReasonId.OK_ALLOW.value

    # Capture what was executed (must not change on replay)
    assert executor.called is True
    first_req = executor.last_request
    assert first_req is not None

    # Second execution -> deny replay
    r2 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    assert r2["status"] == "deny"
    assert r2["reason_id"] == ReasonId.TVA_NONCE_REPLAY.value

    # Executor must NOT be called again: last_request must remain identical
    assert executor.called is True
    assert executor.last_request is first_req

    # Determinism: further replays are stable
    r3 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store, policy=policy)
    assert r3 == r2
    assert executor.last_request is first_req
