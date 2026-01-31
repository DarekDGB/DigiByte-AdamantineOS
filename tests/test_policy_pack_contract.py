from __future__ import annotations

import pytest

from adamantine.v1.contracts.policy_pack import PolicyPack
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.shield import ExternalReasonMap, ExternalReasonMapEntry


def test_default_policy_pack_is_valid() -> None:
    p = PolicyPack()
    p.validate()
    assert p.min_overall_score == 85
    assert p.allowed_external_reason_ids == ("ok",)


def test_policy_pack_rejects_invalid_score_types_and_ranges() -> None:
    with pytest.raises(ValueError):
        PolicyPack(min_overall_score="x").validate()  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        PolicyPack(min_overall_score=-1).validate()
    with pytest.raises(ValueError):
        PolicyPack(min_overall_score=101).validate()


def test_policy_pack_requires_tuple_allowlist() -> None:
    with pytest.raises(ValueError):
        PolicyPack(allowed_external_reason_ids=["ok"]).validate()  # type: ignore[arg-type]


def test_policy_pack_requires_non_empty_allowlist() -> None:
    with pytest.raises(ValueError):
        PolicyPack(allowed_external_reason_ids=()).validate()


def test_policy_pack_rejects_blank_and_duplicate_entries() -> None:
    with pytest.raises(ValueError):
        PolicyPack(allowed_external_reason_ids=("ok", "")).validate()
    with pytest.raises(ValueError):
        PolicyPack(allowed_external_reason_ids=("ok", "ok")).validate()


def test_policy_pack_requires_non_empty_reason_map() -> None:
    m = ExternalReasonMap(entries=())
    p = PolicyPack(external_reason_map=m)
    with pytest.raises(ValueError):
        p.validate()


def test_policy_pack_requires_allowlist_subset_of_map() -> None:
    m = ExternalReasonMap(
        entries=(ExternalReasonMapEntry(external_id="ok", internal_reason_id=ReasonId.EVIDENCE_OK.value),)
    )
    p = PolicyPack(allowed_external_reason_ids=("ok", "NEW_REASON"), external_reason_map=m)
    with pytest.raises(ValueError):
        p.validate()
