from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, NoReturn

from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.obs.metrics import Metrics


@dataclass(frozen=True, slots=True)
class ParsedExecutionRequestEnvelopeV2:
    """
    Parsed and validated Execution Request Envelope v2.

    v2 is additive to v1 and introduces required evidence wiring inside payload:
      payload.evidence.{qid,oracle,shield}
      payload.body

    This is *not* a wallet runtime request and contains no key material.
    It is the deterministic boundary input used for later wiring (orchestrator v2).
    """

    request_id: str
    intent: str

    # Deterministic execution context used by EQC/TVA/WSQK enforcement
    context: ExecutionContext

    # Authority declaration (opaque to foundation; validated for shape only)
    authority_class: str
    authority_scope: Mapping[str, Any]
    authority_proofs: Mapping[str, Any] | None

    # Timebox and nonce inputs (validated here; consumption happens later)
    issued_at: int
    expires_at: int
    max_skew_seconds: int

    nonce_value: str
    nonce_store: str

    # v2 evidence wiring (shape validated here; deep validation happens in adapters/EQC v2)
    evidence_qid: Mapping[str, Any]
    evidence_oracle: Mapping[str, Any]
    evidence_shield: Mapping[str, Any]

    # Intent-specific body (validated as strict object only; schema enforced later per-intent)
    body: Mapping[str, Any]

    # Optional audit fields (non-authoritative)
    audit: Mapping[str, Any] | None


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> NoReturn:
    if metrics is not None:
        metrics.inc(rid.value)
    raise EnvelopeError(rid, msg)


def _require_mapping(metrics: Metrics | None, obj: Any, *, rid: ReasonId, name: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        _fail(metrics, rid, f"{name} must be object")
    return obj  # type: ignore[return-value]


def _require_mapping_nonempty(metrics: Metrics | None, obj: Any, *, rid: ReasonId, name: str) -> Mapping[str, Any]:
    m = _require_mapping(metrics, obj, rid=rid, name=name)
    if len(m) == 0:
        _fail(metrics, rid, f"{name} must be non-empty object")
    return m


def _expect_keys(
    metrics: Metrics | None,
    m: Mapping[str, Any],
    *,
    name: str,
    required: set[str],
    allowed: set[str],
) -> None:
    keys = set(m.keys())
    missing = required - keys
    if missing:
        _fail(metrics, ReasonId.DENY_SCHEMA_INVALID, f"{name} missing required keys: {sorted(missing)}")

    unknown = keys - allowed
    if unknown:
        _fail(metrics, ReasonId.DENY_UNKNOWN_FIELD, f"{name} has unknown keys: {sorted(unknown)}")


def _require_nonempty_str(metrics: Metrics | None, v: Any, *, rid: ReasonId, name: str) -> str:
    if not isinstance(v, str) or v == "":
        _fail(metrics, rid, f"{name} must be non-empty str")
    return v


def _parse_iso8601_to_unix_seconds(metrics: Metrics | None, s: Any, *, name: str) -> int:
    if not isinstance(s, str) or s == "":
        _fail(metrics, ReasonId.DENY_TIMEBOX_INVALID, f"{name} must be non-empty ISO-8601 str")

    # Require explicit timezone. Accept trailing 'Z' or explicit offset.
    iso = s
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        _fail(metrics, ReasonId.DENY_TIMEBOX_INVALID, f"{name} must be ISO-8601 with timezone")

    if dt.tzinfo is None:
        _fail(metrics, ReasonId.DENY_TIMEBOX_INVALID, f"{name} must include timezone")

    # Normalize to UTC then to unix seconds deterministically
    dt_utc = dt.astimezone(timezone.utc)
    return int(dt_utc.timestamp())


def parse_execution_request_envelope_v2(
    *,
    payload: Mapping[str, Any],
    now: int,
    metrics: Metrics | None = None,
) -> ParsedExecutionRequestEnvelopeV2:
    """
    Strict parser for Execution Request Envelope v2 (mobile -> Adamantine).

    Fail-closed:
      - unknown fields rejected at every contract-defined level
      - missing required fields rejected
      - type mismatches rejected
      - timebox enforced against injected `now` (unix seconds)
      - nonce mode must be single_use
      - payload must include strict evidence wiring: evidence.{qid,oracle,shield} + body

    Notes:
      - Evidence objects are validated for strict presence + non-empty object shape only.
        Deep validation happens later in adapters and EQC v2.
      - `body` is validated as strict object only; per-intent schemas are enforced later.
    """
    if not isinstance(now, int):
        _fail(metrics, ReasonId.DENY_SCHEMA_INVALID, "now must be int (unix seconds)")

    env = _require_mapping(metrics, payload, rid=ReasonId.DENY_SCHEMA_INVALID, name="envelope")

    _expect_keys(
        metrics,
        env,
        name="envelope",
        required={"v", "request_id", "intent", "context", "authority", "timebox", "nonce", "payload"},
        allowed={"v", "request_id", "intent", "context", "authority", "timebox", "nonce", "payload", "audit"},
    )

    v = _require_nonempty_str(metrics, env.get("v"), rid=ReasonId.DENY_VERSION_MISMATCH, name="v")
    if v != "execution_request_v2":
        _fail(metrics, ReasonId.DENY_VERSION_MISMATCH, "unsupported envelope version")

    request_id = _require_nonempty_str(
        metrics, env.get("request_id"), rid=ReasonId.DENY_SCHEMA_INVALID, name="request_id"
    )
    intent = _require_nonempty_str(metrics, env.get("intent"), rid=ReasonId.DENY_SCHEMA_INVALID, name="intent")

    ctx_m = _require_mapping(metrics, env.get("context"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context")
    _expect_keys(
        metrics,
        ctx_m,
        name="context",
        required={"wallet_id", "device_id", "app_id", "session_id", "action", "fields"},
        allowed={"wallet_id", "device_id", "app_id", "session_id", "action", "fields"},
    )

    wallet_id = _require_nonempty_str(
        metrics, ctx_m.get("wallet_id"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.wallet_id"
    )
    action = _require_nonempty_str(metrics, ctx_m.get("action"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.action")

    # IDs are required but not currently bound into context_hash v1
    _require_nonempty_str(metrics, ctx_m.get("device_id"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.device_id")
    _require_nonempty_str(metrics, ctx_m.get("app_id"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.app_id")
    _require_nonempty_str(
        metrics, ctx_m.get("session_id"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.session_id"
    )

    fields_m = _require_mapping(metrics, ctx_m.get("fields"), rid=ReasonId.DENY_SCHEMA_INVALID, name="context.fields")

    # Keep v1 contract for context hashing: string-only fields.
    fields: dict[str, str] = {}
    for k, val in fields_m.items():
        if not isinstance(k, str) or k == "":
            _fail(metrics, ReasonId.DENY_SCHEMA_INVALID, "context.fields keys must be non-empty str")
        if not isinstance(val, str):
            _fail(metrics, ReasonId.DENY_SCHEMA_INVALID, "context.fields values must be str")
        fields[k] = val

    context_hash = compute_context_hash(wallet_id=wallet_id, action=action, fields=fields)
    context = ExecutionContext(wallet_id=wallet_id, action=action, context_hash=context_hash)

    auth_m = _require_mapping(metrics, env.get("authority"), rid=ReasonId.DENY_AUTHORITY_INVALID, name="authority")
    _expect_keys(
        metrics,
        auth_m,
        name="authority",
        required={"class", "scope"},
        allowed={"class", "scope", "proofs"},
    )

    authority_class = _require_nonempty_str(
        metrics, auth_m.get("class"), rid=ReasonId.DENY_AUTHORITY_INVALID, name="authority.class"
    )
    authority_scope = _require_mapping(
        metrics, auth_m.get("scope"), rid=ReasonId.DENY_AUTHORITY_INVALID, name="authority.scope"
    )
    proofs_raw = auth_m.get("proofs")
    authority_proofs = None if proofs_raw is None else _require_mapping(
        metrics, proofs_raw, rid=ReasonId.DENY_AUTHORITY_INVALID, name="authority.proofs"
    )

    tb_m = _require_mapping(metrics, env.get("timebox"), rid=ReasonId.DENY_TIMEBOX_INVALID, name="timebox")
    _expect_keys(
        metrics,
        tb_m,
        name="timebox",
        required={"issued_at", "expires_at"},
        allowed={"issued_at", "expires_at", "max_skew_seconds"},
    )

    issued_at = _parse_iso8601_to_unix_seconds(metrics, tb_m.get("issued_at"), name="timebox.issued_at")
    expires_at = _parse_iso8601_to_unix_seconds(metrics, tb_m.get("expires_at"), name="timebox.expires_at")
    if expires_at <= issued_at:
        _fail(metrics, ReasonId.DENY_TIMEBOX_INVALID, "timebox.expires_at must be > issued_at")

    skew = tb_m.get("max_skew_seconds", 0)
    if not isinstance(skew, int) or skew < 0:
        _fail(metrics, ReasonId.DENY_TIMEBOX_INVALID, "timebox.max_skew_seconds must be non-negative int")
    max_skew_seconds = skew

    # Enforce timebox against injected now (unix seconds)
    if now < (issued_at - max_skew_seconds):
        _fail(metrics, ReasonId.DENY_TIMEBOX_NOT_YET_VALID, "request not yet valid")
    if now > (expires_at + max_skew_seconds):
        _fail(metrics, ReasonId.DENY_TIMEBOX_EXPIRED, "request expired")

    n_m = _require_mapping(metrics, env.get("nonce"), rid=ReasonId.DENY_NONCE_INVALID, name="nonce")
    _expect_keys(
        metrics,
        n_m,
        name="nonce",
        required={"value", "store", "mode"},
        allowed={"value", "store", "mode"},
    )

    nonce_value = _require_nonempty_str(metrics, n_m.get("value"), rid=ReasonId.DENY_NONCE_INVALID, name="nonce.value")
    nonce_store = _require_nonempty_str(metrics, n_m.get("store"), rid=ReasonId.DENY_NONCE_INVALID, name="nonce.store")
    mode = _require_nonempty_str(metrics, n_m.get("mode"), rid=ReasonId.DENY_NONCE_INVALID, name="nonce.mode")
    if mode != "single_use":
        _fail(metrics, ReasonId.DENY_NONCE_INVALID, "nonce.mode must be single_use")

    payload_m = _require_mapping(metrics, env.get("payload"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload")
    _expect_keys(
        metrics,
        payload_m,
        name="payload",
        required={"evidence", "body"},
        allowed={"evidence", "body"},
    )

    evidence_m = _require_mapping(metrics, payload_m.get("evidence"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload.evidence")
    _expect_keys(
        metrics,
        evidence_m,
        name="payload.evidence",
        required={"qid", "oracle", "shield"},
        allowed={"qid", "oracle", "shield"},
    )

    evidence_qid = _require_mapping_nonempty(
        metrics, evidence_m.get("qid"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload.evidence.qid"
    )
    evidence_oracle = _require_mapping_nonempty(
        metrics, evidence_m.get("oracle"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload.evidence.oracle"
    )
    evidence_shield = _require_mapping_nonempty(
        metrics, evidence_m.get("shield"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload.evidence.shield"
    )

    body = _require_mapping(metrics, payload_m.get("body"), rid=ReasonId.DENY_PAYLOAD_INVALID, name="payload.body")

    audit_raw = env.get("audit")
    audit = None if audit_raw is None else _require_mapping(metrics, audit_raw, rid=ReasonId.DENY_SCHEMA_INVALID, name="audit")

    # Keep same audit strictness as v1: allow only known keys.
    if audit is not None:
        _expect_keys(
            metrics,
            audit,
            name="audit",
            required=set(),
            allowed={"client_version", "platform", "locale", "notes"},
        )

    return ParsedExecutionRequestEnvelopeV2(
        request_id=request_id,
        intent=intent,
        context=context,
        authority_class=authority_class,
        authority_scope=authority_scope,
        authority_proofs=authority_proofs,
        issued_at=issued_at,
        expires_at=expires_at,
        max_skew_seconds=max_skew_seconds,
        nonce_value=nonce_value,
        nonce_store=nonce_store,
        evidence_qid=evidence_qid,
        evidence_oracle=evidence_oracle,
        evidence_shield=evidence_shield,
        body=body,
        audit=audit,
    )
