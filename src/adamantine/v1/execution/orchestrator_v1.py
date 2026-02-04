from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.response_v1 import build_execution_response_v1
from adamantine.v1.execution.executor import Executor
from adamantine.v1.enforcement.nonce_store import NonceStore


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
) -> dict[str, Any]:
    """
    Execution Orchestrator v1 (sealed skeleton).

    Invariants:
    - Always returns execution_response_v1
    - Never raises
    - Response contract is always valid
    - Deny-by-default
    - No execution wiring in C1/C2
    """
    try:
        parsed = parse_execution_request_envelope_v1(payload=payload, now=now)

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
        request_id = _safe_str(payload.get("request_id"), fallback="invalid-request")
        action = _safe_str(
            payload.get("context", {}).get("action"),
            fallback="invalid-action",
        )

        # Deterministic placeholder — must be non-empty
        context_hash = "0" * 64

        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(payload.get("intent"), fallback="unknown"),
            action=action,
            context_hash=context_hash,
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
        request_id = _safe_str(payload.get("request_id"), fallback="invalid-request")
        action = _safe_str(
            payload.get("context", {}).get("action"),
            fallback="invalid-action",
        )

        context_hash = "0" * 64

        return build_execution_response_v1(
            request_id=request_id,
            intent=_safe_str(payload.get("intent"), fallback="unknown"),
            action=action,
            context_hash=context_hash,
            status="error",
            reason_id=ReasonId.DENY_SCHEMA_INVALID,
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
            artifacts={"error": str(e)},
        )
