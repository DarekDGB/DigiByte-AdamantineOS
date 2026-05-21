from adamantine.v1.contracts.reason_ids import (
    WSQK_V2_QID_BINDING_MISSING,
    WSQK_V2_QID_HYBRID_REQUIRED,
)
from adamantine.v1.wsqk.qid_binding import validate_qid_posture_binding


def test_qid_binding_allows_matching_hybrid_posture() -> None:
    result = validate_qid_posture_binding(
        required_quantum_posture="hybrid",
        qid_posture={
            "classical": True,
            "pqc": True,
        },
    )

    assert result.allowed is True
    assert result.reason_id == "ALLOW"


def test_qid_binding_denies_missing_qid_posture() -> None:
    result = validate_qid_posture_binding(
        required_quantum_posture="hybrid",
        qid_posture=None,
    )

    assert result.allowed is False
    assert result.reason_id == WSQK_V2_QID_BINDING_MISSING


def test_qid_binding_denies_classical_only_when_hybrid_required() -> None:
    result = validate_qid_posture_binding(
        required_quantum_posture="hybrid",
        qid_posture={
            "classical": True,
            "pqc": False,
        },
    )

    assert result.allowed is False
    assert result.reason_id == WSQK_V2_QID_HYBRID_REQUIRED


def test_qid_binding_allows_non_hybrid_requirement_without_qid_posture() -> None:
    result = validate_qid_posture_binding(
        required_quantum_posture="classical",
        qid_posture=None,
    )

    assert result.allowed is True
    assert result.reason_id == "ALLOW"
