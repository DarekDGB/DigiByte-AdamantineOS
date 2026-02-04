from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.executor import Executor
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.policy.risk_policy import RiskPolicy


def _safe_str(value: Any, *, fallback: str) -> str:
    if isinstance(value, str) and value:
        return value
    return fallback


def orchestrate_execution_v1(
    *,
    payload: Mapping[str, Any],
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    """
    Execution Orchestrator v1.

    Invariants:
    - Always returns execution_response_v1
    - Never raises
    - Deny-by-default
    - ALLOW path is wired only via EQC -> WSQK -> TVA -> executor
    """
    try:
        # 1) Parse execution request envelope
        req = parse_execution_request_envelope_v1(payload=payload, now=now)

        # 2) Parse external evidence (fail-closed)
        session = parse_qid_session(
            payload=req.evidence.qid,
            now=now,
        )

        risk = parse_risk_report(
            payload=req.evidence.risk,
            now=now,
            expected_context_hash=req.context.context_hash,
            policy=policy,
        )

        # 3) Evaluate EQC (deterministic decision)
        eqc = evaluate_eqc(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            fields=req.context.fields,
            session=session,
            risk=risk,
            now=now,
            policy=policy,
        )

        # 4) DENY path (default)
        if eqc.verdict is not Verdict.ALLOW:
            return build_execution_response_v1(
                request_id=req.request_id,
                intent=req.intent,
                action=req.context.action,
                context_hash=eqc.context_hash,
                status="deny",
                reason_id=eqc.reason_ids[0],
                tva_allowed=False,
                eqc_allowed=False,
                wsqk_allowed=False,
                nonce_consumed=False,
                timebox_valid=True,
            )

        # 5) ALLOW path — enforce TVA and execute
        out = run_with_tva(
            executor=executor,
            request=req.request,
            context=req.context,
            verdict=eqc.verdict,
            authority=req.authority,
            now=now,
            nonce_store=nonce_store,
        )

        return build_execution_response_v1(
            request_id=req.request_id,
            intent=req.intent,
            action=req.context.action,
            context_hash=req.context.context_hash,
            status="allow",
            reason_id=ReasonId.OK_ALLOW,
            tva_allowed=True,
            eqc_allowed=True,
            wsqk_allowed=True,
            nonce_consumed=True,
            timebox_valid=True,
            artifacts={"executor_result": out},
        )

    except EnvelopeError as e:
        # Envelope validation errors already carry stable reason ids
        request_id = _safe_str(payload.get("request_id"), fallback="invalid-request")
        action = _safe_str(payload.get("context", {}).get("action"), fallback="invalid-action")

        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(payload.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="error",
            reason_id=e.reason_id,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": e.message},
        )

    except Exception as e:
        # Unknown failures are reported deterministically without inventing new reason ids
        request_id = _safe_str(payload.get("request_id"), fallback="invalid-request")
        action = _safe_str(payload.get("context", {}).get("action"), fallback="invalid-action")

        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(payload.get("intent"), fallback="unknown"),
            action=action,
            context_hash="0" * 64,
            status="error",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
