from __future__ import annotations

import hashlib
import json
import re
from typing import Any

CONTRACT = "adamantineos.combined_context_hash"
DOMAIN = "ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1"
VERSION = 1
EXPECTED_VALID_HASH = "30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a"

HEX_64 = re.compile(r"^[0-9a-f]{64}$")
ASCII_REF = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
ASCII_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

REQUIRED_FIELDS = frozenset(
    {
        "contract",
        "version",
        "domain",
        "request_id",
        "wallet_context_hash",
        "transaction_context_hash",
        "qid_auth_context_hash",
        "wsqk_posture_context_hash",
        "policy_context_hash",
        "replay_context_ref",
        "shield_receipt_context_hash",
    }
)

HASH_FIELDS = frozenset(
    {
        "wallet_context_hash",
        "transaction_context_hash",
        "qid_auth_context_hash",
        "wsqk_posture_context_hash",
        "policy_context_hash",
        "shield_receipt_context_hash",
    }
)

FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "allow",
        "approved",
        "authority",
        "auto_approve",
        "bypass",
        "broadcast",
        "can_sign",
        "decision",
        "execute",
        "final_approval",
        "force_allow",
        "human_approved",
        "override",
        "sign",
        "trusted",
    }
)

FORBIDDEN_NONDETERMINISTIC_FIELDS = frozenset(
    {
        "created_at",
        "generated_at",
        "timestamp",
        "time",
        "random",
        "randomness",
        "nonce_random",
    }
)


class CombinedContextHashError(ValueError):
    """Fail-closed combined context hash contract violation."""


def load_combined_context_hash_json(raw_json: str) -> dict[str, Any]:
    """Load a combined context hash JSON object while rejecting duplicate keys."""

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise CombinedContextHashError("duplicate key")
            seen.add(key)
            output[key] = value
        return output

    try:
        payload = json.loads(raw_json, object_pairs_hook=reject_duplicate_keys)
    except CombinedContextHashError:
        raise
    except json.JSONDecodeError as exc:
        raise CombinedContextHashError("invalid json") from exc

    if not isinstance(payload, dict):
        raise CombinedContextHashError("payload must be a JSON object")
    return payload


def canonical_combined_context_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes for a validated combined context hash payload."""

    validate_combined_context_hash_payload(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_combined_context_hash(payload: dict[str, Any]) -> str:
    """Compute the deterministic SHA-256 combined context hash."""

    return hashlib.sha256(canonical_combined_context_json_bytes(payload)).hexdigest()


def _validate_ascii_string(value: Any, *, pattern: re.Pattern[str], field: str) -> None:
    if not isinstance(value, str):
        raise CombinedContextHashError(f"invalid {field}")
    if value.strip() != value:
        raise CombinedContextHashError(f"invalid {field}")
    if any(ord(char) < 0x20 or ord(char) > 0x7E for char in value):
        raise CombinedContextHashError(f"invalid {field}")
    if not pattern.fullmatch(value):
        raise CombinedContextHashError(f"invalid {field}")


def validate_combined_context_hash_payload(payload: Any) -> None:
    """Validate the locked AdamantineOS combined context hash contract."""

    if not isinstance(payload, dict):
        raise CombinedContextHashError("payload must be a JSON object")

    field_set = set(payload)
    unknown_fields = field_set - REQUIRED_FIELDS
    missing_fields = REQUIRED_FIELDS - field_set

    if unknown_fields & (FORBIDDEN_AUTHORITY_FIELDS | FORBIDDEN_NONDETERMINISTIC_FIELDS):
        raise CombinedContextHashError("forbidden field present")
    if unknown_fields:
        raise CombinedContextHashError("unknown field present")
    if missing_fields:
        raise CombinedContextHashError("required field missing")

    if payload["contract"] != CONTRACT:
        raise CombinedContextHashError("invalid contract")
    if type(payload["version"]) is not int or payload["version"] != VERSION:
        raise CombinedContextHashError("invalid version")
    if payload["domain"] != DOMAIN:
        raise CombinedContextHashError("invalid domain")

    _validate_ascii_string(payload["request_id"], pattern=ASCII_REQUEST_ID, field="request_id")
    _validate_ascii_string(payload["replay_context_ref"], pattern=ASCII_REF, field="replay_context_ref")

    for field in sorted(HASH_FIELDS):
        value = payload[field]
        if not isinstance(value, str) or not HEX_64.fullmatch(value):
            raise CombinedContextHashError(f"invalid hash field: {field}")
