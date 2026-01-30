from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.enforcement.nonce_store import DurableNonceStore, InMemoryNonceStore
from adamantine.v1.enforcement.nonce_store_selector import select_nonce_store


def test_non_production_defaults_to_inmemory_when_none() -> None:
    s = select_nonce_store(production=False, store=None)
    assert isinstance(s, InMemoryNonceStore)


def test_non_production_accepts_provided_store() -> None:
    store = InMemoryNonceStore()
    s = select_nonce_store(production=False, store=store)
    assert s is store


def test_production_requires_store() -> None:
    with pytest.raises(TVAError) as e:
        select_nonce_store(production=True, store=None)
    assert str(e.value) == ReasonId.TVA_MISSING_NONCE_STORE.value


def test_production_rejects_inmemory_store() -> None:
    with pytest.raises(TVAError) as e:
        select_nonce_store(production=True, store=InMemoryNonceStore())
    assert str(e.value) == ReasonId.TVA_MISSING_NONCE_STORE.value


def test_production_accepts_durable_store_subclass() -> None:
    class FakeDurable(DurableNonceStore):
        def check_and_mark(self, wallet_id: str, nonce: str, expires_at: int) -> bool:
            return True

    s = select_nonce_store(production=True, store=FakeDurable())
    assert isinstance(s, DurableNonceStore)
