from __future__ import annotations

import pytest

from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def _reason_map() -> ExternalReasonMap:
    rm = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )
    rm.validate()
    return rm


def _registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),
            ExternalReasonLayerAllowlist(layer="guardian_wallet", allowed_external_reason_ids=("OK",)),
        ),
    )
    reg.validate()
    return reg


def _bundle(*, signals: list[dict]) -> dict:
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": ["qwg", "guardian_wallet"],
        "signals": signals,
    }


def _sig(*, layer: str) -> dict:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "signal_id": f"{layer}-1",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "verdict": "deny",
        "reason_id": "OK",
        "confidence": 90,
        "facts": {"k": "v"},
    }


def _expect_invalid(fn) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AdapterError) as e:
        fn()
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_facts_key_too_long_branch() -> None:
    s = _sig(layer="qwg")
    s["facts"] = {"x" * 300: "v"}  # key too long -> hits "signal.facts key too long"
    b = _bundle(signals=[s, _sig(layer="guardian_wallet")])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_facts_list_string_value_too_long_branch() -> None:
    s = _sig(layer="qwg")
    s["facts"] = {"arr": ["x" * 300]}  # list item too long -> hits list string too long branch
    b = _bundle(signals=[s, _sig(layer="guardian_wallet")])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_signal_expires_before_issued_branch() -> None:
    s = _sig(layer="qwg")
    s["issued_at"] = 150
    s["expires_at"] = 140  # expires_at < issued_at -> hits that branch
    b = _bundle(signals=[s, _sig(layer="guardian_wallet")])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_meta_empty_key_branch() -> None:
    s = _sig(layer="qwg")
    s["meta"] = {"": "v"}  # empty key -> hits meta key must be non-empty
    b = _bundle(signals=[s, _sig(layer="guardian_wallet")])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_meta_value_too_long_branch() -> None:
    s = _sig(layer="qwg")
    s["meta"] = {"k": "x" * 300}  # value too long -> hits meta value too long branch
    b = _bundle(signals=[s, _sig(layer="guardian_wallet")])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)
