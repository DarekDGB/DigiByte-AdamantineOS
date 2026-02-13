from __future__ import annotations

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc_v2
from adamantine.v1.policy.risk_policy import RiskPolicy


def _session(*, now: int) -> QIDSessionProof:
    # Minimal valid session spanning `now`.
    return QIDSessionProof(
        subject="user-1",
        issued_at=now - 10,
        expires_at=now + 10,
        proof_hash="p" * 32,
    )


def _oracle(*, ctx_hash: str, now: int) -> AdaptiveCoreOracleV3:
    report = RiskReport(
        context_hash=ctx_hash,
        signals=(RiskSignal(source="ac", severity=0, reason_ids=("ok",)),),
        overall_score=100,
        generated_at=now - 1,
        oracle_version="3.0.0",
    )
    return AdaptiveCoreOracleV3(
        context_hash=ctx_hash,
        issued_at=now - 5,
        expires_at=now + 5,
        report=report,
    )


def _shield(*, ctx_hash: str, now: int, signals: tuple[ShieldSignal, ...]) -> ShieldBundleV3:
    return ShieldBundleV3(
        bundle_id="b-1",
        context_hash=ctx_hash,
        issued_at=now - 5,
        expires_at=now + 5,
        required_layers=("sentinel_ai", "adn", "dqsn", "qwg", "guardian_wallet"),
        signals=signals,
    )


def test_regression_lock_shield_can_only_strengthen_deny() -> None:
    """
    Deliverable #4 regression lock:

    If Shield evidence causes DENY, adding more allow evidence or reordering signals
    must NEVER flip the outcome to ALLOW.

    This test is designed to fail forever if someone accidentally weakens the Shield
    conflict rule (e.g., only checking the first signal).
    """

    now = 1_700_000_000
    wallet_id = "w1"
    action = "send"

    ctx_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=None)

    # 4 OK signals + 1 conflicting (non-OK) reason.
    ok = ShieldSignal(source=ShieldSource.SENTINEL, severity=0, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    ok2 = ShieldSignal(source=ShieldSource.ADN, severity=0, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    ok3 = ShieldSignal(source=ShieldSource.DQSN, severity=0, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    ok4 = ShieldSignal(source=ShieldSource.QWG, severity=0, reason_ids=(ReasonId.EVIDENCE_OK.value,))
    bad = ShieldSignal(
        source=ShieldSource.GUARDIAN,
        severity=100,
        reason_ids=(ReasonId.DENY_POLICY.value,),
    )

    # Baseline: conflicting evidence present -> DENY.
    shield_a = _shield(ctx_hash=ctx_hash, now=now, signals=(ok, ok2, ok3, ok4, bad))

    res_a = evaluate_eqc_v2(
        wallet_id=wallet_id,
        action=action,
        fields=None,
        session=_session(now=now),
        oracle=_oracle(ctx_hash=ctx_hash, now=now),
        shield=shield_a,
        now=now,
        policy=RiskPolicy(),
    )
    assert res_a.verdict.value == "DENY"
    assert res_a.reason_ids == (ReasonId.EQC_CONFLICTING_EVIDENCE.value,)

    # Reorder signals so the conflicting one is NOT first.
    shield_b = _shield(ctx_hash=ctx_hash, now=now, signals=(ok, bad, ok2, ok3, ok4))

    res_b = evaluate_eqc_v2(
        wallet_id=wallet_id,
        action=action,
        fields=None,
        session=_session(now=now),
        oracle=_oracle(ctx_hash=ctx_hash, now=now),
        shield=shield_b,
        now=now,
        policy=RiskPolicy(),
    )
    assert res_b.verdict.value == "DENY"
    assert res_b.reason_ids == (ReasonId.EQC_CONFLICTING_EVIDENCE.value,)

    # Strengthen with additional allow reason on the conflicting signal.
    # (This represents extra evidence attached to the same signal; the deny reason remains.)
    bad_plus = ShieldSignal(
        source=ShieldSource.GUARDIAN,
        severity=100,
        reason_ids=(ReasonId.DENY_POLICY.value, ReasonId.EVIDENCE_OK.value),
    )
    shield_c = _shield(ctx_hash=ctx_hash, now=now, signals=(ok, ok2, ok3, ok4, bad_plus))

    res_c = evaluate_eqc_v2(
        wallet_id=wallet_id,
        action=action,
        fields=None,
        session=_session(now=now),
        oracle=_oracle(ctx_hash=ctx_hash, now=now),
        shield=shield_c,
        now=now,
        policy=RiskPolicy(),
    )
    assert res_c.verdict.value == "DENY"
    assert res_c.reason_ids == (ReasonId.EQC_CONFLICTING_EVIDENCE.value,)
