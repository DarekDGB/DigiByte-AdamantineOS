from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures" / "shield_v3_integration"
COMBINED_CONTEXT_HASH_ROOT = FIXTURE_ROOT / "combined_context_hash"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"

CONTRACT = "adamantineos.combined_context_hash"
DOMAIN = "ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1"
EXPECTED_VALID_HASH = "30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a"
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
ASCII_REF = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
ASCII_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

REQUIRED_FIELDS = {
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

HASH_FIELDS = {
    "wallet_context_hash",
    "transaction_context_hash",
    "qid_auth_context_hash",
    "wsqk_posture_context_hash",
    "policy_context_hash",
    "shield_receipt_context_hash",
}

FORBIDDEN_AUTHORITY_FIELDS = {
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

FORBIDDEN_NONDETERMINISTIC_FIELDS = {
    "created_at",
    "generated_at",
    "timestamp",
    "time",
    "random",
    "randomness",
    "nonce_random",
}


def _load_json_rejecting_duplicate_keys(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(f"duplicate key: {key}")
            seen.add(key)
            output[key] = value
        return output

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _combined_context_hash(payload: dict[str, Any]) -> str:
    _validate_combined_context_hash_payload(payload)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _validate_ascii_string(value: Any, *, pattern: re.Pattern[str]) -> bool:
    if not isinstance(value, str):
        return False
    if not pattern.fullmatch(value):
        return False
    if value.strip() != value:
        return False
    if any(ord(char) < 0x20 or ord(char) > 0x7E for char in value):
        return False
    return True


def _validate_combined_context_hash_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("combined context hash payload must be a JSON object")

    field_set = set(payload)
    if field_set != REQUIRED_FIELDS:
        unknown = field_set - REQUIRED_FIELDS
        missing = REQUIRED_FIELDS - field_set
        if unknown & (FORBIDDEN_AUTHORITY_FIELDS | FORBIDDEN_NONDETERMINISTIC_FIELDS):
            raise ValueError("forbidden field present")
        if unknown:
            raise ValueError("unknown field present")
        if missing:
            raise ValueError("required field missing")
        raise ValueError("field set mismatch")

    if payload["contract"] != CONTRACT:
        raise ValueError("invalid contract")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ValueError("invalid version")
    if payload["domain"] != DOMAIN:
        raise ValueError("invalid domain")
    if not _validate_ascii_string(payload["request_id"], pattern=ASCII_REQUEST_ID):
        raise ValueError("invalid request_id")
    if not _validate_ascii_string(payload["replay_context_ref"], pattern=ASCII_REF):
        raise ValueError("invalid replay_context_ref")

    for field in HASH_FIELDS:
        value = payload[field]
        if not isinstance(value, str) or not HEX_64.fullmatch(value):
            raise ValueError(f"invalid hash field: {field}")


def test_manifest_is_level_1_fixture_only_contract() -> None:
    manifest = _load_json_rejecting_duplicate_keys(MANIFEST_PATH)

    assert manifest["contract"] == "adamantineos.shield_v3_fixture_negative_test_plan"
    assert manifest["version"] == 1
    assert manifest["adamantineos_boundary"] == "v2.2.0"
    assert manifest["external_shield_baseline"] == "v3.2.0"
    assert manifest["level"] == 1
    assert manifest["fixtures"]

    for fixture in manifest["fixtures"]:
        fixture_path = FIXTURE_ROOT / fixture["path"]
        assert fixture_path.is_file(), fixture["path"]
        assert fixture["category"] == "combined_context_hash"
        assert fixture["expected"] in {"ACCEPT", "REJECT"}
        assert "ALLOW" not in fixture["expected"]


def test_valid_combined_context_hash_fixture_matches_locked_vector() -> None:
    fixture = _load_json_rejecting_duplicate_keys(
        COMBINED_CONTEXT_HASH_ROOT / "valid_combined_context_hash_v1.json"
    )

    assert _combined_context_hash(fixture) == EXPECTED_VALID_HASH
    assert _canonical_json_bytes(fixture).decode("utf-8") == (
        '{"contract":"adamantineos.combined_context_hash",'
        '"domain":"ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1",'
        '"policy_context_hash":"5555555555555555555555555555555555555555555555555555555555555555",'
        '"qid_auth_context_hash":"3333333333333333333333333333333333333333333333333333333333333333",'
        '"replay_context_ref":"replay:v1:nonce:000001",'
        '"request_id":"req-000001",'
        '"shield_receipt_context_hash":"6666666666666666666666666666666666666666666666666666666666666666",'
        '"transaction_context_hash":"2222222222222222222222222222222222222222222222222222222222222222",'
        '"version":1,'
        '"wallet_context_hash":"1111111111111111111111111111111111111111111111111111111111111111",'
        '"wsqk_posture_context_hash":"4444444444444444444444444444444444444444444444444444444444444444"}'
    )


def test_reordered_valid_fixture_produces_same_hash() -> None:
    fixture = _load_json_rejecting_duplicate_keys(
        COMBINED_CONTEXT_HASH_ROOT / "valid_combined_context_hash_v1_reordered.json"
    )

    assert _combined_context_hash(fixture) == EXPECTED_VALID_HASH


def test_invalid_combined_context_hash_fixtures_reject_fail_closed() -> None:
    manifest = _load_json_rejecting_duplicate_keys(MANIFEST_PATH)
    invalid_fixture_paths = [
        FIXTURE_ROOT / fixture["path"]
        for fixture in manifest["fixtures"]
        if fixture["expected"] == "REJECT"
    ]

    assert invalid_fixture_paths
    for fixture_path in invalid_fixture_paths:
        try:
            payload = _load_json_rejecting_duplicate_keys(fixture_path)
            _combined_context_hash(payload)
        except ValueError:
            continue
        raise AssertionError(f"fixture must reject fail-closed: {fixture_path}")


def test_change_detection_fixtures_match_locked_hashes() -> None:
    manifest = _load_json_rejecting_duplicate_keys(MANIFEST_PATH)
    changed_fixtures = [
        fixture
        for fixture in manifest["fixtures"]
        if fixture["reason"] == "COMBINED_CONTEXT_HASH_ACCEPTED_CHANGED_INPUT"
    ]

    assert changed_fixtures
    for fixture in changed_fixtures:
        payload = _load_json_rejecting_duplicate_keys(FIXTURE_ROOT / fixture["path"])
        assert _combined_context_hash(payload) == fixture["expected_hash"]
        assert fixture["expected_hash"] != EXPECTED_VALID_HASH
