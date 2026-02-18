from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution import orchestrator_v1 as o1
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy


def _v1_allowish_payload(*, now: int) -> dict[str, Any]:
    """
    Build a payload that would pass EQC allow, but we will REMOVE WSQK proof
    to hit orchestrator_v1 wsqk-missing deny branch (line ~216).
    """
    fields = {"amount": "10", "to": "DGB1"}
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=fields)

    # These ISO timestamps must parse into the same epoch window used by the WSQK binding logic.
    issued_iso = "2024-02-03T20:00:00Z"
    expires_iso = "2024-02-03T20:01:00Z"

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
            "proofs": {},  # IMPORTANT: no wsqk proof -> should deny DENY_AUTHORITY_INVALID
        },
        "timebox": {"issued_at": issued_iso, "expires_at": expires_iso},
        "nonce": {"value": "nonce-1", "store": "tva", "mode": "single_use"},
        "payload": {
            "ui_confirmed": True,
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
                    "context_hash": ctx_hash,
                    "generated_at": now - 10,
                    "overall_score": 95,
                    "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
                    "oracle_version": "ac-v0",
                    "external_source_id": "rpt-1",
                },
            },
        },
        "audit": {"platform": "ios", "client_version": "0.1.0"},
    }


def test_orchestrator_v1_denies_when_wsqk_missing_even_if_eqc_allows() -> None:
    now = 1706990410  # within the envelope timebox window
    resp = o1.orchestrate_execution_v1(
        payload=_v1_allowish_payload(now=now),
        now=now,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value


def test_orchestrator_v1_outer_adapter_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hit orchestrator_v1 outer "except AdapterError" block (lines ~265-267)
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    monkeypatch.setattr(o1, "parse_execution_request_envelope_v1", boom, raising=True)

    resp = o1.orchestrate_execution_v1(
        payload={"request_id": "req-x", "context": {"action": "SEND"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "error"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_outer_adapter_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # IMPORTANT: orchestrator_v2 has an inner AdapterError handling,
    # but we want the OUTER catch at the bottom (lines ~724-756).
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", boom, raising=True)

    resp = o2.orchestrate_execution_v2(
        payload={"request_id": "req-x", "intent": "authorize", "context": {"action": "send"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_outer_generic_exception_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hit orchestrator_v2 bottom "except Exception" (lines ~826-858)
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", boom, raising=True)

    resp = o2.orchestrate_execution_v2(
        payload={"request_id": "req-x", "intent": "authorize", "context": {"action": "send"}},
        now=123,
        executor=RecordingExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=RiskPolicy(),
    )
    assert resp["status"] == "error"
    assert resp["reason_id"] == ReasonId.DENY_SCHEMA_INVALID.value
