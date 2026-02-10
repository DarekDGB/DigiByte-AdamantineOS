from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution import orchestrator_v2 as orch_mod
from adamantine.v1.policy.risk_policy import RiskPolicy


class _NoopExecutor(Executor):
    def execute(self, *, request, context, now: int) -> dict:  # type: ignore[override]
        return {"ok": True}


NOW = 1706990400  # fixed test "now"


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _policy() -> RiskPolicy:
    p = RiskPolicy(min_overall_score=85)
    p.validate()
    return p


def _base_payload() -> dict:
    issued = NOW - 10
    expires = NOW + 60
    return {
        "v": "execution_request_v2",
        "request_id": "req_1",
        "intent": "authorize",
        "context": {
            "wallet_id": "w1",
            "device_id": "d1",
            "app_id": "com.example.wallet",
            "session_id": "s1",
            "action": "send",
            "fields": {"asset": "DGB", "amount": "1"},
        },
        "authority": {"class": "user", "scope": {"policy_pack": "default"}, "proofs": {}},
        "timebox": {"issued_at": _iso(issued), "expires_at": _iso(expires)},
        "nonce": {"value": "n1", "store": "tva", "mode": "single_use"},
        "payload": {
            "evidence": {
                "qid": {"v": "qid_session_v1", "dummy": True},
                "oracle": {"v": "adaptive_core_oracle_v3", "dummy": True},
                "shield": {"v": "shield_bundle_v3", "dummy": True},
            },
            "body": {"ui_confirmed": True},
        },
        "audit": {"platform": "ios"},
    }


def test_orchestrator_v2_envelope_error_path_status_error() -> None:
    resp = orch_mod.orchestrate_execution_v2(
        payload={"v": "execution_request_v2", "bad": True},
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "error"


def test_orchestrator_v2_adapter_error_path_status_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.integrations.errors import AdapterError

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    # IMPORTANT: patch the symbol as imported into orchestrator_v2 module
    monkeypatch.setattr(orch_mod, "parse_qid_session", boom, raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value


def test_orchestrator_v2_required_layers_mismatch_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ShieldObj:
        def __init__(self) -> None:
            self.required_layers = ("guardian_wallet",)  # wrong
            self.bundle_id = "b1"
            self.signals = ()

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)

    # Ensure EQC doesn't block us before the required_layers check
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = "a" * 64

    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value


def test_orchestrator_v2_eqc_deny_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.DENY
        reason_ids = (ReasonId.DENY_POLICY.value,)
        context_hash = "a" * 64

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)

    class _ShieldObj:
        required_layers = orch_mod.REQUIRED_SHIELD_LAYERS_V3

    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value


def test_orchestrator_v2_wsqk_missing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = "a" * 64

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)

    class _ShieldObj:
        required_layers = orch_mod.REQUIRED_SHIELD_LAYERS_V3

    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    p = _base_payload()
    p["authority"]["proofs"] = {}  # no wsqk

    resp = orch_mod.orchestrate_execution_v2(
        payload=p,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value


def test_orchestrator_v2_tva_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = "a" * 64

    class _ShieldObj:
        required_layers = orch_mod.REQUIRED_SHIELD_LAYERS_V3

    p = _base_payload()

    # Real context hash so WSQK proof matches parsed envelope context_hash
    ctx = p["context"]
    ch = compute_context_hash(wallet_id=ctx["wallet_id"], action=ctx["action"], fields=ctx["fields"])

    issued_at = NOW - 10
    expires_at = NOW + 60

    p["authority"]["proofs"] = {
        "wsqk": {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": ch,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": "n1",
        }
    }

    monkeypatch.setattr(orch_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(orch_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(orch_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    def boom_run_with_tva(*args: Any, **kwargs: Any) -> Any:
        raise TVAError("DENY_NONCE_REPLAY")

    # IMPORTANT: patch the symbol as imported into orchestrator_v2 module
    monkeypatch.setattr(orch_mod, "run_with_tva", boom_run_with_tva, raising=True)

    resp = orch_mod.orchestrate_execution_v2(
        payload=p,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] in (ReasonId.DENY_NONCE_REPLAY.value, ReasonId.DENY_SCHEMA_INVALID.value)
