from __future__ import annotations

import pytest

from adamantine.v1.enforcement.nonce_store import DurableNonceStore, InMemoryNonceStore, NonceStore


def test_durable_nonce_store_is_a_nonce_store() -> None:
    assert issubclass(DurableNonceStore, NonceStore)


def test_nonce_store_interface_is_abstract() -> None:
    store = NonceStore()
    with pytest.raises(NotImplementedError):
        store.check_and_mark("w1", "n1", 123)


def test_durable_nonce_store_interface_is_abstract() -> None:
    store = DurableNonceStore()
    with pytest.raises(NotImplementedError):
        store.check_and_mark("w1", "n1", 123)


def test_inmemory_nonce_store_enforces_single_use() -> None:
    store = InMemoryNonceStore()
    assert store.check_and_mark("w1", "n1", 999) is True
    assert store.check_and_mark("w1", "n1", 999) is False


def test_inmemory_nonce_store_scopes_by_wallet() -> None:
    store = InMemoryNonceStore()
    assert store.check_and_mark("w1", "n1", 999) is True
    assert store.check_and_mark("w2", "n1", 999) is True
