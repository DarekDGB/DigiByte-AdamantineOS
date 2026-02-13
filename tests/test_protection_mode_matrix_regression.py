from __future__ import annotations

import pytest

from adamantine.v1.execution.orchestrator_v2 import _compute_protection_mode


@pytest.mark.parametrize(
    "protected_requested,qid_ok,oracle_ok,shield_ok,expected",
    [
        # Not protected -> always legacy
        (False, False, False, False, "legacy"),
        (False, True, True, True, "legacy"),
        (False, True, False, True, "legacy"),

        # Protected requested but QID invalid -> legacy
        (True, False, True, True, "legacy"),
        (True, False, False, False, "legacy"),

        # QID valid but not full evidence -> minimal
        (True, True, False, False, "minimal"),
        (True, True, True, False, "minimal"),
        (True, True, False, True, "minimal"),

        # All valid -> full
        (True, True, True, True, "full"),
    ],
)
def test_protection_mode_matrix_is_locked(
    protected_requested: bool,
    qid_ok: bool,
    oracle_ok: bool,
    shield_ok: bool,
    expected: str,
) -> None:
    """
    Regression lock for v1.3.0 security posture.

    If this test fails, someone has changed protection mode semantics.
    """
    mode = _compute_protection_mode(
        protected_requested=protected_requested,
        qid_ok=qid_ok,
        oracle_ok=oracle_ok,
        shield_ok=shield_ok,
    )

    assert mode == expected
