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
from adamantine.v1.wsqk.issuer_v2 import WSQKIssueRequestV2, issue_wsqk_authority_v2


def _ctx() -> ExecutionContext:
    return ExecutionContext(wallet_id="wallet-1", action="SEND", context_hash="ctx-hash")


def _v2_authority(*, nonce: str = "nonce-1"):
    return issue_wsqk_authority_v2(
        WSQKIssueRequestV2(
            wallet_id="wallet-1",
            action="SEND",
            context_hash="ctx-hash",
            now=100,
            ttl_seconds=100,
            nonce=nonce,
            required_evidence_families=["qid_hybrid", "pqc_signature"],
            quantum_posture="hybrid_required",
        )
    )


def test_tva_allows_matching_wsqk_v2_quantum_requirements() -> None:
    enforce_tva(
        _ctx(),
        Verdict.ALLOW,
        _v2_authority(),
        now=150,
        nonce_store=InMemoryNonceStore(),
        required_evidence_families=["pqc_signature", "qid_hybrid", "pqc_signature"],
        required_quantum_posture="hybrid_required",
    )


def test_tva_requires_v2_authority_when_quantum_requirements_are_present() -> None:
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
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            authority_v1,
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=["pqc_signature", "qid_hybrid"],
        )

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_REQUIRED.value


def test_tva_denies_wsqk_v2_evidence_family_mismatch() -> None:
    with pytest.raises(TVAError) as exc:
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            _v2_authority(),
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=["classical_signature", "pqc_signature", "qid_hybrid"],
            required_quantum_posture="hybrid_required",
        )

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_EVIDENCE_FAMILY_MISMATCH.value


def test_tva_denies_wsqk_v2_quantum_posture_mismatch() -> None:
    with pytest.raises(TVAError) as exc:
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            _v2_authority(),
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=["pqc_signature", "qid_hybrid"],
            required_quantum_posture="pqc_required",
        )

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_QUANTUM_POSTURE_MISMATCH.value


def test_tva_denies_wsqk_v2_tampered_proof_bindings_hash() -> None:
    tampered = dataclasses.replace(_v2_authority(), proof_bindings_hash="0" * 64)

    with pytest.raises(TVAError) as exc:
        enforce_tva(
            _ctx(),
            Verdict.ALLOW,
            tampered,
            now=150,
            nonce_store=InMemoryNonceStore(),
            required_evidence_families=["pqc_signature", "qid_hybrid"],
            required_quantum_posture="hybrid_required",
        )

    assert str(exc.value) == ReasonId.TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH.value
