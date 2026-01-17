from __future__ import annotations

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict


def enforce_tva(
    context: ExecutionContext | None,
    verdict: Verdict | None,
    authority: WSQKAuthority | None,
) -> None:
    """
    TVA (Truth Vector Authority) — final enforcement gate (fail-closed).

    Execution is allowed ONLY if:
      - context exists
      - verdict exists and is ALLOW
      - authority exists
      - authority binds EXACTLY to context (wallet_id, action, context_hash)

    TVA does NOT:
      - decide policy
      - generate authority
      - execute actions
    """
    if context is None:
        raise TVAError(ReasonId.TVA_MISSING_CONTEXT.value)

    if verdict is None:
        raise TVAError(ReasonId.TVA_MISSING_VERDICT.value)

    if authority is None:
        raise TVAError(ReasonId.TVA_MISSING_AUTHORITY.value)

    if verdict is not Verdict.ALLOW:
        raise TVAError(ReasonId.TVA_VERDICT_NOT_ALLOW.value)

    # --- Authority must bind to the exact execution context (fail-closed) ---
    if authority.wallet_id != context.wallet_id:
        raise TVAError(ReasonId.TVA_AUTHORITY_WALLET_MISMATCH.value)

    if authority.action != context.action:
        raise TVAError(ReasonId.TVA_AUTHORITY_ACTION_MISMATCH.value)

    if authority.context_hash != context.context_hash:
        raise TVAError(ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value)
