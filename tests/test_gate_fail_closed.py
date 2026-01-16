import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.tva_gate import enforce_tva


def test_tva_fail_closed_missing_context():
    with pytest.raises(TVAError) as e:
        enforce_tva(context=None, verdict=None, authority=None)
    assert str(e.value) == ReasonId.TVA_MISSING_CONTEXT.value


def test_tva_denies_when_verdict_not_allow():
    ctx = ExecutionContext(wallet_id="w1", action="SEND", context_hash="h1")
    with pytest.raises(TVAError) as e:
        enforce_tva(context=ctx, verdict=Verdict.DENY, authority=object())
    assert str(e.value) == ReasonId.TVA_VERDICT_NOT_ALLOW.value
