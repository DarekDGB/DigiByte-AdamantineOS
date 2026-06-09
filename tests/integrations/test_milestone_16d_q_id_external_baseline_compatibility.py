from __future__ import annotations

import copy
import json
from pathlib import Path

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.integrations.qid_policy_binding import (
    QIDPolicyBindingState,
    normalize_qid_policy_binding,
)

FIXTURE = Path(
    "tests/fixtures/q_id_external_baseline/qid_adamantine_evidence_v2_policy_binding.json"
)
NOW = 1_760_000_000
WALLET = "wallet-darek-16d"
SUBJECT = "did:qid:darek-16d"
NONCE = "qid-session-nonce-16d"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _policy_input() -> dict[str, object]:
    return copy.deepcopy(_fixture()["adamantine_policy_binding_input"])  # type: ignore[index]


def _run(value: object):
    return normalize_qid_policy_binding(
        value,
        now=NOW,
        expected_wallet_id=WALLET,
        expected_subject=SUBJECT,
        expected_session_nonce=NONCE,
        expected_quantum_posture="pqc_required",
        expected_device_binding=None,
    )


def test_milestone_16d_external_qid_v2_session_shape_parses_through_existing_adapter() -> None:
    payload = _fixture()["qid_evidence_v2"]

    proof = parse_qid_session(payload=payload, now=NOW)  # type: ignore[arg-type]

    assert proof.subject == SUBJECT
    assert proof.issued_at < NOW < proof.expires_at
    assert proof.device_binding is None
    assert proof.proof_hash == payload["proof_hash"]  # type: ignore[index]


def test_milestone_16d_external_qid_v2_policy_binding_is_evidence_only() -> None:
    result = _run(_policy_input())

    assert result.state == QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.outcome == "ALLOW_EVIDENCE"
    assert result.reason_id == ReasonId.EVIDENCE_OK
    assert result.accepted_as_evidence is True
    assert result.handoff_allowed is True
    assert result.final_approval is False
    assert result.source == "qid"
    assert result.wallet_id == WALLET
    assert result.subject == SUBJECT
    assert result.session_nonce == NONCE
    assert result.quantum_posture == "pqc_required"
    assert result.qid_posture_pqc is True
    assert result.session_proof is not None
    assert result.replay_proof is not None


def test_milestone_16d_external_qid_v2_alone_cannot_be_final_authority() -> None:
    value = copy.deepcopy(_fixture()["qid_evidence_v2"])

    result = _run(value)

    assert result.state == QIDPolicyBindingState.DENY_POSTURE_MISSING
    assert result.reason_id == ReasonId.WSQK_QID_BINDING_INVALID
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.handoff_allowed is False


def test_milestone_16d_external_qid_v2_hidden_authority_field_denies() -> None:
    value = _policy_input()
    session = value["session"]
    assert isinstance(session, dict)
    session["final_approval"] = True

    result = _run(value)

    assert result.state == QIDPolicyBindingState.DENY_HIDDEN_AUTHORITY_FIELD
    assert result.reason_id == ReasonId.DENY_ADAPTER_INVALID
    assert result.final_approval is False


def test_milestone_16d_external_qid_v2_proof_hash_mismatch_fails_closed() -> None:
    value = _policy_input()
    session = value["session"]
    assert isinstance(session, dict)
    session["proof_hash"] = "b" * 64

    result = _run(value)

    assert result.state == QIDPolicyBindingState.DENY_QID_REJECTED
    assert result.reason_id == ReasonId.EQC_INVALID_QID_PROOF
    assert result.accepted_as_evidence is False
    assert result.final_approval is False


def test_milestone_16d_external_qid_v2_subject_mismatch_denies_before_replay() -> None:
    result = normalize_qid_policy_binding(
        _policy_input(),
        now=NOW,
        expected_wallet_id=WALLET,
        expected_subject="did:qid:other-subject",
        expected_session_nonce=NONCE,
        expected_quantum_posture="pqc_required",
        expected_device_binding=None,
    )

    assert result.state == QIDPolicyBindingState.DENY_SUBJECT_MISMATCH
    assert result.reason_id == ReasonId.QID_REPLAY_SUBJECT_MISMATCH
    assert result.session_proof is not None
    assert result.replay_proof is None
    assert result.final_approval is False


def test_milestone_16d_external_qid_v2_import_failure_shape_is_not_allow() -> None:
    with_external_import_error_shape = {
        "source": "DigiByte-Q-ID",
        "error": "ImportError",
        "message": "external Q-ID package unavailable",
    }

    result = _run(with_external_import_error_shape)

    assert result.state == QIDPolicyBindingState.DENY_UNSUPPORTED_INPUT
    assert result.reason_id == ReasonId.EQC_MISSING_QID_SESSION
    assert result.final_approval is False
