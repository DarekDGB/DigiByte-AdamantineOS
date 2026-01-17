from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthority
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva


def _ctx() -> ExecutionContext:
    return ExecutionContext(wallet_id="w1", action="SEND", context_hash="abc123")


def _auth_matching(ctx: ExecutionContext, *, issued_at: int = 100, expires_at: int = 200, nonce: str = "n1") -> WSQKAuthority:
    return WSQKAuthority(
        wallet_id=ctx.wallet_id,
        action=ctx.action,
        context_hash=ctx.context_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )


def test_missing_context_fail_closed() -> None:
    store = InMemoryNonceStore()
    with pytest.raises(TVAError) as e:
        enforce_tva(None, Verdict.ALLOW, _auth_matching(_ctx()), now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_MISSING_CONTEXT.value


def test_missing_verdict_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, None, _auth_matching(ctx), now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_MISSING_VERDICT.value


def test_missing_authority_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, None, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_MISSING_AUTHORITY.value


def test_missing_now_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, _auth_matching(ctx), nonce_store=store)
    assert str(e.value) == ReasonId.TVA_MISSING_NOW.value


def test_missing_nonce_store_fail_closed() -> None:
    ctx = _ctx()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, _auth_matching(ctx), now=150, nonce_store=None)
    assert str(e.value) == ReasonId.TVA_MISSING_NONCE_STORE.value


def test_verdict_deny_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.DENY, _auth_matching(ctx), now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_VERDICT_NOT_ALLOW.value


def test_authority_wallet_mismatch_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    bad = WSQKAuthority(
        wallet_id="w2",
        action=ctx.action,
        context_hash=ctx.context_hash,
        issued_at=100,
        expires_at=200,
        nonce="n1",
    )
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_WALLET_MISMATCH.value


def test_authority_action_mismatch_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    bad = WSQKAuthority(
        wallet_id=ctx.wallet_id,
        action="RECEIVE",
        context_hash=ctx.context_hash,
        issued_at=100,
        expires_at=200,
        nonce="n1",
    )
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_ACTION_MISMATCH.value


def test_authority_context_hash_mismatch_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    bad = WSQKAuthority(
        wallet_id=ctx.wallet_id,
        action=ctx.action,
        context_hash="wrong",
        issued_at=100,
        expires_at=200,
        nonce="n1",
    )
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH.value


def test_invalid_time_window_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    bad = _auth_matching(ctx, issued_at=200, expires_at=100, nonce="n1")
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, bad, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_INVALID_TIME_WINDOW.value


def test_not_yet_valid_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    auth = _auth_matching(ctx, issued_at=200, expires_at=300, nonce="n1")
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_NOT_YET_VALID.value


def test_expired_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    auth = _auth_matching(ctx, issued_at=100, expires_at=120, nonce="n1")
    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth, now=150, nonce_store=store)
    assert str(e.value) == ReasonId.TVA_AUTHORITY_EXPIRED.value


def test_nonce_replay_fail_closed() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    auth = _auth_matching(ctx, issued_at=100, expires_at=200, nonce="replay")

    enforce_tva(ctx, Verdict.ALLOW, auth, now=150, nonce_store=store)  # first time ok

    with pytest.raises(TVAError) as e:
        enforce_tva(ctx, Verdict.ALLOW, auth, now=150, nonce_store=store)  # replay
    assert str(e.value) == ReasonId.TVA_NONCE_REPLAY.value


def test_allow_path_passes_when_all_truths_align() -> None:
    ctx = _ctx()
    store = InMemoryNonceStore()
    auth = _auth_matching(ctx, issued_at=100, expires_at=200, nonce="unique")
    enforce_tva(ctx, Verdict.ALLOW, auth, now=150, nonce_store=store)  # should not raise
