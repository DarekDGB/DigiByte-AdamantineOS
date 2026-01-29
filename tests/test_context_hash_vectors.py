from __future__ import annotations

from adamantine.v1.eqc.context_hash import compute_context_hash


def test_context_hash_vector_send_with_fields() -> None:
    h = compute_context_hash(wallet_id="w1", action="SEND", fields={"amount": "10", "to": "DGB1"})
    assert h == "8990cd8089da0c51d483be3265e4aed7aae21fa7958658baecad2f07e9a043e7"


def test_context_hash_vector_unicode_wallet_id() -> None:
    h = compute_context_hash(wallet_id="wallet-α", action="LOGIN", fields={"nonce": "0001"})
    assert h == "fdc6eeb092c6749fabc6b1be4de4cf928e05d93c31af989de62d7bfd7e832a71"


def test_context_hash_vector_no_fields() -> None:
    h = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    assert h == "88a4e92ae21cbfe30b41aee7bea87f7696485ca88a4776637d1d36e4bc27c04f"
