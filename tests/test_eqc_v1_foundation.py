from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.policy.risk_policy import RiskPolicy


def _valid_session(*, now: int) -> QIDSessionProof:
    return QIDSessionProof(
        subject="did:example:123",
        issued_at=now - 50,
        expires_at=now + 50,
        proof_hash="proofhash123",
        device_binding="device-1",
        issuer_version="qid-v0",
    )


def _valid_risk(*, context_hash: str, now: int, score: int = 90) -> RiskReport:
    sig = RiskSignal(source="adaptive-core", severity=10, reason_ids=("ok",))
    return RiskReport(
        context_hash=context_hash,
        signals=(sig,),
        overall_score=score,
        generated_at=now - 10,
        oracle_version="ac-v0",
        external_source_id="rpt-1",
    )


def test_context_hash_deterministic_with_sorted_fields() -> None:
    h1 = compute_context_hash(wallet_id="w1", action="SEND", fields={"b": "2", "a": "1"})
    h2 = compute_context_hash(wallet_id="w1", action="SEND", fields={"a": "1", "b": "2"})
    assert h1 == h2


def test_eqc_denies_missing_now() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=ctx_hash, now=now),
        now=None,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_NOW.value in res.reason_ids


def test_eqc_denies_missing_qid_session() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=None,
        risk=_valid_risk(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_QID_SESSION.value in res.reason_ids


def test_eqc_denies_missing_risk_report() -> None:
    now = 150
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        risk=None,
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_RISK_REPORT.value in res.reason_ids


def test_eqc_denies_risk_context_hash_mismatch() -> None:
    now = 150
    good_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    bad_hash = "0" * 64
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=bad_hash, now=now),
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH.value in res.reason_ids
    assert res.context_hash == good_hash


def test_eqc_denies_score_below_threshold() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    policy = RiskPolicy(min_overall_score=95)
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=ctx_hash, now=now, score=90),
        now=now,
        policy=policy,
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD.value in res.reason_ids


def test_eqc_denies_missing_wallet_id() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="", action="SEND", fields=None)
    res = evaluate_eqc(
        wallet_id="",
        action="SEND",
        fields=None,
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_WALLET_ID.value in res.reason_ids


def test_eqc_denies_missing_action() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="", fields=None)
    res = evaluate_eqc(
        wallet_id="w1",
        action="",
        fields=None,
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=ctx_hash, now=now),
        now=now,
        policy=RiskPolicy(),
    )
    assert res.verdict is Verdict.DENY
    assert ReasonId.EQC_MISSING_ACTION.value in res.reason_ids


def test_eqc_allows_when_evidence_present_and_score_meets_policy() -> None:
    now = 150
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields={"amount": "10"})
    res = evaluate_eqc(
        wallet_id="w1",
        action="SEND",
        fields={"amount": "10"},
        session=_valid_session(now=now),
        risk=_valid_risk(context_hash=ctx_hash, now=now, score=90),
        now=now,
        policy=RiskPolicy(min_overall_score=85),
    )
    assert res.verdict is Verdict.ALLOW
    assert res.reason_ids == ()
    assert isinstance(res.context_hash, str)
    assert len(res.context_hash) == 64
