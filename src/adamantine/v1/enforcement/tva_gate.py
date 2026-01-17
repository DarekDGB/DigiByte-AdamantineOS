from __future__ import annotations

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict


def enforce_tva(*, context: ExecutionContext | None, verdict: Verdict | None, authority: object | None) -> None:
    # Fail-closed minimal TVA gate (skeleton).
    if context is None:
        raise TVAError(ReasonId.TVA_MISSING_CONTEXT.value)
    if verdict is None:
        raise TVAError(ReasonId.TVA_MISSING_VERDICT.value)
    if verdict is not Verdict.ALLOW:
        raise TVAError(ReasonId.TVA_VERDICT_NOT_ALLOW.value)

    # Authority semantics will be defined later; for now, presence is required.
    if authority is None:
        raise TVAError("TVA_MISSING_AUTHORITY")
