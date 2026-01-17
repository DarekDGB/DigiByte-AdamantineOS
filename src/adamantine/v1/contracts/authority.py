from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WSQKAuthority:
    """
    Wallet-Scoped Quantum Key (WSQK) Authority token (v1 foundation shape).

    This is the *authority layer* output that must bind to the exact
    ExecutionContext (wallet_id, action, context_hash).

    Note:
    - This is intentionally minimal. TTL/nonce/proof come later (Phase 2).
    - Deterministic + fail-closed by design.
    """
    wallet_id: str
    action: str
    context_hash: str
