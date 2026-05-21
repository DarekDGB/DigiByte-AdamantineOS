from __future__ import annotations

import dataclasses

import pytest

from adamantine.errors import TVAError
from adamantine.v1.contracts.context import ExecutionContext
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.enforcement.nonce_store import InMemoryNonceStore
from adamantine.v1.enforcement.tva_gate import enforce_tva
from adamantine.v1.wsqk.issuer import WSQKIssueRequest, issue_wsqk_authority
from adamantine.v1.wsqk.issuer_v2 import (
    WSQK_AUTHORITY_V2,
    WSQKIssueRequestV2,
    compute_wsqk_v2_proof_bindings_hash,
    issue_wsqk_authority_v2,
)
from adamantine.v1.wsqk.qid_binding import QIDPosture, validate_qid_binding


REQUIRED_FAMILIES = ["pqc_signature", "qid_hybrid"]
REQUIRED_POSTURE = "hybrid_required"


def _ctx() -> ExecutionContext:
    return ExecutionContext(wallet_id="wallet-1", action="SEND", context_hash="ctx-hash")


def _issue_v2(*, nonce: str = "nonce-1"):
    return issue_wsqk_authority_v2(
        WSQKIssueRequestV2(
            wallet_id="wallet-1",
            action="SEND",
            context_hash="ctx-hash",
            now=100,
            ttl_seconds=100,
            nonce=nonce,
            required_evidence_families=["qid_hybrid", "pqc_signature", "qid_hybrid"],
            quantum_posture=REQUIRED_POSTURE,
        )
    )


def _enforce(authority, *, nonce_store: InMemoryNonceStore | None = None) -> None:
    enforce_tva(
        _ctx(),
        Verdict.ALLOW,
        authority,
        now=150,
        nonce_store=nonce_store or InMemoryNonceStore(),
        required_evidence_families=REQUIRED_FAMILIES,
        required_quantum_posture=REQUIRED_POSTURE,
    )


def test_phase7_same_families_different_order_and_duplicates_produce_same_hash() -> None:
    left = issue_wsqk_authority_v2(
        WSQKIssueRequestV2(
            wallet_id="wallet-1",
            action="SEND",
            context_hash="ctx-hash",
            now=100,
            ttl_seconds=100,
            nonce="nonce-1",
            required_evidence_families=["qid_hybrid", "pqc_signature", "qid_hybrid"],
            quantum_posture=REQUIRED_POSTURE,
        )
    )
    right = issue_wsqk_authority_v2(
        WSQKIssueRequestV2(
            wallet_id="wallet-1",
            action="SEND",
            context_hash="ctx-hash",
            now=100,
            ttl_seconds=100,
            nonce="nonce-1",
            required_evidence_families=["pqc_signature", "qid_hybrid"],
            quantum_posture=REQUIRED_POSTURE,
        )
    )

    assert left.required_evidence_families == ("pqc_signature", "qid_hybrid")
    assert right.required_evidence_families == ("pqc_signature", "qid_hybrid")
    assert left.proof_bindings_hash == right.proof_bindings_hash


def test_phase7_hash_direct_computation_is_order_independent() -> None:
    base = dict(
        contract_version=WSQK_AUTHORITY_V2,
        wallet_id="wallet-1",
        action="SEND",
        context_hash="ctx-hash",
        issued_at=100,
        expires_at=200,
        nonce="nonce-1",
        quantum_posture=REQUIRED_POSTURE,
    )

    assert compute_wsqk_v2_proof_bindings_hash(
        **base,
        required_evidence_families=["qid_hybrid", "pqc_signature", "qid_hybrid"],
    ) == compute_wsqk_v2_proof_bindings_hash(
        **base,
        required_evidence_families=["pqc_signature", "qid_hybrid"],
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contract_version", "WSQK_AUTHORITY_V2_TAMPERED"),
        ("issued_at", 101),
        ("expires_at", 201),
        ("nonce", "nonce-tampered"),
        ("proof_bindings_hash", "0" * 64),
    ],
)
def test_phase7_tva_denies_proof_binding_tamper_before_nonce_use(field: str, value: object) -> None:
    authority = _issue_v2()
    tampered = dataclasses.replace(authority, **{field: value})
    nonce_store = InMemoryNonceStore()

    with pytest.raises(TVAError) as exc:
        _enforce(tampered, nonce_store=nonce_store)

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH.value

    # Tampered authorities must fail before the nonce is consumed.
    _enforce(authority, nonce_store=nonce_store)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("wallet_id", "wallet-2", ReasonId.TVA_AUTHORITY_WALLET_MISMATCH),
        ("action", "BURN", ReasonId.TVA_AUTHORITY_ACTION_MISMATCH),
        ("context_hash", "other-hash", ReasonId.TVA_AUTHORITY_CONTEXT_HASH_MISMATCH),
    ],
)
def test_phase7_tva_denies_context_binding_tamper_before_nonce_use(
    field: str,
    value: object,
    reason: ReasonId,
) -> None:
    authority = _issue_v2()
    tampered = dataclasses.replace(authority, **{field: value})
    nonce_store = InMemoryNonceStore()

    with pytest.raises(TVAError) as exc:
        _enforce(tampered, nonce_store=nonce_store)

    assert str(exc.value) == reason.value

    # Context-binding failures must also fail before nonce consumption.
    _enforce(authority, nonce_store=nonce_store)


def test_phase7_tva_denies_required_family_order_tamper() -> None:
    tampered = dataclasses.replace(
        _issue_v2(),
        required_evidence_families=("qid_hybrid", "pqc_signature"),
    )

    with pytest.raises(TVAError) as exc:
        _enforce(tampered)

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_EVIDENCE_FAMILY_MISMATCH.value


@pytest.mark.parametrize(
    "required_families",
    [
        ["qid_hybrid"],
        ["classical_signature", "pqc_signature", "qid_hybrid"],
    ],
)
def test_phase7_tva_denies_missing_or_extra_required_family(required_families: list[str]) -> None:
    with pytest.raises(TVAError) as exc:
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            _issue_v2(),
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=required_families,
            required_quantum_posture=REQUIRED_POSTURE,
        )

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_EVIDENCE_FAMILY_MISMATCH.value


def test_phase7_tva_denies_unknown_required_family_fail_closed() -> None:
    with pytest.raises(TVAError) as exc:
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            _issue_v2(),
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=["pqc_signature", "qid_hybrid", "unknown_family"],
            required_quantum_posture=REQUIRED_POSTURE,
        )

    assert str(exc.value) == ReasonId.WSQK_V2_UNKNOWN_EVIDENCE_FAMILY.value


def test_phase7_tva_denies_v1_downgrade_when_v2_requirements_are_present() -> None:
    authority_v1 = issue_wsqk_authority(
        WSQKIssueRequest(
            wallet_id="wallet-1",
            action="SEND",
            context_hash="ctx-hash",
            now=100,
            ttl_seconds=100,
            nonce="nonce-1",
        )
    )

    with pytest.raises(TVAError) as exc:
        _enforce(authority_v1)

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_REQUIRED.value


@pytest.mark.parametrize(
    "posture",
    [
        QIDPosture(classical=True, pqc=False),
        QIDPosture(classical=False, pqc=True),
        QIDPosture(classical=False, pqc=False),
    ],
)
def test_phase7_qid_binding_denies_hybrid_tamper(posture: QIDPosture) -> None:
    with pytest.raises(TVAError) as exc:
        validate_qid_binding(quantum_posture=REQUIRED_POSTURE, qid_posture=posture)

    assert str(exc.value) == ReasonId.WSQK_QID_HYBRID_REQUIRED.value


def test_phase7_qid_binding_allows_strict_hybrid_and_pqc_required() -> None:
    validate_qid_binding(
        quantum_posture="hybrid_required",
        qid_posture=QIDPosture(classical=True, pqc=True),
    )
    validate_qid_binding(
        quantum_posture="pqc_required",
        qid_posture=QIDPosture(classical=False, pqc=True),
    )
