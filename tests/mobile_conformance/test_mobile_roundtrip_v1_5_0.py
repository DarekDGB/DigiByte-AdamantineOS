from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import pytest

from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.executor import RecordingExecutor
from adamantine.v1.execution.fixture_harness import (
    _default_policy,
    load_canonical_json,
    verify_manifest_strict_for,
)
from adamantine.v1.execution.orchestrator_v2 import orchestrate_execution_v2


NOW = 1706990400
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_dir() -> Path:
    return _repo_root() / "src" / "adamantine" / "v1" / "fixtures" / "v1_5_0_mobile"


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _assert_keys_exact(obj: dict, allowed: Iterable[str], *, where: str) -> None:
    allowed_set = set(allowed)
    extra = sorted([k for k in obj.keys() if k not in allowed_set])
    missing = sorted([k for k in allowed_set if k not in obj])
    if extra:
        raise AssertionError(f"{where}: unknown keys not allowed: {extra}")
    if missing:
        raise AssertionError(f"{where}: missing required keys: {missing}")


def _assert_optional_allowlist(obj: dict, allowed: Iterable[str], *, where: str) -> None:
    allowed_set = set(allowed)
    extra = sorted([k for k in obj.keys() if k not in allowed_set])
    if extra:
        raise AssertionError(f"{where}: unknown keys not allowed: {extra}")


def _assert_str(x: Any, *, where: str, non_empty: bool = True) -> str:
    if not isinstance(x, str):
        raise AssertionError(f"{where}: expected string")
    if non_empty and not x:
        raise AssertionError(f"{where}: expected non-empty string")
    return x


def _assert_int(x: Any, *, where: str) -> int:
    if not isinstance(x, int):
        raise AssertionError(f"{where}: expected int")
    return x


def _assert_bool(x: Any, *, where: str) -> bool:
    if not isinstance(x, bool):
        raise AssertionError(f"{where}: expected bool")
    return x


def _assert_dict(x: Any, *, where: str) -> dict:
    if not isinstance(x, dict):
        raise AssertionError(f"{where}: expected object")
    return x


def _validate_request_v2(req: dict) -> None:
    _assert_keys_exact(
        req,
        [
            "v",
            "request_id",
            "intent",
            "context",
            "authority",
            "timebox",
            "nonce",
            "payload",
            "audit",  # optional (allowed)
        ],
        where="request",
    )
    if req.get("v") != "execution_request_v2":
        raise AssertionError("request.v must equal execution_request_v2")

    _assert_str(req["request_id"], where="request.request_id")
    _assert_str(req["intent"], where="request.intent")

    # context (strict)
    ctx = _assert_dict(req["context"], where="request.context")
    _assert_keys_exact(
        ctx,
        ["wallet_id", "device_id", "app_id", "session_id", "action", "fields"],
        where="request.context",
    )
    _assert_str(ctx["wallet_id"], where="request.context.wallet_id")
    _assert_str(ctx["device_id"], where="request.context.device_id")
    _assert_str(ctx["app_id"], where="request.context.app_id")
    _assert_str(ctx["session_id"], where="request.context.session_id")
    _assert_str(ctx["action"], where="request.context.action")

    fields = _assert_dict(ctx["fields"], where="request.context.fields")
    for k, v in fields.items():
        _assert_str(k, where="request.context.fields.key")
        _assert_str(v, where=f"request.context.fields[{k!r}]")

    # authority (strict)
    auth = _assert_dict(req["authority"], where="request.authority")
    _assert_optional_allowlist(auth, ["class", "scope", "proofs"], where="request.authority")
    _assert_str(auth.get("class"), where="request.authority.class")
    if "scope" not in auth:
        raise AssertionError("request.authority.scope is required")
    _assert_dict(auth["scope"], where="request.authority.scope")
    if "proofs" in auth:
        _assert_dict(auth["proofs"], where="request.authority.proofs")

    # timebox (strict)
    tb = _assert_dict(req["timebox"], where="request.timebox")
    _assert_optional_allowlist(tb, ["issued_at", "expires_at", "max_skew_seconds"], where="request.timebox")
    _assert_str(tb.get("issued_at"), where="request.timebox.issued_at")
    _assert_str(tb.get("expires_at"), where="request.timebox.expires_at")
    if "max_skew_seconds" in tb:
        skew = _assert_int(tb["max_skew_seconds"], where="request.timebox.max_skew_seconds")
        if skew < 0:
            raise AssertionError("request.timebox.max_skew_seconds must be >= 0")

    # nonce (strict)
    nonce = _assert_dict(req["nonce"], where="request.nonce")
    _assert_keys_exact(nonce, ["value", "store", "mode"], where="request.nonce")
    _assert_str(nonce["value"], where="request.nonce.value")
    _assert_str(nonce["store"], where="request.nonce.store")
    if nonce["mode"] != "single_use":
        raise AssertionError("request.nonce.mode must equal single_use")

    # payload (strict wiring; evidence blocks opaque but must be non-empty objects)
    payload = _assert_dict(req["payload"], where="request.payload")
    _assert_keys_exact(payload, ["evidence", "body"], where="request.payload")

    evidence = _assert_dict(payload["evidence"], where="request.payload.evidence")
    _assert_keys_exact(evidence, ["qid", "oracle", "shield"], where="request.payload.evidence")

    for name in ("qid", "oracle", "shield"):
        block = _assert_dict(evidence[name], where=f"request.payload.evidence.{name}")
        if len(block) < 1:
            raise AssertionError(f"request.payload.evidence.{name} must be non-empty object")

    _assert_dict(payload["body"], where="request.payload.body")

    # audit (optional strict allowlist)
    if "audit" in req:
        audit = _assert_dict(req["audit"], where="request.audit")
        _assert_optional_allowlist(audit, ["client_version", "platform", "locale", "notes"], where="request.audit")
        for k in audit:
            _assert_str(audit[k], where=f"request.audit.{k}", non_empty=False)


def _validate_response_v2(resp: dict) -> None:
    _assert_optional_allowlist(resp, ["v", "request_id", "status", "reason_id", "context_hash", "decision", "artifacts", "metrics"], where="response")
    for k in ["v", "request_id", "status", "reason_id", "context_hash", "decision"]:
        if k not in resp:
            raise AssertionError(f"response missing required key: {k}")

    if resp["v"] != "execution_response_v2":
        raise AssertionError("response.v must equal execution_response_v2")

    _assert_str(resp["request_id"], where="response.request_id")
    status = _assert_str(resp["status"], where="response.status")
    if status not in ("allow", "deny", "error"):
        raise AssertionError("response.status must be allow|deny|error")

    reason_id = _assert_str(resp["reason_id"], where="response.reason_id")
    ch = _assert_str(resp["context_hash"], where="response.context_hash")
    if not HEX64_RE.match(ch):
        raise AssertionError("response.context_hash must be 64 lowercase hex")

    decision = _assert_dict(resp["decision"], where="response.decision")
    _assert_keys_exact(
        decision,
        ["intent", "action", "allowed", "protection_mode", "gates", "timebox", "nonce", "evidence", "policy"],
        where="response.decision",
    )
    _assert_str(decision["intent"], where="response.decision.intent")
    _assert_str(decision["action"], where="response.decision.action")
    allowed = _assert_bool(decision["allowed"], where="response.decision.allowed")

    pm = _assert_str(decision["protection_mode"], where="response.decision.protection_mode")
    if pm not in ("legacy", "minimal", "full"):
        raise AssertionError("response.decision.protection_mode must be legacy|minimal|full")

    # allow invariant
    if status == "allow":
        if not allowed:
            raise AssertionError("status=allow requires decision.allowed=true")
        if reason_id != "OK_ALLOW":
            raise AssertionError("status=allow requires reason_id==OK_ALLOW")
    else:
        if allowed:
            raise AssertionError("status!=allow requires decision.allowed=false")

    # gates strict
    gates = _assert_dict(decision["gates"], where="response.decision.gates")
    _assert_keys_exact(gates, ["tva", "eqc", "wsqk"], where="response.decision.gates")
    for gate in ("tva", "eqc", "wsqk"):
        g = _assert_dict(gates[gate], where=f"response.decision.gates.{gate}")
        _assert_keys_exact(g, ["allowed", "reason_id"], where=f"response.decision.gates.{gate}")
        _assert_bool(g["allowed"], where=f"response.decision.gates.{gate}.allowed")
        _assert_str(g["reason_id"], where=f"response.decision.gates.{gate}.reason_id")

    # timebox strict
    tb = _assert_dict(decision["timebox"], where="response.decision.timebox")
    _assert_keys_exact(tb, ["valid", "issued_at", "expires_at", "max_skew_seconds", "reason_id"], where="response.decision.timebox")
    _assert_bool(tb["valid"], where="response.decision.timebox.valid")
    _assert_str(tb["issued_at"], where="response.decision.timebox.issued_at")
    _assert_str(tb["expires_at"], where="response.decision.timebox.expires_at")
    skew = _assert_int(tb["max_skew_seconds"], where="response.decision.timebox.max_skew_seconds")
    if skew < 0:
        raise AssertionError("response.decision.timebox.max_skew_seconds must be >= 0")
    _assert_str(tb["reason_id"], where="response.decision.timebox.reason_id")

    # nonce strict
    nonce = _assert_dict(decision["nonce"], where="response.decision.nonce")
    _assert_keys_exact(nonce, ["consumed", "store", "value", "reason_id"], where="response.decision.nonce")
    _assert_bool(nonce["consumed"], where="response.decision.nonce.consumed")
    _assert_str(nonce["store"], where="response.decision.nonce.store")
    _assert_str(nonce["value"], where="response.decision.nonce.value")
    _assert_str(nonce["reason_id"], where="response.decision.nonce.reason_id")

    # evidence strict summary
    ev = _assert_dict(decision["evidence"], where="response.decision.evidence")
    _assert_keys_exact(ev, ["qid", "shield", "oracle"], where="response.decision.evidence")
    for name in ("qid", "shield", "oracle"):
        e = _assert_dict(ev[name], where=f"response.decision.evidence.{name}")
        _assert_keys_exact(e, ["present", "valid", "reason_id"], where=f"response.decision.evidence.{name}")
        _assert_bool(e["present"], where=f"response.decision.evidence.{name}.present")
        _assert_bool(e["valid"], where=f"response.decision.evidence.{name}.valid")
        _assert_str(e["reason_id"], where=f"response.decision.evidence.{name}.reason_id")

    # policy strict summary
    pol = _assert_dict(decision["policy"], where="response.decision.policy")
    _assert_keys_exact(pol, ["mode", "override_allowed", "reason_id"], where="response.decision.policy")
    _assert_str(pol["mode"], where="response.decision.policy.mode")
    _assert_bool(pol["override_allowed"], where="response.decision.policy.override_allowed")
    _assert_str(pol["reason_id"], where="response.decision.policy.reason_id")

    # artifacts/metrics (optional; object if present)
    if "artifacts" in resp:
        _assert_dict(resp["artifacts"], where="response.artifacts")
    if "metrics" in resp:
        _assert_dict(resp["metrics"], where="response.metrics")


def _run_request(request_fixture_name: str) -> dict:
    base = _fixture_dir()
    payload = load_canonical_json(base / request_fixture_name)
    executor = RecordingExecutor()
    store = InMemoryNonceStore()
    policy = _default_policy()
    return orchestrate_execution_v2(payload=payload, now=NOW, executor=executor, nonce_store=store, policy=policy)


@pytest.mark.parametrize(
    "request_name,response_name",
    [
        ("request_legacy.json", "response_legacy.json"),
        ("request_minimal.json", "response_minimal.json"),
        ("request_full_allow.json", "response_full_allow.json"),
        ("request_full_deny.json", "response_full_deny.json"),
    ],
)
def test_mobile_v1_5_0_roundtrip_is_contract_valid_and_exact(request_name: str, response_name: str) -> None:
    # Fixture integrity lock
    verify_manifest_strict_for("v1_5_0_mobile")

    base = _fixture_dir()
    req = load_canonical_json(base / request_name)
    expected = load_canonical_json(base / response_name)

    _validate_request_v2(req)
    _validate_response_v2(expected)

    got = _run_request(request_name)
    _validate_response_v2(got)

    assert _canonical(got) == _canonical(expected)


def test_mobile_v1_5_0_is_deterministic_across_100_runs() -> None:
    verify_manifest_strict_for("v1_5_0_mobile")
    first = _canonical(_run_request("request_full_deny.json"))
    for _ in range(100):
        assert _canonical(_run_request("request_full_deny.json")) == first
