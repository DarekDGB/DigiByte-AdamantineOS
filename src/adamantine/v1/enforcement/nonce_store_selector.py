from __future__ import annotations

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import DurableNonceStore, InMemoryNonceStore, NonceStore


def select_nonce_store(*, production: bool, store: NonceStore | None) -> NonceStore:
    """
    Enforce explicit nonce store selection.

    Fail-closed rules:
      - production=True requires a DurableNonceStore instance.
      - production=False may use InMemoryNonceStore if store is None.

    No environment reads. Caller decides `production`.
    """
    if production:
        if store is None:
            raise TVAError(ReasonId.TVA_MISSING_NONCE_STORE.value)
        if not isinstance(store, DurableNonceStore):
            raise TVAError(ReasonId.TVA_MISSING_NONCE_STORE.value)
        return store

    # non-production path
    return store if store is not None else InMemoryNonceStore()
