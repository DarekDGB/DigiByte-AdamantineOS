from __future__ import annotations

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.wsqk.issuer import WSQKIssueRequest, issue_wsqk_authority


def test_issuer_creates_expected_authority() -> None:
    req = WSQKIssueRequest(
        wallet_id="w1",
        action="SEND",
        context_hash="abc123",
        now=100,
        ttl_seconds=60,
        nonce="n1",
    )
    a = issue_wsqk_authority(req)
    assert a.wallet_id == "w1"
    assert a.action == "SEND"
    assert a.context_hash == "abc123"
    assert a.issued_at == 100
    assert a.expires_at == 160
    assert a.nonce == "n1"


def test_issuer_rejects_non_positive_ttl() -> None:
    req = WSQKIssueRequest(
        wallet_id="w1",
        action="SEND",
        context_hash="abc123",
        now=100,
        ttl_seconds=0,
        nonce="n1",
    )
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(req)
    assert str(e.value) == ReasonId.TVA_INVALID_TIME_WINDOW.value


def test_issuer_rejects_empty_nonce() -> None:
    req = WSQKIssueRequest(
        wallet_id="w1",
        action="SEND",
        context_hash="abc123",
        now=100,
        ttl_seconds=60,
        nonce="",
    )
    with pytest.raises(TVAError) as e:
        issue_wsqk_authority(req)
    assert str(e.value) == ReasonId.TVA_INVALID_NONCE.value
