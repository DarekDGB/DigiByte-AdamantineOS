from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="QWG_DEVICE_COMPROMISED", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="GW_POLICY_BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )


def _bundle(*, signals: list[dict], required_layers: list[str] | None = None) -> dict:
    req = required_layers or ["qwg", "guardian_wallet"]
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": req,
        "signals": signals,
    }


def _sig(*, layer: str, signal_id: str, ext_reason: str) -> dict:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "signal_id": signal_id,
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "verdict": "deny",
        "reason_id": ext_reason,
        "confidence": 90,
        "facts": {"k": "v", "risk": 97, "flag": True, "arr": ["a", "b", "c"]},
    }


def test_shield_v3_accepts_valid_bundle() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    # Must be sorted by (layer, signal_id): guardian_wallet < qwg
    out = parse_shield_bundle_v3(
        payload=_bundle(signals=signals),
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
    )
    assert out.bundle_id == "b1"
    assert len(out.signals) == 2


def test_shield_v3_rejects_unknown_layer() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="nope", signal_id="x-1", ext_reason="OK"),
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_unknown_external_reason() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="UNKNOWN_CODE"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_shield_v3_rejects_missing_required_layer() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals, required_layers=["qwg", "guardian_wallet"]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_unsorted_signals() -> None:
    # Unsorted: qwg should come after guardian_wallet, but we put it first
    signals = [
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_duplicate_layer() -> None:
    signals = [
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
        _sig(layer="qwg", signal_id="qwg-2", ext_reason="OK"),
    ]
    # sorted by (layer, signal_id) already; still invalid due to duplication
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals, required_layers=["qwg"]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_nested_facts_object() -> None:
    bad = _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED")
    bad["facts"] = {"nested": {"nope": True}}  # nested object forbidden
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        bad,
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_determinism_replay() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    payload = _bundle(signals=signals)
    out1 = parse_shield_bundle_v3(
        payload=payload,
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
    )
    out2 = parse_shield_bundle_v3(
        payload=payload,
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
    )
    assert out1 == out2
