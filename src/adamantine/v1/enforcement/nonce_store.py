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
