from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v1.wsqk.issuer import WSQKIssueRequest, issue_wsqk_authority


def _qid_payload(*, issued_at: int, expires_at: int) -> dict:
    return {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "proof_hash": "proofhash123",
        "device_binding": "device-1",
        "issuer_version": "qid-v0",
    }


def _risk_payload(*, context_hash: str, generated_at: int, overall_score: int, reason_ids: list[str]) -> dict:
    return {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": context_hash,
        "generated_at": generated_at,
        "overall_score": overall_score,
        "signals": [
            {"source": "adaptive-core", "severity": 10, "reason_ids": reason_ids},
        ],
        "oracle_version": "ac-v0",
        "external_source_id": "rpt-1",
    }


def test_e2e_allows_and_executes_with_valid_evidence() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10", "to": "DGB1"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    # External payloads -> adapters -> contracts
    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        policy=RiskPolicy(min_overall_score=85),
    )

    # EQC decision
    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.ALLOW

    # WSQK authority
    auth = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id=wallet_id,
            action=action,
            context_hash=eqc.context_hash,
            now=now,
            ttl_seconds=30,
            nonce="nonce-1",
        )
    )

    # TVA + execution boundary
    store = InMemoryNonceStore()
    executor = RecordingExecutor()

    ctx = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=eqc.context_hash)
    req = ExecutionRequest(wallet_id=wallet_id, action=action, payload={"x": 1})

    out = run_with_tva(ctx, eqc.verdict, auth, now=now, nonce_store=store, executor=executor, request=req)
    assert out == {"ok": True}

    # Ensure executor was actually called once
    assert len(executor.calls) == 1


def test_e2e_denies_on_unknown_external_reason() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    # Unknown reason ID should fail-closed at adapter boundary
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["NEW_REASON"]),
            now=now,
            expected_context_hash=ctx_hash,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id is ReasonId.UNKNOWN_EXTERNAL_REASON


def test_e2e_denies_on_score_below_threshold() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=80, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        policy=RiskPolicy(),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.DENY
    assert ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value in eqc.reason_ids


def test_tva_nonce_replay_denies_second_execution() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    session = parse_qid_session(payload=_qid_payload(issued_at=150, expires_at=250), now=now)
    risk = parse_risk_report(
        payload=_risk_payload(context_hash=ctx_hash, generated_at=190, overall_score=90, reason_ids=["ok"]),
        now=now,
        expected_context_hash=ctx_hash,
        policy=RiskPolicy(min_overall_score=85),
    )

    eqc = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=session,
        risk=risk,
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert eqc.verdict is Verdict.ALLOW

    auth = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id=wallet_id,
            action=action,
            context_hash=eqc.context_hash,
            now=now,
            ttl_seconds=30,
            nonce="nonce-replay",
        )
    )

    ctx = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=eqc.context_hash)
    store = InMemoryNonceStore()

    # First enforce passes
    enforce_tva(ctx, Verdict.ALLOW, auth, now=now, nonce_store=store)

    # Second enforce must fail due to replay
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth, now=now, nonce_store=store)

    assert str(e.value) == ReasonId.TVA_NONCE_REPLAY.value
