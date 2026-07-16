from __future__ import annotations

from typing import Iterable

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority, WSQKAuthorityV2
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.wsqk.issuer_v2 import (
    compute_wsqk_v2_proof_bindings_hash,
    canonical_required_evidence_families,
)


def _enforce_wsqk_v2_quantum_posture(
    authority: WSQKAuthority | WSQKAuthorityV2,
    *,
    required_evidence_families: Iterable[str] | None,
    required_quantum_posture: str | None,
) -> None:
    """
    Enforce WSQK v2 quantum-aware posture requirements.

    This path is opt-in so WSQK v1 callers remain unchanged. When a caller
    requires v2 semantics, v1 authority is denied rather than silently upgraded
    or interpreted as quantum-aware.
    """
    if required_evidence_families is None and required_quantum_posture is None:
        return

    if not isinstance(authority, WSQKAuthorityV2):
        raise TVAError(ReasonId.TVA_WSQK_V2_REQUIRED.value)

    authority_families = canonical_required_evidence_families(authority.required_evidence_families)

    if required_evidence_families is not None:
        expected_families = canonical_required_evidence_families(required_evidence_families)
        if authority_families != expected_families:
            raise TVAError(ReasonId.TVA_WSQK_V2_EVIDENCE_FAMILY_MISMATCH.value)

    if required_quantum_posture is not None:
        expected_posture = str(required_quantum_posture or "").strip()
        if authority.quantum_posture != expected_posture:
            raise TVAError(ReasonId.TVA_WSQK_V2_QUANTUM_POSTURE_MISMATCH.value)

    expected_hash = compute_wsqk_v2_proof_bindings_hash(
        contract_version=authority.contract_version,
        wallet_id=authority.wallet_id,
        action=authority.action,
        context_hash=authority.context_hash,
        issued_at=authority.issued_at,
        expires_at=authority.expires_at,
        nonce=authority.nonce,
        required_evidence_families=authority_families,
        quantum_posture=authority.quantum_posture,
    )
    if authority.proof_bindings_hash != expected_hash:
        raise TVAError(ReasonId.TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH.value)


def enforce_tva(
    context: ExecutionContext | None,
    verdict: Verdict | None,
    authority: WSQKAuthority | WSQKAuthorityV2 | None,
    *,
    now: int | None = None,
    nonce_store: NonceStore | None = None,
    required_evidence_families: Iterable[str] | None = None,
    required_quantum_posture: str | None = None,
) -> None:
    """
    TVA (Truth Vector Authority) - final enforcement gate (fail-closed).

    Execution is allowed ONLY if:
      - context exists
      - verdict exists and is ALLOW
      - authority exists
      - authority binds EXACTLY to context (wallet_id, action, context_hash)
      - time window is valid (issued_at <= now <= expires_at)
      - nonce is valid and single-use (via injected nonce_store)
      - when v2 requirements are provided, authority is WSQK v2 and matches
        the required quantum-aware evidence family and posture policy

    Determinism:
      - `now` is injected (no global time)
      - `nonce_store` is injected (no global state)
      - WSQK v2 evidence families are compared as sorted canonical sets
    """
    if context is None:
        raise TVAError(ReasonId.TVA_MISSING_CONTEXT.value)

    if verdict is None:
        raise TVAError(ReasonId.TVA_MISSING_VERDICT.value)

    if authority is None:
        raise TVAError(ReasonId.TVA_MISSING_AUTHORITY.value)

    if verdict is not Verdict.ALLOW:
        raise TVAError(ReasonId.TVA_VERDICT_NOT_ALLOW.value)

    # --- Authority must bind to the exact execution context (fail-closed) ---
    if authority.wallet_id != context.wallet_id:
        raise TVAError(ReasonId.TVA_AUTHORITY_WALLET_MISMATCH.value)

    if authority.action != context.action:
        raise TVAError(ReasonId.TVA_AUTHORITY_ACTION_MISMATCH.value)

    if authority.context_hash != context.context_hash:
        raise TVAError(ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value)

    # --- Deterministic time validation (requires injected now) ---
    if now is None:
        raise TVAError(ReasonId.TVA_MISSING_NOW.value)

    issued_at = int(authority.issued_at)
    expires_at = int(authority.expires_at)

    if expires_at < issued_at:
        raise TVAError(ReasonId.TVA_INVALID_TIME_WINDOW.value)

    if now < issued_at:
        raise TVAError(ReasonId.TVA_AUTHORITY_NOT_YET_VALID.value)

    if now > expires_at:
        raise TVAError(ReasonId.TVA_AUTHORITY_EXPIRED.value)

    _enforce_wsqk_v2_quantum_posture(
        authority,
        required_evidence_families=required_evidence_families,
        required_quantum_posture=required_quantum_posture,
    )

    # --- Nonce validation + replay protection (requires injected store) ---
    if nonce_store is None:
        raise TVAError(ReasonId.TVA_MISSING_NONCE_STORE.value)

    nonce = str(authority.nonce or "").strip()
    if not nonce:
        raise TVAError(ReasonId.TVA_INVALID_NONCE.value)

    accepted = nonce_store.check_and_mark(authority.wallet_id, nonce, expires_at)
    if not accepted:
        raise TVAError(ReasonId.TVA_NONCE_REPLAY.value)
