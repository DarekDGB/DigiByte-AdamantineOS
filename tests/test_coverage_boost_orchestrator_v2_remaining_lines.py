from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution import orchestrator_v2 as orch_mod
from adamantine.v1.execution.executor import Executor
from adamantine.v1.policy.risk_policy import RiskPolicy


class _NoopExecutor(Executor):
    def execute(self, *, request, context, now: int) -> dict:  # type: ignore[override]
        return {"ok": True}


NOW = 1770148800  # 2026-02-03T20:00:00Z


def _policy() -> RiskPolicy:
    p = RiskPolicy()
    p.validate()
    return p


def _base_payload() -> dict:
    return {
        "v": "execution_request_v2",
        "request_id": "req_cov",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}},
        "timebox": {"issued_at": "2026-02-03T20:00:00Z", "expires_at": "2026-02-03T20:01:00Z"},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": {"v": "qid_session_v1", "dummy": True},
                "oracle": {"v": "adaptive_core_oracle_v3", "dummy": True},
                "shield": {"v": "shield_bundle_v3", "dummy": True},
            },
            "body": {"ui_confirmed": True},
        },
        "audit": {"platform": "ios", "client_version": "1.0.0"},
    }


def test_orchestrator_v2_qid_verifier_non_adapter_exception_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _base_payload()

    def should_not_call(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("parse_qid_session must not be called when qid_verifier fails")

    monkeypatch.setattr(orch_mod, "parse_qid_session", should_not_call, raising=True)

    def boom(_evidence: Any) -> None:
        raise ValueError("kaboom")

    resp = orch_mod.orchestrate_execution_v2(
        payload=payload,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
        qid_verifier=boom,
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_QID_PROOF.value


def test_orchestrator_v2_oracle_adapter_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.integrations.errors import AdapterError

    payload = _base_payload()

    class _Session:
        subject = "did:example:123"
        proof_hash = "h"
        device_binding = None

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: _Session(), raising=True)

    def oracle_boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "oracle boom")

    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", oracle_boom, raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=payload,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_wsqk_nonce_mismatch_hits_private_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.contracts.verdict import Verdict

    payload = _base_payload()
    ch = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    payload["authority"]["proofs"] = {
        "wsqk": {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": ch,
            "issued_at": NOW,
            "expires_at": NOW + 60,
            "nonce": "WRONG",
        }
    }

    class _Session:
        subject = "did:example:123"
        proof_hash = "h"
        device_binding = None

    class _Shield:
        required_layers = orch_mod.REQUIRED_SHIELD_LAYERS_V3
        bundle_id = "b1"
        signals = ()

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = ch

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: _Session(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _Shield(), raising=True)
    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=payload,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value


def test_orchestrator_v2_wsqk_timebox_mismatch_hits_private_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.contracts.verdict import Verdict

    payload = _base_payload()
    ch = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})
    payload["authority"]["proofs"] = {
        "wsqk": {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": ch,
            "issued_at": NOW + 1,
            "expires_at": NOW + 60,
            "nonce": "n1",
        }
    }

    class _Session:
        subject = "did:example:123"
        proof_hash = "h"
        device_binding = None

    class _Shield:
        required_layers = orch_mod.REQUIRED_SHIELD_LAYERS_V3
        bundle_id = "b1"
        signals = ()

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = ch

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: _Session(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _Shield(), raising=True)
    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=payload,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value
