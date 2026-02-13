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
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="QWG_DEVICE_COMPROMISED", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="GW_POLICY_BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )


def _registry() -> ExternalReasonRegistryV1:
    # Phase M hard-lock: registry is mandatory and deny-by-default.
    # These tests only use qwg + guardian_wallet layers.
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(
                layer="qwg",
                allowed_external_reason_ids=("QWG_DEVICE_COMPROMISED", "OK"),
            ),
            ExternalReasonLayerAllowlist(
                layer="guardian_wallet",
                allowed_external_reason_ids=("GW_POLICY_BLOCK", "OK"),
            ),
        ),
    )
    reg.validate()
    return reg


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


def _expect_invalid(fn) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AdapterError) as e:
        fn()
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_accepts_valid_bundle() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    out = parse_shield_bundle_v3(
        payload=_bundle(signals=signals),
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        reason_registry=_registry(),
    )
    assert out.bundle_id == "b1"
    assert out.context_hash == "a" * 64


def test_shield_v3_rejects_malformed_payload_type() -> None:
    def _run() -> None:
        parse_shield_bundle_v3(  # type: ignore[arg-type]
            payload=["not", "a", "mapping"],
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_wrong_type_fields_in_bundle() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    b = _bundle(signals=signals)
    b["issued_at"] = "100"  # wrong type

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,  # type: ignore[arg-type]
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_missing_required_fields() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    b = _bundle(signals=signals)
    del b["bundle_id"]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,  # type: ignore[arg-type]
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_unknown_keys_in_bundle() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    b = _bundle(signals=signals)
    b["wat"] = 1

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_unknown_keys_in_signal() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    signals[0]["wat"] = 2

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_unsorted_signals() -> None:
    signals = [
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_missing_required_layer_signal() -> None:
    signals = [
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_disallowed_external_reason_id_with_stable_reason() -> None:
    # This is NOT a structural adapter error; it is "unknown/disallowed external reason".
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="NOT_ALLOWED"),
    ]
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_shield_v3_is_deterministic_on_same_input() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    out1 = parse_shield_bundle_v3(
        payload=_bundle(signals=signals),
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        reason_registry=_registry(),
    )
    out2 = parse_shield_bundle_v3(
        payload=_bundle(signals=signals),
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        reason_registry=_registry(),
    )
    assert out1 == out2


def _bundle_v13(*, signals: list[dict], required_layers: list[str] | None = None) -> dict:
    req = required_layers or ["qwg", "guardian_wallet"]
    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": req,
        "signals": signals,
    }


def _sig_v13(*, layer: str, signal_id: str, ext_reason: str) -> dict:
    d = _sig(layer=layer, signal_id=signal_id, ext_reason=ext_reason)
    d["layer_version"] = "1.0.0"
    return d


def test_shield_v3_requires_versions_when_flag_set() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
            require_versions=True,
        )

    _expect_invalid(_run)


def test_shield_v3_accepts_versions_when_flag_set() -> None:
    signals = [
        _sig_v13(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig_v13(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    out = parse_shield_bundle_v3(
        payload=_bundle_v13(signals=signals),
        now=123,
        expected_context_hash="a" * 64,
        reason_map=_reason_map(),
        reason_registry=_registry(),
        require_versions=True,
    )
    assert out.bundle_id == "b1"
    assert out.context_hash == "a" * 64


def test_shield_v3_rejects_bad_semver_versions_when_flag_set() -> None:
    signals = [
        _sig_v13(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig_v13(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    b = _bundle_v13(signals=signals)
    b["shield_bundle_version"] = "1"

    def _run1() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
            require_versions=True,
        )

    _expect_invalid(_run1)

    b2 = _bundle_v13(signals=signals)
    b2["signals"][0]["layer_version"] = "v1"

    def _run2() -> None:
        parse_shield_bundle_v3(
            payload=b2,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
            require_versions=True,
        )

    _expect_invalid(_run2)


def test_shield_v3_requires_sorted_required_layers_when_flag_set() -> None:
    signals = [
        _sig_v13(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig_v13(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    # intentionally wrong vs canonical order (qwg -> guardian_wallet)
    b = _bundle_v13(signals=signals, required_layers=["guardian_wallet", "qwg"])

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
            require_versions=True,
        )

    _expect_invalid(_run)


# ---- v1.3.0 Toxic Input: Size Caps ----

def test_shield_v3_rejects_oversized_signal_list() -> None:
    # Adapter caps signals deterministically (must deny adapter invalid).
    base = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    # Create 33 signals, keep them sorted by (layer, signal_id) to ensure failure is from size cap, not ordering.
    many: list[dict] = []
    for i in range(17):
        many.append(_sig(layer="guardian_wallet", signal_id=f"gw-{i:02d}", ext_reason="GW_POLICY_BLOCK"))
    for i in range(16):
        many.append(_sig(layer="qwg", signal_id=f"qwg-{i:02d}", ext_reason="QWG_DEVICE_COMPROMISED"))
    # Now add one more in guardian_wallet to reach 33 total.
    many.append(_sig(layer="guardian_wallet", signal_id="gw-99", ext_reason="GW_POLICY_BLOCK"))
    many = sorted(many, key=lambda d: (d["layer"], d["signal_id"]))

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=many, required_layers=["qwg", "guardian_wallet"]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_oversized_required_layers_list() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    # Keep signals valid; overflow should be from required_layers cap.
    req = ["qwg", "guardian_wallet"] + ["qwg"] * 7  # length 9

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=signals, required_layers=req),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_oversized_fact_entries() -> None:
    s = _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK")
    # 33 entries triggers cap
    s["facts"] = {f"k{i}": "v" for i in range(33)}
    signals = [
        s,
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=sorted(signals, key=lambda d: (d["layer"], d["signal_id"]))),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_long_fact_value() -> None:
    s = _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK")
    s["facts"]["k"] = "a" * 300  # > 256
    signals = [
        s,
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=sorted(signals, key=lambda d: (d["layer"], d["signal_id"]))),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_long_fact_list() -> None:
    s = _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK")
    s["facts"]["arr"] = ["a"] * 40  # > 32
    signals = [
        s,
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=sorted(signals, key=lambda d: (d["layer"], d["signal_id"]))),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_oversized_meta_entries_on_signal() -> None:
    s = _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK")
    s["meta"] = {f"m{i}": "v" for i in range(33)}
    signals = [
        s,
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=_bundle(signals=sorted(signals, key=lambda d: (d["layer"], d["signal_id"]))),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)


def test_shield_v3_rejects_oversized_meta_entries_on_bundle() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    b = _bundle(signals=signals)
    b["meta"] = {f"m{i}": "v" for i in range(33)}

    def _run() -> None:
        parse_shield_bundle_v3(
            payload=b,  # type: ignore[arg-type]
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )

    _expect_invalid(_run)
