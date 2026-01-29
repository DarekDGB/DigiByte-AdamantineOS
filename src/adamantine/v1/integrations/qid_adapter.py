from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError


def parse_qid_session(*, payload: Mapping[str, Any], now: int) -> QIDSessionProof:
    """
    External Q-ID session payload -> QIDSessionProof (contract)

    Fail-closed:
      - missing required fields
      - invalid types
      - invalid time window (not yet valid / expired)
      - empty subject / empty proof_hash
    """
    if not isinstance(now, int):
        raise AdapterError(ReasonId.EQC_MISSING_NOW, "now must be int")

    if not isinstance(payload, Mapping):
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "payload must be mapping")

    # Required: version (shape enforcement; semantics can evolve later)
    iface = payload.get("qid_iface_version")
    if not isinstance(iface, str) or not iface:
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "qid_iface_version must be non-empty str")

    subject = payload.get("subject")
    issued_at = payload.get("issued_at")
    expires_at = payload.get("expires_at")
    proof_hash = payload.get("proof_hash")

    if not isinstance(subject, str) or not subject:
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "subject must be non-empty str")

    if not isinstance(proof_hash, str) or not proof_hash:
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "proof_hash must be non-empty str")

    if not isinstance(issued_at, int) or not isinstance(expires_at, int):
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "issued_at/expires_at must be int")

    # Provide precise time reasons
    if now < issued_at:
        raise AdapterError(ReasonId.EQC_QID_SESSION_NOT_YET_VALID, "session not yet valid")
    if now >= expires_at:
        raise AdapterError(ReasonId.EQC_QID_SESSION_EXPIRED, "session expired")

    device_binding = payload.get("device_binding", None)
    if device_binding is not None and (not isinstance(device_binding, str) or not device_binding):
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "device_binding must be non-empty str or None")

    issuer_version = payload.get("issuer_version", None)
    if issuer_version is not None and not isinstance(issuer_version, str):
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, "issuer_version must be str or None")

    proof = QIDSessionProof(
        subject=subject,
        issued_at=issued_at,
        expires_at=expires_at,
        proof_hash=proof_hash,
        device_binding=device_binding,
        issuer_version=issuer_version,
    )

    # Contract-level validation (defense in depth)
    try:
        proof.validate(now=now)
    except ValueError as e:
        raise AdapterError(ReasonId.EQC_INVALID_QID_PROOF, f"contract validation failed: {e}") from e

    return proof
