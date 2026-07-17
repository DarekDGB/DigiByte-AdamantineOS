from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest

from adamantine.v1.integrations import ai_gateway_canonical_json_v1 as canonical
from adamantine.v1.integrations.ai_gateway_canonical_json_v1 import (
    AI_GATEWAY_CANONICAL_JSON_V1,
    AIGatewayCanonicalJSONError,
    AIGatewayDuplicateKeyError,
    AIGatewayResourceLimitError,
    canonical_ai_gateway_json_v1_bytes,
    parse_ai_gateway_json_v1,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "ai_gateway_external_baseline"
    / "ai_gateway_canonical_json_v1_vectors.json"
)
FIXTURE_SHA256 = "b14b240cd3f0bd5c9c8e7a55698a92609bcbf5ebb19dfe913514dad8802b4733"
EXPECTED_VECTOR_IDS = {
    "golden_vectors": (
        "null",
        "false",
        "true",
        "zero",
        "one",
        "negative-one",
        "ascii-key-order",
        "empty-key",
        "empty-values-and-nesting",
        "quote",
        "backslash",
        "raw-solidus",
        "short-controls",
        "other-controls-lowercase-hex",
        "del-u007f",
        "c1-u0080-u009f",
        "raw-non-ascii",
        "raw-line-separators",
        "astral-value",
        "astral-key",
        "bmp-before-astral-key-order",
        "nfc-e-acute",
        "nfd-e-acute",
        "array-order",
    ),
    "equivalence_pairs": (
        "object-order",
        "solidus-escape",
        "newline-short-vs-unicode",
        "tab-short-vs-unicode",
        "bmp-raw-vs-unicode",
        "astral-raw-vs-surrogate-pair",
        "insignificant-wire-whitespace",
        "negative-zero-integer",
    ),
    "injective_pairs": (
        "true-vs-one",
        "false-vs-zero",
        "nfc-vs-nfd",
        "array-order",
        "empty-array-vs-object",
        "empty-string-vs-null",
        "del-scalar-vs-six-literal-characters",
        "empty-key-vs-nonempty-key",
        "astral-vs-bmp",
        "nested-empty-shapes",
    ),
    "rejected_wire_vectors": (
        "duplicate-top-level",
        "duplicate-nested",
        "duplicate-after-escape-decoding",
        "float-zero",
        "negative-float-zero",
        "float-exponent",
        "nan",
        "infinity",
        "negative-infinity",
        "lone-high-surrogate",
        "lone-low-surrogate",
        "invalid-utf8",
        "utf8-bom",
        "trailing-second-value",
        "plus-integer",
        "leading-zero-integer",
        "unescaped-line-feed",
    ),
    "boundary_vectors": (
        "positive-4096-bit",
        "negative-4096-bit",
        "positive-4097-bit",
        "string-10000-astral-scalars",
        "string-10001-astral-scalars",
        "key-10000-astral-scalars",
        "key-10001-astral-scalars",
        "depth-10",
        "depth-11",
        "array-1000-items",
        "array-1001-items",
        "object-1000-keys",
        "object-1001-keys",
        "nodes-20000",
        "nodes-20001",
        "canonical-bytes-1048576",
        "canonical-bytes-1048577",
    ),
}


def _fixture() -> dict[str, Any]:
    value = json.loads(FIXTURE_PATH.read_text(encoding="ascii"))
    assert type(value) is dict
    return value


def _case_value(case: dict[str, Any], *, prefix: str = "") -> Any:
    value_field = f"{prefix}value"
    wire_field = f"{prefix}wire_utf8_hex"
    if value_field in case:
        return case[value_field]
    return parse_ai_gateway_json_v1(bytes.fromhex(case[wire_field]))


def _build_boundary_value(case: dict[str, Any]) -> Any:
    """Construct governed boundary inputs without importing Gateway code."""

    kind = case["kind"]
    if kind == "integer_bits":
        value = 1 << (int(case["bits"]) - 1)
        return -value if case.get("negative") else value
    if kind == "string_repeat":
        return chr(int(case["scalar_codepoint"], 16)) * int(case["count"])
    if kind == "key_repeat":
        scalar = chr(int(case["scalar_codepoint"], 16))
        return {scalar * int(case["count"]): 0}
    if kind == "nested_depth":
        value: Any = 0
        for _ in range(int(case["wrappers"])):
            value = [value]
        return value
    if kind == "list_items":
        return [0] * int(case["count"])
    if kind == "object_keys":
        return {f"k{index:04d}": 0 for index in range(int(case["count"]))}
    if kind == "node_budget":
        counts = [int(case["default_items"])] * int(case["sublist_count"])
        if "last_items" in case:
            counts[-1] = int(case["last_items"])
        return [[0] * count for count in counts]
    if kind == "canonical_bytes_array":
        values = [
            "x" * int(case["full_string_length"])
            for _ in range(int(case["full_string_count"]))
        ]
        return values + ["x" * int(case["tail_string_length"])]
    raise AssertionError(f"unrecognized fixture boundary kind: {kind}")


def test_frozen_portable_fixture_identity_and_exact_inventory() -> None:
    fixture_bytes = FIXTURE_PATH.read_bytes()
    fixture = _fixture()

    assert AI_GATEWAY_CANONICAL_JSON_V1 == "ai_gateway_canonical_json_v1"
    assert fixture_bytes.isascii()
    assert hashlib.sha256(fixture_bytes).hexdigest() == FIXTURE_SHA256
    assert fixture["profile"] == AI_GATEWAY_CANONICAL_JSON_V1
    assert fixture["hash_algorithm"] == "sha256"
    assert tuple(fixture["required_vector_ids"]) == tuple(EXPECTED_VECTOR_IDS)

    total = 0
    for section, expected_ids in EXPECTED_VECTOR_IDS.items():
        actual_ids = tuple(case["id"] for case in fixture[section])
        declared_ids = tuple(fixture["required_vector_ids"][section])
        assert actual_ids == expected_ids
        assert declared_ids == expected_ids
        assert len(actual_ids) == len(set(actual_ids))
        total += len(actual_ids)

    assert total == 76
    assert tuple(map(len, EXPECTED_VECTOR_IDS.values())) == (24, 8, 10, 17, 17)


def test_frozen_golden_bytes_and_hashes_match_independent_consumer() -> None:
    for case in _fixture()["golden_vectors"]:
        expected = bytes.fromhex(case["expected_canonical_utf8_hex"])
        actual = canonical_ai_gateway_json_v1_bytes(case["value"])

        assert actual == expected, case["id"]
        assert hashlib.sha256(actual).hexdigest() == case["expected_sha256"]


def test_wire_equivalence_pairs_canonicalize_to_the_same_frozen_bytes() -> None:
    for case in _fixture()["equivalence_pairs"]:
        expected = bytes.fromhex(case["expected_canonical_utf8_hex"])
        left = canonical_ai_gateway_json_v1_bytes(_case_value(case, prefix="left_"))
        right = canonical_ai_gateway_json_v1_bytes(_case_value(case, prefix="right_"))

        assert left == expected, case["id"]
        assert right == expected, case["id"]
        assert hashlib.sha256(left).hexdigest() == case["expected_sha256"]


def test_injective_pairs_have_frozen_distinct_bytes_and_hashes() -> None:
    for case in _fixture()["injective_pairs"]:
        left_expected = bytes.fromhex(case["left_expected_canonical_utf8_hex"])
        right_expected = bytes.fromhex(case["right_expected_canonical_utf8_hex"])
        left = canonical_ai_gateway_json_v1_bytes(_case_value(case, prefix="left_"))
        right = canonical_ai_gateway_json_v1_bytes(_case_value(case, prefix="right_"))

        assert left == left_expected, case["id"]
        assert right == right_expected, case["id"]
        assert left != right, case["id"]
        assert hashlib.sha256(left).hexdigest() == case["left_expected_sha256"]
        assert hashlib.sha256(right).hexdigest() == case["right_expected_sha256"]


def test_all_rejected_wire_vectors_fail_closed() -> None:
    for case in _fixture()["rejected_wire_vectors"]:
        with pytest.raises(AIGatewayCanonicalJSONError):
            parse_ai_gateway_json_v1(bytes.fromhex(case["wire_utf8_hex"]))


def test_duplicate_decoded_keys_are_rejected_at_every_depth() -> None:
    duplicate_wires = (
        b'{"a":1,"a":2}',
        b'{"nested":{"a":1,"a":2}}',
        b'{"a":1,"\\u0061":2}',
    )

    for raw in duplicate_wires:
        with pytest.raises(AIGatewayDuplicateKeyError, match="duplicate decoded"):
            parse_ai_gateway_json_v1(raw)


def test_malformed_utf8_bom_numbers_and_trailing_data_are_rejected() -> None:
    failures = (
        b'"\xff"',
        b"\xef\xbb\xbfnull",
        b"0.0",
        b"1e0",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"null true",
        b"+1",
        b"01",
        b'"line\nfeed"',
        b'{"unterminated":',
    )

    for raw in failures:
        with pytest.raises(AIGatewayCanonicalJSONError):
            parse_ai_gateway_json_v1(raw)


def test_every_governed_boundary_vector_matches_frozen_result() -> None:
    for case in _fixture()["boundary_vectors"]:
        value = _build_boundary_value(case)
        if case["expected"] == "reject":
            with pytest.raises(AIGatewayResourceLimitError):
                canonical_ai_gateway_json_v1_bytes(value)
            continue

        actual = canonical_ai_gateway_json_v1_bytes(value)
        assert len(actual) == case["expected_canonical_byte_length"], case["id"]
        assert hashlib.sha256(actual).hexdigest() == case["expected_sha256"]


def test_exact_host_types_non_string_keys_and_cycles_are_rejected() -> None:
    class DictSubclass(dict):
        pass

    class ListSubclass(list):
        pass

    class StringSubclass(str):
        pass

    class IntegerSubclass(int):
        pass

    unsupported = (
        DictSubclass(),
        ListSubclass(),
        StringSubclass("value"),
        IntegerSubclass(1),
        1.0,
        (1,),
        object(),
    )
    for value in unsupported:
        with pytest.raises(AIGatewayCanonicalJSONError, match="unsupported JSON"):
            canonical_ai_gateway_json_v1_bytes(value)

    with pytest.raises(AIGatewayCanonicalJSONError, match="exact string"):
        canonical_ai_gateway_json_v1_bytes({StringSubclass("key"): 1})

    cyclic_list: list[Any] = []
    cyclic_list.append(cyclic_list)
    with pytest.raises(AIGatewayCanonicalJSONError, match="container cycle"):
        canonical_ai_gateway_json_v1_bytes(cyclic_list)

    cyclic_dict: dict[str, Any] = {}
    cyclic_dict["self"] = cyclic_dict
    with pytest.raises(AIGatewayCanonicalJSONError, match="container cycle"):
        canonical_ai_gateway_json_v1_bytes(cyclic_dict)


def test_direct_unicode_and_internal_encoder_defenses_fail_closed() -> None:
    lone_surrogate = chr(0xD800)
    with pytest.raises(AIGatewayCanonicalJSONError, match="invalid Unicode"):
        canonical_ai_gateway_json_v1_bytes(lone_surrogate)
    with pytest.raises(AIGatewayCanonicalJSONError, match="surrogate code point"):
        canonical._encode_string(lone_surrogate)
    with pytest.raises(AIGatewayCanonicalJSONError, match="unsupported JSON"):
        canonical._encode_value(object())


def test_additional_preflight_and_raw_resource_limits_fail_closed() -> None:
    maximum_integer = (1 << canonical.MAX_INTEGER_BITS) - 1
    with pytest.raises(AIGatewayResourceLimitError, match="text preflight"):
        canonical_ai_gateway_json_v1_bytes([maximum_integer] * 1_000)

    with pytest.raises(AIGatewayResourceLimitError, match="text preflight"):
        canonical_ai_gateway_json_v1_bytes(["x" * 10_000] * 105)

    oversized_raw = b" " * (canonical.MAX_RAW_JSON_BYTES + 1)
    with pytest.raises(AIGatewayResourceLimitError, match="raw JSON byte"):
        parse_ai_gateway_json_v1(oversized_raw)

    exact_maximum_raw = b" " * (canonical.MAX_RAW_JSON_BYTES - 4) + b"null"
    assert len(exact_maximum_raw) == canonical.MAX_RAW_JSON_BYTES
    assert parse_ai_gateway_json_v1(exact_maximum_raw) is None

    oversized_integer_wire = str(1 << canonical.MAX_INTEGER_BITS).encode("ascii")
    with pytest.raises(AIGatewayResourceLimitError, match="integer bit"):
        parse_ai_gateway_json_v1(oversized_integer_wire)

    runtime_digit_cap_attack = b"1" * 4_301
    with pytest.raises(AIGatewayResourceLimitError, match="integer bit"):
        parse_ai_gateway_json_v1(runtime_digit_cap_attack)


def test_raw_parser_requires_exact_bytes_and_wraps_dependency_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BytesSubclass(bytes):
        pass

    for raw in ("null", bytearray(b"null"), memoryview(b"null"), BytesSubclass(b"null")):
        with pytest.raises(AIGatewayCanonicalJSONError, match="exact bytes"):
            parse_ai_gateway_json_v1(raw)  # type: ignore[arg-type]

    def fail_loads(*_args: Any, **_kwargs: Any) -> Any:
        raise RecursionError("dependency failure")

    monkeypatch.setattr(canonical.json, "loads", fail_loads)
    with pytest.raises(AIGatewayCanonicalJSONError, match="malformed JSON"):
        parse_ai_gateway_json_v1(b"null")


def test_integer_parsing_is_independent_of_cpython_digit_configuration() -> None:
    previous_limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(640)
    try:
        raw = b"1" * 641
        parsed = parse_ai_gateway_json_v1(raw)
        assert parsed.bit_length() < canonical.MAX_INTEGER_BITS
        assert canonical_ai_gateway_json_v1_bytes(parsed) == raw
    finally:
        sys.set_int_max_str_digits(previous_limit)


def test_private_boundary_builder_rejects_unknown_fixture_kind() -> None:
    with pytest.raises(AssertionError, match="unrecognized fixture boundary kind"):
        _build_boundary_value({"kind": "unknown"})
