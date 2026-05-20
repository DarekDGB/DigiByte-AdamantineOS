from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthorityV2
from adamantine.v1.contracts.reason_ids import ReasonId

WSQK_AUTHORITY_V2 = "WSQK_AUTHORITY_V2"

# Phase 2 keeps this list deliberately small and explicit.
# Phase 3 may replace generic failures with WSQK-v2-specific reason IDs.
ALLOWED_EVIDENCE_FAMILIES: tuple[str, ...] = (
    "classical_signature",
    "pqc_signature",
    "qid_hybrid",
)

ALLOWED_QUANTUM_POSTURES: tuple[str, ...] = (
    "classical_only",
    "hybrid_required",
    "pqc_required",
)


@dataclass(frozen=True, slots=True)
class WSQKIssueRequestV2:
    wallet_id: str
    action: str
    context_hash: str
    now: int
    ttl_seconds: int
    nonce: str
    required_evidence_families: Iterable[str]
    quantum_posture: str


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_required_evidence_families(families: Iterable[str]) -> tuple[str, ...]:
    """Return the Phase 1 locked sorted canonical unique set."""
    if isinstance(families, (str, bytes)):
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)

    try:
        raw = tuple(families)
    except TypeError:
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)

    if not raw:
        raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)

    normalized: set[str] = set()
    allowed = set(ALLOWED_EVIDENCE_FAMILIES)
    for family in raw:
        if not isinstance(family, str):
            raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)
        item = family.strip()
        if not item or item not in allowed:
            raise TVAError(ReasonId.DENY_AUTHORITY_INVALID.value)
        normalized.add(item)

    return tuple(sorted(normalized))


def compute_wsqk_v2_proof_bindings_hash(
    *,
    contract_version: str,
    wallet_id: str,
    action: str,
    context_hash: str,
    issued_at: int,
    expires_at: int,
    nonce: str,
    required_evidence_families: Iterable[str],
    quantum_posture: str,
) -> str:
    canonical_families = canonical_required_evidence_families(required_evidence_families)
    binding = {
        "action": action,
        "context_hash": context_hash,
        "contract_version": contract_version,
        "expires_at": expires_at,
        "issued_at": issued_at,
        "nonce": nonce,
        "quantum_posture": quantum_posture,
        "required_evidence_families": list(canonical_families),
        "wallet_id": wallet_id,
    }
    return hashlib.sha256(_canonical_json_bytes(binding)).hexdigest()


def issue_wsqk_authority_v2(req: WSQKIssueRequestV2) -> WSQKAuthorityV2:
    """Issue deterministic WSQK v2 authority from explicit injected inputs."""
    wallet_id = str(req.wallet_id or "").strip()
    if not wallet_id:
        raise TVAError(ReasonId.WSQK_MISSING_WALLET_ID.value)

    action = str(req.action or "").strip()
    if not action:
        raise TVAError(ReasonId.WSQK_MISSING_ACTION.value)

    context_hash = str(req.context_hash or "").strip()
    if not context_hash:
        raise TVAError(ReasonId.WSQK_MISSING_CONTEXT_HASH.value)

    try:
        issued_at = int(req.now)
    except Exception:
        raise TVAError(ReasonId.WSQK_MISSING_NOW.value)

    try:
        ttl = int(req.ttl_seconds)
    except Exception:
        raise TVAError(ReasonId.WSQK_INVALID_TTL.value)
    if ttl <= 0:
        raise TVAError(ReasonId.WSQK_INVALID_TTL.value)

    nonce = str(req.nonce or "").strip()
    if not nonce:
        raise TVAError(ReasonId.WSQK_INVALID_NONCE.value)

    quantum_posture = str(req.quantum_posture or "").strip()
    if quantum_posture not in ALLOWED_QUANTUM_POSTURES:
        raise TVAError(ReasonId.DENY_AUTHORITY_INSUFFICIENT.value)

    canonical_families = canonical_required_evidence_families(req.required_evidence_families)
    expires_at = issued_at + ttl
    proof_hash = compute_wsqk_v2_proof_bindings_hash(
        contract_version=WSQK_AUTHORITY_V2,
        wallet_id=wallet_id,
        action=action,
        context_hash=context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        required_evidence_families=canonical_families,
        quantum_posture=quantum_posture,
    )

    return WSQKAuthorityV2(
        contract_version=WSQK_AUTHORITY_V2,
        wallet_id=wallet_id,
        action=action,
        context_hash=context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
        required_evidence_families=canonical_families,
        quantum_posture=quantum_posture,
        proof_bindings_hash=proof_hash,
    )
