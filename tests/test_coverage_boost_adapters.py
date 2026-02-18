from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from adamantine.v1.contracts.external_reason_registry import (
    ExternalReasonLayerAllowlist,
    ExternalReasonRegistryV1,
)
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof
from adamantine.v1.integrations.shield_v3_adapter import parse_shield_bundle_v3


def _load_request_allow() -> dict:
    p = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "adamantine"
        / "v1"
        / "fixtures"
        / "v2_0_0_runtime"
        / "request_allow.json"
    )
    return json.loads(p.read_text(encoding="utf-8"))


def _base_qid() -> dict:
    return deepcopy(_load_request_allow()["payload"]["evidence"]["qid"])


def _reason_map() -> ExternalReasonMap:
    return ExternalReasonMap(
        entries=(
            ExternalReasonMapEntry(
                external_id="QWG_DEVICE_COMPROMISED",
                internal_reason_id=ReasonId.DENY_POLICY.value,
            ),
            ExternalReasonMapEntry(
                external_id="GW_POLICY_BLOCK",
                internal_reason_id=ReasonId.DENY_POLICY.value,
            ),
            ExternalReasonMapEntry(
                external_id="OK",
                internal_reason_id=ReasonId.EVIDENCE_OK.value,
            ),
        )
    )


def _registry() -> ExternalReasonRegistryV1:
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


def _bundle(signals: list[dict]) -> dict:
    return {
        "v": "shield_bundle_v3",
        "bundle_id": "b1",
        "context_hash": "a" * 64,
        "issued_at": 100,
        "expires_at": 200,
        "required_layers": ["qwg", "guardian_wallet"],
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
    }


@pytest.mark.parametrize(
    "mutator, expected_reason",
    [
        (lambda e: e.pop("replay_proof"), "QID_REPLAY_PROOF_MISSING"),
        (lambda e: e.__setitem__("replay_proof", "nope"), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("proof_version", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("device_binding", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("proof_hash", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("subject", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("wallet_id", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("session_nonce", ""), "QID_REPLAY_PROOF_INVALID"),
        (lambda e: e["replay_proof"].__setitem__("fresh", False), "QID_NONCE_REPLAY"),
        (lambda e: e["replay_proof"].__setitem__("device_binding", "other-device"), "QID_REPLAY_DEVICE_MISMATCH"),
    ],
)
def test_qid_adapter_negative_paths_cover_reason_branches(mutator, expected_reason: str) -> None:
    evidence = _base_qid()
    base_rp = evidence.get("replay_proof", {}) if isinstance(evidence, dict) else {}
    base_expected_device_binding = base_rp.get("device_binding") if isinstance(base_rp, dict) else None

    mutator(evidence)
    rp = evidence.get("replay_proof") if isinstance(evidence, dict) else None

    with pytest.raises(AdapterError) as ei:
        parse_qid_replay_proof(
            evidence_qid=evidence,
            expected_wallet_id=(rp.get("wallet_id") if isinstance(rp, dict) else "w1"),
            expected_subject=(rp.get("subject") if isinstance(rp, dict) else "sub"),
            expected_proof_hash=(rp.get("proof_hash") if isinstance(rp, dict) else "h"),
            expected_device_binding=base_expected_device_binding,
            expected_session_nonce=(rp.get("session_nonce") if isinstance(rp, dict) else "n"),
            require_fresh=True,
        )
    assert ei.value.reason_id == expected_reason


def test_qid_adapter_rejects_non_mapping_evidence() -> None:
    with pytest.raises(AdapterError) as ei:
        parse_qid_replay_proof(
            evidence_qid="not-a-mapping",
            expected_wallet_id="w",
            expected_subject="s",
            expected_proof_hash="h",
            expected_device_binding=None,
            expected_session_nonce="n",
            require_fresh=True,
        )
    assert ei.value.reason_id == "QID_REPLAY_PROOF_INVALID"


@pytest.mark.parametrize(
    "field, value, expected_reason",
    [
        ("wallet_id", "other-wallet", "QID_REPLAY_WALLET_MISMATCH"),
        ("subject", "other-subject", "QID_REPLAY_SUBJECT_MISMATCH"),
        ("proof_hash", "other-hash", "QID_REPLAY_PROOF_HASH_MISMATCH"),
        ("session_nonce", "other-nonce", "QID_REPLAY_NONCE_MISMATCH"),
    ],
)
def test_qid_adapter_mismatch_branches_are_distinct(field: str, value: str, expected_reason: str) -> None:
    evidence = _base_qid()
    rp = evidence["replay_proof"]

    expected_wallet_id = rp["wallet_id"]
    expected_subject = rp["subject"]
    expected_proof_hash = rp["proof_hash"]
    expected_session_nonce = rp["session_nonce"]
    expected_device_binding = rp.get("device_binding")

    rp[field] = value
    with pytest.raises(AdapterError) as ei:
        parse_qid_replay_proof(
            evidence_qid=evidence,
            expected_wallet_id=expected_wallet_id,
            expected_subject=expected_subject,
            expected_proof_hash=expected_proof_hash,
            expected_device_binding=expected_device_binding,
            expected_session_nonce=expected_session_nonce,
            require_fresh=True,
        )
    assert ei.value.reason_id == expected_reason


def test_qid_adapter_rejects_registry_commitment_type_and_empty() -> None:
    evidence = _base_qid()
    rp = evidence["replay_proof"]

    rp["registry_commitment"] = 123
    with pytest.raises(AdapterError) as ei1:
        parse_qid_replay_proof(
            evidence_qid=evidence,
            expected_wallet_id=rp["wallet_id"],
            expected_subject=rp["subject"],
            expected_proof_hash=rp["proof_hash"],
            expected_device_binding=rp.get("device_binding"),
            expected_session_nonce=rp["session_nonce"],
            require_fresh=True,
        )
    assert ei1.value.reason_id == "QID_REPLAY_PROOF_INVALID"

    evidence2 = _base_qid()
    rp2 = evidence2["replay_proof"]
    rp2["registry_commitment"] = ""
    with pytest.raises(AdapterError) as ei2:
        parse_qid_replay_proof(
            evidence_qid=evidence2,
            expected_wallet_id=rp2["wallet_id"],
            expected_subject=rp2["subject"],
            expected_proof_hash=rp2["proof_hash"],
            expected_device_binding=rp2.get("device_binding"),
            expected_session_nonce=rp2["session_nonce"],
            require_fresh=True,
        )
    assert ei2.value.reason_id == "QID_REPLAY_PROOF_INVALID"


def test_shield_v3_adapter_rejects_signal_id_over_max_len() -> None:
    signals = [
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
        _sig(layer="qwg", signal_id="x" * 129, ext_reason="QWG_DEVICE_COMPROMISED"),
    ]
    shield = _bundle(signals)

    with pytest.raises(AdapterError) as ei:
        parse_shield_bundle_v3(
            payload=shield,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert ei.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_adapter_rejects_unsorted_signals_list() -> None:
    # signals must be sorted by (layer, signal_id); we intentionally violate that.
    signals = [
        _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED"),
        _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK"),
    ]
    shield = _bundle(signals)

    with pytest.raises(AdapterError) as ei:
        parse_shield_bundle_v3(
            payload=shield,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert ei.value.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_shield_v3_adapter_rejects_duplicate_signals() -> None:
    sig1 = _sig(layer="guardian_wallet", signal_id="gw-1", ext_reason="GW_POLICY_BLOCK")
    sig2 = _sig(layer="qwg", signal_id="qwg-1", ext_reason="QWG_DEVICE_COMPROMISED")
    shield = _bundle([sig1, sig2, deepcopy(sig1)])

    with pytest.raises(AdapterError) as ei:
        parse_shield_bundle_v3(
            payload=shield,
            now=123,
            expected_context_hash="a" * 64,
            reason_map=_reason_map(),
            reason_registry=_registry(),
        )
    assert ei.value.reason_id == ReasonId.DENY_ADAPTER_INVALID
