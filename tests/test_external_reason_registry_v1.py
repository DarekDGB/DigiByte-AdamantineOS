from __future__ import annotations

from typing import Any

import pytest

from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.policy.risk_policy import RiskPolicy


def _reason_map() -> ExternalReasonMap:
    # Small deterministic table for tests.
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="AC_OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )


def _oracle_payload(*, ctx: str, now: int, reason_id: str) -> dict[str, Any]:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": ctx,
        "issued_at": now - 5,
        "expires_at": now + 5,
        "generated_at": now - 1,
        "overall_score": 99,
        "signals": [{"source": "ac_model", "severity": 10, "reason_ids": [reason_id]}],
        "oracle_version": "adaptive-core/3.0.0",
        "external_source_id": "ac-prod-1",
    }


def _shield_bundle(*, ctx: str, required_layers: list[str], ext_reason_by_layer: dict[str, str]) -> dict[str, Any]:
    def sig(layer: str) -> dict[str, Any]:
        return {
            "v": "shield_signal_v3",
            "layer": layer,
            "signal_id": f"{layer}-1",
            "context_hash": ctx,
            "issued_at": 1706990400,
            "expires_at": 1706990460,
            "verdict": "allow",
            "reason_id": ext_reason_by_layer.get(layer, "OK"),
            "confidence": 90,
            "facts": {"k": "v"},
            "meta": {},
        }

    # Must be sorted by (layer, signal_id)
    layers_sorted = sorted(required_layers)
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": ctx,
        "issued_at": 1706990400,
        "expires_at": 1706990460,
        "required_layers": required_layers,
        "signals": [sig(l) for l in layers_sorted],
        "meta": {},
    }


def test_registry_validate_rejects_unknown_layer() -> None:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("AC_OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="not_a_layer", allowed_external_reason_ids=("OK",)),
        ),
    )

    with pytest.raises(ValueError):
        reg.validate()


def test_shield_adapter_denies_reason_not_allowed_for_layer() -> None:
    now = 1706990400
    ctx = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})

    # Allow only OK for sentinel_ai; deny-by-default for other layers (missing entries).
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("AC_OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="sentinel_ai", allowed_external_reason_ids=("OK",)),
        ),
    )

    bundle = _shield_bundle(
        ctx=ctx,
        required_layers=["sentinel_ai", "adn"],
        ext_reason_by_layer={"adn": "OK"},
    )

    # adn layer has no allowlist entry => deny-by-default
    with pytest.raises(AdapterError) as ei:
        parse_shield_bundle_v3(
            payload=bundle,
            now=now,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=reg,
        )

    assert ei.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_oracle_adapter_denies_reason_not_allowed_by_registry() -> None:
    now = 1706990400
    ctx = compute_context_hash(wallet_id="w1", action="send", fields={"asset": "DGB", "amount": "1"})

    # Deny-by-default registry that does NOT allow AC_OK for oracle.
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(),
    )

    pack = PolicyPack(
        min_overall_score=85,
        allowed_external_reason_ids=("AC_OK",),
        external_reason_map=_reason_map(),
    )
    pol = RiskPolicy(min_overall_score=85, policy_pack=pack)

    # Provide explicit reason_map so parse_risk_report can map.
    payload = _oracle_payload(ctx=ctx, now=now, reason_id="AC_OK")

    with pytest.raises(AdapterError) as ei:
        parse_adaptive_core_oracle_v3(
            payload=payload,
            now=now,
            expected_context_hash=ctx,
            reason_map=_reason_map(),
            reason_registry=reg,
            policy=pol,
        )

    assert ei.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
