from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


AI_GATEWAY_CANONICAL_JSON_V1 = "ai_gateway_canonical_json_v1"

MAX_DEPTH = 10
MAX_KEYS_PER_OBJECT = 1_000
MAX_ITEMS_PER_ARRAY = 1_000
MAX_STRING_SCALARS = 10_000
MAX_INTEGER_BITS = 4_096
MAX_INTEGER_DECIMAL_DIGITS = 1_234
MAX_SNAPSHOT_NODES = 20_000
MAX_CANONICAL_BYTES = 1_048_576
MAX_RAW_JSON_BYTES = 1_048_576


class AIGatewayCanonicalJSONError(ValueError):
    """Base failure for the independent AI Gateway canonical profile."""


class AIGatewayDuplicateKeyError(AIGatewayCanonicalJSONError):
    """A raw JSON object contained a duplicate decoded key."""


class AIGatewayResourceLimitError(AIGatewayCanonicalJSONError):
    """A governed D2/V2 resource ceiling was exceeded."""


@dataclass
class _Budget:
    nodes: int = 0
    text_bytes: int = 0


def _resource_failure(message: str) -> AIGatewayResourceLimitError:
    return AIGatewayResourceLimitError(message)


def _count_text(value: str, budget: _Budget) -> None:
    if len(value) > MAX_STRING_SCALARS:
        raise _resource_failure("string scalar limit exceeded")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise AIGatewayCanonicalJSONError("invalid Unicode scalar value") from exc
    budget.text_bytes += len(encoded)
    if budget.text_bytes > MAX_CANONICAL_BYTES:
        raise _resource_failure("text preflight byte limit exceeded")


def _encode_integer(value: int) -> bytes:
    if value == 0:
        return b"0"
    negative = value < 0
    magnitude = -value if negative else value
    reversed_digits = bytearray()
    while magnitude:
        magnitude, digit = divmod(magnitude, 10)
        reversed_digits.append(ord("0") + digit)
    encoded = bytes(reversed(reversed_digits))
    return b"-" + encoded if negative else encoded


def _preflight(
    value: Any,
    *,
    depth: int,
    active_containers: set[int],
    budget: _Budget,
) -> None:
    if depth > MAX_DEPTH:
        raise _resource_failure("depth limit exceeded")

    budget.nodes += 1
    if budget.nodes > MAX_SNAPSHOT_NODES:
        raise _resource_failure("node limit exceeded")

    if type(value) is str:
        _count_text(value, budget)
        return

    if value is None or type(value) is bool:
        return

    if type(value) is int:
        if abs(value).bit_length() > MAX_INTEGER_BITS:
            raise _resource_failure("integer bit limit exceeded")
        budget.text_bytes += len(_encode_integer(value))
        if budget.text_bytes > MAX_CANONICAL_BYTES:
            raise _resource_failure("text preflight byte limit exceeded")
        return

    if type(value) is list:
        if len(value) > MAX_ITEMS_PER_ARRAY:
            raise _resource_failure("array item limit exceeded")
        identity = id(value)
        if identity in active_containers:
            raise AIGatewayCanonicalJSONError("container cycle rejected")
        active_containers.add(identity)
        try:
            for item in value:
                _preflight(
                    item,
                    depth=depth + 1,
                    active_containers=active_containers,
                    budget=budget,
                )
        finally:
            active_containers.remove(identity)
        return

    if type(value) is dict:
        if len(value) > MAX_KEYS_PER_OBJECT:
            raise _resource_failure("object key limit exceeded")
        identity = id(value)
        if identity in active_containers:
            raise AIGatewayCanonicalJSONError("container cycle rejected")
        active_containers.add(identity)
        try:
            for key, child in value.items():
                if type(key) is not str:
                    raise AIGatewayCanonicalJSONError("object key must be an exact string")
                _count_text(key, budget)
                _preflight(
                    child,
                    depth=depth + 1,
                    active_containers=active_containers,
                    budget=budget,
                )
        finally:
            active_containers.remove(identity)
        return

    raise AIGatewayCanonicalJSONError("unsupported JSON value type")


def _encode_string(value: str) -> bytes:
    output = bytearray(b'"')
    short_escapes = {
        0x08: b"\\b",
        0x09: b"\\t",
        0x0A: b"\\n",
        0x0C: b"\\f",
        0x0D: b"\\r",
    }

    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise AIGatewayCanonicalJSONError("surrogate code point rejected")
        if codepoint == 0x22:
            output.extend(b'\\"')
        elif codepoint == 0x5C:
            output.extend(b"\\\\")
        elif codepoint in short_escapes:
            output.extend(short_escapes[codepoint])
        elif codepoint <= 0x1F:
            output.extend(f"\\u{codepoint:04x}".encode("ascii"))
        else:
            output.extend(character.encode("utf-8"))

    output.extend(b'"')
    return bytes(output)


def _encode_value(value: Any) -> bytes:
    if value is None:
        return b"null"
    if type(value) is bool:
        return b"true" if value else b"false"
    if type(value) is int:
        return _encode_integer(value)
    if type(value) is str:
        return _encode_string(value)
    if type(value) is list:
        return b"[" + b",".join(_encode_value(item) for item in value) + b"]"
    if type(value) is dict:
        members = (
            _encode_string(key) + b":" + _encode_value(value[key])
            for key in sorted(value)
        )
        return b"{" + b",".join(members) + b"}"
    raise AIGatewayCanonicalJSONError("unsupported JSON value type")


def canonical_ai_gateway_json_v1_bytes(value: Any) -> bytes:
    """Return governed canonical bytes without importing Gateway code."""

    _preflight(
        value,
        depth=0,
        active_containers=set(),
        budget=_Budget(),
    )
    encoded = _encode_value(value)
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise _resource_failure("canonical byte limit exceeded")
    return encoded


def _reject_float(_token: str) -> None:
    raise AIGatewayCanonicalJSONError("float grammar rejected")


def _reject_constant(_token: str) -> None:
    raise AIGatewayCanonicalJSONError("non-finite number rejected")


def _parse_integer(token: str) -> int:
    negative = token.startswith("-")
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INTEGER_DECIMAL_DIGITS:
        raise _resource_failure("integer bit limit exceeded")
    magnitude = 0
    for digit in digits:
        magnitude = (magnitude * 10) + (ord(digit) - ord("0"))
        if magnitude.bit_length() > MAX_INTEGER_BITS:
            raise _resource_failure("integer bit limit exceeded")
    return -magnitude if negative else magnitude


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise AIGatewayDuplicateKeyError("duplicate decoded object key")
        value[key] = child
    return value


def parse_ai_gateway_json_v1(raw_json: bytes) -> Any:
    """Strictly parse one governed raw D2/V2 JSON value.

    Duplicate decoded keys are rejected by the object-pairs hook before a
    mapping is constructed. The returned value has also passed the complete
    governed resource profile and canonical byte ceiling.
    """

    if type(raw_json) is not bytes:
        raise AIGatewayCanonicalJSONError("raw JSON must be exact bytes")
    if len(raw_json) > MAX_RAW_JSON_BYTES:
        raise _resource_failure("raw JSON byte limit exceeded")
    if raw_json.startswith(b"\xef\xbb\xbf"):
        raise AIGatewayCanonicalJSONError("UTF-8 BOM rejected")

    try:
        text = raw_json.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AIGatewayCanonicalJSONError("invalid UTF-8") from exc

    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_from_pairs,
            parse_float=_reject_float,
            parse_int=_parse_integer,
            parse_constant=_reject_constant,
        )
    except AIGatewayCanonicalJSONError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise AIGatewayCanonicalJSONError("malformed JSON") from exc

    canonical_ai_gateway_json_v1_bytes(value)
    return value
