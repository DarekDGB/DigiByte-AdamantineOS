from __future__ import annotations

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.adaptive_core_oracle_v3_adapter import parse_adaptive_core_oracle_v3
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def _risk_map_ok_only() -> ExternalReasonMap:
    # parse_risk_report default allowlist is ("ok",) when no PolicyPack.
    return ExternalReasonMap(entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),))


def _risk_payload(reason_id: str) -> dict:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "generated_at": 120,
        "overall_score": 90,
        "signals": [{"source": "ac", "severity": 50, "reason_ids": [reason_id]}],
    }


def test_adaptive_core_adapter_hits_unmapped_external_reason_id_line_122() -> None:
    # rid "ok" is allowlisted by default; but reason_map doesn't map it => line 122
    bad_map = ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="something_else", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )
    with pytest.raises(AdapterError) as e:
        parse_risk_report(payload=_risk_payload("ok"), now=150, expected_context_hash="a" * 64, reason_map=bad_map)
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_adaptive_core_oracle_v3_adapter_hits_contract_validation_except(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cover the "except ValueError" branch in parse_adaptive_core_oracle_v3 by forcing validate() to fail.
    def _boom(self, *, now: int) -> None:  # noqa: ANN001
        raise ValueError("boom")

    monkeypatch.setattr(AdaptiveCoreOracleV3, "validate", _boom)

    payload = _risk_payload("ok")
    out_map = _risk_map_ok_only()
    out_reg = None

    with pytest.raises(AdapterError) as e:
        parse_adaptive_core_oracle_v3(
            payload=payload,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=out_map,
            reason_registry=out_reg,
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


# -------------------------
# Shield v3 adapter helpers
# -------------------------

def _shield_reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
            ExternalReasonMapEntry(external_id="QWG_DEVICE_COMPROMISED", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="GW_POLICY_BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
        )
    )


def _shield_registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK", "QWG_DEVICE_COMPROMISED")),
            ExternalReasonLayerAllowlist(layer="guardian_wallet", allowed_external_reason_ids=("OK", "GW_POLICY_BLOCK")),
        ),
    )
    reg.validate()
    return reg


def _sig(layer: str, signal_id: str, *, issued_at: int = 100, expires_at: int = 200) -> dict:
    return {
        "v": "shield_signal_v3",
        "layer": layer,
        "layer_version": "1.2.3",  # for require_versions=True
        "signal_id": signal_id,
        "context_hash": "a" * 64,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "verdict": "allow",
        "reason_id": "OK",
        "confidence": 50,
        "facts": {"k": "v"},
        "meta": {"m": "x"},
    }


def _bundle(required_layers: list[str], signals: list[dict], *, issued_at: int = 100, expires_at: int = 200) -> dict:
    return {
        "v": "shield_bundle_v3",
        "shield_bundle_version": "1.0.0",  # for require_versions=True
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "required_layers": required_layers,
        "signals": signals,
        "meta": {"k": "v"},
    }


def test_shield_required_layers_duplicate_fails_in_strict_mode() -> None:
    b = _bundle(
        required_layers=["qwg", "qwg"],  # duplicates
        signals=[_sig("qwg", "qwg-1"), _sig("guardian_wallet", "gw-1")],
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_required_layers_wrong_canonical_order_fails_in_strict_mode() -> None:
    # canonical should not be ["guardian_wallet", "qwg"] (this hits the ordering branch)
    b = _bundle(
        required_layers=["guardian_wallet", "qwg"],
        signals=[_sig("guardian_wallet", "gw-1"), _sig("qwg", "qwg-1")],  # sorted by layer then signal_id
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_bundle_signals_must_be_sorted_by_layer_and_signal_id() -> None:
    # signals out of sort order triggers the explicit "must be sorted" branch
    b = _bundle(
        required_layers=["qwg", "guardian_wallet"],
        signals=[_sig("qwg", "qwg-2"), _sig("qwg", "qwg-1"), _sig("guardian_wallet", "gw-1")],
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_missing_required_layer_signal_fails() -> None:
    # required guardian_wallet but not provided => "missing required layer signal"
    b = _bundle(
        required_layers=["qwg", "guardian_wallet"],
        signals=[_sig("qwg", "qwg-1")],
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_duplicate_layer_signal_fails() -> None:
    # two qwg signals => duplicate layer branch
    b = _bundle(
        required_layers=["qwg", "guardian_wallet"],
        signals=[_sig("qwg", "qwg-1"), _sig("qwg", "qwg-2"), _sig("guardian_wallet", "gw-1")],
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_signal_expires_before_issued_fails() -> None:
    # hits signal.expires_at >= issued_at branch
    bad = _sig("qwg", "qwg-1", issued_at=200, expires_at=100)
    b = _bundle(
        required_layers=["qwg", "guardian_wallet"],
        signals=[bad, _sig("guardian_wallet", "gw-1")],
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_bundle_expires_before_issued_fails() -> None:
    # hits bundle.expires_at >= issued_at branch
    b = _bundle(
        required_layers=["qwg", "guardian_wallet"],
        signals=[_sig("qwg", "qwg-1"), _sig("guardian_wallet", "gw-1")],
        issued_at=200,
        expires_at=100,
    )
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_shield_reason_map(),
            reason_registry=_shield_registry(),
            require_versions=True,
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID
