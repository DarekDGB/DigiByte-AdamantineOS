from __future__ import annotations

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore


def enforce_tva(
    context: ExecutionContext | None,
    verdict: Verdict | None,
    authority: WSQKAuthority | None,
    *,
    now: int | None = None,
    nonce_store: NonceStore | None = None,
) -> None:
    """
    TVA (Truth Vector Authority) — final enforcement gate (fail-closed).

    Execution is allowed ONLY if:
      - context exists
      - verdict exists and is ALLOW
      - authority exists
      - authority binds EXACTLY to context (wallet_id, action, context_hash)
      - time window is valid (issued_at <= now <= expires_at)
      - nonce is valid and single-use (via injected nonce_store)

    Determinism:
      - `now` is injected (no global time)
      - `nonce_store` is injected (no global state)
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

    # --- Deterministic time validation (requires injected now) ---
    if now is None:
        raise TVAError(ReasonId.TVA_MISSING_NOW.value)

    issued_at = int(authority.issued_at)
    expires_at = int(authority.expires_at)

    if expires_at < issued_at:
        raise TVAError(ReasonId.TVA_INVALID_TIME_WINDOW.value)

    if now < issued_at:
        raise TVAError(ReasonId.TVA_AUTHORITY_NOT_YET_VALID.value)

    if now > expires_at:
        raise TVAError(ReasonId.TVA_AUTHORITY_EXPIRED.value)

    # --- Nonce validation + replay protection (requires injected store) ---
    if nonce_store is None:
        raise TVAError(ReasonId.TVA_MISSING_NONCE_STORE.value)

    nonce = str(authority.nonce or "").strip()
    if not nonce:
        raise TVAError(ReasonId.TVA_INVALID_NONCE.value)

    accepted = nonce_store.check_and_mark(authority.wallet_id, nonce, expires_at)
    if not accepted:
        raise TVAError(ReasonId.TVA_NONCE_REPLAY.value)
