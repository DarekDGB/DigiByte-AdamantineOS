from __future__ import annotations

from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport
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
    if now is None or not isinstance(now, int):
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
