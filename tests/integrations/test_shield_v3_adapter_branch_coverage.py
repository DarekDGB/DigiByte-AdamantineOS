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
from adamantine.v1.obs.metrics import InMemoryMetrics


def _reason_map() -> ExternalReasonMap:
    m = ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="GW_POLICY_BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )
    m.validate()
    return m


def _registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="guardian_wallet", allowed_external_reason_ids=("OK", "GW_POLICY_BLOCK")),
        ),
    )
    reg.validate()
    return reg


def _sig(
    *,
    layer: str = "guardian_wallet",
    signal_id: str = "gw-1",
    context_hash: str = "a" * 64,
    issued_at: int = 100,
    expires_at: int = 200,
    reason_id: str = "GW_POLICY_BLOCK",
    facts: object = None,
) -> dict:
    if facts is None:
        facts = {"k": "v", "risk": 1, "flag": True, "arr": ["a", "b"]}
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "signal_id": signal_id,
        "context_hash": context_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "verdict": "deny",
        "reason_id": reason_id,
        "confidence": 90,
        "facts": facts,
        "meta": {},
    }


def _bundle(*, signals: list[dict], required_layers: list[str] | None = None, ctx: str = "a" * 64) -> dict:
    req = required_layers or ["guardian_wallet"]
    # must be sorted by (layer, signal_id) to reach deeper branches
    signals_sorted = sorted(signals, key=lambda s: (str(s.get("layer", "")), str(s.get("signal_id", ""))))
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": ctx,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": req,
        "signals": signals_sorted,
        "meta": {},
    }


def test_metrics_inc_path_is_hit_on_fail() -> None:
    metrics = InMemoryMetrics()

    # Force a fail via unknown top-level bundle field to hit _deny_unknown_keys -> _fail(metrics...)
    payload = _bundle(signals=[_sig()])
    payload["unknown_field"] = True

    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=payload,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
            metrics=metrics,
        )

    snap = metrics.snapshot()
    # Ensure the counter increment path executed (exact key may vary by failure)
    assert sum(snap.values()) >= 1


def test_rejects_context_hash_wrong_length() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(context_hash="a" * 63)]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_context_hash_invalid_hex_char() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(context_hash="g" * 64)]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_signal_unknown_field() -> None:
    s = _sig()
    s["extra"] = "nope"

    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[s]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_empty_required_str_field() -> None:
    # signal_id must be non-empty str
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(signal_id="")]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_non_int_field() -> None:
    # issued_at must be int
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(issued_at="100")]),  # type: ignore[arg-type]
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_facts_not_object() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(facts="nope")]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_facts_empty_key() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(facts={"": "v"})]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_rejects_facts_list_with_bad_item_type() -> None:
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=_bundle(signals=[_sig(facts={"arr": [{"x": 1}]})]),
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID
