from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WSQKAuthority:
    """
    Wallet-Scoped Quantum Key (WSQK) Authority token (v1).

    Phase 2 adds:
      - issued_at / expires_at (unix seconds, int)
      - nonce (single-use)

    Notes:
    - TVA must validate all fields (fail-closed).
    - No reliance on global time; TVA receives `now` injected.
    - Single-use requires an injected nonce store (no global state).
    """
    wallet_id: str
    action: str
    context_hash: str

    issued_at: int
    expires_at: int
    nonce: str
