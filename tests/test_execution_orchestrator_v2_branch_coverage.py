from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.eqc import evaluator as eqc_eval_mod
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2, REQUIRED_SHIELD_LAYERS_V3
from adamantine.v1.integrations import qid_adapter as qid_mod
from adamantine.v1.integrations import adaptive_core_oracle_v3_adapter as oracle_mod
from adamantine.v1.integrations import shield_v3_adapter as shield_mod
from adamantine.v1.execution import boundary as boundary_mod
from adamantine.v1.policy.risk_policy import RiskPolicy


class _NoopExecutor(Executor):
    def execute(self, *, request, context, now: int) -> dict:  # type: ignore[override]
        return {"ok": True}


NOW = 1706990400


def _base_payload() -> dict:
    # Must be a valid v2 envelope for orchestrator to reach deeper paths.
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
        "timebox": {"issued_at": "2024-02-03T00:00:00Z", "expires_at": "2024-02-03T00:10:00Z"},
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


def _policy() -> RiskPolicy:
    p = RiskPolicy(min_overall_score=85)
    p.validate()
    return p


def test_orchestrator_v2_envelope_error_path_status_error() -> None:
    # Force EnvelopeError by making payload not a mapping (or missing required v2 shape).
    resp = orchestrate_execution_v2(
        payload={"v": "execution_request_v2", "bad": True},  # missing required fields
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "error"
    assert resp["reason_id"] in (
        ReasonId.DENY_SCHEMA_INVALID.value,
        ReasonId.DENY_UNKNOWN_FIELD.value,
    )


def test_orchestrator_v2_adapter_error_path_status_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force AdapterError by making Q-ID adapter raise.
    from adamantine.v1.integrations.errors import AdapterError

    def boom(*args, **kwargs):
        raise AdapterError(ReasonId.DENY_ADAPTER_INVALID, "boom")

    monkeypatch.setattr(qid_mod, "parse_qid_session", boom, raising=True)

    resp = orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_ADAPTER_INVALID.value
    assert "error" in resp.get("artifacts", {})


def test_orchestrator_v2_required_layers_mismatch_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make shield adapter return required_layers != REQUIRED_SHIELD_LAYERS_V3.
    class _ShieldObj:
        def __init__(self):
            self.required_layers = ("guardian_wallet",)  # wrong
            self.bundle_id = "b1"
            self.signals = ()

    monkeypatch.setattr(qid_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(oracle_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(shield_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)

    resp = orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.EQC_INVALID_SHIELD_BUNDLE.value
    arts = resp.get("artifacts", {})
    assert arts["shield_required_layers_expected"] == list(REQUIRED_SHIELD_LAYERS_V3)


def test_orchestrator_v2_eqc_deny_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make EQC return verdict != ALLOW and provide a string reason id.
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.DENY
        reason_ids = (ReasonId.DENY_POLICY.value,)
        context_hash = "a" * 64

    monkeypatch.setattr(qid_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(oracle_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)

    class _ShieldObj:
        required_layers = REQUIRED_SHIELD_LAYERS_V3

    monkeypatch.setattr(shield_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(eqc_eval_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    resp = orchestrate_execution_v2(
        payload=_base_payload(),
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value


def test_orchestrator_v2_wsqk_missing_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make EQC allow, but wsqk authority extraction fail due to no proofs.wsqk.
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = "a" * 64

    monkeypatch.setattr(qid_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(oracle_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)

    class _ShieldObj:
        required_layers = REQUIRED_SHIELD_LAYERS_V3

    monkeypatch.setattr(shield_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(eqc_eval_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    p = _base_payload()
    p["authority"]["proofs"] = {}  # no wsqk object

    resp = orchestrate_execution_v2(
        payload=p,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value


def test_orchestrator_v2_tva_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Make everything allow until TVA boundary raises TVAError.
    from adamantine.v1.contracts.verdict import Verdict

    class _Eqc:
        verdict = Verdict.ALLOW
        reason_ids = (ReasonId.OK_ALLOW.value,)
        context_hash = "a" * 64

    class _ShieldObj:
        required_layers = REQUIRED_SHIELD_LAYERS_V3

    # Inject a valid wsqk authority proof that matches envelope fields.
    p = _base_payload()
    req = p
    ch = "a" * 64
    req["context"]["fields"] = {"asset": "DGB", "amount": "1"}  # used in context hash upstream
    # NOTE: orchestrator uses parsed envelope's context_hash, so we just ensure wsqk proof keys exist
    req["authority"]["proofs"] = {
        "wsqk": {
            "wallet_id": "w1",
            "action": "send",
            "context_hash": ch,  # must match parsed context_hash
            "issued_at": 1706918400,
            "expires_at": 1706919000,
            "nonce": "n1",
        }
    }

    monkeypatch.setattr(qid_mod, "parse_qid_session", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(oracle_mod, "parse_adaptive_core_oracle_v3", lambda *a, **k: object(), raising=True)
    monkeypatch.setattr(shield_mod, "parse_shield_bundle_v3", lambda *a, **k: _ShieldObj(), raising=True)
    monkeypatch.setattr(eqc_eval_mod, "evaluate_eqc_v2", lambda *a, **k: _Eqc(), raising=True)

    def boom_run_with_tva(*args, **kwargs):
        raise TVAError("DENY_NONCE_REPLAY")

    monkeypatch.setattr(boundary_mod, "run_with_tva", boom_run_with_tva, raising=True)

    resp = orchestrate_execution_v2(
        payload=req,
        now=NOW,
        executor=_NoopExecutor(),
        nonce_store=InMemoryNonceStore(),
        policy=_policy(),
    )
    assert resp["status"] == "deny"
    # TVAError message is coerced by _reason_from_message
    assert resp["reason_id"] in (ReasonId.DENY_NONCE_REPLAY.value, ReasonId.DENY_SCHEMA_INVALID.value)
