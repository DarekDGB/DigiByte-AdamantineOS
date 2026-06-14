from __future__ import annotations

import re

from typing import Any, Mapping

from adamantine.v1.contracts.adaptive_core_oracle_v3 import AdaptiveCoreOracleV3
from adamantine.v1.contracts.external_reason_registry import ExternalReasonRegistryV1
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.obs.metrics import Metrics
from adamantine.v1.policy.risk_policy import RiskPolicy


_CONTEXT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_canonical_context_hash(value: Any) -> bool:
    return isinstance(value, str) and _CONTEXT_HASH_RE.fullmatch(value) is not None


_ALLOWED_KEYS = {
    "ac_iface_version",
    "context_hash",
    "issued_at",
    "expires_at",
    "generated_at",
    "overall_score",
    "signals",
    "oracle_version",
    "external_source_id",
}


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> "NoReturn":  # type: ignore[name-defined]
    if metrics is not None:
        metrics.inc(rid.value)
    raise AdapterError(rid, msg)


def _deny_unknown_keys(metrics: Metrics | None, m: Mapping[str, Any]) -> None:
    unknown = set(m.keys()) - _ALLOWED_KEYS
    if unknown:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"oracle payload contains unknown fields: {sorted(unknown)}")


def parse_adaptive_core_oracle_v3(
    *,
    payload: Mapping[str, Any],
    now: int,
    expected_context_hash: str,
    reason_map: ExternalReasonMap | None = None,
    reason_registry: ExternalReasonRegistryV1 | None = None,
    policy: RiskPolicy | None = None,
    metrics: Metrics | None = None,
) -> AdaptiveCoreOracleV3:
    if type(now) is not int:
        _fail(metrics, ReasonId.EQC_MISSING_NOW, "now must be int")

    if not _is_canonical_context_hash(expected_context_hash):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "expected_context_hash must be lowercase 64-character hex")

    if not isinstance(payload, Mapping):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "payload must be mapping")

    _deny_unknown_keys(metrics, payload)

    iface = payload.get("ac_iface_version")
    if iface != "adaptive_core_oracle_v3":
        _fail(metrics, ReasonId.DENY_VERSION_MISMATCH, "ac_iface_version must be adaptive_core_oracle_v3")

    ctx = payload.get("context_hash")
    if not _is_canonical_context_hash(ctx):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "context_hash must be lowercase 64-character hex")

    if ctx != expected_context_hash:
        _fail(metrics, ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH, "oracle context_hash mismatch")

    issued_at = payload.get("issued_at")
    expires_at = payload.get("expires_at")
    if type(issued_at) is not int or type(expires_at) is not int:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "issued_at/expires_at must be int")

    if expires_at < issued_at:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "expires_at must be >= issued_at")

    if issued_at > now:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "issued_at cannot be in the future")

    if expires_at < now:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "expires_at cannot be in the past")

    report = parse_risk_report(
        payload=payload,
        now=now,
        expected_context_hash=expected_context_hash,
        reason_map=reason_map,
        reason_registry=reason_registry,
        policy=policy,
        metrics=metrics,
    )

    out = AdaptiveCoreOracleV3(
        context_hash=expected_context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        report=report,
    )

    try:
        out.validate(now=now)
    except ValueError as e:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"oracle contract validation failed: {e}")

    return out
