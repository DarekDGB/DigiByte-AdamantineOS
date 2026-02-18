from __future__ import annotations

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.policy.risk_policy import RiskPolicy


def _ok_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )


def _minimal_risk_payload(*, ctx: str = "a" * 64, reason_id: str = "ok") -> dict:
    return {
        "ac_iface_version": "adaptive_core_oracle_v3",
        "context_hash": ctx,
        "issued_at": 100,
        "expires_at": 200,
        "generated_at": 100,
        "overall_score": 90,
        "signals": [{"source": "ac", "severity": 50, "reason_ids": [reason_id]}],
    }


def test_parse_risk_report_rejects_reason_map_wrong_type() -> None:
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_minimal_risk_payload(),
            now=1000,
            expected_context_hash="a" * 64,
            reason_map=object(),  # type: ignore[arg-type]
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_risk_report_rejects_invalid_reason_registry_object() -> None:
    # reason_registry.validate() throws => adapter fails closed
    class BadRegistry:
        def validate(self) -> None:
            raise ValueError("nope")

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_minimal_risk_payload(),
            now=1000,
            expected_context_hash="a" * 64,
            reason_map=_ok_map(),
            reason_registry=BadRegistry(),  # type: ignore[arg-type]
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_risk_report_rejects_missing_context_hash() -> None:
    p = _minimal_risk_payload()
    p["context_hash"] = ""
    with pytest.raises(AdapterError) as e:
        parse_risk_report(payload=p, now=1000, expected_context_hash="a" * 64, reason_map=_ok_map())
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_risk_report_hits_unmapped_external_reason_id_branch() -> None:
    # allowlist from default policy includes ("ok",)
    # but explicit reason_map does NOT map "ok" => unmapped branch
    bad_map = ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="something_else", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_minimal_risk_payload(reason_id="ok"),
            now=1000,
            expected_context_hash="a" * 64,
            reason_map=bad_map,
            policy=RiskPolicy(),  # allowlist includes "ok"
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON


def test_parse_qid_replay_proof_fresh_must_be_bool() -> None:
    rp = {
        "proof_version": "v1",
        "wallet_id": "w1",
        "subject": "s",
        "proof_hash": "h",
        "session_nonce": "n",
        "registry_commitment": "c",
        "fresh": "yes",  # invalid
        "device_binding": None,
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            payload={"replay_proof": rp},
            expected_wallet_id="w1",
            expected_subject="s",
            expected_proof_hash="h",
            expected_device_binding=None,
        )
    assert e.value.reason_id == ReasonId.QID_REPLAY_PROOF_INVALID


def test_parse_qid_replay_proof_hits_contract_validation_except_path() -> None:
    # device_binding="" triggers proof.validate() ValueError => caught => AdapterError
    rp = {
        "proof_version": "v1",
        "wallet_id": "w1",
        "subject": "s",
        "proof_hash": "h",
        "session_nonce": "n",
        "registry_commitment": "c",
        "fresh": True,
        "device_binding": "",  # invalid by contract
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            payload={"replay_proof": rp},
            expected_wallet_id="w1",
            expected_subject="s",
            expected_proof_hash="h",
            expected_device_binding="",
        )
    assert e.value.reason_id == ReasonId.QID_REPLAY_PROOF_INVALID


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
        "facts": {"k": "v"},
        "meta": {"m": "x"},
    }


def test_shield_v3_rejects_wrong_signal_v() -> None:
    b = _bundle(signals=[{**_sig(layer="qwg", signal_id="qwg-1", ext_reason="ok"), "v": "nope"}])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, expected_context_hash="a" * 64, policy=RiskPolicy())
    assert e.value.reason_id == ReasonId.DENY_VERSION_MISMATCH


def test_shield_v3_rejects_unknown_layer() -> None:
    b = _bundle(signals=[_sig(layer="unknown_layer", signal_id="x-1", ext_reason="ok")])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, expected_context_hash="a" * 64, policy=RiskPolicy())
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_context_hash_mismatch() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="ok")
    s["context_hash"] = "b" * 64
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, expected_context_hash="a" * 64, policy=RiskPolicy())
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_meta_not_object_when_present() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="ok")
    s["meta"] = "nope"
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, expected_context_hash="a" * 64, policy=RiskPolicy())
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_facts_key_too_long() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="ok")
    s["facts"] = {"x" * 200: "v"}  # triggers key-too-long branch
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(payload=b, expected_context_hash="a" * 64, policy=RiskPolicy())
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID
