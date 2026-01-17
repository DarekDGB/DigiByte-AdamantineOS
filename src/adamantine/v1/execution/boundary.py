from __future__ import annotations

from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import NonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.execution.executor import Executor


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

    This function is the *only* allowed path to real execution.
    It enforces TVA first. If TVA passes, it calls the executor.
    """
    enforce_tva(context, verdict, authority, now=now, nonce_store=nonce_store)
    return executor.execute(request)
