from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from adamantine.errors import TVAError
from adamantine.v1.contracts.qid import QIDReplayProof, QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_replay_proof, parse_qid_session
from adamantine.v1.wsqk.qid_binding import QIDPosture, validate_qid_binding


class QIDPolicyBindingState(str, Enum):
    """Stable Q-ID policy binding states.

    Q-ID can authenticate and bind evidence for later policy gates. It cannot
    grant final AdamantineOS approval by itself.
    """

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_QID_REJECTED = "DENY_QID_REJECTED"
    DENY_UNSUPPORTED_INPUT = "DENY_UNSUPPORTED_INPUT"
    DENY_SUBJECT_MISMATCH = "DENY_SUBJECT_MISMATCH"
    DENY_POSTURE_MISSING = "DENY_POSTURE_MISSING"
    DENY_POSTURE_INVALID = "DENY_POSTURE_INVALID"
    DENY_POSTURE_MISMATCH = "DENY_POSTURE_MISMATCH"
    DENY_HIDDEN_AUTHORITY_FIELD = "DENY_HIDDEN_AUTHORITY_FIELD"


@dataclass(frozen=True)
class QIDPolicyBindingResult:
    """Normalized Q-ID evidence for the future AdamantineOS policy engine."""

    source: str
    state: QIDPolicyBindingState
    outcome: str
    reason_id: ReasonId | str
    accepted_as_evidence: bool
    final_approval: bool
    handoff_allowed: bool
    wallet_id: str | None
    subject: str | None
    proof_hash: str | None
    device_binding: str | None
    session_nonce: str | None
    quantum_posture: str | None
    qid_posture_classical: bool | None
    qid_posture_pqc: bool | None
    dominant_reason_ids: tuple[str, ...]
    session_proof: QIDSessionProof | None = None
    replay_proof: QIDReplayProof | None = None


def _reason_text(reason_id: ReasonId | str) -> str:
    return reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)


def _deny(
    *,
    state: QIDPolicyBindingState,
    reason_id: ReasonId | str,
    wallet_id: str | None = None,
    subject: str | None = None,
    proof_hash: str | None = None,
    device_binding: str | None = None,
    session_nonce: str | None = None,
    quantum_posture: str | None = None,
    qid_posture_classical: bool | None = None,
    qid_posture_pqc: bool | None = None,
    session_proof: QIDSessionProof | None = None,
    replay_proof: QIDReplayProof | None = None,
) -> QIDPolicyBindingResult:
    reason = _reason_text(reason_id)
    return QIDPolicyBindingResult(
        source="qid",
        state=state,
        outcome="DENY",
        reason_id=reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        handoff_allowed=False,
        wallet_id=wallet_id,
        subject=subject,
        proof_hash=proof_hash,
        device_binding=device_binding,
        session_nonce=session_nonce,
        quantum_posture=quantum_posture,
        qid_posture_classical=qid_posture_classical,
        qid_posture_pqc=qid_posture_pqc,
        dominant_reason_ids=(reason,),
        session_proof=session_proof,
        replay_proof=replay_proof,
    )


def _contains_forbidden_authority_field(value: Any) -> bool:
    forbidden = {
        "allow",
        "approve",
        "approved",
        "authority",
        "authorization",
        "bypass",
        "final_approval",
        "grant_execution",
        "handoff_allowed",
        "override",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key in forbidden:
                return True
            if _contains_forbidden_authority_field(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_authority_field(item) for item in value)
    return False


def _session_payload_from_input(value: Mapping[str, Any]) -> Mapping[str, Any] | None:
    session = value.get("session")
    if isinstance(session, Mapping):
        return session
    if "qid_iface_version" in value:
        return value
    if value.get("v") == "2" and value.get("kind") == "qid_login_v2":
        return value
    return None


def _posture_from_input(value: Mapping[str, Any]) -> QIDPosture | QIDPolicyBindingResult:
    posture = value.get("qid_posture")
    if not isinstance(posture, Mapping):
        return _deny(
            state=QIDPolicyBindingState.DENY_POSTURE_MISSING,
            reason_id=ReasonId.WSQK_QID_BINDING_INVALID,
        )
    classical = posture.get("classical")
    pqc = posture.get("pqc")
    if not isinstance(classical, bool) or not isinstance(pqc, bool):
        return _deny(
            state=QIDPolicyBindingState.DENY_POSTURE_INVALID,
            reason_id=ReasonId.WSQK_QID_BINDING_INVALID,
        )
    return QIDPosture(classical=classical, pqc=pqc)


def normalize_qid_policy_binding(
    qid_input: Any,
    *,
    now: int,
    expected_wallet_id: str,
    expected_subject: str,
    expected_session_nonce: str,
    expected_quantum_posture: str,
    expected_device_binding: str | None = None,
    require_fresh: bool = True,
) -> QIDPolicyBindingResult:
    """Normalize Q-ID evidence for deterministic policy-engine consumption.

    The boundary consumes existing Q-ID adapter outputs through the adapter
    functions instead of duplicating cryptographic or replay parsing logic. Valid
    Q-ID evidence becomes ALLOW_EVIDENCE_CONTINUE_CHECKS only. Any adapter
    failure, binding mismatch, stale replay flag, unsupported shape, hidden
    authority field, or WSQK/Q-ID posture mismatch becomes a structured DENY.
    """

    if not isinstance(qid_input, Mapping):
        return _deny(
            state=QIDPolicyBindingState.DENY_UNSUPPORTED_INPUT,
            reason_id=ReasonId.EQC_INVALID_QID_PROOF,
            quantum_posture=expected_quantum_posture,
        )

    if _contains_forbidden_authority_field(qid_input):
        return _deny(
            state=QIDPolicyBindingState.DENY_HIDDEN_AUTHORITY_FIELD,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
            quantum_posture=expected_quantum_posture,
        )

    session_payload = _session_payload_from_input(qid_input)
    if session_payload is None:
        return _deny(
            state=QIDPolicyBindingState.DENY_UNSUPPORTED_INPUT,
            reason_id=ReasonId.EQC_MISSING_QID_SESSION,
            quantum_posture=expected_quantum_posture,
        )

    posture = _posture_from_input(qid_input)
    if isinstance(posture, QIDPolicyBindingResult):
        return _deny(
            state=posture.state,
            reason_id=posture.reason_id,
            quantum_posture=expected_quantum_posture,
        )

    try:
        validate_qid_binding(quantum_posture=expected_quantum_posture, qid_posture=posture)
    except TVAError as exc:
        return _deny(
            state=QIDPolicyBindingState.DENY_POSTURE_MISMATCH,
            reason_id=str(exc),
            quantum_posture=expected_quantum_posture,
            qid_posture_classical=posture.classical,
            qid_posture_pqc=posture.pqc,
        )

    try:
        session_proof = parse_qid_session(payload=session_payload, now=now)
    except AdapterError as exc:
        return _deny(
            state=QIDPolicyBindingState.DENY_QID_REJECTED,
            reason_id=exc.reason_id,
            quantum_posture=expected_quantum_posture,
            qid_posture_classical=posture.classical,
            qid_posture_pqc=posture.pqc,
        )

    if session_proof.subject != expected_subject:
        return _deny(
            state=QIDPolicyBindingState.DENY_SUBJECT_MISMATCH,
            reason_id=ReasonId.QID_REPLAY_SUBJECT_MISMATCH,
            subject=session_proof.subject,
            proof_hash=session_proof.proof_hash,
            device_binding=session_proof.device_binding,
            quantum_posture=expected_quantum_posture,
            qid_posture_classical=posture.classical,
            qid_posture_pqc=posture.pqc,
            session_proof=session_proof,
        )

    try:
        replay_proof = parse_qid_replay_proof(
            evidence_qid=qid_input,
            expected_wallet_id=expected_wallet_id,
            expected_subject=session_proof.subject,
            expected_proof_hash=session_proof.proof_hash,
            expected_device_binding=expected_device_binding,
            expected_session_nonce=expected_session_nonce,
            require_fresh=require_fresh,
        )
    except AdapterError as exc:
        return _deny(
            state=QIDPolicyBindingState.DENY_QID_REJECTED,
            reason_id=exc.reason_id,
            wallet_id=expected_wallet_id,
            subject=session_proof.subject,
            proof_hash=session_proof.proof_hash,
            device_binding=session_proof.device_binding,
            session_nonce=expected_session_nonce,
            quantum_posture=expected_quantum_posture,
            qid_posture_classical=posture.classical,
            qid_posture_pqc=posture.pqc,
            session_proof=session_proof,
        )

    return QIDPolicyBindingResult(
        source="qid",
        state=QIDPolicyBindingState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
        outcome="ALLOW_EVIDENCE",
        reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        handoff_allowed=True,
        wallet_id=replay_proof.wallet_id,
        subject=session_proof.subject,
        proof_hash=session_proof.proof_hash,
        device_binding=session_proof.device_binding,
        session_nonce=replay_proof.session_nonce,
        quantum_posture=expected_quantum_posture,
        qid_posture_classical=posture.classical,
        qid_posture_pqc=posture.pqc,
        dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
        session_proof=session_proof,
        replay_proof=replay_proof,
    )
