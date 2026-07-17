from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.ai_gateway_canonical_json_v1 import (
    AIGatewayCanonicalJSONError,
    AIGatewayDuplicateKeyError,
    AIGatewayResourceLimitError,
    canonical_ai_gateway_json_v1_bytes,
    parse_ai_gateway_json_v1,
)


ADAMANTINE_AI_GATEWAY_EVIDENCE_V2 = "adamantine_ai_gateway_evidence_v2"
ADAMANTINE_AI_GATEWAY_SOURCE = "adamantine-ai-gateway"
ADAMANTINE_EVIDENCE_ROLE = "evidence_only"
AI_GATEWAY_HANDOFF_V1 = "ai_gateway_handoff_v1"
AI_GATEWAY_RECEIPT_V1 = "ai_gateway_receipt_v1"
AI_GATEWAY_OUTPUT_V1 = "ai_gateway_output_v1"
AI_GATEWAY_POLICY_BINDING_V1 = "ai_gateway_policy_binding_v1"
POLICY_PACK_V1 = "policy_pack_v1"
RECEIPT_DETERMINISM_PROFILE_V1 = "canonical_sha256_no_time_v1"

MAX_POLICY_ID_SCALARS = 256
MAX_POLICY_BINDING_BYTES = 4_096

_HEX = frozenset("0123456789abcdef")
_EVIDENCE_FIELDS = frozenset(
    {
        "evidence_version",
        "source",
        "evidence_role",
        "expected_context_hash",
        "handoff",
        "receipt",
        "policy_binding",
    }
)
_HANDOFF_FIELDS = frozenset(
    {
        "handoff_version",
        "adapter",
        "task_type",
        "policy_decision",
        "reason_id",
        "envelope_hash",
        "output_hash",
        "context_hash",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "receipt_version",
        "gateway_version",
        "adapter_id",
        "adapter_version",
        "envelope_hash",
        "output_hash",
        "policy_decision",
        "reason_id",
        "created_from_contract",
        "determinism_profile",
    }
)
_POLICY_BINDING_FIELDS = frozenset(
    {
        "policy_binding_version",
        "policy_pack_contract_version",
        "policy_pack_id",
        "policy_pack_version_id",
        "policy_pack_hash",
        "receipt_hash",
        "handoff_hash",
    }
)
_FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
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
)
_GATEWAY_REJECTED_REASON_IDS = frozenset(
    {
        "ADAPTER_NOT_REGISTERED",
        "ADAPTER_VALIDATION_FAILED",
        "CANONICALIZATION_FAILED",
        "HASHING_FAILED",
        "INTERNAL_ERROR",
        "INVALID_ENVELOPE",
        "INVALID_OUTPUT",
        "MISSING_REQUIRED_FIELD",
        "NON_DETERMINISTIC_OUTPUT",
        "POLICY_DENIED",
        "SCHEMA_VIOLATION",
        "UNSUPPORTED_MODEL",
        "UNSUPPORTED_TASK",
    }
)


class AIGatewayPolicyBoundEvidenceState(str, Enum):
    """Stable states for the independent policy-bound V2 consumer."""

    ALLOW_EVIDENCE_CONTINUE_CHECKS = "ALLOW_EVIDENCE_CONTINUE_CHECKS"
    DENY_EARLIER_GATE_DENIED = "DENY_EARLIER_GATE_DENIED"
    DENY_EXPECTED_POLICY_INVALID = "DENY_EXPECTED_POLICY_INVALID"
    DENY_UNSUPPORTED_INPUT = "DENY_UNSUPPORTED_INPUT"
    DENY_INVALID_WIRE = "DENY_INVALID_WIRE"
    DENY_DUPLICATE_KEY = "DENY_DUPLICATE_KEY"
    DENY_RESOURCE_LIMIT = "DENY_RESOURCE_LIMIT"
    DENY_SCHEMA_INVALID = "DENY_SCHEMA_INVALID"
    DENY_UNKNOWN_FIELD = "DENY_UNKNOWN_FIELD"
    DENY_VERSION_MISMATCH = "DENY_VERSION_MISMATCH"
    DENY_MISSING_POLICY_BINDING = "DENY_MISSING_POLICY_BINDING"
    DENY_HIDDEN_AUTHORITY_FIELD = "DENY_HIDDEN_AUTHORITY_FIELD"
    DENY_CONTEXT_HASH_MISMATCH = "DENY_CONTEXT_HASH_MISMATCH"
    DENY_RECEIPT_MISMATCH = "DENY_RECEIPT_MISMATCH"
    DENY_BINDING_HASH_MISMATCH = "DENY_BINDING_HASH_MISMATCH"
    DENY_POLICY_ID_MISMATCH = "DENY_POLICY_ID_MISMATCH"
    DENY_POLICY_VERSION_MISMATCH = "DENY_POLICY_VERSION_MISMATCH"
    DENY_POLICY_HASH_MISMATCH = "DENY_POLICY_HASH_MISMATCH"
    DENY_AI_GATEWAY_REJECTED = "DENY_AI_GATEWAY_REJECTED"
    DENY_INTERNAL_ERROR = "DENY_INTERNAL_ERROR"


@dataclass(frozen=True)
class AIGatewayExpectedPolicyV1:
    """Verifier-controlled expected policy identity, never untrusted evidence."""

    policy_pack_id: str
    policy_pack_version_id: str
    policy_pack_hash: str


@dataclass(frozen=True)
class AIGatewayPolicyBoundEvidenceResult:
    """Evidence-only result for later AdamantineOS policy gates."""

    source: str
    state: AIGatewayPolicyBoundEvidenceState
    outcome: str
    reason_id: ReasonId | str
    accepted_as_evidence: bool
    final_approval: bool
    policy_binding_verified: bool
    context_hash: str | None
    policy_pack_id: str | None
    policy_pack_version_id: str | None
    policy_pack_hash: str | None
    receipt_hash: str | None
    handoff_hash: str | None
    dominant_reason_ids: tuple[str, ...]


class _EvidenceFailure(Exception):
    def __init__(
        self,
        state: AIGatewayPolicyBoundEvidenceState,
        reason_id: ReasonId | str,
    ) -> None:
        super().__init__(state.value)
        self.state = state
        self.reason_id = reason_id


def _reason_text(reason_id: ReasonId | str) -> str:
    return reason_id.value if isinstance(reason_id, ReasonId) else str(reason_id)


def _deny(
    *,
    state: AIGatewayPolicyBoundEvidenceState,
    reason_id: ReasonId | str,
    dominant_reason_ids: tuple[str, ...] | None = None,
    policy_binding_verified: bool = False,
    context_hash: str | None = None,
    policy_pack_id: str | None = None,
    policy_pack_version_id: str | None = None,
    policy_pack_hash: str | None = None,
    receipt_hash: str | None = None,
    handoff_hash: str | None = None,
) -> AIGatewayPolicyBoundEvidenceResult:
    reason = _reason_text(reason_id)
    return AIGatewayPolicyBoundEvidenceResult(
        source="ai_gateway",
        state=state,
        outcome="DENY",
        reason_id=reason_id,
        accepted_as_evidence=False,
        final_approval=False,
        policy_binding_verified=policy_binding_verified,
        context_hash=context_hash,
        policy_pack_id=policy_pack_id,
        policy_pack_version_id=policy_pack_version_id,
        policy_pack_hash=policy_pack_hash,
        receipt_hash=receipt_hash,
        handoff_hash=handoff_hash,
        dominant_reason_ids=dominant_reason_ids or (reason,),
    )


def _is_non_empty_exact_string(value: Any, *, maximum: int | None = None) -> bool:
    if type(value) is not str or not value.strip():
        return False
    if maximum is not None and len(value) > maximum:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _is_sha256_hex(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(character in _HEX for character in value)


def _expected_policy_is_valid(value: Any) -> bool:
    return (
        type(value) is AIGatewayExpectedPolicyV1
        and _is_non_empty_exact_string(value.policy_pack_id, maximum=MAX_POLICY_ID_SCALARS)
        and _is_non_empty_exact_string(value.policy_pack_version_id, maximum=MAX_POLICY_ID_SCALARS)
        and _is_sha256_hex(value.policy_pack_hash)
    )


def _extract_earlier_denies(prior_gate_results: Sequence[Any] | None) -> tuple[str, ...]:
    if prior_gate_results is None:
        return ()
    if type(prior_gate_results) not in {list, tuple}:
        raise TypeError("prior gate results must be an exact list or tuple")
    denies: list[str] = []
    missing = object()
    for result in prior_gate_results:
        if type(result) is dict:
            outcome = result.get("outcome", missing)
            reason_id = result.get("reason_id", missing)
        elif isinstance(result, Mapping):
            raise TypeError("prior gate mapping must be an exact dictionary")
        else:
            outcome = getattr(result, "outcome", missing)
            reason_id = getattr(result, "reason_id", missing)
        if outcome is missing:
            raise TypeError("prior gate result has no outcome")
        if type(outcome) is not str or outcome not in {"DENY", "ALLOW_EVIDENCE"}:
            raise TypeError("prior gate result has an unsupported outcome")
        if outcome == "DENY":
            if reason_id is missing:
                reason_id = None
            denies.append(_reason_text(reason_id or ReasonId.DENY_POLICY))
    return tuple(denies)


def _contains_forbidden_authority_field(value: Any) -> bool:
    if type(value) is dict:
        for key, child in value.items():
            if key in _FORBIDDEN_AUTHORITY_FIELDS:
                return True
            if _contains_forbidden_authority_field(child):
                return True
    elif type(value) is list:
        return any(_contains_forbidden_authority_field(item) for item in value)
    return False


def _require_exact_object(value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_SCHEMA_INVALID,
        )
    actual = set(value)
    if actual - fields:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_UNKNOWN_FIELD,
            ReasonId.DENY_UNKNOWN_FIELD,
        )
    if fields - actual:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_SCHEMA_INVALID,
        )
    return value


def _require_hashes(value: Mapping[str, Any], fields: tuple[str, ...]) -> None:
    if any(not _is_sha256_hex(value[field]) for field in fields):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_ADAPTER_INVALID,
        )


def _validate_reason_semantics(policy_decision: Any, reason_id: Any) -> None:
    if policy_decision not in {"accepted", "rejected"} or not _is_non_empty_exact_string(reason_id):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_POLICY,
        )
    if policy_decision == "accepted" and reason_id != "ACCEPTED":
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_POLICY,
        )
    if policy_decision == "rejected" and reason_id not in _GATEWAY_REJECTED_REASON_IDS:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
            ReasonId.DENY_POLICY,
        )


def _validate_handoff(value: Any) -> dict[str, Any]:
    handoff = _require_exact_object(value, _HANDOFF_FIELDS)
    if handoff["handoff_version"] != AI_GATEWAY_HANDOFF_V1:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
            ReasonId.DENY_VERSION_MISMATCH,
        )
    for field in ("adapter", "task_type"):
        if not _is_non_empty_exact_string(handoff[field]):
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
                ReasonId.DENY_SCHEMA_INVALID,
            )
    _validate_reason_semantics(handoff["policy_decision"], handoff["reason_id"])
    _require_hashes(handoff, ("envelope_hash", "output_hash", "context_hash"))
    return handoff


def _validate_receipt(value: Any) -> dict[str, Any]:
    receipt = _require_exact_object(value, _RECEIPT_FIELDS)
    if (
        receipt["receipt_version"] != AI_GATEWAY_RECEIPT_V1
        or receipt["created_from_contract"] != AI_GATEWAY_OUTPUT_V1
        or receipt["determinism_profile"] != RECEIPT_DETERMINISM_PROFILE_V1
    ):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
            ReasonId.DENY_VERSION_MISMATCH,
        )
    for field in ("gateway_version", "adapter_id", "adapter_version"):
        if not _is_non_empty_exact_string(receipt[field]):
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
                ReasonId.DENY_SCHEMA_INVALID,
            )
    _validate_reason_semantics(receipt["policy_decision"], receipt["reason_id"])
    _require_hashes(receipt, ("envelope_hash", "output_hash"))
    return receipt


def _validate_policy_binding(value: Any) -> dict[str, Any]:
    binding = _require_exact_object(value, _POLICY_BINDING_FIELDS)
    if (
        binding["policy_binding_version"] != AI_GATEWAY_POLICY_BINDING_V1
        or binding["policy_pack_contract_version"] != POLICY_PACK_V1
    ):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
            ReasonId.DENY_VERSION_MISMATCH,
        )
    for field in ("policy_pack_id", "policy_pack_version_id"):
        if not _is_non_empty_exact_string(binding[field], maximum=MAX_POLICY_ID_SCALARS):
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
                ReasonId.DENY_SCHEMA_INVALID,
            )
    _require_hashes(binding, ("policy_pack_hash", "receipt_hash", "handoff_hash"))
    if len(canonical_ai_gateway_json_v1_bytes(binding)) > MAX_POLICY_BINDING_BYTES:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT,
            ReasonId.DENY_ADAPTER_INVALID,
        )
    return binding


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_ai_gateway_json_v1_bytes(value)).hexdigest()


def _validate_artifact_chain(
    *,
    handoff: Mapping[str, Any],
    receipt: Mapping[str, Any],
    binding: Mapping[str, Any],
    expected_context_hash: str,
) -> tuple[str, str]:
    if (
        handoff["context_hash"] != expected_context_hash
        or handoff["context_hash"] != handoff["envelope_hash"]
    ):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
            ReasonId.DENY_POLICY,
        )
    if (
        receipt["adapter_id"] != handoff["adapter"]
        or receipt["envelope_hash"] != handoff["envelope_hash"]
        or receipt["output_hash"] != handoff["output_hash"]
        or receipt["policy_decision"] != handoff["policy_decision"]
        or receipt["reason_id"] != handoff["reason_id"]
    ):
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
            ReasonId.DENY_ADAPTER_INVALID,
        )

    receipt_hash = _sha256(receipt)
    handoff_hash = _sha256(handoff)
    if binding["receipt_hash"] != receipt_hash or binding["handoff_hash"] != handoff_hash:
        raise _EvidenceFailure(
            AIGatewayPolicyBoundEvidenceState.DENY_BINDING_HASH_MISMATCH,
            ReasonId.DENY_POLICY,
        )
    return receipt_hash, handoff_hash


def consume_ai_gateway_policy_bound_evidence_v2(
    raw_evidence: bytes,
    *,
    expected_context_hash: str,
    expected_policy: AIGatewayExpectedPolicyV1,
    prior_gate_results: Sequence[Any] | None = None,
) -> AIGatewayPolicyBoundEvidenceResult:
    """Consume policy-bound Gateway V2 bytes without V1 fallback.

    `expected_policy` and `expected_context_hash` are verifier-controlled local
    inputs. Valid upstream evidence can only continue later AdamantineOS checks;
    it can never grant final approval.
    """

    try:
        earlier_denies = _extract_earlier_denies(prior_gate_results)
    except Exception:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR,
            reason_id=ReasonId.ERR_INTERNAL,
        )
    if earlier_denies:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_EARLIER_GATE_DENIED,
            reason_id=earlier_denies[0],
            dominant_reason_ids=earlier_denies,
        )

    if not _is_sha256_hex(expected_context_hash) or not _expected_policy_is_valid(expected_policy):
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_EXPECTED_POLICY_INVALID,
            reason_id=ReasonId.DENY_POLICY,
        )
    if type(raw_evidence) is not bytes:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_UNSUPPORTED_INPUT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )

    try:
        evidence = parse_ai_gateway_json_v1(raw_evidence)
        if type(evidence) is not dict:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
                ReasonId.DENY_SCHEMA_INVALID,
            )
        if _contains_forbidden_authority_field(evidence):
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
                ReasonId.DENY_ADAPTER_INVALID,
            )
        if evidence.get("evidence_version") != ADAMANTINE_AI_GATEWAY_EVIDENCE_V2:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
                ReasonId.DENY_VERSION_MISMATCH,
            )
        if "policy_binding" not in evidence or evidence.get("policy_binding") is None:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_MISSING_POLICY_BINDING,
                ReasonId.DENY_POLICY,
            )

        evidence = _require_exact_object(evidence, _EVIDENCE_FIELDS)
        if evidence["source"] != ADAMANTINE_AI_GATEWAY_SOURCE:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
                ReasonId.DENY_VERSION_MISMATCH,
            )
        if evidence["evidence_role"] != ADAMANTINE_EVIDENCE_ROLE:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
                ReasonId.DENY_ADAPTER_INVALID,
            )
        if evidence["expected_context_hash"] != expected_context_hash:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
                ReasonId.DENY_POLICY,
            )

        handoff = _validate_handoff(evidence["handoff"])
        receipt = _validate_receipt(evidence["receipt"])
        binding = _validate_policy_binding(evidence["policy_binding"])
        receipt_hash, handoff_hash = _validate_artifact_chain(
            handoff=handoff,
            receipt=receipt,
            binding=binding,
            expected_context_hash=expected_context_hash,
        )

        if binding["policy_pack_id"] != expected_policy.policy_pack_id:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_POLICY_ID_MISMATCH,
                ReasonId.DENY_POLICY,
            )
        if binding["policy_pack_version_id"] != expected_policy.policy_pack_version_id:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_POLICY_VERSION_MISMATCH,
                ReasonId.DENY_POLICY,
            )
        if binding["policy_pack_hash"] != expected_policy.policy_pack_hash:
            raise _EvidenceFailure(
                AIGatewayPolicyBoundEvidenceState.DENY_POLICY_HASH_MISMATCH,
                ReasonId.DENY_POLICY,
            )

        if handoff["policy_decision"] == "rejected":
            return _deny(
                state=AIGatewayPolicyBoundEvidenceState.DENY_AI_GATEWAY_REJECTED,
                reason_id=str(handoff["reason_id"]),
                policy_binding_verified=True,
                context_hash=str(handoff["context_hash"]),
                policy_pack_id=str(binding["policy_pack_id"]),
                policy_pack_version_id=str(binding["policy_pack_version_id"]),
                policy_pack_hash=str(binding["policy_pack_hash"]),
                receipt_hash=receipt_hash,
                handoff_hash=handoff_hash,
            )

        return AIGatewayPolicyBoundEvidenceResult(
            source="ai_gateway",
            state=AIGatewayPolicyBoundEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
            outcome="ALLOW_EVIDENCE",
            reason_id=ReasonId.EVIDENCE_OK,
            accepted_as_evidence=True,
            final_approval=False,
            policy_binding_verified=True,
            context_hash=str(handoff["context_hash"]),
            policy_pack_id=str(binding["policy_pack_id"]),
            policy_pack_version_id=str(binding["policy_pack_version_id"]),
            policy_pack_hash=str(binding["policy_pack_hash"]),
            receipt_hash=receipt_hash,
            handoff_hash=handoff_hash,
            dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
        )
    except AIGatewayDuplicateKeyError:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_DUPLICATE_KEY,
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
        )
    except AIGatewayResourceLimitError:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT,
            reason_id=ReasonId.DENY_ADAPTER_INVALID,
        )
    except AIGatewayCanonicalJSONError:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE,
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
        )
    except _EvidenceFailure as exc:
        return _deny(state=exc.state, reason_id=exc.reason_id)
    except Exception:
        return _deny(
            state=AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR,
            reason_id=ReasonId.ERR_INTERNAL,
        )
