from __future__ import annotations

import hashlib
import json

import pytest

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry, ShieldSignal, ShieldSource
from adamantine.v1.contracts.shield_v3 import ShieldBundleV3
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.execution.response_v2 import build_execution_response_v2
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3
from adamantine.v1.policy.risk_policy import RiskPolicy
from adamantine.v2.runtime_host.host import run_mobile_execution_call_v2


CTX = "a" * 64


def _risk_signal() -> RiskSignal:
    return RiskSignal(source="adaptive-core", severity=10, reason_ids=("ok",))


def _risk_report(**overrides: object) -> RiskReport:
    values = {
        "context_hash": CTX,
        "signals": (_risk_signal(),),
        "overall_score": 90,
        "generated_at": 100,
    }
    values.update(overrides)
    return RiskReport(**values)  # type: ignore[arg-type]


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="OK", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )


def _registry() -> ExternalReasonRegistryV1:
    reg = ExternalReasonRegistryV1(
        oracle_allowed_external_reason_ids=("OK",),
        shield_layer_allowlists=(
            ExternalReasonLayerAllowlist(layer="qwg", allowed_external_reason_ids=("OK",)),
        ),
    )
    reg.validate()
    return reg


def _shield_signal(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "v": "shield_signal_v3",
        "layer": "qwg",
        "signal_id": "sig-1",
        "context_hash": CTX,
        "issued_at": 100,
        "expires_at": 200,
        "verdict": "allow",
        "reason_id": "OK",
        "confidence": 90,
        "facts": {"flag": True, "score": 1},
    }
    values.update(overrides)
    return values


def _shield_bundle(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "v": "shield_bundle_v3",
        "bundle_id": "bundle-1",
        "context_hash": CTX,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": ["qwg"],
        "signals": [_shield_signal()],
    }
    values.update(overrides)
    return values


def _qid_shape_a(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "proof",
        "context_hash": CTX,
    }
    values.update(overrides)
    return values


def _qid_shape_b_response(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "type": "login_response",
        "service_id": "svc",
        "nonce": "nonce",
        "address": "DGB1",
        "pubkey": "pub",
        "require": "full",
        "version": "1",
        "issued_at": 100,
        "expires_at": 200,
        "context_hash": CTX,
    }
    values.update(overrides)
    return values


def _qid_shape_b(response_payload: dict[str, object]) -> dict[str, object]:
    proof_hash = hashlib.sha256(
        json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "v": "2",
        "kind": "qid_login_v2",
        "login_uri": "qid://login?x=1",
        "response_payload": response_payload,
        "signature": "sig",
        "subject": "DGB1",
        "proof_hash": proof_hash,
    }


def test_contract_numeric_fields_reject_bool() -> None:
    with pytest.raises(ValueError):
        QIDSessionProof(subject="s", issued_at=True, expires_at=200, proof_hash="p", context_hash=CTX).validate(now=150)
    with pytest.raises(ValueError):
        QIDSessionProof(subject="s", issued_at=100, expires_at=200, proof_hash="p", context_hash=CTX).validate(now=True)
    with pytest.raises(ValueError):
        RiskSignal(source="adaptive-core", severity=True, reason_ids=("ok",)).validate()
    with pytest.raises(ValueError):
        _risk_report(overall_score=True).validate(now=150)
    with pytest.raises(ValueError):
        _risk_report(generated_at=True).validate(now=150)
    with pytest.raises(ValueError):
        _risk_report().validate(now=True)
    with pytest.raises(ValueError):
        ShieldSignal(source=ShieldSource.ADN, severity=True, reason_ids=(ReasonId.EVIDENCE_OK.value,)).validate()
    with pytest.raises(ValueError):
        AdaptiveCoreOracleV3(context_hash=CTX, issued_at=True, expires_at=200, report=_risk_report()).validate(now=150)
    with pytest.raises(ValueError):
        AdaptiveCoreOracleV3(context_hash=CTX, issued_at=100, expires_at=200, report=_risk_report()).validate(now=True)
    with pytest.raises(ValueError):
        ShieldBundleV3(
            bundle_id="b",
            context_hash=CTX,
            issued_at=True,
            expires_at=200,
            required_layers=("qwg",),
            signals=(ShieldSignal(source=ShieldSource.QWG, severity=0, reason_ids=(ReasonId.EVIDENCE_OK.value,)),),
        ).validate()
    with pytest.raises(ValueError):
        PolicyPack(min_overall_score=True).validate()
    with pytest.raises(ValueError):
        RiskPolicy(min_overall_score=True).validate()


def test_eqc_and_adapters_reject_bool_numeric_inputs() -> None:
    result = evaluate_eqc(wallet_id="w", action="a", session=None, risk=None, now=True)
    assert result.verdict.value == "DENY"
    assert ReasonId.EQC_MISSING_NOW.value in result.reason_ids

    with pytest.raises(AdapterError):
        parse_qid_session(payload=_qid_shape_a(), now=True)
    with pytest.raises(AdapterError):
        parse_qid_session(payload=_qid_shape_a(issued_at=True), now=150)
    with pytest.raises(AdapterError):
        parse_qid_session(payload=_qid_shape_b(_qid_shape_b_response(expires_at=True)), now=150)

    with pytest.raises(AdapterError):
        parse_risk_report(payload={}, now=True, expected_context_hash=CTX, reason_map=_reason_map(), policy=RiskPolicy())
    risk_payload = {
        "ac_iface_version": "adaptive-core-risk-v0",
        "context_hash": CTX,
        "generated_at": 100,
        "overall_score": True,
        "signals": [{"source": "adaptive-core", "severity": 10, "reason_ids": ["ok"]}],
    }
    with pytest.raises(AdapterError):
        parse_risk_report(payload=risk_payload, now=150, expected_context_hash=CTX, reason_map=_reason_map(), policy=RiskPolicy())

    shield_payload = _shield_bundle()
    shield_payload["issued_at"] = True
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=shield_payload,
            now=150,
            expected_context_hash=CTX,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    shield_payload = _shield_bundle(signals=[_shield_signal(confidence=True)])
    with pytest.raises(AdapterError):
        parse_shield_bundle_v3(
            payload=shield_payload,
            now=150,
            expected_context_hash=CTX,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )


def test_runtime_and_response_paths_treat_bool_as_non_int() -> None:
    with pytest.raises(TypeError):
        run_mobile_execution_call_v2(payload={}, now=True, executor=object(), nonce_store=object())  # type: ignore[arg-type]

    response = build_execution_response_v2(
        request_id="r",
        intent="send",
        action="SEND",
        context_hash=CTX,
        status="deny",
        reason_id=ReasonId.DENY_SCHEMA_INVALID,
        protection_mode="full",
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=False,
        issued_at=True,
        expires_at=False,
        max_skew_seconds=0,
        timebox_valid=False,
        nonce_store="mem",
        nonce_value="n",
        nonce_consumed=False,
        qid_present=False,
        qid_valid=False,
        shield_present=False,
        shield_valid=False,
        oracle_present=False,
        oracle_valid=False,
        policy_mode="strict",
        override_allowed=False,
        policy_reason_id=ReasonId.DENY_SCHEMA_INVALID,
    )
    assert response["decision"]["timebox"]["issued_at"] == "1970-01-01T00:00:00Z"
    assert response["decision"]["timebox"]["expires_at"] == "1970-01-01T00:00:00Z"
