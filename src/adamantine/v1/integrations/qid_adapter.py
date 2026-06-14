from __future__ import annotations

import hashlib
import json

from typing import Any, Mapping, NoReturn

from adamantine.v1.contracts.qid import QIDReplayProof, QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.obs.metrics import Metrics


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> NoReturn:
    if metrics is not None:
        metrics.inc(rid.value)
    raise AdapterError(rid, msg)


def _canon_json_bytes(obj: object) -> bytes:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return s.encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _is_sha256_hex(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def parse_qid_session(*, payload: Mapping[str, Any], now: int, metrics: Metrics | None = None) -> QIDSessionProof:
    """
    External Q-ID session payload -> QIDSessionProof (contract)

    Accepted shapes:
      A) Adamantine session proof interface:
         - qid_iface_version, subject, issued_at, expires_at, proof_hash, ...
      B) Q-ID Adamantine evidence v2:
         - v="2", kind="qid_login_v2", response_payload{address, issued_at, expires_at, ...}, proof_hash

    Observability:
      - If metrics is provided, increments on AdapterError ReasonId only.
      - Metrics MUST NOT receive payloads or request objects.

    Fail-closed:
      - missing required fields
      - invalid types
      - invalid time window (not yet valid / expired)
      - empty subject / empty proof_hash
      - proof_hash mismatch (v2)
      - missing/malformed context_hash
    """
    if type(now) is not int:
        _fail(metrics, ReasonId.EQC_MISSING_NOW, "now must be int")

    if not isinstance(payload, Mapping):
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "payload must be mapping")

    # ------------------------------------------------------------------
    # Shape B: Q-ID Adamantine evidence v2
    # ------------------------------------------------------------------
    v = payload.get("v")
    kind = payload.get("kind")
    if v == "2" and kind == "qid_login_v2":
        response_payload = payload.get("response_payload")
        if not isinstance(response_payload, Mapping):
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "response_payload must be object")

        subject = response_payload.get("address")
        issued_at = response_payload.get("issued_at")
        expires_at = response_payload.get("expires_at")
        context_hash = response_payload.get("context_hash")

        if not isinstance(subject, str) or not subject:
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "response_payload.address must be non-empty str")

        if type(issued_at) is not int or type(expires_at) is not int:
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "response_payload.issued_at/expires_at must be int")

        if context_hash is not None and not _is_sha256_hex(context_hash):
            _fail(
                metrics,
                ReasonId.EQC_INVALID_QID_PROOF,
                "response_payload.context_hash must be a 64-character lowercase sha256 hex string",
            )

        if now < issued_at:
            _fail(metrics, ReasonId.EQC_QID_SESSION_NOT_YET_VALID, "session not yet valid")
        if now >= expires_at:
            _fail(metrics, ReasonId.EQC_QID_SESSION_EXPIRED, "session expired")

        proof_hash = payload.get("proof_hash")
        if not isinstance(proof_hash, str) or not proof_hash:
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "proof_hash must be non-empty str")

        expected_hash = _sha256_hex(_canon_json_bytes(dict(response_payload)))
        if proof_hash != expected_hash:
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "proof_hash mismatch")

        proof = QIDSessionProof(
            subject=subject,
            issued_at=issued_at,
            expires_at=expires_at,
            proof_hash=proof_hash,
            context_hash=context_hash,
            device_binding=None,
            issuer_version=None,
        )

        try:
            proof.validate(now=now)
        except ValueError as e:
            _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, f"contract validation failed: {e}")

        return proof

    # ------------------------------------------------------------------
    # Shape A: existing Adamantine session proof interface
    # ------------------------------------------------------------------
    iface = payload.get("qid_iface_version")
    if not isinstance(iface, str) or not iface:
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "qid_iface_version must be non-empty str")

    subject = payload.get("subject")
    issued_at = payload.get("issued_at")
    expires_at = payload.get("expires_at")
    proof_hash = payload.get("proof_hash")
    context_hash = payload.get("context_hash")

    if not isinstance(subject, str) or not subject:
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "subject must be non-empty str")

    if not isinstance(proof_hash, str) or not proof_hash:
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "proof_hash must be non-empty str")

    if context_hash is not None and not _is_sha256_hex(context_hash):
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "context_hash must be a 64-character lowercase sha256 hex string")

    if type(issued_at) is not int or type(expires_at) is not int:
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "issued_at/expires_at must be int")

    if now < issued_at:
        _fail(metrics, ReasonId.EQC_QID_SESSION_NOT_YET_VALID, "session not yet valid")
    if now >= expires_at:
        _fail(metrics, ReasonId.EQC_QID_SESSION_EXPIRED, "session expired")

    device_binding = payload.get("device_binding", None)
    if device_binding is not None and (not isinstance(device_binding, str) or not device_binding):
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "device_binding must be non-empty str or None")

    issuer_version = payload.get("issuer_version", None)
    if issuer_version is not None and not isinstance(issuer_version, str):
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, "issuer_version must be str or None")

    proof = QIDSessionProof(
        subject=subject,
        issued_at=issued_at,
        expires_at=expires_at,
        proof_hash=proof_hash,
        context_hash=context_hash,
        device_binding=device_binding,
        issuer_version=issuer_version,
    )

    try:
        proof.validate(now=now)
    except ValueError as e:
        _fail(metrics, ReasonId.EQC_INVALID_QID_PROOF, f"contract validation failed: {e}")

    return proof


def parse_qid_replay_proof(
    *,
    evidence_qid: Mapping[str, Any],
    expected_wallet_id: str,
    expected_subject: str,
    expected_proof_hash: str,
    expected_device_binding: str | None,
    expected_session_nonce: str,
    require_fresh: bool = True,
    metrics: Metrics | None = None,
) -> QIDReplayProof:
    """
    v1.4.0 Q-ID linkage hardening (clock-free replay gate).

    We require untrusted runtime to supply a replay proof object and we validate it
    deterministically. Adamantine remains pure/stateless.

    Missing proof:
      - deny with QID_REPLAY_PROOF_MISSING (call-site decides when mandatory)

    Invalid proof / mismatches:
      - distinct deterministic reasons (no generic failures)
    """
    if not isinstance(evidence_qid, Mapping):
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "evidence_qid must be mapping")

    rp = evidence_qid.get("replay_proof")
    if rp is None:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_MISSING, "qid.replay_proof is required")
    if not isinstance(rp, Mapping):
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "qid.replay_proof must be object")

    proof_version = rp.get("proof_version")
    wallet_id = rp.get("wallet_id")
    subject = rp.get("subject")
    proof_hash = rp.get("proof_hash")
    session_nonce = rp.get("session_nonce")
    registry_commitment = rp.get("registry_commitment")
    fresh = rp.get("fresh")
    device_binding = rp.get("device_binding", None)

    if not isinstance(proof_version, str) or not proof_version:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.proof_version must be non-empty str")
    if not isinstance(wallet_id, str) or not wallet_id:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.wallet_id must be non-empty str")
    if not isinstance(subject, str) or not subject:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.subject must be non-empty str")
    if not isinstance(proof_hash, str) or not proof_hash:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.proof_hash must be non-empty str")
    if not isinstance(session_nonce, str) or not session_nonce:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.session_nonce must be non-empty str")
    if not isinstance(registry_commitment, str) or not registry_commitment:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.registry_commitment must be non-empty str")
    if not isinstance(fresh, bool):
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.fresh must be bool")
    if device_binding is not None and (not isinstance(device_binding, str) or not device_binding):
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, "replay_proof.device_binding must be non-empty str or None")

    proof = QIDReplayProof(
        proof_version=proof_version,
        wallet_id=wallet_id,
        subject=subject,
        proof_hash=proof_hash,
        session_nonce=session_nonce,
        registry_commitment=registry_commitment,
        fresh=fresh,
        device_binding=device_binding,
    )
    try:
        proof.validate()
    except ValueError as e:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_INVALID, f"contract validation failed: {e}")

    if wallet_id != expected_wallet_id:
        _fail(metrics, ReasonId.QID_REPLAY_WALLET_MISMATCH, "replay_proof.wallet_id mismatch")

    if subject != expected_subject:
        _fail(metrics, ReasonId.QID_REPLAY_SUBJECT_MISMATCH, "replay_proof.subject mismatch")

    if proof_hash != expected_proof_hash:
        _fail(metrics, ReasonId.QID_REPLAY_PROOF_HASH_MISMATCH, "replay_proof.proof_hash mismatch")

    # Binding must match exactly (no implicit widening/narrowing at boundary).
    if device_binding != expected_device_binding:
        _fail(metrics, ReasonId.QID_REPLAY_DEVICE_MISMATCH, "replay_proof.device_binding mismatch")

    if session_nonce != expected_session_nonce:
        _fail(metrics, ReasonId.QID_REPLAY_NONCE_MISMATCH, "replay_proof.session_nonce mismatch")

    if require_fresh and fresh is not True:
        _fail(metrics, ReasonId.QID_NONCE_REPLAY, "replay_proof indicates nonce replay")

    return proof
