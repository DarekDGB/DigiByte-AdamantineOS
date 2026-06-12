from __future__ import annotations

from dataclasses import dataclass

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.reason_ids import ReasonId


@dataclass(frozen=True, slots=True)
class WSQKIssueRequest:
    wallet_id: str
    action: str
    context_hash: str
    now: int
    ttl_seconds: int
    nonce: str


def issue_wsqk_authority(req: WSQKIssueRequest) -> WSQKAuthority:
    """
    Deterministic WSQK issuer (foundation).

    Rules (fail-closed):
    - wallet_id/action/context_hash must be non-empty
    - now must be provided (int)
    - ttl_seconds must be > 0
    - nonce must be non-empty (injected; not generated here)

    Output:
    - issued_at = now
    - expires_at = now + ttl_seconds
    """
    wallet_id = str(req.wallet_id or "").strip()
    if not wallet_id:
        raise TVAError(ReasonId.WSQK_MISSING_WALLET_ID.value)

    action = str(req.action or "").strip()
    if not action:
        raise TVAError(ReasonId.WSQK_MISSING_ACTION.value)

    context_hash = str(req.context_hash or "").strip()
    if not context_hash:
        raise TVAError(ReasonId.WSQK_MISSING_CONTEXT_HASH.value)

    try:
        now = int(req.now)
    except Exception as exc:
        raise TVAError(ReasonId.WSQK_MISSING_NOW.value) from exc

    ttl = int(req.ttl_seconds)
    if ttl <= 0:
        raise TVAError(ReasonId.WSQK_INVALID_TTL.value)

    nonce = str(req.nonce or "").strip()
    if not nonce:
        raise TVAError(ReasonId.WSQK_INVALID_NONCE.value)

    issued_at = now
    expires_at = now + ttl

    return WSQKAuthority(
        wallet_id=wallet_id,
        action=action,
        context_hash=context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
