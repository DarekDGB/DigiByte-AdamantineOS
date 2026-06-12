from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthorityV2
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.wsqk.issuer_v2 import (
    WSQK_AUTHORITY_V2,
    WSQKIssueRequestV2,
    compute_wsqk_v2_proof_bindings_hash,
    issue_wsqk_authority_v2,
)


class WSQKV2PolicyEvidenceState(str, Enum):
    """Stable WSQK v2 policy evidence states.

    WSQK can only provide evidence to continue checks. It cannot grant final
    AdamantineOS approval by itself.
    """

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_WSQK_REJECTED = "DENY_WSQK_REJECTED"
    DENY_UNSUPPORTED_INPUT = "DENY_UNSUPPORTED_INPUT"
    DENY_WALLET_MISMATCH = "DENY_WALLET_MISMATCH"
    DENY_ACTION_MISMATCH = "DENY_ACTION_MISMATCH"
    DENY_CONTEXT_HASH_MISMATCH = "DENY_CONTEXT_HASH_MISMATCH"
    DENY_CONTRACT_VERSION_MISMATCH = "DENY_CONTRACT_VERSION_MISMATCH"
    DENY_PROOF_BINDINGS_HASH_MISMATCH = "DENY_PROOF_BINDINGS_HASH_MISMATCH"


@dataclass(frozen=True)
class WSQKV2PolicyEvidenceResult:
    """Normalized WSQK v2 evidence for the future AdamantineOS policy engine."""

    source: str
    state: WSQKV2PolicyEvidenceState
    outcome: str
    reason_id: ReasonId | str
    accepted_as_evidence: bool
    final_approval: bool
    handoff_allowed: bool
    wallet_id: str | None
    action: str | None
    context_hash: str | None
    nonce: str | None
    quantum_posture: str | None
    required_evidence_families: tuple[str, ...]
    proof_bindings_hash: str | None
    dominant_reason_ids: tuple[str, ...]
    authority: WSQKAuthorityV2 | None = None


def _deny(
    *,
    state: WSQKV2PolicyEvidenceState,
    reason_id: ReasonId | str,
    wallet_id: str | None = None,
    action: str | None = None,
    context_hash: str | None = None,
    nonce: str | None = None,
    quantum_posture: str | None = None,
    required_evidence_families: tuple[str, ...] = (),
    proof_bindings_hash: str | None = None,
    authority: WSQKAuthorityV2 | None = None,
) -> WSQKV2PolicyEvidenceResult:
    reason = reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)
    return WSQKV2PolicyEvidenceResult(
        source="wsqk_v2",
        state=state,
        outcome="DENY",
        reason_id=reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        handoff_allowed=False,
        wallet_id=wallet_id,
        action=action,
        context_hash=context_hash,
        nonce=nonce,
        quantum_posture=quantum_posture,
        required_evidence_families=required_evidence_families,
        proof_bindings_hash=proof_bindings_hash,
        dominant_reason_ids=(reason,),
        authority=authority,
    )


_AUTHORITY_MAPPING_FIELDS = frozenset(
    {
        "contract_version",
        "wallet_id",
        "action",
        "context_hash",
        "issued_at",
        "expires_at",
        "nonce",
        "required_evidence_families",
        "quantum_posture",
        "proof_bindings_hash",
    }
)
_AUTHORITY_MAPPING_SHAPE_FIELDS = frozenset({"contract_version", "issued_at", "expires_at", "proof_bindings_hash"})


def _looks_like_authority_mapping(value: Mapping[str, Any]) -> bool:
    return bool(_AUTHORITY_MAPPING_SHAPE_FIELDS.intersection(value.keys()))


def _authority_from_mapping(
    value: Mapping[str, Any],
) -> tuple[WSQKAuthorityV2 | None, ReasonId | None]:
    if not _AUTHORITY_MAPPING_FIELDS.issubset(value.keys()):
        if _looks_like_authority_mapping(value):
            return None, ReasonId.WSQK_V2_AUTHORITY_MAPPING_MISSING_FIELD
        return None, None
    families = value["required_evidence_families"]
    if isinstance(families, (str, bytes)):
        families_tuple: tuple[str, ...] = (str(families),)
    else:
        try:
            families_tuple = tuple(str(item) for item in families)
        except TypeError:
            families_tuple = ()
    try:
        return (
            WSQKAuthorityV2(
                contract_version=str(value["contract_version"]),
                wallet_id=str(value["wallet_id"]),
                action=str(value["action"]),
                context_hash=str(value["context_hash"]),
                issued_at=int(value["issued_at"]),
                expires_at=int(value["expires_at"]),
                nonce=str(value["nonce"]),
                required_evidence_families=families_tuple,
                quantum_posture=str(value["quantum_posture"]),
                proof_bindings_hash=str(value["proof_bindings_hash"]),
            ),
            None,
        )
    except (TypeError, ValueError):
        return None, ReasonId.WSQK_V2_AUTHORITY_MAPPING_INVALID_FIELD


def _request_from_mapping(value: Mapping[str, Any]) -> WSQKIssueRequestV2 | None:
    request_fields = {
        "wallet_id",
        "action",
        "context_hash",
        "now",
        "ttl_seconds",
        "nonce",
        "required_evidence_families",
        "quantum_posture",
    }
    if not request_fields.issubset(value.keys()):
        return None
    return WSQKIssueRequestV2(
        wallet_id=value["wallet_id"],
        action=value["action"],
        context_hash=value["context_hash"],
        now=value["now"],
        ttl_seconds=value["ttl_seconds"],
        nonce=value["nonce"],
        required_evidence_families=value["required_evidence_families"],
        quantum_posture=value["quantum_posture"],
    )


def _normalize_authority(value: Any) -> WSQKAuthorityV2 | WSQKV2PolicyEvidenceResult:
    if isinstance(value, WSQKAuthorityV2):
        return value
    if isinstance(value, WSQKIssueRequestV2):
        try:
            return issue_wsqk_authority_v2(value)
        except TVAError as exc:
            return _deny(state=WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED, reason_id=str(exc))
    if isinstance(value, Mapping):
        request = _request_from_mapping(value)
        if request is not None:
            try:
                return issue_wsqk_authority_v2(request)
            except TVAError as exc:
                return _deny(state=WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED, reason_id=str(exc))
        authority, authority_mapping_reason = _authority_from_mapping(value)
        if authority is not None:
            return authority
        if authority_mapping_reason is not None:
            return _deny(
                state=WSQKV2PolicyEvidenceState.DENY_UNSUPPORTED_INPUT,
                reason_id=authority_mapping_reason,
            )
    return _deny(
        state=WSQKV2PolicyEvidenceState.DENY_UNSUPPORTED_INPUT,
        reason_id=ReasonId.DENY_WSQK,
    )


def normalize_wsqk_v2_policy_evidence(
    wsqk_input: Any,
    *,
    expected_wallet_id: str,
    expected_action: str,
    expected_context_hash: str,
) -> WSQKV2PolicyEvidenceResult:
    """Normalize WSQK v2 evidence for deterministic policy-engine consumption.

    This boundary accepts either a WSQKIssueRequestV2, a WSQKAuthorityV2, or a
    mapping with one of those exact shapes. All WSQK issuer failures become a
    structured DENY with the explicit WSQK reason ID. A valid authority only
    returns ALLOW_EVIDENCE_CONTINUE_CHECKS and never final approval.
    """

    normalized = _normalize_authority(wsqk_input)
    if isinstance(normalized, WSQKV2PolicyEvidenceResult):
        return normalized
    authority = normalized

    if authority.contract_version != WSQK_AUTHORITY_V2:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_CONTRACT_VERSION_MISMATCH,
            reason_id=ReasonId.DENY_WSQK,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )
    if authority.wallet_id != expected_wallet_id:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_WALLET_MISMATCH,
            reason_id=ReasonId.TVA_AUTHORITY_WALLET_MISMATCH,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )
    if authority.action != expected_action:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_ACTION_MISMATCH,
            reason_id=ReasonId.TVA_AUTHORITY_ACTION_MISMATCH,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )
    if authority.context_hash != expected_context_hash:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
            reason_id=ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )

    try:
        expected_proof_hash = compute_wsqk_v2_proof_bindings_hash(
            contract_version=authority.contract_version,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            issued_at=authority.issued_at,
            expires_at=authority.expires_at,
            nonce=authority.nonce,
            required_evidence_families=authority.required_evidence_families,
            quantum_posture=authority.quantum_posture,
        )
    except TVAError as exc:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_WSQK_REJECTED,
            reason_id=str(exc),
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )
    if authority.proof_bindings_hash != expected_proof_hash:
        return _deny(
            state=WSQKV2PolicyEvidenceState.DENY_PROOF_BINDINGS_HASH_MISMATCH,
            reason_id=ReasonId.TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH,
            wallet_id=authority.wallet_id,
            action=authority.action,
            context_hash=authority.context_hash,
            nonce=authority.nonce,
            quantum_posture=authority.quantum_posture,
            required_evidence_families=authority.required_evidence_families,
            proof_bindings_hash=authority.proof_bindings_hash,
            authority=authority,
        )

    return WSQKV2PolicyEvidenceResult(
        source="wsqk_v2",
        state=WSQKV2PolicyEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
        outcome="ALLOW_EVIDENCE",
        reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        handoff_allowed=True,
        wallet_id=authority.wallet_id,
        action=authority.action,
        context_hash=authority.context_hash,
        nonce=authority.nonce,
        quantum_posture=authority.quantum_posture,
        required_evidence_families=authority.required_evidence_families,
        proof_bindings_hash=authority.proof_bindings_hash,
        dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
        authority=authority,
    )
