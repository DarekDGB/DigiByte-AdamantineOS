from __future__ import annotations

import hashlib
import json

from tests.qid_shape_a_test_helpers import bind_shape_a_proof_hash

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.qid_policy_binding import (
    QIDPolicyBindingState,
    normalize_qid_policy_binding,
)

WALLET = "wallet-darek"
SUBJECT = "did:qid:darek"
DEVICE = "device-iphone"
NONCE = "qid-session-nonce-001"
NOW = 1_760_000_000
PROOF_HASH = "a" * 64
REGISTRY = "registry-commitment-001"
CTX = "c" * 64


def _session(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "qid_iface_version": "qid_session_v1",
        "subject": SUBJECT,
        "issued_at": NOW - 10,
        "expires_at": NOW + 300,
        "proof_hash": PROOF_HASH,
        "context_hash": CTX,
        "device_binding": DEVICE,
        "issuer_version": "qid-adamantine-v1",
    }
    data.update(overrides)
    return bind_shape_a_proof_hash(data)  # type: ignore[arg-type]


def _replay(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "proof_version": "qid_replay_proof_v1",
        "wallet_id": WALLET,
        "subject": SUBJECT,
        "proof_hash": str(_session()["proof_hash"]),
        "session_nonce": NONCE,
        "registry_commitment": REGISTRY,
        "fresh": True,
        "device_binding": DEVICE,
    }
    data.update(overrides)
    return data


def _evidence(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "session": _session(),
        "replay_proof": _replay(),
        "qid_posture": {"classical": True, "pqc": True},
    }
    data.update(overrides)
    return data


def _run(value: object, **overrides: object):
    expected: dict[str, object] = {
        "now": NOW,
        "expected_wallet_id": WALLET,
        "expected_subject": SUBJECT,
        "expected_session_nonce": NONCE,
        "expected_quantum_posture": "hybrid_required",
        "expected_context_hash": CTX,
        "expected_device_binding": DEVICE,
    }
    expected.update(overrides)
    return normalize_qid_policy_binding(value, **expected)  # type: ignore[arg-type]


def _shape_b_payload() -> dict[str, object]:
    response_payload = {
        "address": SUBJECT,
        "issued_at": NOW - 10,
        "expires_at": NOW + 300,
        "context_hash": CTX,
    }
    proof_hash = hashlib.sha256(
        json.dumps(response_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "v": "2",
        "kind": "qid_login_v2",
        "response_payload": response_payload,
        "proof_hash": proof_hash,
    }


def test_qid_success_becomes_evidence_only() -> None:
    result = _run(_evidence())

    assert result.source == "qid"
    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.final_approval is False
    assert result.handoff_allowed is True
    assert result.wallet_id == WALLET
    assert result.subject == SUBJECT
    assert result.proof_hash == _session()["proof_hash"]
    assert result.device_binding == DEVICE
    assert result.session_nonce == NONCE
    assert result.quantum_posture == "hybrid_required"
    assert result.qid_posture_classical is True
    assert result.qid_posture_pqc is True
    assert result.dominant_reason_ids == (ReasonId.EVIDENCE_OK.value,)
    assert result.session_proof is not None
    assert result.replay_proof is not None


def test_qid_shape_b_success_is_supported() -> None:
    payload = _shape_b_payload()
    proof_hash = str(payload["proof_hash"])
    value = _evidence(
        session=payload,
        replay_proof=_replay(proof_hash=proof_hash, device_binding=None),
        qid_posture={"classical": False, "pqc": True},
    )

    result = _run(
        value,
        expected_device_binding=None,
        expected_quantum_posture="pqc_required",
    )

    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.proof_hash == proof_hash
    assert result.device_binding is None
    assert result.final_approval is False


def test_qid_top_level_session_shape_success_is_supported() -> None:
    value = _session()
    value["replay_proof"] = _replay()
    value["qid_posture"] = {"classical": True, "pqc": True}

    result = _run(value)

    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.subject == SUBJECT
    assert result.final_approval is False


def test_qid_boolean_input_fails_closed() -> None:
    result = _run(True)

    assert result.state == QIDPolicyBindingState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id == ReasonId.EQC_INVALID_QID_PROOF
    assert result.final_approval is False


def test_qid_missing_session_fails_closed() -> None:
    result = _run({"replay_proof": _replay(), "qid_posture": {"classical": True, "pqc": True}})

    assert result.state == QIDPolicyBindingState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id == ReasonId.EQC_MISSING_QID_SESSION
    assert result.accepted_as_evidence is False


def test_qid_hidden_authority_field_fails_closed() -> None:
    result = _run(_evidence(final_approval=True))

    assert result.state == QIDPolicyBindingState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id == ReasonId.DENY_ADAPTER_INVALID
    assert result.final_approval is False


def test_qid_nested_hidden_authority_field_fails_closed() -> None:
    result = _run(_evidence(metadata={"override": "allow"}))

    assert result.state == QIDPolicyBindingState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_qid_missing_posture_fails_closed() -> None:
    value = _evidence()
    value.pop("qid_posture")

    result = _run(value)

    assert result.state == QIDPolicyBindingState.DENY_POSTURE_MISSING
    assert result.reason_id == ReasonId.WSQK_QID_BINDING_INVALID


def test_qid_invalid_posture_fails_closed() -> None:
    result = _run(_evidence(qid_posture={"classical": "yes", "pqc": True}))

    assert result.state == QIDPolicyBindingState.DENY_POSTURE_INVALID
    assert result.reason_id == ReasonId.WSQK_QID_BINDING_INVALID


def test_qid_hybrid_posture_mismatch_denies() -> None:
    result = _run(_evidence(qid_posture={"classical": True, "pqc": False}))

    assert result.state == QIDPolicyBindingState.DENY_POSTURE_MISMATCH
    assert result.reason_id == ReasonId.WSQK_QID_HYBRID_REQUIRED.value
    assert result.qid_posture_classical is True
    assert result.qid_posture_pqc is False


def test_qid_pqc_required_posture_mismatch_denies() -> None:
    result = _run(
        _evidence(qid_posture={"classical": True, "pqc": False}),
        expected_quantum_posture="pqc_required",
    )

    assert result.state == QIDPolicyBindingState.DENY_POSTURE_MISMATCH
    assert result.reason_id == ReasonId.WSQK_QID_POSTURE_MISMATCH.value


def test_qid_expired_session_denies_with_adapter_reason() -> None:
    result = _run(_evidence(session=_session(expires_at=NOW)))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.EQC_QID_SESSION_EXPIRED
    assert result.accepted_as_evidence is False


def test_qid_not_yet_valid_session_denies_with_adapter_reason() -> None:
    result = _run(_evidence(session=_session(issued_at=NOW + 1, expires_at=NOW + 300)))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.EQC_QID_SESSION_NOT_YET_VALID


def test_qid_invalid_session_hash_denies_for_shape_b() -> None:
    payload = _shape_b_payload()
    payload["proof_hash"] = "b" * 64

    result = _run(_evidence(session=payload))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.EQC_INVALID_QID_PROOF




def test_qid_missing_expected_context_hash_fails_closed() -> None:
    result = normalize_qid_policy_binding(
        _evidence(),
        now=NOW,
        expected_wallet_id=WALLET,
        expected_subject=SUBJECT,
        expected_session_nonce=NONCE,
        expected_quantum_posture="hybrid_required",
        expected_device_binding=DEVICE,
    )

    assert result.state == QIDPolicyBindingState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id == ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False
    assert result.session_proof is not None


def test_qid_context_hash_mismatch_fails_closed_before_replay() -> None:
    result = _run(_evidence(), expected_context_hash="d" * 64)

    assert result.state == QIDPolicyBindingState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id == ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH
    assert result.subject == SUBJECT
    assert result.session_proof is not None
    assert result.replay_proof is None
    assert result.final_approval is False


def test_qid_contextless_session_fails_closed() -> None:
    result = _run(_evidence(session=_session(context_hash=None)))

    assert result.state == QIDPolicyBindingState.DENY_CONTEXT_HASH_MISMATCH
    assert result.reason_id == ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH
    assert result.session_proof is not None
    assert result.session_proof.context_hash is None
    assert result.replay_proof is None

def test_qid_subject_mismatch_denies_before_replay() -> None:
    result = _run(_evidence(), expected_subject="did:qid:other")

    assert result.state == QIDPolicyBindingState.DENY_SUBJECT_MISMATCH
    assert result.reason_id == ReasonId.QID_REPLAY_SUBJECT_MISMATCH
    assert result.subject == SUBJECT
    assert result.session_proof is not None
    assert result.replay_proof is None


def test_qid_missing_replay_proof_denies() -> None:
    value = _evidence()
    value.pop("replay_proof")

    result = _run(value)

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_PROOF_MISSING
    assert result.session_proof is not None


def test_qid_wallet_mismatch_denies() -> None:
    result = _run(_evidence(replay_proof=_replay(wallet_id="other-wallet")))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_WALLET_MISMATCH
    assert result.wallet_id == WALLET
    assert result.final_approval is False


def test_qid_replay_subject_mismatch_denies() -> None:
    result = _run(_evidence(replay_proof=_replay(subject="did:qid:other")))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_SUBJECT_MISMATCH


def test_qid_proof_hash_mismatch_denies() -> None:
    result = _run(_evidence(replay_proof=_replay(proof_hash="b" * 64)))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_PROOF_HASH_MISMATCH


def test_qid_device_mismatch_denies() -> None:
    result = _run(_evidence(replay_proof=_replay(device_binding="other-device")))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_DEVICE_MISMATCH


def test_qid_nonce_mismatch_denies() -> None:
    result = _run(_evidence(replay_proof=_replay(session_nonce="other-nonce")))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_REPLAY_NONCE_MISMATCH


def test_qid_replay_flag_denies_when_fresh_required() -> None:
    result = _run(_evidence(replay_proof=_replay(fresh=False)))

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.QID_NONCE_REPLAY


def test_qid_replay_flag_can_be_accepted_when_explicitly_not_required() -> None:
    result = _run(_evidence(replay_proof=_replay(fresh=False)), require_fresh=False)

    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.accepted_as_evidence is True
    assert result.final_approval is False


def test_qid_hidden_authority_inside_list_fails_closed() -> None:
    result = _run(_evidence(notes=[{"final_approval": True}]))

    assert result.state == QIDPolicyBindingState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id == ReasonId.DENY_ADAPTER_INVALID


def test_qid_top_level_shape_b_success_is_supported() -> None:
    value = _shape_b_payload()
    proof_hash = str(value["proof_hash"])
    value["replay_proof"] = _replay(proof_hash=proof_hash, device_binding=None)
    value["qid_posture"] = {"classical": False, "pqc": True}

    result = _run(
        value,
        expected_device_binding=None,
        expected_quantum_posture="pqc_required",
    )

    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.subject == SUBJECT
    assert result.proof_hash == proof_hash
