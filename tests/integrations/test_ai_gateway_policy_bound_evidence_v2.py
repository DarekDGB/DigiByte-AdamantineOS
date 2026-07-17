from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, dataclass, fields
import hashlib
import json
from pathlib import Path

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations import (
    AIGatewayExpectedPolicyV1,
    AIGatewayPolicyBoundEvidenceResult,
    AIGatewayPolicyBoundEvidenceState,
    consume_ai_gateway_policy_bound_evidence_v2,
)
from adamantine.v1.integrations import ai_gateway_policy_bound_evidence_v2 as consumer


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "ai_gateway_external_baseline"
    / "ai_gateway_adamantine_evidence_v2.json"
)
EVIDENCE_FIXTURE_SHA256 = (
    "deaa523cd28a1f8d2a97dbf681bfbc94ee7b682aa62d5c3c5747fbe244e13843"
)
EXPECTED_CONTEXT_HASH = (
    "dab7c6a2b93454e259894a9e0d68da7370d03626fb7154020362aeb756d436d6"
)
EXPECTED_POLICY_ID = "d2-policy"
EXPECTED_POLICY_VERSION_ID = "v1"
EXPECTED_POLICY_HASH = (
    "87d3c7f9fcfe8d7f84648c272b5793b0a15cf634f1a02536d606e88232f131fa"
)
EXPECTED_RECEIPT_HASH = (
    "ba04340d93e658eb243fef7f060c16b52aeecbc4a100806931f8b8463c0d41e6"
)
EXPECTED_HANDOFF_HASH = (
    "77f576ef98296e59e45f9bc104165a77def827ae7aa9a1368ca313321533462b"
)


def _fixture_bytes() -> bytes:
    raw = EVIDENCE_FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EVIDENCE_FIXTURE_SHA256
    return raw


def _evidence() -> dict:
    value = json.loads(_fixture_bytes().decode("ascii"))
    assert type(value) is dict
    return value


def _wire(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _independent_hash(value: object) -> str:
    return hashlib.sha256(_wire(value)).hexdigest()


def _policy(**overrides: str) -> AIGatewayExpectedPolicyV1:
    values = {
        "policy_pack_id": EXPECTED_POLICY_ID,
        "policy_pack_version_id": EXPECTED_POLICY_VERSION_ID,
        "policy_pack_hash": EXPECTED_POLICY_HASH,
    }
    values.update(overrides)
    return AIGatewayExpectedPolicyV1(**values)


def _consume(
    value: object | None = None,
    *,
    raw: bytes | object | None = None,
    expected_context_hash: str = EXPECTED_CONTEXT_HASH,
    expected_policy: object | None = None,
    prior_gate_results: object = None,
) -> AIGatewayPolicyBoundEvidenceResult:
    if raw is None:
        raw = _fixture_bytes() if value is None else _wire(value)
    return consume_ai_gateway_policy_bound_evidence_v2(
        raw,  # type: ignore[arg-type]
        expected_context_hash=expected_context_hash,
        expected_policy=_policy() if expected_policy is None else expected_policy,  # type: ignore[arg-type]
        prior_gate_results=prior_gate_results,  # type: ignore[arg-type]
    )


def _assert_deny(
    result: AIGatewayPolicyBoundEvidenceResult,
    state: AIGatewayPolicyBoundEvidenceState,
) -> None:
    assert result.state is state
    assert result.outcome == "DENY"
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.policy_binding_verified is False


def _coherent_rejection(reason_id: str = "POLICY_DENIED") -> dict:
    value = _evidence()
    value["handoff"]["policy_decision"] = "rejected"
    value["handoff"]["reason_id"] = reason_id
    value["receipt"]["policy_decision"] = "rejected"
    value["receipt"]["reason_id"] = reason_id
    value["policy_binding"]["handoff_hash"] = _independent_hash(value["handoff"])
    value["policy_binding"]["receipt_hash"] = _independent_hash(value["receipt"])
    return value


def test_external_fixture_is_pinned_and_valid_binding_remains_evidence_only() -> None:
    result = _consume()

    assert result == AIGatewayPolicyBoundEvidenceResult(
        source="ai_gateway",
        state=AIGatewayPolicyBoundEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS,
        outcome="ALLOW_EVIDENCE",
        reason_id=ReasonId.EVIDENCE_OK,
        accepted_as_evidence=True,
        final_approval=False,
        policy_binding_verified=True,
        context_hash=EXPECTED_CONTEXT_HASH,
        policy_pack_id=EXPECTED_POLICY_ID,
        policy_pack_version_id=EXPECTED_POLICY_VERSION_ID,
        policy_pack_hash=EXPECTED_POLICY_HASH,
        receipt_hash=EXPECTED_RECEIPT_HASH,
        handoff_hash=EXPECTED_HANDOFF_HASH,
        dominant_reason_ids=(ReasonId.EVIDENCE_OK.value,),
    )
    assert tuple(field.name for field in fields(result)) == (
        "source",
        "state",
        "outcome",
        "reason_id",
        "accepted_as_evidence",
        "final_approval",
        "policy_binding_verified",
        "context_hash",
        "policy_pack_id",
        "policy_pack_version_id",
        "policy_pack_hash",
        "receipt_hash",
        "handoff_hash",
        "dominant_reason_ids",
    )
    with pytest.raises(FrozenInstanceError):
        result.final_approval = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        _policy().policy_pack_id = "replacement"  # type: ignore[misc]


@dataclass
class _PriorGate:
    outcome: str
    reason_id: ReasonId | str | None


def test_all_earlier_denials_dominate_even_malformed_or_downgraded_wire() -> None:
    prior = [
        _PriorGate("ALLOW_EVIDENCE", ReasonId.EVIDENCE_OK),
        _PriorGate("DENY", ReasonId.DENY_NONCE_REPLAY),
        {"outcome": "DENY", "reason_id": "DENY_EXTERNAL_REPLAY"},
        {"outcome": "DENY"},
    ]
    result = _consume(
        raw=b'{"evidence_version":"v1","x":',
        expected_context_hash="invalid",
        expected_policy="invalid",
        prior_gate_results=prior,
    )

    assert result.state is AIGatewayPolicyBoundEvidenceState.DENY_EARLIER_GATE_DENIED
    assert result.outcome == "DENY"
    assert result.reason_id == ReasonId.DENY_NONCE_REPLAY.value
    assert result.dominant_reason_ids == (
        ReasonId.DENY_NONCE_REPLAY.value,
        "DENY_EXTERNAL_REPLAY",
        ReasonId.DENY_POLICY.value,
    )
    assert result.final_approval is False


def test_exact_tuple_of_valid_allow_evidence_results_can_continue() -> None:
    prior = (
        _PriorGate("ALLOW_EVIDENCE", ReasonId.EVIDENCE_OK),
        {"outcome": "ALLOW_EVIDENCE", "reason_id": "EVIDENCE_OK"},
    )
    result = _consume(prior_gate_results=prior)
    assert result.state is AIGatewayPolicyBoundEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.final_approval is False


class _ExplodingPriorGate:
    @property
    def outcome(self) -> str:
        raise RuntimeError("hostile prior result")


class _ConflictingPriorGate(dict):
    @property
    def outcome(self) -> str:
        return "DENY"

    @property
    def reason_id(self) -> str:
        return "MUST_DOMINATE"


class _OutcomeString(str):
    pass


def test_hostile_or_noniterable_prior_gate_input_fails_closed() -> None:
    for prior in (
        [_ExplodingPriorGate()],
        object(),
        {"outcome": "DENY", "reason_id": "MUST_NOT_BE_IGNORED"},
        [object()],
        [
            _ConflictingPriorGate(
                outcome="ALLOW_EVIDENCE",
                reason_id="HIDDEN_MAPPING_ALLOW",
            )
        ],
    ):
        result = _consume(prior_gate_results=prior)
        _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR)
        assert result.reason_id is ReasonId.ERR_INTERNAL


@pytest.mark.parametrize(
    "prior",
    [
        [{"outcome": None}],
        [{"outcome": 1}],
        [{"outcome": "ALLOW"}],
        [{"outcome": "UNKNOWN"}],
        [{"outcome": _OutcomeString("DENY"), "reason_id": "HIDDEN_DENY"}],
        [_PriorGate("ALLOW", ReasonId.EVIDENCE_OK)],
        [_PriorGate("UNKNOWN", ReasonId.EVIDENCE_OK)],
    ],
)
def test_malformed_prior_gate_outcomes_cannot_be_ignored(prior: list[object]) -> None:
    result = _consume(prior_gate_results=prior)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR)
    assert result.reason_id is ReasonId.ERR_INTERNAL


@pytest.mark.parametrize(
    "expected_context_hash,expected_policy",
    [
        ("short", _policy()),
        ("A" * 64, _policy()),
        (EXPECTED_CONTEXT_HASH, object()),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_id=" ")),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_id="x" * 257)),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_id=chr(0xD800))),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_version_id="")),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_version_id="x" * 257)),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_version_id=chr(0xDFFF))),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_hash="A" * 64)),
        (EXPECTED_CONTEXT_HASH, _policy(policy_pack_hash="short")),
    ],
)
def test_invalid_verifier_controlled_expectations_fail_closed(
    expected_context_hash: str,
    expected_policy: object,
) -> None:
    result = _consume(
        expected_context_hash=expected_context_hash,
        expected_policy=expected_policy,
    )
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_EXPECTED_POLICY_INVALID)


def test_expected_policy_subclass_is_not_an_exact_trusted_configuration() -> None:
    class _PolicySubclass(AIGatewayExpectedPolicyV1):
        pass

    result = _consume(
        expected_policy=_PolicySubclass(
            EXPECTED_POLICY_ID,
            EXPECTED_POLICY_VERSION_ID,
            EXPECTED_POLICY_HASH,
        )
    )
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_EXPECTED_POLICY_INVALID)


@pytest.mark.parametrize("raw", ["{}", bytearray(b"{}"), memoryview(b"{}"), {}])
def test_only_exact_raw_bytes_are_accepted(raw: object) -> None:
    result = _consume(raw=raw)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_UNSUPPORTED_INPUT)


@pytest.mark.parametrize(
    "raw,state",
    [
        (b"{", AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE),
        (b"\xff", AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE),
        (b"\xef\xbb\xbf{}", AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE),
        (b'{"n":1.0}', AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE),
        (b'{"n":NaN}', AIGatewayPolicyBoundEvidenceState.DENY_INVALID_WIRE),
        (b"null", AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        (b'{"a":1,"a":2}', AIGatewayPolicyBoundEvidenceState.DENY_DUPLICATE_KEY),
        (
            b'{"outer":{"a":1,"a":2}}',
            AIGatewayPolicyBoundEvidenceState.DENY_DUPLICATE_KEY,
        ),
        (
            b'{"a":1,"\\u0061":2}',
            AIGatewayPolicyBoundEvidenceState.DENY_DUPLICATE_KEY,
        ),
        (
            str(1 << 4_096).encode("ascii"),
            AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT,
        ),
        (
            _wire("x" * 10_001),
            AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT,
        ),
        (
            b" " * 1_048_577,
            AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT,
        ),
    ],
)
def test_raw_wire_attacks_fail_closed(
    raw: bytes,
    state: AIGatewayPolicyBoundEvidenceState,
) -> None:
    result = _consume(raw=raw)
    _assert_deny(result, state)


def test_v1_or_missing_binding_never_falls_back_to_the_legacy_consumer() -> None:
    legacy_bundle = {
        "handoff": _evidence()["handoff"],
        "receipt": _evidence()["receipt"],
    }
    result = _consume(legacy_bundle)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH)

    for missing in (None, "absent"):
        value = _evidence()
        if missing is None:
            value["policy_binding"] = None
        else:
            del value["policy_binding"]
        result = _consume(value)
        _assert_deny(
            result,
            AIGatewayPolicyBoundEvidenceState.DENY_MISSING_POLICY_BINDING,
        )


@pytest.mark.parametrize(
    "mutate,state",
    [
        (
            lambda value: value.update(evidence_version="adamantine_ai_gateway_evidence_v1"),
            AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
        ),
        (
            lambda value: value.update(source="unknown-producer"),
            AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH,
        ),
        (
            lambda value: value.update(evidence_role="execution_authority"),
            AIGatewayPolicyBoundEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD,
        ),
        (
            lambda value: value.update(expected_context_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
        ),
        (
            lambda value: value.update(extra="unknown"),
            AIGatewayPolicyBoundEvidenceState.DENY_UNKNOWN_FIELD,
        ),
        (
            lambda value: value.pop("source"),
            AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID,
        ),
    ],
)
def test_outer_contract_confusion_fails_closed(mutate, state) -> None:
    value = _evidence()
    mutate(value)
    result = _consume(value)
    _assert_deny(result, state)


@pytest.mark.parametrize(
    "field",
    (
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
    ),
)
def test_every_authority_shaped_field_name_is_rejected(field: str) -> None:
    value = _evidence()
    value[field] = False
    result = _consume(value)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD)


@pytest.mark.parametrize(
    "extra",
    [
        {"nested": {"override": False}},
        {"nested": [{"grant_execution": True}]},
    ],
)
def test_authority_shaped_fields_are_rejected_at_nested_depths(extra: dict) -> None:
    value = _evidence()
    value.update(extra)
    result = _consume(value)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_HIDDEN_AUTHORITY_FIELD)


@pytest.mark.parametrize(
    "artifact,mutate,state",
    [
        ("handoff", lambda value: value.update(extra="x"), AIGatewayPolicyBoundEvidenceState.DENY_UNKNOWN_FIELD),
        ("handoff", lambda value: value.pop("task_type"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("handoff", lambda value: value.update(handoff_version="v0"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("handoff", lambda value: value.update(adapter=" "), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("handoff", lambda value: value.update(task_type=1), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("handoff", lambda value: value.update(policy_decision="allow"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("handoff", lambda value: value.update(reason_id="UNKNOWN_REASON"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("handoff", lambda value: value.update(envelope_hash="A" * 64), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("receipt", lambda value: value.update(extra="x"), AIGatewayPolicyBoundEvidenceState.DENY_UNKNOWN_FIELD),
        ("receipt", lambda value: value.pop("gateway_version"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("receipt", lambda value: value.update(receipt_version="v0"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("receipt", lambda value: value.update(created_from_contract="v0"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("receipt", lambda value: value.update(determinism_profile="other-profile"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("receipt", lambda value: value.update(adapter_version=""), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("receipt", lambda value: value.update(policy_decision="allow"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("receipt", lambda value: value.update(reason_id="UNKNOWN_REASON"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("receipt", lambda value: value.update(output_hash="short"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("policy_binding", lambda value: value.update(extra="x"), AIGatewayPolicyBoundEvidenceState.DENY_UNKNOWN_FIELD),
        ("policy_binding", lambda value: value.pop("receipt_hash"), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("policy_binding", lambda value: value.update(policy_binding_version="v0"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("policy_binding", lambda value: value.update(policy_pack_contract_version="other"), AIGatewayPolicyBoundEvidenceState.DENY_VERSION_MISMATCH),
        ("policy_binding", lambda value: value.update(policy_pack_id=" "), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("policy_binding", lambda value: value.update(policy_pack_version_id="x" * 257), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
        ("policy_binding", lambda value: value.update(policy_pack_hash="A" * 64), AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID),
    ],
)
def test_artifact_schema_profile_and_algorithm_confusion_fail_closed(
    artifact: str,
    mutate,
    state: AIGatewayPolicyBoundEvidenceState,
) -> None:
    value = _evidence()
    mutate(value[artifact])
    result = _consume(value)
    _assert_deny(result, state)


@pytest.mark.parametrize("artifact", ["handoff", "receipt", "policy_binding"])
def test_artifacts_must_be_exact_objects(artifact: str) -> None:
    value = _evidence()
    value[artifact] = []
    result = _consume(value)
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID)


@pytest.mark.parametrize(
    "mutate,state",
    [
        (
            lambda value: value["handoff"].update(context_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
        ),
        (
            lambda value: value["handoff"].update(envelope_hash="b" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_CONTEXT_HASH_MISMATCH,
        ),
        (
            lambda value: value["receipt"].update(adapter_id="wallet"),
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
        ),
        (
            lambda value: value["receipt"].update(envelope_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
        ),
        (
            lambda value: value["receipt"].update(output_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
        ),
        (
            lambda value: value["receipt"].update(policy_decision="rejected", reason_id="POLICY_DENIED"),
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
        ),
        (
            lambda value: (
                value["handoff"].update(
                    policy_decision="rejected",
                    reason_id="POLICY_DENIED",
                ),
                value["receipt"].update(
                    policy_decision="rejected",
                    reason_id="UNSUPPORTED_TASK",
                ),
            ),
            AIGatewayPolicyBoundEvidenceState.DENY_RECEIPT_MISMATCH,
        ),
        (
            lambda value: value["policy_binding"].update(receipt_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_BINDING_HASH_MISMATCH,
        ),
        (
            lambda value: value["policy_binding"].update(handoff_hash="a" * 64),
            AIGatewayPolicyBoundEvidenceState.DENY_BINDING_HASH_MISMATCH,
        ),
    ],
)
def test_context_receipt_and_splice_mismatches_fail_closed(mutate, state) -> None:
    value = _evidence()
    mutate(value)
    result = _consume(value)
    _assert_deny(result, state)


@pytest.mark.parametrize(
    "field,replacement,state",
    [
        ("policy_pack_id", "other-policy", AIGatewayPolicyBoundEvidenceState.DENY_POLICY_ID_MISMATCH),
        ("policy_pack_version_id", "v2", AIGatewayPolicyBoundEvidenceState.DENY_POLICY_VERSION_MISMATCH),
        ("policy_pack_hash", "a" * 64, AIGatewayPolicyBoundEvidenceState.DENY_POLICY_HASH_MISMATCH),
    ],
)
def test_policy_substitution_fails_against_independent_local_expectations(
    field: str,
    replacement: str,
    state: AIGatewayPolicyBoundEvidenceState,
) -> None:
    value = _evidence()
    value["policy_binding"][field] = replacement
    result = _consume(value)
    _assert_deny(result, state)


def test_coherent_gateway_rejection_remains_a_deny_and_cannot_be_rescued() -> None:
    value = _coherent_rejection()
    result = _consume(value)

    assert result.state is AIGatewayPolicyBoundEvidenceState.DENY_AI_GATEWAY_REJECTED
    assert result.outcome == "DENY"
    assert result.reason_id == "POLICY_DENIED"
    assert result.accepted_as_evidence is False
    assert result.final_approval is False
    assert result.policy_binding_verified is True
    assert result.context_hash == EXPECTED_CONTEXT_HASH
    assert result.policy_pack_id == EXPECTED_POLICY_ID
    assert result.policy_pack_version_id == EXPECTED_POLICY_VERSION_ID
    assert result.policy_pack_hash == EXPECTED_POLICY_HASH
    assert result.receipt_hash == value["policy_binding"]["receipt_hash"]
    assert result.handoff_hash == value["policy_binding"]["handoff_hash"]
    assert result.dominant_reason_ids == ("POLICY_DENIED",)


@pytest.mark.parametrize("reason_id", ["ACCEPTED", "UNKNOWN_REASON", ""])
def test_unknown_or_contradictory_rejected_reason_semantics_fail_closed(
    reason_id: str,
) -> None:
    result = _consume(_coherent_rejection(reason_id))
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_SCHEMA_INVALID)


def test_binding_specific_byte_ceiling_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(consumer, "MAX_POLICY_BINDING_BYTES", 1)
    result = _consume()
    _assert_deny(result, AIGatewayPolicyBoundEvidenceState.DENY_RESOURCE_LIMIT)


def test_current_binding_field_caps_remain_below_defensive_byte_ceiling() -> None:
    maximum_scalar_id = chr(0x10FFFF) * consumer.MAX_POLICY_ID_SCALARS
    value = _evidence()
    value["policy_binding"]["policy_pack_id"] = maximum_scalar_id
    value["policy_binding"]["policy_pack_version_id"] = maximum_scalar_id
    expected = _policy(
        policy_pack_id=maximum_scalar_id,
        policy_pack_version_id=maximum_scalar_id,
    )

    binding_bytes = consumer.canonical_ai_gateway_json_v1_bytes(
        value["policy_binding"]
    )
    assert len(binding_bytes) == 2_451
    assert len(binding_bytes) < consumer.MAX_POLICY_BINDING_BYTES

    result = _consume(value, expected_policy=expected)
    assert result.state is AIGatewayPolicyBoundEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.final_approval is False


def test_unexpected_parser_canonicalizer_or_hash_exceptions_fail_closed(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("hostile backend details must not escape")

    monkeypatch.setattr(consumer, "parse_ai_gateway_json_v1", explode)
    parsed = _consume()
    _assert_deny(parsed, AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR)
    assert "hostile" not in str(parsed)

    monkeypatch.undo()
    monkeypatch.setattr(consumer, "canonical_ai_gateway_json_v1_bytes", explode)
    canonicalized = _consume()
    _assert_deny(canonicalized, AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR)
    assert "hostile" not in str(canonicalized)

    monkeypatch.undo()
    monkeypatch.setattr(consumer, "_sha256", explode)
    hashed = _consume()
    _assert_deny(hashed, AIGatewayPolicyBoundEvidenceState.DENY_INTERNAL_ERROR)
    assert "hostile" not in str(hashed)


def test_public_integration_exports_are_the_independent_v2_objects() -> None:
    from adamantine.v1 import integrations

    assert integrations.AIGatewayExpectedPolicyV1 is AIGatewayExpectedPolicyV1
    assert (
        integrations.consume_ai_gateway_policy_bound_evidence_v2
        is consume_ai_gateway_policy_bound_evidence_v2
    )
    assert "consume_ai_gateway_policy_bound_evidence_v2" in integrations.__all__
    assert "normalize_ai_gateway_policy_evidence" in integrations.__all__


def test_consumer_has_no_gateway_qid_shield_or_internal_policy_dependency() -> None:
    source_path = (
        REPO_ROOT
        / "src"
        / "adamantine"
        / "v1"
        / "integrations"
        / "ai_gateway_policy_bound_evidence_v2.py"
    )
    canonical_path = source_path.with_name("ai_gateway_canonical_json_v1.py")
    imported_modules: set[str] = set()

    for path in (source_path, canonical_path):
        source = path.read_text(encoding="ascii")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            if (
                path == canonical_path
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "json"
                and node.func.attr == "dumps"
            ):
                raise AssertionError("independent canonicalizer called json.dumps")

    assert imported_modules == {
        "__future__",
        "dataclasses",
        "enum",
        "hashlib",
        "json",
        "typing",
        "adamantine.v1.contracts.reason_ids",
        "adamantine.v1.integrations.ai_gateway_canonical_json_v1",
    }
    assert not any(
        module == "ai_gateway" or module.startswith("ai_gateway.")
        for module in imported_modules
    )
    assert not any("qid" in module.lower() for module in imported_modules)
    assert not any("shield" in module.lower() for module in imported_modules)
    assert "adamantine.v1.contracts.policy_pack" not in imported_modules
    consumer_source = source_path.read_text(encoding="ascii")
    assert "normalize_ai_gateway_policy_evidence" not in consumer_source


def test_v2_consumer_cannot_call_the_legacy_v1_normalizer(monkeypatch) -> None:
    from adamantine.v1.integrations import ai_gateway_policy_evidence as legacy

    def explode(*_args, **_kwargs):
        raise AssertionError("legacy V1 fallback was invoked")

    monkeypatch.setattr(legacy, "normalize_ai_gateway_policy_evidence", explode)
    result = _consume()
    assert result.state is AIGatewayPolicyBoundEvidenceState.ALLOW_EVIDENCE_CONTINUE_CHECKS
    assert result.final_approval is False
