from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from adamantine.v1.contracts.combined_context_hash import (
    EXPECTED_VALID_HASH,
    CombinedContextHashError,
    canonical_combined_context_json_bytes,
    compute_combined_context_hash,
    load_combined_context_hash_json,
    validate_combined_context_hash_payload,
)

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures" / "shield_v3_integration"
COMBINED_CONTEXT_HASH_ROOT = FIXTURE_ROOT / "combined_context_hash"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


def _load_json_rejecting_duplicate_keys(path: Path) -> dict[str, Any]:
    return load_combined_context_hash_json(path.read_text(encoding="utf-8"))


def test_manifest_is_level_1_fixture_only_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

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

    validate_combined_context_hash_payload(fixture)
    assert compute_combined_context_hash(fixture) == EXPECTED_VALID_HASH
    assert canonical_combined_context_json_bytes(fixture).decode("utf-8") == (
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

    assert compute_combined_context_hash(fixture) == EXPECTED_VALID_HASH


def test_invalid_combined_context_hash_fixtures_reject_fail_closed() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    invalid_fixture_paths = [
        FIXTURE_ROOT / fixture["path"]
        for fixture in manifest["fixtures"]
        if fixture["expected"] == "REJECT"
    ]

    assert invalid_fixture_paths
    for fixture_path in invalid_fixture_paths:
        with pytest.raises(CombinedContextHashError):
            payload = _load_json_rejecting_duplicate_keys(fixture_path)
            compute_combined_context_hash(payload)


def test_change_detection_fixtures_match_locked_hashes() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    changed_fixtures = [
        fixture
        for fixture in manifest["fixtures"]
        if fixture["reason"] == "COMBINED_CONTEXT_HASH_ACCEPTED_CHANGED_INPUT"
    ]

    assert changed_fixtures
    for fixture in changed_fixtures:
        payload = _load_json_rejecting_duplicate_keys(FIXTURE_ROOT / fixture["path"])
        assert compute_combined_context_hash(payload) == fixture["expected_hash"]
        assert fixture["expected_hash"] != EXPECTED_VALID_HASH


def test_json_loader_rejects_invalid_json_fail_closed() -> None:
    with pytest.raises(CombinedContextHashError, match="invalid json"):
        load_combined_context_hash_json("{")


def test_validator_rejects_non_object_payload_fail_closed() -> None:
    with pytest.raises(CombinedContextHashError, match="payload must be a JSON object"):
        validate_combined_context_hash_payload(["not", "object"])

    with pytest.raises(CombinedContextHashError, match="payload must be a JSON object"):
        load_combined_context_hash_json("[]")


def test_validator_rejects_invalid_contract_and_domain_fail_closed() -> None:
    fixture = _load_json_rejecting_duplicate_keys(
        COMBINED_CONTEXT_HASH_ROOT / "valid_combined_context_hash_v1.json"
    )

    invalid_contract = dict(fixture)
    invalid_contract["contract"] = "wrong.contract"
    with pytest.raises(CombinedContextHashError, match="invalid contract"):
        validate_combined_context_hash_payload(invalid_contract)

    invalid_domain = dict(fixture)
    invalid_domain["domain"] = "WRONG_DOMAIN"
    with pytest.raises(CombinedContextHashError, match="invalid domain"):
        validate_combined_context_hash_payload(invalid_domain)
