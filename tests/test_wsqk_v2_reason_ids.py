from __future__ import annotations

from adamantine.v1.contracts.reason_ids import ReasonId


def test_wsqk_v2_reason_ids_are_stable_contract_values() -> None:
    assert ReasonId.WSQK_V2_INVALID_EVIDENCE_FAMILIES.value == "WSQK_V2_INVALID_EVIDENCE_FAMILIES"
    assert ReasonId.WSQK_V2_UNKNOWN_EVIDENCE_FAMILY.value == "WSQK_V2_UNKNOWN_EVIDENCE_FAMILY"
    assert ReasonId.WSQK_V2_INVALID_QUANTUM_POSTURE.value == "WSQK_V2_INVALID_QUANTUM_POSTURE"


def test_wsqk_v2_reason_ids_are_unique() -> None:
    values = [reason.value for reason in ReasonId]

    assert len(values) == len(set(values))
