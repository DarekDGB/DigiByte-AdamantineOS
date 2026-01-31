from __future__ import annotations

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.risk import RiskReport, RiskSignal


def _session_ok(now: int) -> QIDSessionProof:
    return QIDSessionProof(
        subject="did:example:123",
        issued_at=now - 10,
        expires_at=now + 10,
        proof_hash="h",
        device_binding="device-1",
        issuer_version="qid-v0",
    )


def _risk(now: int, *, ctx_hash: str, score: int) -> RiskReport:
    return RiskReport(
        context_hash=ctx_hash,
        signals=(RiskSignal(source="adaptive-core", severity=1, reason_ids=("ok",)),),
        overall_score=score,
        generated_at=now - 1,
        oracle_version="ac-v0",
        external_source_id="rpt-1",
    )


def test_eqc_threshold_comes_from_policy_pack_denies_below() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    pack = PolicyPack(min_overall_score=85, allowed_external_reason_ids=("ok",))
    policy = RiskPolicy(min_overall_score=85, policy_pack=pack)

    res = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=_session_ok(now),
        risk=_risk(now, ctx_hash=ctx_hash, score=84),
        now=now,
        policy=policy,
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value in res.reason_ids


def test_eqc_threshold_comes_from_policy_pack_allows_at_threshold() -> None:
    now = 200
    wallet_id = "w1"
    action = "SEND"
    fields = {"amount": "10"}

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)

    pack = PolicyPack(min_overall_score=85, allowed_external_reason_ids=("ok",))
    policy = RiskPolicy(min_overall_score=85, policy_pack=pack)

    res = evaluate_eqc(
        wallet_id=wallet_id,
        action=action,
        fields=fields,
        session=_session_ok(now),
        risk=_risk(now, ctx_hash=ctx_hash, score=85),
        now=now,
        policy=policy,
    )
    assert res.verdict is Verdict.ALLOW
