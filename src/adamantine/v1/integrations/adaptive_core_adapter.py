from __future__ import annotations

from typing import Any, Mapping, Sequence

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.risk import RiskReport, RiskSignal
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.policy.risk_policy import RiskPolicy, UnknownReasonMode


# Minimal explicit allowlist for v0 adapters.
# Expand intentionally as the external system stabilizes.
_ALLOWED_EXTERNAL_REASON_IDS = {"ok"}


def parse_risk_report(
    *,
    payload: Mapping[str, Any],
    now: int,
    expected_context_hash: str,
    policy: RiskPolicy | None = None,
) -> RiskReport:
    """
    External Adaptive Core payload -> RiskReport (contract)

    Fail-closed:
      - missing required fields
      - invalid types/ranges
      - context_hash mismatch
      - unknown external reason ids (per policy, default deny)
    """
    if not isinstance(now, int):
        raise AdapterError(ReasonId.EQC_MISSING_NOW, "now must be int")

    if not isinstance(expected_context_hash, str) or not expected_context_hash:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "expected_context_hash must be non-empty str")

    if not isinstance(payload, Mapping):
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "payload must be mapping")

    p = policy or RiskPolicy()
    p.validate()

    iface = payload.get("ac_iface_version")
    if not isinstance(iface, str) or not iface:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "ac_iface_version must be non-empty str")

    context_hash = payload.get("context_hash")
    if not isinstance(context_hash, str) or not context_hash:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "context_hash must be non-empty str")

    if context_hash != expected_context_hash:
        raise AdapterError(ReasonId.EQC_RISK_CONTEXT_HASH_MISMATCH, "risk context_hash mismatch")

    generated_at = payload.get("generated_at")
    overall_score = payload.get("overall_score")
    signals_raw = payload.get("signals")

    if not isinstance(generated_at, int) or generated_at <= 0:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "generated_at must be positive int")

    if generated_at > now:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "generated_at cannot be in the future")

    if not isinstance(overall_score, int) or not (0 <= overall_score <= 100):
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "overall_score must be int in range 0..100")

    if not isinstance(signals_raw, Sequence) or isinstance(signals_raw, (str, bytes)):
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "signals must be a sequence")

    if len(signals_raw) == 0:
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "signals must not be empty")

    signals: list[RiskSignal] = []
    for idx, s in enumerate(signals_raw):
        if not isinstance(s, Mapping):
            raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}] must be mapping")

        source = s.get("source")
        severity = s.get("severity")
        reason_ids_raw = s.get("reason_ids")

        if not isinstance(source, str) or not source:
            raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].source must be non-empty str")

        if not isinstance(severity, int) or not (0 <= severity <= 100):
            raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].severity must be 0..100 int")

        if not isinstance(reason_ids_raw, Sequence) or isinstance(reason_ids_raw, (str, bytes)):
            raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].reason_ids must be a list of str")

        reason_ids: list[str] = []
        for rid in reason_ids_raw:
            if not isinstance(rid, str) or not rid:
                raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal[{idx}].reason_ids must be non-empty str")

            if rid not in _ALLOWED_EXTERNAL_REASON_IDS and p.unknown_reason_mode is UnknownReasonMode.DENY_EXPLICIT:
                raise AdapterError(ReasonId.UNKNOWN_EXTERNAL_REASON, f"unknown external reason_id: {rid}")

            reason_ids.append(rid)

        sig = RiskSignal(source=source, severity=severity, reason_ids=tuple(reason_ids))
        try:
            sig.validate()
        except ValueError as e:
            raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"signal contract validation failed: {e}") from e

        signals.append(sig)

    oracle_version = payload.get("oracle_version", None)
    if oracle_version is not None and not isinstance(oracle_version, str):
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "oracle_version must be str or None")

    external_source_id = payload.get("external_source_id", None)
    if external_source_id is not None and not isinstance(external_source_id, str):
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, "external_source_id must be str or None")

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
        raise AdapterError(ReasonId.EQC_INVALID_RISK_REPORT, f"contract validation failed: {e}") from e

    return report
