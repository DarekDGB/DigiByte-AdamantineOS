import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.wsqk.qid_binding import QIDPosture, validate_qid_binding


def test_qid_binding_allows_matching_hybrid_posture() -> None:
    validate_qid_binding(
        quantum_posture="hybrid_required",
        qid_posture=QIDPosture(classical=True, pqc=True),
    )


def test_qid_binding_denies_classical_only_when_hybrid_required() -> None:
    with pytest.raises(TVAError) as exc:
        validate_qid_binding(
            quantum_posture="hybrid_required",
            qid_posture=QIDPosture(classical=True, pqc=False),
        )

    assert str(exc.value) == ReasonId.WSQK_QID_HYBRID_REQUIRED.value


def test_qid_binding_denies_pqc_only_when_hybrid_required() -> None:
    with pytest.raises(TVAError) as exc:
        validate_qid_binding(
            quantum_posture="hybrid_required",
            qid_posture=QIDPosture(classical=False, pqc=True),
        )

    assert str(exc.value) == ReasonId.WSQK_QID_HYBRID_REQUIRED.value


def test_qid_binding_allows_matching_pqc_required_posture() -> None:
    validate_qid_binding(
        quantum_posture="pqc_required",
        qid_posture=QIDPosture(classical=False, pqc=True),
    )


def test_qid_binding_denies_missing_pqc_when_pqc_required() -> None:
    with pytest.raises(TVAError) as exc:
        validate_qid_binding(
            quantum_posture="pqc_required",
            qid_posture=QIDPosture(classical=True, pqc=False),
        )

    assert str(exc.value) == ReasonId.WSQK_QID_POSTURE_MISMATCH.value


def test_qid_binding_allows_non_quantum_required_posture() -> None:
    validate_qid_binding(
        quantum_posture="classical_allowed",
        qid_posture=QIDPosture(classical=True, pqc=False),
    )
