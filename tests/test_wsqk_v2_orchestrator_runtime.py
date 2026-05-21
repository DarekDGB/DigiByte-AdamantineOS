import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.authority import WSQKAuthorityV2
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.execution import orchestrator_v2 as o2
from adamantine.v1.wsqk.issuer_v2 import WSQK_AUTHORITY_V2


BASE_WSQK_V2 = {
    "contract_version": WSQK_AUTHORITY_V2,
    "wallet_id": "wallet-1",
    "action": "sign",
    "context_hash": "a" * 64,
    "issued_at": 100,
    "expires_at": 200,
    "nonce": "nonce-1",
    "required_evidence_families": ["pqc_signature", "qid_hybrid"],
    "quantum_posture": "hybrid_required",
    "proof_bindings_hash": "b" * 64,
}


def _extract_with(wsqk: dict[str, object]):
    return o2._extract_wsqk_authority(
        wallet_id="wallet-1",
        action="sign",
        context_hash="a" * 64,
        nonce_value="nonce-1",
        issued_at=100,
        expires_at=200,
        authority_proofs={"wsqk": wsqk},
    )


def test_orchestrator_extracts_wsqk_v2_authority() -> None:
    authority = _extract_with(dict(BASE_WSQK_V2))

    assert isinstance(authority, WSQKAuthorityV2)
    assert authority.contract_version == WSQK_AUTHORITY_V2
    assert authority.required_evidence_families == ("pqc_signature", "qid_hybrid")
    assert authority.quantum_posture == "hybrid_required"
    assert authority.proof_bindings_hash == "b" * 64


@pytest.mark.parametrize(
    "patch",
    [
        {"required_evidence_families": "pqc_signature"},
        {"required_evidence_families": ["pqc_signature", 7]},
        {"quantum_posture": ""},
        {"quantum_posture": None},
        {"proof_bindings_hash": ""},
        {"proof_bindings_hash": None},
    ],
)
def test_orchestrator_rejects_malformed_wsqk_v2_authority(patch: dict[str, object]) -> None:
    wsqk = dict(BASE_WSQK_V2)
    wsqk.update(patch)

    assert _extract_with(wsqk) is None


def test_orchestrator_wsqk_v2_requirements_default_to_legacy_none() -> None:
    assert o2._extract_wsqk_v2_runtime_requirements({}) == (None, None)


def test_orchestrator_extracts_wsqk_v2_runtime_requirements() -> None:
    families, posture = o2._extract_wsqk_v2_runtime_requirements(
        {
            "wsqk_v2": {
                "required_evidence_families": ["qid_hybrid", "pqc_signature"],
                "required_quantum_posture": "hybrid_required",
            }
        }
    )

    assert families == ("qid_hybrid", "pqc_signature")
    assert posture == "hybrid_required"


@pytest.mark.parametrize(
    "scope",
    [
        {"wsqk_v2": "required"},
        {"wsqk_v2": {"required_evidence_families": "qid_hybrid", "required_quantum_posture": "hybrid_required"}},
        {"wsqk_v2": {"required_evidence_families": ["qid_hybrid", 7], "required_quantum_posture": "hybrid_required"}},
        {"wsqk_v2": {"required_evidence_families": ["qid_hybrid"], "required_quantum_posture": ""}},
        {"wsqk_v2": {"required_evidence_families": ["qid_hybrid"], "required_quantum_posture": None}},
    ],
)
def test_orchestrator_rejects_invalid_wsqk_v2_runtime_requirements(scope: dict[str, object]) -> None:
    with pytest.raises(TVAError) as exc:
        o2._extract_wsqk_v2_runtime_requirements(scope)

    assert str(exc.value) == ReasonId.DENY_AUTHORITY_INVALID.value
