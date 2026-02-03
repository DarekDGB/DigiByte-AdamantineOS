from __future__ import annotations

import re

from adamantine.v1.contracts.reason_ids import ReasonId


def test_reason_id_values_are_unique() -> None:
    values = [r.value for r in ReasonId]
    assert len(values) == len(set(values))


def test_reason_id_names_are_upper_snake_case() -> None:
    pat = re.compile(r"^[A-Z0-9_]+$")
    for r in ReasonId:
        assert pat.match(r.name), f"bad ReasonId name: {r.name}"


def test_execution_envelope_v1_required_reason_ids_are_present() -> None:
    required = {
        "OK_ALLOW",
        "DENY_SCHEMA_INVALID",
        "DENY_UNKNOWN_FIELD",
        "DENY_VERSION_MISMATCH",
        "DENY_INTENT_UNSUPPORTED",
        "DENY_PAYLOAD_INVALID",
        "DENY_TIMEBOX_INVALID",
        "DENY_TIMEBOX_EXPIRED",
        "DENY_TIMEBOX_NOT_YET_VALID",
        "DENY_TIMEBOX_SKEW_EXCEEDED",
        "DENY_NONCE_INVALID",
        "DENY_NONCE_REPLAY",
        "DENY_NONCE_STORE_ERROR",
        "DENY_AUTHORITY_INVALID",
        "DENY_AUTHORITY_INSUFFICIENT",
        "DENY_POLICY",
        "DENY_EQC",
        "DENY_WSQK",
        "DENY_TVA",
        "DENY_ADAPTER_INVALID",
        "DENY_ADAPTER_UNAVAILABLE",
        "ERR_INTERNAL",
        "ERR_UNHANDLED",
    }
    present = {r.name for r in ReasonId}
    missing = required - present
    assert not missing, f"missing envelope reason ids: {sorted(missing)}"
