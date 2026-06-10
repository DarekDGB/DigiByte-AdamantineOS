from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.result import EQCResult
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.envelope_v2 import ParsedExecutionRequestEnvelopeV2, parse_execution_request_envelope_v2
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.mobile_call_v1 import validate_execution_response_v1
from adamantine.v1.integrations.shield_orchestrator_receipt_verifier import (
    ShieldReceiptVerificationState,
    _classify_base_error,
)
from adamantine.v1.integrations.shield_v3_adapter import _is_hex_64
from adamantine.v1.policy.risk_policy import RiskPolicy


@dataclass(frozen=True)
class _AllowEQC:
    verdict: Verdict
    context_hash: str
    reason_ids: list[ReasonId]


def _mobile_response(*, reason_id: str) -> dict:
    return {
        "v": "execution_response_v1",
        "request_id": "r1",
        "status": "deny",
        "reason_id": reason_id,
        "decision": {
            "intent": "send",
            "action": "SEND",
            "allowed": False,
            "context_hash": "a" * 64,
            "tva": {"allowed": False},
            "eqc": {"allowed": False},
            "wsqk": {"allowed": False},
            "nonce": {"consumed": False},
            "timebox": {"valid": True},
        },
    }


def _envelope_v1_base() -> dict:
    return {
        "v": "execution_request_v1",
        "request_id": "req_guard",
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
        "payload": {"ui_confirmed": True},
    }


def _envelope_v2_base() -> dict:
    env = _envelope_v1_base()
    env["v"] = "execution_request_v2"
    env["payload"] = {
        "evidence": {
            "qid": {"v": "qid_session_v1", "dummy": True},
            "oracle": {"v": "adaptive_core_oracle_v3", "dummy": True},
            "shield": {"v": "shield_bundle_v3", "dummy": True},
        },
        "body": {"ui_confirmed": True},
    }
    return env


def test_tva_error_denial_does_not_report_full_protection(monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(o2, "run_with_tva", lambda **_: (_ for _ in ()).throw(TVAError(ReasonId.TVA_NONCE_REPLAY.value)))

    out = o2.orchestrate_execution_v2(
        payload={"request_id": "r3", "intent": "sign", "context": {"action": "sign"}, "body": {}},
        now=1706990410,
        executor=lambda *_args, **_kw: {"ok": True},
        nonce_store=lambda *_args, **_kw: False,
        policy=RiskPolicy(),
    )

    assert out["status"] == "deny"
    assert out["reason_id"] == ReasonId.TVA_NONCE_REPLAY.value
    assert out["decision"]["protection_mode"] != "full"


def test_mobile_validator_accepts_canonical_tva_and_eqc_deny_reasons() -> None:
    assert validate_execution_response_v1(payload=_mobile_response(reason_id=ReasonId.TVA_NONCE_REPLAY.value))["status"] == "deny"
    assert validate_execution_response_v1(payload=_mobile_response(reason_id=ReasonId.EQC_MISSING_QID_SESSION.value))["status"] == "deny"


def test_shield_v3_hex_helper_requires_lowercase_sha256_hex() -> None:
    assert _is_hex_64("a" * 64) is True
    assert _is_hex_64("A" * 64) is False


def test_envelopes_reject_unbounded_max_skew_seconds() -> None:
    env1 = _envelope_v1_base()
    env1["timebox"]["max_skew_seconds"] = 301
    with pytest.raises(EnvelopeError) as e1:
        parse_execution_request_envelope_v1(payload=env1, now=1770148800)
    assert e1.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID

    env2 = _envelope_v2_base()
    env2["timebox"]["max_skew_seconds"] = 301
    with pytest.raises(EnvelopeError) as e2:
        parse_execution_request_envelope_v2(payload=env2, now=1770148800)
    assert e2.value.reason_id is ReasonId.DENY_TIMEBOX_INVALID


def test_production_sources_do_not_disable_qid_freshness_or_upgrade_receipts() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src" / "adamantine"
    offenders: list[str] = []
    for path in src_root.rglob("*.py"):
        text = path.read_text()
        if "require_fresh=False" in text or "require_receipt=False" in text:
            offenders.append(str(path.relative_to(src_root)))
    assert offenders == []


def test_shield_receipt_error_message_classifier_dependency_is_pinned() -> None:
    state, reason = _classify_base_error(ValueError("context mismatch"))
    assert state is ShieldReceiptVerificationState.REJECTED_CONTEXT_MISMATCH
    assert reason is ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH

    state, reason = _classify_base_error(ValueError("hash mismatch"))
    assert state is ShieldReceiptVerificationState.REJECTED_TAMPERED_RECEIPT
    assert reason is ReasonId.EQC_INVALID_SHIELD_BUNDLE

    state, reason = _classify_base_error(ValueError("direct shield component"))
    assert state is ShieldReceiptVerificationState.REJECTED_RAW_COMPONENT_BYPASS
    assert reason is ReasonId.EQC_INVALID_SHIELD_BUNDLE
