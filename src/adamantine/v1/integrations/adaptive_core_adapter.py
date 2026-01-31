from __future__ import annotations

from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.contracts.shield import ExternalReasonMap
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.obs.metrics import Metrics
from adamantine.v1.policy.risk_policy import RiskPolicy, UnknownReasonMode


def _fail(metrics: Metrics | None, rid: ReasonId, msg: str) -> "NoReturn":  # type: ignore[name-defined]
    if metrics is not None:
        metrics.inc(rid.value)
    raise AdapterError(rid, msg)


def parse_risk_report(
    *,
    payload: Mapping[str, Any],
    now: int,
    expected_context_hash: str,
    reason_map: ExternalReasonMap,
    policy: RiskPolicy | None = None,
    metrics: Metrics | None = None,
) -> RiskReport:
    """
    External Adaptive Core payload -> RiskReport (contract)

    Fail-closed:
      - missing required fields
      - invalid types/ranges
      - context_hash mismatch
      - unknown external reason ids (per policy allowlist)
      - unmapped external reason ids (mapping table)
    """
    if not isinstance(now, int):
        _fail(metrics, ReasonId.EQC_MISSING_NOW, "now must be int")

    if not isinstance(expected_context_hash, str) or not expected_context_hash:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "expected_context_hash must be non-empty str")

    if not isinstance(payload, Mapping):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "payload must be mapping")

    p = policy or RiskPolicy()
    p.validate()

    if not isinstance(reason_map, ExternalReasonMap):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "reason_map must be ExternalReasonMap")
    reason_map.validate()

    allowed_reason_ids = set(p.effective_allowed_external_reason_ids())

    iface = payload.get("ac_iface_version")
    if not isinstance(iface, str) or not iface:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "ac_iface_version must be non-empty str")

    context_hash = payload.get("context_hash")
    if not isinstance(context_hash, str) or not context_hash:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "context_hash must be non-empty str")

    if context_hash != expected_context_hash:
        _fail(metrics, ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH, "risk context_hash mismatch")

    generated_at = payload.get("generated_at")
    overall_score = payload.get("overall_score")
    signals_raw = payload.get("signals")

    if not isinstance(generated_at, int) or generated_at <= 0:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "generated_at must be positive int")

    if generated_at > now:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "generated_at cannot be in the future")

    if not isinstance(overall_score, int) or not (0 <= overall_score <= 100):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "overall_score must be int in range 0..100")

    if not isinstance(signals_raw, Sequence) or isinstance(signals_raw, (str, bytes)):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "signals must be a sequence")

    if len(signals_raw) == 0:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "signals must not be empty")

    signals: list[RiskSignal] = []
    for idx, s in enumerate(signals_raw):
        if not isinstance(s, Mapping):
            _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}] must be mapping")

        source = s.get("source")
        severity = s.get("severity")
        reason_ids_raw = s.get("reason_ids")

        if not isinstance(source, str) or not source:
            _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].source must be non-empty str")

        if not isinstance(severity, int) or not (0 <= severity <= 100):
            _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].severity must be 0..100 int")

        if not isinstance(reason_ids_raw, Sequence) or isinstance(reason_ids_raw, (str, bytes)):
            _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].reason_ids must be a list of str")

        internal_reason_ids: list[str] = []
        for rid in reason_ids_raw:
            if not isinstance(rid, str) or not rid:
                _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].reason_ids must be non-empty str")

            # Policy allowlist gate (external code)
            if rid not in allowed_reason_ids and p.unknown_reason_mode is UnknownReasonMode.DENY_EXPLICIT:
                _fail(metrics, ReasonId.UNKNOWN_EXTERNAL_REASON, f"unknown external reason_id: {rid}")

            # Mapping table (external -> internal ReasonId)
            internal = reason_map.lookup(rid)
            if internal is None:
                _fail(metrics, ReasonId.UNKNOWN_EXTERNAL_REASON, f"unmapped external reason_id: {rid}")

            internal_reason_ids.append(internal)

        sig = RiskSignal(source=source, severity=severity, reason_ids=tuple(internal_reason_ids))
        try:
            sig.validate()
        except ValueError as e:
            _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"signal contract validation failed: {e}")

        signals.append(sig)

    oracle_version = payload.get("oracle_version", None)
    if oracle_version is not None and not isinstance(oracle_version, str):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "oracle_version must be str or None")

    external_source_id = payload.get("external_source_id", None)
    if external_source_id is not None and not isinstance(external_source_id, str):
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, "external_source_id must be str or None")

    report = RiskReport(
        context_hash=context_hash,
        signals=tuple(signals),
        overall_score=overall_score,
        generated_at=generated_at,
        oracle_version=oracle_version,
        external_source_id=external_source_id,
    )

    try:
        report.validate(now=now)
    except ValueError as e:
        _fail(metrics, ReasonId.EQC_INVALID_RISK_REPORT, f"contract validation failed: {e}")

    return report
