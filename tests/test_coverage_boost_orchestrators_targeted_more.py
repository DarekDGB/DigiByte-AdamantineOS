from __future__ import annotations

from dataclasses import dataclass

import pytest

from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.tva_gate import TVAError
from adamantine.v1.execution import orchestrator_v1 as o1
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.execution.envelope_v1 import ParsedExecutionRequestEnvelopeV1
from adamantine.v1.execution.envelope_v2 import ParsedExecutionRequestEnvelopeV2
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.policy.risk_policy import RiskPolicy


@dataclass(frozen=True)
class _AllowEQC:
    verdict: Verdict
    context_hash: str
    reason_ids: list[ReasonId]


def test_orchestrator_v1_helper_paths_and_wsqk_missing_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hit helper branches + wsqk-missing deny path without touching core."""

    # Helper paths that were still reported as missed.
    assert o1._reason_from_message("not-a-reason") == ReasonId.DENY_SCHEMA_INVALID
    assert o1._require_mapping(None) is None
    assert o1._require_mapping([]) is None
    assert o1._extract_fields({"context": {"fields": "nope"}}) is None
    assert o1._extract_fields({}) is None
    assert o1._extract_evidence({}) == (None, None)
    assert o1._extract_evidence({"evidence": "nope"}) == (None, None)

    # Parsed request that always succeeds, but has no authority proofs.
    ctx = ExecutionContext(wallet_id="w1", action="sign", context_hash="a" * 64)
    req = ParsedExecutionRequestEnvelopeV1(
        request_id="r1",
        intent="sign",
        context=ctx,
        authority_class="wsqk",
        authority_scope={},
        authority_proofs=None,
        issued_at=1706990400,
        expires_at=1706990500,
        max_skew_seconds=60,
        nonce_value="n",
        nonce_store="mem",
        payload={"evidence": {}},
        audit=None,
    )

    monkeypatch.setattr(o1, "parse_execution_request_envelope_v1", lambda **_: req)
    monkeypatch.setattr(o1, "evaluate_eqc", lambda **_: _AllowEQC(Verdict.ALLOW, ctx.context_hash, [ReasonId.OK_ALLOW]))
    monkeypatch.setattr(o1, "_extract_evidence", lambda _payload: (None, None))

    resp = o1.orchestrate_execution_v1(
        payload={"request_id": "r1", "context": {"action": "sign"}},
        now=1706990410,
        executor=lambda *_args, **_kw: {"ok": True},  # not reached
        nonce_store=lambda *_args, **_kw: False,  # not reached
        policy=RiskPolicy(),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_AUTHORITY_INVALID.value
    assert resp["decision"]["eqc"]["allowed"] is True
    assert resp["decision"]["wsqk"]["allowed"] is False


def test_orchestrator_v2_coerce_reason_id_except_path() -> None:
    """Cover _coerce_reason_id exception fallback (lines 57-58)."""

    class _Bad:
        @property
        def value(self) -> str:  # type: ignore[override]
            raise RuntimeError("boom")

    assert o2._coerce_reason_id(_Bad()) == ReasonId.DENY_SCHEMA_INVALID


def test_orchestrator_v2_registry_build_failure_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover mandatory reason registry failure (lines 315-316) without core changes."""

    ctx = ExecutionContext(wallet_id="w1", action="sign", context_hash="a" * 64)
    req = ParsedExecutionRequestEnvelopeV2(
        request_id="r2",
        intent="sign",
        context=ctx,
        authority_class="wsqk",
        authority_scope={},
        authority_proofs=None,
        issued_at=1706990400,
        expires_at=1706990500,
        max_skew_seconds=60,
        nonce_value="n",
        nonce_store="mem",
        evidence_qid={"session": {"subject": "s", "issued_at": 1, "expires_at": 2, "proof_hash": "h"}},
        evidence_oracle={},
        evidence_shield={},
        body={},
        audit=None,
    )

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", lambda **_: req)
    monkeypatch.setattr(
        o2,
        "parse_qid_session",
        lambda **_: type("S", (), {"subject": "s", "proof_hash": "h", "device_binding": None})(),
    )

    class _EvilPolicy(RiskPolicy):
        def effective_allowed_external_reason_ids(self) -> tuple[str, ...]:  # type: ignore[override]
            return ()

    resp = o2.orchestrate_execution_v2(
        payload={"request_id": "r2", "intent": "sign", "context": {"action": "sign"}, "body": {}},
        now=1706990410,
        executor=lambda *_args, **_kw: {"ok": True},
        nonce_store=lambda *_args, **_kw: False,
        policy=_EvilPolicy(),
    )

    assert resp["status"] == "deny"
    assert resp["reason_id"] == ReasonId.DENY_POLICY.value
    assert "reason registry build failed" in resp["artifacts"]["error"]


def test_orchestrator_v2_tva_and_envelope_error_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover TVAError and EnvelopeError handlers."""

    # 1) TVAError path
    ctx = ExecutionContext(wallet_id="w1", action="sign", context_hash="a" * 64)
    req = ParsedExecutionRequestEnvelopeV2(
        request_id="r3",
        intent="sign",
        context=ctx,
        authority_class="wsqk",
        authority_scope={},
        authority_proofs={
            "wsqk": {
                "wallet_id": "w1",
                "action": "sign",
                "context_hash": "a" * 64,
                "nonce": "n",
                "issued_at": 1,
                "expires_at": 2,
            }
        },
        issued_at=1,
        expires_at=2,
        max_skew_seconds=60,
        nonce_value="n",
        nonce_store="mem",
        evidence_qid={"session": {"subject": "s", "issued_at": 1, "expires_at": 2, "proof_hash": "h"}},
        evidence_oracle={},
        evidence_shield={},
        body={},
        audit=None,
    )

    monkeypatch.setattr(o2, "parse_execution_request_envelope_v2", lambda **_: req)
    monkeypatch.setattr(
        o2,
        "parse_qid_session",
        lambda **_: type("S", (), {"subject": "s", "proof_hash": "h", "device_binding": None})(),
    )
    monkeypatch.setattr(o2, "parse_adaptive_core_oracle_v3", lambda **_: type("O", (), {})())
    monkeypatch.setattr(o2, "parse_shield_bundle_v3", lambda **_: type("B", (), {"required_layers": o2.REQUIRED_SHIELD_LAYERS_V3})())
    monkeypatch.setattr(o2, "evaluate_eqc_v2", lambda **_: _AllowEQC(Verdict.ALLOW, ctx.context_hash, [ReasonId.OK_ALLOW]))
    monkeypatch.setattr(
        o2,
        "_extract_wsqk_authority",
        lambda **_: WSQKAuthority(wallet_id="w1", action="sign", context_hash=ctx.context_hash, issued_at=1, expires_at=2, nonce="n"),
    )
    monkeypatch.setattr(o2, "run_with_tva", lambda **_: (_ for _ in ()).throw(TVAError("DENY_POLICY")))

    r1 = o2.orchestrate_execution_v2(
        payload={"request_id": "r3", "intent": "sign", "context": {"action": "sign"}, "body": {}},
        now=1706990410,
        executor=lambda *_args, **_kw: {"ok": True},
        nonce_store=lambda *_args, **_kw: False,
        policy=RiskPolicy(),
    )
    assert r1["status"] == "deny"

    # 2) EnvelopeError path
    monkeypatch.setattr(
        o2,
        "parse_execution_request_envelope_v2",
        lambda **_: (_ for _ in ()).throw(EnvelopeError(ReasonId.DENY_SCHEMA_INVALID, "bad envelope")),
    )
    r2 = o2.orchestrate_execution_v2(
        payload={"request_id": "r4", "intent": "sign", "context": {"action": "sign"}, "body": {}},
        now=1706990410,
        executor=lambda *_args, **_kw: {"ok": True},
        nonce_store=lambda *_args, **_kw: False,
        policy=RiskPolicy(),
    )
    assert r2["status"] == "error"
    assert r2["reason_id"] == ReasonId.DENY_SCHEMA_INVALID.value
