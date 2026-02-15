from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "contracts"

REQ_SCHEMA_PATH = CONTRACTS_DIR / "mobile_request_v2.schema.json"
RESP_SCHEMA_PATH = CONTRACTS_DIR / "mobile_response_v2.schema.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"missing required file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"schema must be a JSON object: {path}")
    return data


def _get(m: Mapping[str, Any], key: str) -> Any:
    if key not in m:
        raise AssertionError(f"missing key '{key}' in schema")
    return m[key]


def _assert_is_obj(x: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(x, dict):
        raise AssertionError(f"{where} must be object")
    return x


def _assert_additional_properties_false(schema: dict[str, Any], *, where: str) -> None:
    ap = schema.get("additionalProperties")
    if ap is not False:
        raise AssertionError(f"{where}: additionalProperties must be false (got {ap!r})")


def _assert_enum(schema: dict[str, Any], expected: list[str], *, where: str) -> None:
    enum = schema.get("enum")
    if enum != expected:
        raise AssertionError(f"{where}: enum mismatch (got {enum!r}, expected {expected!r})")


def test_contract_schema_files_exist_and_are_objects() -> None:
    _load_json(REQ_SCHEMA_PATH)
    _load_json(RESP_SCHEMA_PATH)


def test_mobile_request_v2_schema_core_constraints() -> None:
    s = _load_json(REQ_SCHEMA_PATH)

    _assert_additional_properties_false(s, where="request:root")
    v = _assert_is_obj(_get(_assert_is_obj(_get(s, "properties"), where="request:properties"), "v"), where="request:properties.v")
    if v.get("const") != "execution_request_v2":
        raise AssertionError("request:v must const == execution_request_v2")

    required = _get(s, "required")
    if not isinstance(required, list):
        raise AssertionError("request:required must be list")
    for k in ["v", "request_id", "intent", "context", "authority", "timebox", "nonce", "payload"]:
        if k not in required:
            raise AssertionError(f"request:required missing {k}")

    # context strict
    ctx = _assert_is_obj(_get(_assert_is_obj(_get(s, "properties"), where="request:properties"), "context"), where="request:context")
    _assert_additional_properties_false(ctx, where="request:context")
    ctx_props = _assert_is_obj(_get(ctx, "properties"), where="request:context.properties")
    fields = _assert_is_obj(_get(ctx_props, "fields"), where="request:context.fields")
    # fields is dynamic string->string map (patternProperties), but must not allow random nested objects as values
    pp = fields.get("patternProperties")
    if not isinstance(pp, dict) or "^.+$" not in pp:
        raise AssertionError("request:context.fields must define patternProperties '^.+$'")
    if _assert_is_obj(pp["^.+$"], where="request:context.fields.patternProperties['^.+$']").get("type") != "string":
        raise AssertionError("request:context.fields values must be strings")

    # evidence wiring must be strict at wiring level, but opaque inside blocks
    payload = _assert_is_obj(_get(_assert_is_obj(_get(s, "properties"), where="request:properties"), "payload"), where="request:payload")
    _assert_additional_properties_false(payload, where="request:payload")
    payload_props = _assert_is_obj(_get(payload, "properties"), where="request:payload.properties")
    ev = _assert_is_obj(_get(payload_props, "evidence"), where="request:payload.evidence")
    _assert_additional_properties_false(ev, where="request:payload.evidence")
    ev_props = _assert_is_obj(_get(ev, "properties"), where="request:payload.evidence.properties")

    for block in ["qid", "oracle", "shield"]:
        b = _assert_is_obj(_get(ev_props, block), where=f"request:evidence.{block}")
        # OPAQUE by design (Option B)
        if b.get("type") != "object":
            raise AssertionError(f"request:evidence.{block} must be object")
        if b.get("minProperties") != 1:
            raise AssertionError(f"request:evidence.{block} must require non-empty object (minProperties=1)")
        ap = b.get("additionalProperties")
        if ap is not True:
            raise AssertionError(f"request:evidence.{block} must be opaque (additionalProperties true), got {ap!r}")


def test_mobile_response_v2_schema_core_constraints() -> None:
    s = _load_json(RESP_SCHEMA_PATH)

    _assert_additional_properties_false(s, where="response:root")
    props = _assert_is_obj(_get(s, "properties"), where="response:properties")

    v = _assert_is_obj(_get(props, "v"), where="response:properties.v")
    if v.get("const") != "execution_response_v2":
        raise AssertionError("response:v must const == execution_response_v2")

    status = _assert_is_obj(_get(props, "status"), where="response:properties.status")
    _assert_enum(status, ["allow", "deny", "error"], where="response:status")

    decision = _assert_is_obj(_get(props, "decision"), where="response:decision")
    _assert_additional_properties_false(decision, where="response:decision")

    dprops = _assert_is_obj(_get(decision, "properties"), where="response:decision.properties")
    pm = _assert_is_obj(_get(dprops, "protection_mode"), where="response:decision.protection_mode")
    _assert_enum(pm, ["legacy", "minimal", "full"], where="response:decision.protection_mode")

    # Gate structure must be strict
    gates = _assert_is_obj(_get(dprops, "gates"), where="response:decision.gates")
    _assert_additional_properties_false(gates, where="response:decision.gates")
    gates_props = _assert_is_obj(_get(gates, "properties"), where="response:decision.gates.properties")
    for gate in ["tva", "eqc", "wsqk"]:
        g = _assert_is_obj(_get(gates_props, gate), where=f"response:decision.gates.{gate}")
        _assert_additional_properties_false(g, where=f"response:decision.gates.{gate}")

    # artifacts/metrics are intentionally permissive (contract says deterministic + bounded; schema does not deep-lock)
    # Just assert they're objects if present in schema.
    for k in ["artifacts", "metrics"]:
        if k in props:
            if _assert_is_obj(props[k], where=f"response:{k}").get("type") != "object":
                raise AssertionError(f"response:{k} must be object")
