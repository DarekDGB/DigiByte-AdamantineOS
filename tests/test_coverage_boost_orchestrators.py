from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution import orchestrator_v1 as o1
from adamantine.v1.execution import orchestrator_v2 as o2


def test_orchestrator_v1_reason_parsing_is_fail_closed() -> None:
    assert o1._reason_from_message("DENY_POLICY") == ReasonId.DENY_POLICY
    assert o1._reason_from_message("NOT_A_REASON") == ReasonId.DENY_SCHEMA_INVALID


def test_orchestrator_v2_reason_parsing_and_coercion_paths() -> None:
    assert o2._reason_from_message("DENY_POLICY") == ReasonId.DENY_POLICY
    assert o2._reason_from_message("NOT_A_REASON") == ReasonId.DENY_SCHEMA_INVALID

    assert o2._coerce_reason_id(ReasonId.DENY_POLICY) == ReasonId.DENY_POLICY
    assert o2._coerce_reason_id("DENY_POLICY") == ReasonId.DENY_POLICY
    assert o2._coerce_reason_id("") == ReasonId.DENY_SCHEMA_INVALID
    assert o2._coerce_reason_id(None) == ReasonId.DENY_SCHEMA_INVALID
    assert o2._coerce_reason_id(123) == ReasonId.DENY_SCHEMA_INVALID


def test_orchestrator_extract_fields_filters_non_strings_and_requires_context() -> None:
    # _extract_fields reads payload["context"]["fields"] (not payload["fields"])
    payload = {"context": {"fields": {"ok": "v", "empty": "", "nonstr": 123}}}

    # Non-string values are dropped; empty string is still a string so it remains.
    assert o2._extract_fields(payload) == {"ok": "v", "empty": ""}

    # Missing / wrong-shaped context fails closed.
    assert o2._extract_fields({"fields": {"ok": "v"}}) is None
    assert o2._extract_fields({"context": "nope"}) is None
    assert o2._extract_fields({"context": {"fields": "nope"}}) is None
    assert o2._extract_fields({}) is None


def test_orchestrator_require_mapping_behavior() -> None:
    assert o2._require_mapping({"a": 1}) == {"a": 1}
    assert o2._require_mapping(None) is None
    assert o2._require_mapping([]) is None


def test_orchestrator_v2_protected_call_requested_paths() -> None:
    assert o2._protected_call_requested(None) is False
    assert o2._protected_call_requested({}) is False
    assert o2._protected_call_requested({"wsqk": {"proof": "x"}}) is True


def test_orchestrator_v2_map_shield_adapter_reason_is_explicit() -> None:
    assert o2._map_shield_adapter_reason(ReasonId.DENY_ADAPTER_INVALID) == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert o2._map_shield_adapter_reason(ReasonId.DENY_VERSION_MISMATCH) == ReasonId.EQC_INVALID_SHIELD_BUNDLE
    assert o2._map_shield_adapter_reason(ReasonId.UNKNOWN_EXTERNAL_REASON) == ReasonId.UNKNOWN_EXTERNAL_REASON
