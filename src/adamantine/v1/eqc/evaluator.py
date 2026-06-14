from __future__ import annotations

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.result import EQCResult
from adamantine.v1.obs.metrics import Metrics
from adamantine.v1.policy.risk_policy import RiskPolicy


def _inc_all(metrics: Metrics | None, reasons: list[ReasonId]) -> None:
    if metrics is None:
        return
    for r in reasons:
        metrics.inc(r.value)


def evaluate_eqc(
    *,
    wallet_id: str,
    action: str,
    fields: dict[str, str] | None = None,
    session: QIDSessionProof | None = None,
    risk: RiskReport | None = None,
    now: int | None = None,
    policy: RiskPolicy | None = None,
    metrics: Metrics | None = None,
) -> EQCResult:
    """
    Deterministic EQC evaluator (v1 integration gate).

    Observability:
      - If metrics is provided, increments counters for each deny ReasonId.
      - Metrics MUST NOT receive payloads or request objects.

    Fail-closed rules (v1):
      - Missing wallet_id => DENY
      - Missing action   => DENY
      - Missing now      => DENY
      - Missing/invalid Q-ID session => DENY
      - Missing/invalid risk report  => DENY
      - Risk must bind to the computed context_hash => DENY
      - Risk score must meet policy threshold => DENY

    Produces a deterministic context_hash.
    """
    wallet_id_s = str(wallet_id or "").strip()
    action_s = str(action or "").strip()
    ctx_hash = compute_context_hash(wallet_id=wallet_id_s, action=action_s, fields=fields)

    reasons: list[ReasonId] = []

    # Basic presence checks (always evaluated)
    if not wallet_id_s:
        reasons.append(ReasonId.EQC_MISSING_WALLET_ID)
    if not action_s:
        reasons.append(ReasonId.EQC_MISSING_ACTION)

    # Deterministic time must be injected
    if now is None or type(now) is not int:
        reasons.append(ReasonId.EQC_MISSING_NOW)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Policy (deterministic)
    p = policy or RiskPolicy()
    p.validate()

    # Q-ID session evidence (fail-closed)
    if session is None:
        reasons.append(ReasonId.EQC_MISSING_QID_SESSION)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Provide precise reasons for common time validity failures
    if now < session.issued_at:
        reasons.append(ReasonId.EQC_QID_SESSION_NOT_YET_VALID)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if now >= session.expires_at:
        reasons.append(ReasonId.EQC_QID_SESSION_EXPIRED)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    try:
        session.validate(now=now)
    except ValueError:
        reasons.append(ReasonId.EQC_INVALID_QID_PROOF)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if session.context_hash != ctx_hash:
        reasons.append(ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Risk report evidence (fail-closed)
    if risk is None:
        reasons.append(ReasonId.EQC_MISSING_RISK_REPORT)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if risk.context_hash != ctx_hash:
        reasons.append(ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    try:
        risk.validate(now=now)
    except ValueError:
        reasons.append(ReasonId.EQC_INVALID_RISK_REPORT)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # PolicyPack-driven threshold when present (single source of truth)
    threshold = p.policy_pack.min_overall_score if p.policy_pack is not None else p.min_overall_score
    if risk.overall_score < threshold:
        reasons.append(ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # If basic presence checks failed, still deny (but only after evidence validation rules above)
    if reasons:
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    return EQCResult.allow(context_hash=ctx_hash)


def evaluate_eqc_v2(
    *,
    wallet_id: str,
    action: str,
    fields: dict[str, str] | None = None,
    session: QIDSessionProof | None = None,
    oracle: AdaptiveCoreOracleV3 | None = None,
    shield: ShieldBundleV3 | None = None,
    now: int | None = None,
    policy: RiskPolicy | None = None,
    metrics: Metrics | None = None,
) -> EQCResult:
    """
    Deterministic EQC evaluator (v2 multi-evidence gate).

    REQUIRED evidence (fail-closed):
      - Q-ID session proof
      - Adaptive Core oracle v3 (evidence-only)
      - Shield v3 bundle (evidence-only)

    Rules:
      - Missing any required evidence => DENY
      - Conflicting evidence => DENY
      - Shield can strengthen deny, never force allow
      - Oracle can influence deny via threshold, never force allow
      - Deterministic, no side effects

    Conflict rule (v2):
      - If Shield bundle contains any non-EVIDENCE_OK internal reason_id,
        the result MUST be DENY with EQC_CONFLICTING_EVIDENCE.
    """
    wallet_id_s = str(wallet_id or "").strip()
    action_s = str(action or "").strip()
    ctx_hash = compute_context_hash(wallet_id=wallet_id_s, action=action_s, fields=fields)

    reasons: list[ReasonId] = []

    if not wallet_id_s:
        reasons.append(ReasonId.EQC_MISSING_WALLET_ID)
    if not action_s:
        reasons.append(ReasonId.EQC_MISSING_ACTION)

    if now is None or type(now) is not int:
        reasons.append(ReasonId.EQC_MISSING_NOW)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    p = policy or RiskPolicy()
    p.validate()

    # Q-ID required
    if session is None:
        reasons.append(ReasonId.EQC_MISSING_QID_SESSION)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if now < session.issued_at:
        reasons.append(ReasonId.EQC_QID_SESSION_NOT_YET_VALID)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if now >= session.expires_at:
        reasons.append(ReasonId.EQC_QID_SESSION_EXPIRED)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    try:
        session.validate(now=now)
    except ValueError:
        reasons.append(ReasonId.EQC_INVALID_QID_PROOF)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if session.context_hash != ctx_hash:
        reasons.append(ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Oracle required
    if oracle is None:
        reasons.append(ReasonId.EQC_MISSING_ORACLE)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Oracle report must bind to context_hash
    report = oracle.report
    if report.context_hash != ctx_hash:
        reasons.append(ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    try:
        oracle.validate(now=now)
    except ValueError:
        reasons.append(ReasonId.EQC_INVALID_RISK_REPORT)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Threshold
    threshold = p.policy_pack.min_overall_score if p.policy_pack is not None else p.min_overall_score
    if report.overall_score < threshold:
        reasons.append(ReasonId.EQC_RISK_SCORE_BELOW_THRESHOLD)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Shield required
    if shield is None:
        reasons.append(ReasonId.EQC_MISSING_SHIELD_BUNDLE)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    try:
        shield.validate()
    except ValueError:
        reasons.append(ReasonId.EQC_INVALID_SHIELD_BUNDLE)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if shield.context_hash != ctx_hash:
        reasons.append(ReasonId.EQC_SHIELD_CONTEXT_HASH_MISMATCH)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    if not (shield.issued_at <= now < shield.expires_at):
        reasons.append(ReasonId.EQC_SHIELD_STALE)
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # Conflict: any non-OK shield reason => deny (shield can only strengthen deny)
    for sig in shield.signals:
        for rid in sig.reason_ids:
            if rid != ReasonId.EVIDENCE_OK.value:
                reasons.append(ReasonId.EQC_CONFLICTING_EVIDENCE)
                _inc_all(metrics, reasons)
                return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    # If basic presence checks failed, still deny (after evidence checks)
    if reasons:
        _inc_all(metrics, reasons)
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    return EQCResult.allow(context_hash=ctx_hash)
