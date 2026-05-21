from __future__ import annotations

from dataclasses import dataclass

from adamantine.errors import TVAError
from adamantine.v1.contracts.reason_ids import ReasonId


@dataclass(frozen=True, slots=True)
class QIDPosture:
    classical: bool
    pqc: bool


def validate_qid_binding(*, quantum_posture: str, qid_posture: QIDPosture) -> None:
    if quantum_posture == "hybrid_required":
        if not (qid_posture.classical and qid_posture.pqc):
            raise TVAError(ReasonId.WSQK_QID_HYBRID_REQUIRED.value)

    if quantum_posture == "pqc_required" and not qid_posture.pqc:
        raise TVAError(ReasonId.WSQK_QID_POSTURE_MISMATCH.value)
