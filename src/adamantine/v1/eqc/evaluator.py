from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.result import EQCResult


def evaluate_eqc(*, wallet_id: str, action: str, fields: dict[str, str] | None = None) -> EQCResult:
    """
    Minimal deterministic EQC evaluator (foundation).

    Rules (v1):
      - Missing wallet_id => DENY
      - Missing action   => DENY
      - Otherwise => ALLOW

    Produces a deterministic context_hash.
    """
    wallet_id_s = str(wallet_id or "").strip()
    action_s = str(action or "").strip()
    ctx_hash = compute_context_hash(wallet_id=wallet_id_s, action=action_s, fields=fields)

    reasons: list[ReasonId] = []
    if not wallet_id_s:
        reasons.append(ReasonId.EQC_MISSING_WALLET_ID)
    if not action_s:
        reasons.append(ReasonId.EQC_MISSING_ACTION)

    if reasons:
        return EQCResult.deny(context_hash=ctx_hash, reasons=tuple(reasons))

    return EQCResult.allow(context_hash=ctx_hash)
