from __future__ import annotations

import pytest

from adamantine.v1.eqc.context_hash import ContextHashError, compute_context_hash


def test_pinned_vectors_unchanged_after_context_hash_hardening() -> None:
    assert (
        compute_context_hash(wallet_id="w1", action="SEND", fields={"amount": "10", "to": "DGB1"})
        == "8990cd8089da0c51d483be3265e4aed7aae21fa7958658baecad2f07e9a043e7"
    )
    assert (
        compute_context_hash(wallet_id="wallet-α", action="LOGIN", fields={"nonce": "0001"})
        == "fdc6eeb092c6749fabc6b1be4de4cf928e05d93c31af989de62d7bfd7e832a71"
    )
    assert (
        compute_context_hash(wallet_id="w1", action="SEND", fields=None)
        == "88a4e92ae21cbfe30b41aee7bea87f7696485ca88a4776637d1d36e4bc27c04f"
    )


def test_newline_injection_collision_in_wallet_id_and_action_is_rejected() -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1\naction=send", action="x")
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1", action="send\naction=x")


def test_newline_injection_collision_in_field_value_is_rejected() -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w", action="a", fields={"k": "v\nz=1"})


@pytest.mark.parametrize("bad", ["\n", "\r", "\t", "\x00", "\x1f", "\x7f"])
def test_control_characters_are_rejected_in_wallet_id(bad: str) -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id=f"w{bad}1", action="SEND")


@pytest.mark.parametrize("bad", ["\n", "\r", "\t", "\x00", "\x1f", "\x7f"])
def test_control_characters_are_rejected_in_action(bad: str) -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1", action=f"SE{bad}ND")


@pytest.mark.parametrize("bad", ["\n", "\r", "\t", "\x00", "\x1f", "\x7f"])
def test_control_characters_are_rejected_in_field_keys(bad: str) -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1", action="SEND", fields={f"am{bad}ount": "10"})


@pytest.mark.parametrize("bad", ["\n", "\r", "\t", "\x00", "\x1f", "\x7f"])
def test_control_characters_are_rejected_in_field_values(bad: str) -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1", action="SEND", fields={"amount": f"1{bad}0"})


def test_equal_sign_in_field_key_is_rejected() -> None:
    with pytest.raises(ContextHashError):
        compute_context_hash(wallet_id="w1", action="SEND", fields={"amount=minor": "10"})


def test_equal_sign_in_field_value_remains_allowed() -> None:
    assert len(compute_context_hash(wallet_id="w1", action="SEND", fields={"memo": "a=b"})) == 64


@pytest.mark.parametrize(
    ("kwargs", "field_name"),
    [
        ({"wallet_id": 123, "action": "SEND", "fields": None}, "wallet_id"),
        ({"wallet_id": "w1", "action": 123, "fields": None}, "action"),
        ({"wallet_id": "w1", "action": "SEND", "fields": {"amount": 10}}, "field value"),
    ],
)
def test_non_string_context_hash_inputs_fail_closed(kwargs: dict[str, object], field_name: str) -> None:
    with pytest.raises(ContextHashError, match=field_name):
        compute_context_hash(**kwargs)  # type: ignore[arg-type]
