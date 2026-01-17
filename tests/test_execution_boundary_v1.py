from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.execution_request import ExecutionRequest
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.execution.boundary import run_with_tva
from adamantine.v1.execution.executor import RecordingExecutor


def test_execution_never_called_when_tva_fails() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    req = ExecutionRequest(wallet_id="w1", action="SEND", payload="opaque")
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")

    # Authority does NOT match context_hash -> TVA must fail
    auth = WSQKAuthority(
        wallet_id="w1",
        action="SEND",
        context_hash="wrong",
        issued_at=100,
        expires_at=200,
        nonce="n1",
    )

    with pytest.raises(TVAError) as e:
        run_with_tva(
            executor=executor,
            request=req,
            context=ctx,
            verdict=Verdict.ALLOW,
            authority=auth,
            now=150,
            nonce_store=store,
        )

    assert str(e.value) == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value
    assert executor.called is False
    assert executor.last_request is None


def test_execution_called_only_when_tva_passes() -> None:
    executor = RecordingExecutor()
    store = InMemoryNonceStore()

    req = ExecutionRequest(wallet_id="w1", action="SEND", payload="opaque")
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")

    auth = WSQKAuthority(
        wallet_id="w1",
        action="SEND",
        context_hash="abc123",
        issued_at=100,
        expires_at=200,
        nonce="unique",
    )

    out = run_with_tva(
        executor=executor,
        request=req,
        context=ctx,
        verdict=Verdict.ALLOW,
        authority=auth,
        now=150,
        nonce_store=store,
    )

    assert out == "EXECUTED"
    assert executor.called is True
    assert executor.last_request == req
