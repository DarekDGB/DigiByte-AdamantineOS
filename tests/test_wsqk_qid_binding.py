from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.wsqk.qid_binding import QIDPosture, validate_qid_binding


def test_hybrid_required_denies_classical_only():
    try:
        validate_qid_binding(
            quantum_posture="hybrid_required",
            qid_posture=QIDPosture(classical=True, pqc=False),
        )
    except TVAError as exc:
        assert str(exc) == ReasonId.WSQK_QID_HYBRID_REQUIRED.value
    else:
        raise AssertionError("expected deny")


def test_hybrid_required_accepts_hybrid():
    validate_qid_binding(
        quantum_posture="hybrid_required",
        qid_posture=QIDPosture(classical=True, pqc=True),
    )
