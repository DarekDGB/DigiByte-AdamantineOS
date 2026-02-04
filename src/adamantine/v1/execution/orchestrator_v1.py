from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.response_v1 import build_execution_response_v1


def orchestrate_execution_v1(
    *,
    payload: Mapping[str, Any],
    now: int,
) -> dict[str, Any]:
    """
    Execution Orchestrator v1 (skeleton).

    C1 invariant:
    - Always returns execution_response_v1 (never raises).
    - Fail-closed.
    - No execution wiring is performed yet (DENY_NOT_WIRED).
    """
    try:
        parsed = parse_execution_request_envelope_v1(payload=payload, now=now)

        # C1: Orchestrator exists as the single entry point, but is not wired to execute yet.
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
        # Envelope parsing/validation already produces stable, contract-locked reason ids.
        return build_execution_response_v1(
            request_id=str(getattr(payload, "get", lambda *_: "")("request_id", "")),
            intent=str(getattr(payload, "get", lambda *_: "")("intent", "")),
            action=str(getattr(payload, "get", lambda *_: "")("context", {}) or {}).get("action", ""),
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
        # Unknown failures are reported deterministically without inventing new reason ids.
        return build_execution_response_v1(
            request_id=str(getattr(payload, "get", lambda *_: "")("request_id", "")),
            intent=str(getattr(payload, "get", lambda *_: "")("intent", "")),
            action=str(getattr(payload, "get", lambda *_: "")("context", {}) or {}).get("action", ""),
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
