from __future__ import annotations

import hashlib
import json

import pytest

from adamantine.v1.contracts.qid import QIDSessionProof
from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.contracts.verdict import Verdict
from adamantine.v1.eqc.context_hash import compute_context_hash
from adamantine.v1.eqc.evaluator import evaluate_eqc, evaluate_eqc_v2
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import parse_qid_session


def _canon_json_bytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def test_qid_session_rejects_malformed_context_hash_when_present() -> None:
    proof = QIDSessionProof(
        subject="did:example:123",
        issued_at=100,
        expires_at=200,
        proof_hash="proofhash123",
        context_hash="not-a-sha256",
    )

    with pytest.raises(ValueError, match="context_hash"):
        proof.validate(now=150)


def test_qid_adapter_shape_a_rejects_malformed_context_hash() -> None:
    payload = {
        "qid_iface_version": "qid-session-v0",
        "subject": "did:example:123",
        "issued_at": 100,
        "expires_at": 200,
        "proof_hash": "proofhash123",
        "context_hash": "BAD",
    }

    with pytest.raises(AdapterError) as exc:
        parse_qid_session(payload=payload, now=150)

    assert exc.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_qid_adapter_shape_b_rejects_malformed_context_hash() -> None:
    response_payload = {
        "address": "DGB1",
        "issued_at": 100,
        "expires_at": 200,
        "context_hash": "BAD",
    }
    evidence = {
        "v": "2",
        "kind": "qid_login_v2",
        "response_payload": response_payload,
        "proof_hash": hashlib.sha256(_canon_json_bytes(response_payload)).hexdigest(),
    }

    with pytest.raises(AdapterError) as exc:
        parse_qid_session(payload=evidence, now=150)

    assert exc.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF


def test_eqc_v1_denies_qid_context_hash_mismatch_with_dedicated_reason() -> None:
    ctx_hash = compute_context_hash(wallet_id="w1", action="SEND", fields=None)
    assert ctx_hash != "0" * 64
    session = QIDSessionProof(
        subject="did:example:123",
        issued_at=100,
        expires_at=200,
        proof_hash="proofhash123",
        context_hash="0" * 64,
    )

    out = evaluate_eqc(wallet_id="w1", action="SEND", fields=None, session=session, risk=None, now=150)

    assert out.verdict is Verdict.DENY
    assert out.reason_ids == (ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH.value,)


def test_eqc_v2_denies_qid_context_hash_mismatch_with_dedicated_reason() -> None:
    ctx_hash = compute_context_hash(wallet_id="w1", action="send", fields={"a": "1"})
    assert ctx_hash != "0" * 64
    session = QIDSessionProof(
        subject="did:example:123",
        issued_at=100,
        expires_at=200,
        proof_hash="proofhash123",
        context_hash="0" * 64,
    )

    out = evaluate_eqc_v2(wallet_id="w1", action="send", fields={"a": "1"}, session=session, now=150)

    assert out.verdict is Verdict.DENY
    assert out.reason_ids == (ReasonId.EQC_QID_CONTEXT_HASH_MISMATCH.value,)
