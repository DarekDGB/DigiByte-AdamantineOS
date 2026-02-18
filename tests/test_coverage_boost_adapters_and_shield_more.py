from __future__ import annotations

import pytest

from adamantine.v1.contracts import qid as qid_contracts
from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.policy.risk_policy import RiskPolicy


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(external_id="QWG_DEVICE_COMPROMISED", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="GW_POLICY_BLOCK", internal_reason_id=ReasonId.DENY_POLICY.value),
            ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),
        )
    )


def _registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("QWG_DEVICE_COMPROMISED", "OK")),
            ExternalReasonLayerAllowlist(layer="guardian_wallet", allowed_external_reason_ids=("GW_POLICY_BLOCK", "OK")),
        ),
    )
    reg.validate()
    return reg


def _minimal_risk_payload(*, ctx: str = "a" * 64, reason_id: str = "OK") -> dict:
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
            now=150,
            expected_context_hash="a" * 64,
            reason_map=object(),  # type: ignore[arg-type]
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_risk_report_rejects_invalid_reason_registry_object() -> None:
    class BadRegistry:
        def validate(self) -> None:
            raise ValueError("nope")

    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_minimal_risk_payload(),
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=BadRegistry(),  # type: ignore[arg-type]
        )
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_risk_report_rejects_missing_context_hash() -> None:
    p = _minimal_risk_payload()
    p["context_hash"] = ""
    with pytest.raises(AdapterError) as e:
        parse_risk_report(payload=p, now=150, expected_context_hash="a" * 64, reason_map=_reason_map())
    assert e.value.reason_id == ReasonId.EQC_INVALID_RISK_REPORT


def test_parse_qid_replay_proof_fresh_must_be_bool() -> None:
    rp = {
        "proof_version": "v1",
        "wallet_id": "w1",
        "subject": "s",
        "proof_hash": "h",
        "session_nonce": "n",
        "registry_commitment": "c",
        "fresh": "yes",  # invalid (must be bool)
        "device_binding": None,
    }
    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            evidence_qid={"replay_proof": rp},
            expected_wallet_id="w1",
            expected_subject="s",
            expected_proof_hash="h",
            expected_device_binding=None,
            expected_session_nonce="n",
        )
    assert e.value.reason_id == ReasonId.QID_REPLAY_PROOF_INVALID


def test_parse_qid_replay_proof_hits_contract_validation_except_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # The adapter and contract share the same validations, so to cover the
    # "except ValueError" branch we force validate() to raise.
    def _boom(self) -> None:  # noqa: ANN001
        raise ValueError("boom")

    monkeypatch.setattr(qid_contracts.QIDReplayProof, "validate", _boom)

    rp = {
        "proof_version": "v1",
        "wallet_id": "w1",
        "subject": "s",
        "proof_hash": "h",
        "session_nonce": "n",
        "registry_commitment": "c",
        "fresh": True,
        "device_binding": None,
    }

    with pytest.raises(AdapterError) as e:
        parse_qid_replay_proof(
            evidence_qid={"replay_proof": rp},
            expected_wallet_id="w1",
            expected_subject="s",
            expected_proof_hash="h",
            expected_device_binding=None,
            expected_session_nonce="n",
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
        "layer_version": "1.2.3",
    }


def test_shield_v3_rejects_wrong_signal_v() -> None:
    b = _bundle(signals=[{**_sig(layer="qwg", signal_id="qwg-1", ext_reason="OK"), "v": "nope"}])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_VERSION_MISMATCH


def test_shield_v3_rejects_unknown_layer() -> None:
    b = _bundle(signals=[_sig(layer="unknown_layer", signal_id="x-1", ext_reason="OK")])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_context_hash_mismatch() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="OK")
    s["context_hash"] = "b" * 64
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_meta_not_object_when_present() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="OK")
    s["meta"] = "nope"
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_rejects_facts_key_too_long() -> None:
    s = _sig(layer="qwg", signal_id="qwg-1", ext_reason="OK")
    s["facts"] = {"x" * 200: "v"}  # triggers key-too-long branch
    b = _bundle(signals=[s])
    with pytest.raises(AdapterError) as e:
        parse_shield_bundle_v3(
            payload=b,
            now=150,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert e.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_parse_risk_report_hits_allowlist_and_mapping_mismatch_branch() -> None:
    bad_map = ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="SOMETHING_ELSE", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )
    with pytest.raises(AdapterError) as e:
        parse_risk_report(
            payload=_minimal_risk_payload(reason_id="OK"),
            now=150,
            expected_context_hash="a" * 64,
            reason_map=bad_map,
            policy=RiskPolicy(),
        )
    assert e.value.reason_id == ReasonId.UNKNOWN_EXTERNAL_REASON
