from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.executor import Executor
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.eqc.evaluator import evaluate_eqc
from adamantine.v1.integrations.qid_adapter import parse_qid_session
from adamantine.v1.integrations.adaptive_core_adapter import parse_risk_report
from adamantine.v1.policy.risk_policy import RiskPolicy


def orchestrate_execution_v1(
    *,
    payload: Mapping[str, Any],
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
    policy: RiskPolicy | None = None,
) -> dict[str, Any]:
    """
    Versioned execution orchestrator (v1).

    This is a strict coordinator:
    - no decisions are made here
    - no authority is granted here
    - no state is stored here

    Always returns execution_response_v1.
    """
    try:
        req = parse_execution_request_envelope_v1(payload=payload, now=now)

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

        eqc = evaluate_eqc(
            wallet_id=req.context.wallet_id,
            action=req.context.action,
            fields=req.context.fields,
            session=session,
            risk=risk,
            now=now,
            policy=policy,
        )

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

    except Exception as e:
        return build_execution_response_v1(
            request_id=str(payload.get("request_id", "")),
            intent=str(payload.get("intent", "")),
            action=str(payload.get("context", {}).get("action", "")),
            context_hash="",
            status="error",
            reason_id=ReasonId.EXECUTION_ERROR,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
