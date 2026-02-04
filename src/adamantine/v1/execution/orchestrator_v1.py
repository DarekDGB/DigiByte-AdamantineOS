from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.execution.executor import Executor
from adamantine.v1.enforcement.nonce_store import NonceStore


def orchestrate_execution_v1(
    *,
    payload: Mapping[str, Any],
    now: int,
    executor: Executor,
    nonce_store: NonceStore,
) -> dict[str, Any]:
    """
    Execution Orchestrator v1 (sealed skeleton).

    Invariants:
    - Always returns execution_response_v1
    - Never raises
    - Deny-by-default
    - No execution wiring in C1/C2
    """
    try:
        parsed = parse_execution_request_envelope_v1(payload=payload, now=now)

        # C1/C2: orchestrator exists as the single entry point,
        # but execution wiring is intentionally not enabled yet.
        return build_execution_response_v1(
            request_id=parsed.request_id,
            intent=parsed.intent,
            action=parsed.context.action,
            context_hash=parsed.context.context_hash,
            status="deny",
            reason_id=ReasonId.DENY_NOT_WIRED,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=True,
        )

    except EnvelopeError as e:
        return build_execution_response_v1(
            request_id=str(payload.get("request_id", "")),
            intent=str(payload.get("intent", "")),
            action=str(payload.get("context", {}).get("action", "")),
            context_hash="",
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
        return build_execution_response_v1(
            request_id=str(payload.get("request_id", "")),
            intent=str(payload.get("intent", "")),
            action=str(payload.get("context", {}).get("action", "")),
            context_hash="",
            status="error",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
