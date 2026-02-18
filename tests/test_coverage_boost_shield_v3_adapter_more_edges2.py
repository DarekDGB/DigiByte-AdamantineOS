from __future__ import annotations

import pytest

from adamantine.v1.contracts.external_reason_registry import ExternalReasonLayerAllowlist, ExternalReasonRegistryV1
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),))


def _registry() -> ExternalReasonRegistryV1:
    return ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("ok",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("ok",)),
            ExternalReasonLayerAllowlist(layer="guardian_wallet", allowed_external_reason_ids=("ok",)),
        ),
    )


def _valid_signal(layer: str, signal_id: str) -> dict:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "layer_version": "1.0.0",
        "signal_id": signal_id,
        "context_hash": "a" * 64,
        "issued_at": 10,
        "expires_at": 20,
        "verdict": "allow",
        "confidence": 50,
        "reason_id": "ok",
        "facts": {"k": "v"},
    }


def _valid_bundle(*, required_layers: list[str], signals: list[dict]) -> dict:
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": 10,
        "expires_at": 20,
        "required_layers": required_layers,
        "signals": signals,
    }


def test_adapter_rejects_non_int_now() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload={},
            now="nope",  # type: ignore[arg-type]
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_adapter_rejects_blank_expected_context_hash() -> None:
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload={},
            now=0,
            expected_context_hash=" ",
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )


def test_adapter_rejects_bad_reason_map_and_registry() -> None:
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload={},
            now=0,
            expected_context_hash="a" * 64,
            reason_map="nope",  # type: ignore[arg-type]
            reason_registry=_registry(),
        )

    bad_registry = ExternalReasonRegistryV1(oracle_allowed_external_reason_ids=(), shield_layer_allowlists=())
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload={},
            now=0,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=bad_registry,
        )
    assert "reason_registry invalid" in str(e.value)


def test_adapter_required_layers_and_signals_shape_edges() -> None:
    rm = _reason_map()
    reg = _registry()

    b = _valid_bundle(required_layers=["qwg"], signals=[_valid_signal("qwg", "qwg-1")])
    b["required_layers"] = "nope"
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(payload=b, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)

    b2 = _valid_bundle(required_layers=["qwg"], signals=[_valid_signal("qwg", "qwg-1")])
    b2["required_layers"] = ["x" * 200]
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(payload=b2, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)

    b3 = _valid_bundle(required_layers=["qwg"], signals=[_valid_signal("qwg", "qwg-1")])
    b3["signals"] = "nope"
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(payload=b3, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)


def test_adapter_signals_sort_check_rejects_unsorted() -> None:
    rm = _reason_map()
    reg = _registry()

    # Two valid mapping signals but unsorted by (layer, signal_id)
    s1 = _valid_signal("qwg", "b")
    s2 = _valid_signal("qwg", "a")
    b = _valid_bundle(required_layers=["qwg"], signals=[s1, s2])

    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)
    assert "signals must be sorted" in e.value.message


def test_adapter_key_non_mapping_branch_still_fail_closed() -> None:
    rm = _reason_map()
    reg = _registry()

    # Include a non-mapping entry; _key() must handle it (returns ('',''))
    # and parsing must still fail closed.
    s1 = _valid_signal("qwg", "a")
    b = _valid_bundle(required_layers=["qwg"], signals=["nope", s1])  # type: ignore[list-item]

    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)
    assert "signal must be object" in e.value.message


def test_adapter_rejects_duplicate_layer_signal() -> None:
    rm = _reason_map()
    reg = _registry()

    s1 = _valid_signal("qwg", "qwg-1")
    s2 = _valid_signal("qwg", "qwg-2")
    b = _valid_bundle(required_layers=["qwg"], signals=[s1, s2])

    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)
    assert "duplicate layer" in e.value.message


def test_adapter_missing_required_layer_signal() -> None:
    rm = _reason_map()
    reg = _registry()

    s1 = _valid_signal("qwg", "qwg-1")
    b = _valid_bundle(required_layers=["qwg", "guardian_wallet"], signals=[s1])

    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, now=0, expected_context_hash="a" * 64, reason_map=rm, reason_registry=reg)
    assert "missing required layer" in e.value.message
