from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.tva_gate import enforce_tva


def _ctx() -> ExecutionContext:
    return ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")


def _auth_matching(ctx: ExecutionContext) -> WSQKAuthority:
    return WSQKAuthority(wallet_id=ctx.wallet_id, action=ctx.action, context_hash=ctx.context_hash)


def test_missing_context_fail_closed() -> None:
    with pytest.raises(TVAError) as e:
        enforce_tva(None, Verdict.ALLOW, WSQKAuthority(wallet_id="w1", action="SEND", context_hash="abc123"))
    assert str(e.value) == ReasonId.TVA_MISSING_CONTEXT.value


def test_missing_verdict_fail_closed() -> None:
    ctx = _ctx()
    auth = _auth_matching(ctx)
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, None, auth)
    assert str(e.value) == ReasonId.TVA_MISSING_VERDICT.value


def test_missing_authority_fail_closed() -> None:
    ctx = _ctx()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, None)
    assert str(e.value) == ReasonId.TVA_MISSING_AUTHORITY.value


def test_verdict_deny_fail_closed() -> None:
    ctx = _ctx()
    auth = _auth_matching(ctx)
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.DENY, auth)
    assert str(e.value) == ReasonId.TVA_VERDICT_NOT_ALLOW.value


def test_authority_wallet_mismatch_fail_closed() -> None:
    ctx = _ctx()
    bad = WSQKAuthority(wallet_id="w2", action=ctx.action, context_hash=ctx.context_hash)
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_WALLET_MISMATCH.value


def test_authority_action_mismatch_fail_closed() -> None:
    ctx = _ctx()
    bad = WSQKAuthority(wallet_id=ctx.wallet_id, action="RECEIVE", context_hash=ctx.context_hash)
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_ACTION_MISMATCH.value


def test_authority_context_hash_mismatch_fail_closed() -> None:
    ctx = _ctx()
    bad = WSQKAuthority(wallet_id=ctx.wallet_id, action=ctx.action, context_hash="wrong")
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value


def test_allow_path_passes_when_all_truths_align() -> None:
    ctx = _ctx()
    auth = _auth_matching(ctx)
    enforce_tva(ctx, Verdict.ALLOW, auth)  # should not raise
