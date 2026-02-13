from __future__ import annotations

from typing import Any, Mapping

from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.execution.envelope_v1 import parse_execution_request_envelope_v1
from adamantine.v1.execution.errors import EnvelopeError
from adamantine.v1.execution.executor import Executor
from adamantine.v1.execution.response_v1 import build_execution_response_v1


def run_with_tva(
    *,
    executor: Executor,
    request: ExecutionRequest,
    context: ExecutionContext,
    verdict: Verdict,
    authority: WSQKAuthority,
    now: int,
    nonce_store: NonceStore,
) -> str:
    """
    The execution boundary.

    This function is the only permitted path to real execution.
    It enforces TVA first. If TVA passes, it calls the executor.
    """
    enforce_tva(context, verdict, authority, now=now, nonce_store=nonce_store)
    return executor.execute(request)


def handle_execution_request_v1(
    *,
    raw: Mapping[str, Any],
    now: int,
) -> dict[str, Any]:
    """
    Parse and validate an Execution Request Envelope v1 and return an
    Execution Response Envelope v1.

    This function never performs real execution. It exists to provide a strict,
    fail-closed interface for mobile clients. Requests that do not pass
    validation are denied with an explicit ReasonId.
    """
    request_id = "<unknown>"
    intent = "<unknown>"
    action = "<unknown>"
    context_hash = "0" * 64

    try:
        parsed = parse_execution_request_envelope_v1(payload=raw, now=now)
        request_id = parsed.request_id
        intent = parsed.intent
        action = parsed.context.action
        context_hash = parsed.context.context_hash
    except EnvelopeError as e:
        if isinstance(raw, Mapping):
            rid_raw = raw.get("request_id")
            if isinstance(rid_raw, str) and rid_raw:
                request_id = rid_raw

        return build_execution_response_v1(
            request_id=request_id,
            intent=intent,
            action=action,
            context_hash=context_hash,
            status="deny",
            reason_id=e.reason_id,
            protection_mode="legacy",
            tva_allowed=False,
            eqc_allowed=False,
            wsqk_allowed=False,
            nonce_consumed=False,
            timebox_valid=False,
        )

    return build_execution_response_v1(
        request_id=request_id,
        intent=intent,
        action=action,
        context_hash=context_hash,
        status="deny",
        reason_id=ReasonId.DENY_NOT_WIRED,
        protection_mode="legacy",
        tva_allowed=False,
        eqc_allowed=False,
        wsqk_allowed=False,
        nonce_consumed=False,
        timebox_valid=True,
    )
