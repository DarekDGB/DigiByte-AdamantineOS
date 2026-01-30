from __future__ import annotations

from dataclasses import dataclass


class NonceStore:
    """
    Deterministic nonce store interface.

    TVA calls `check_and_mark(...)` to enforce single-use.
    Implementations must be injected (no global state).
    """

    def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:
        """
        Return True if nonce is accepted and marked as used.
        Return False if nonce was already used (replay).

        expires_at is provided for implementations that want to expire entries.
        """
        raise NotImplementedError


class DurableNonceStore(NonceStore):
    """
    Durable nonce store contract (mobile-ready).

    SECURITY/CONSISTENCY REQUIREMENTS:
    - Atomicity: check-and-mark must be atomic (no TOCTOU window).
      If two concurrent calls attempt the same (wallet_id, nonce), exactly one may succeed.
    - Crash safety: once a nonce is marked used, it MUST remain used after process restart.
    - Fail-closed: if storage is unavailable/corrupt, implementations should refuse acceptance
      (i.e., behave as if nonce cannot be safely validated).
    - No global state: must be dependency-injected.

    NOTE:
    This repo only defines the contract. iOS/Android implementations will live in platform layers.
    """

    # Inherits signature from NonceStore; kept here to make the "durable" semantics explicit.
    def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:  # pragma: no cover
        raise NotImplementedError


@dataclass(slots=True)
class InMemoryNonceStore(NonceStore):
    """
    Minimal deterministic store for tests and local use.

    Not production storage. No persistence. No background cleanup.
    """
    _used: dict[tuple[str, str], int] | None = None

    def __post_init__(self) -> None:
        if self._used is None:
            self._used = {}

    def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:
        assert self._used is not None
        key = (wallet_id, nonce)
        if key in self._used:
            return False
        self._used[key] = int(expires_at)
        return True
