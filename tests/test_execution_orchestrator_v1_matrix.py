from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.orchestrator_v1 import orchestrate_execution_v1
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore


def _allow_payload(now: int) -> dict[str, Any]:
    # Matches your envelope v1 test fixtures style and must satisfy:
    # - valid timebox
    # - valid nonce
    # - valid evidence (qid + risk)
    return {
        "v": "execution_request_v1",
        "request_id": "req-allow-1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "app",
            "session_id": "s1",
            "action": "SEND",
            "fields": {"amount": "10", "to": "DGB1"},
        },
        "authority": {
            "class": "user",
            "scope": {"policy_pack": "default"},
            "wallet_id": "w1",
            "action": "SEND",
            "context_hash": "PLACEHOLDER",  # overwritten by envelope parser if needed
            "issued_at": now - 10,
            "expires_at": now + 10,
            "nonce": "n-allow-1",
        },
        "timebox": {
            "issued_at": "2026-02-03T20:00:00Z",
            "expires_at": "2026-02-03T20:01:00Z",
        },
        "nonce": {"value": "n-allow-1", "store": "tva", "mode": "single_use"},
        "payload": {"ui_confirmed": True},
        "audit": {"platform": "ios"},
        "evidence": {
            "qid": {
                "qid_iface_version": "qid-session-v0",
                "subject": "did:example:123",
                "issued_at": now - 50,
                "expires_at": now + 50,
                "proof_hash": "proofhash123",
                "device_binding": "device-1",
                "issuer_version": "qid-v0",
            },
            "risk": {
                "ac_iface_version": "adaptive-core-risk-v0",
                "context_hash": "PLACEHOLDER",
                "generated_at": now - 1,
                "overall_score": 99,
                "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
                "oracle_version": "ac-v0",
                "external_source_id": "rpt-1",
            },
        },
    }


def _deny_payload_missing_evidence() -> dict[str, Any]:
    p = _allow_payload(now=200)
    p["request_id"] = "req-deny-1"
    p["evidence"] = {}  # missing qid/risk => deny
    return p


def test_matrix_allow_flags_and_reason() -> None:
    now = 200
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    payload = _allow_payload(now=now)
    resp = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store)

    assert resp["status"] == "allow"
    assert resp["reason_id"] == ReasonId.OK_ALLOW.value
    assert resp["eqc_allowed"] is True
    assert resp["wsqk_allowed"] is True
    assert resp["tva_allowed"] is True
    assert resp["nonce_consumed"] is True


def test_matrix_deny_flags_and_reason() -> None:
    now = 200
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    payload = _deny_payload_missing_evidence()
    resp = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store)

    assert resp["status"] == "deny"
    assert resp["reason_id"] != ReasonId.OK_ALLOW.value
    assert resp["eqc_allowed"] is False
    assert resp["wsqk_allowed"] is False
    assert resp["tva_allowed"] is False
    assert resp["nonce_consumed"] is False
    assert executor.called is False


def test_matrix_error_flags_and_reason() -> None:
    now = 200
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    resp = orchestrate_execution_v1(payload={}, now=now, executor=executor, nonce_store=store)

    assert resp["status"] == "error"
    assert resp["reason_id"] != ReasonId.OK_ALLOW.value
    assert resp["eqc_allowed"] is False
    assert resp["wsqk_allowed"] is False
    assert resp["tva_allowed"] is False
    assert resp["nonce_consumed"] is False
    assert executor.called is False


def test_matrix_determinism_same_input_same_output() -> None:
    now = 200
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    payload = _deny_payload_missing_evidence()

    r1 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store)
    r2 = orchestrate_execution_v1(payload=payload, now=now, executor=executor, nonce_store=store)

    assert r1 == r2
