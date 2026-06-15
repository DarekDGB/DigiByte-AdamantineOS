from __future__ import annotations

from pathlib import Path

import pytest

from adamantine.v1.contracts.reason_ids import ReasonId
from adamantine.v1.integrations.errors import AdapterError
from adamantine.v1.integrations.qid_adapter import (
    ADAMANTINE_QID_CANONICAL_JSON_PROFILE,
    canonical_qid_json_bytes,
    compute_qid_v2_response_payload_proof_hash,
    parse_qid_session,
)


_CONTEXT_HASH = "c" * 64
_EXPECTED_CANONICAL = (
    b'{"address":"DGB1-ADDRESS","context_hash":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",'
    b'"expires_at":200,"issued_at":100}'
)
_EXPECTED_HASH = "00606241b78c5131af309f8db85cb431e159e36dd2902da966d3599b6f4d54e7"


def _qid_v2_evidence(response_payload: dict[str, object], *, proof_hash: str | None = None) -> dict[str, object]:
    return {
        "v": "2",
        "kind": "qid_login_v2",
        "login_uri": "qid://login?x=1",
        "response_payload": response_payload,
        "signature": "sig",
        "subject": "DGB1-ADDRESS",
        "proof_hash": proof_hash if proof_hash is not None else compute_qid_v2_response_payload_proof_hash(response_payload),
    }


def test_step7_qid_canonical_json_profile_has_stable_name_and_vector() -> None:
    response_payload = {
        "expires_at": 200,
        "address": "DGB1-ADDRESS",
        "issued_at": 100,
        "context_hash": _CONTEXT_HASH,
    }

    assert ADAMANTINE_QID_CANONICAL_JSON_PROFILE == "adamantine-qid-canonical-json-v1"
    assert canonical_qid_json_bytes(response_payload) == _EXPECTED_CANONICAL
    assert compute_qid_v2_response_payload_proof_hash(response_payload) == _EXPECTED_HASH


def test_step7_qid_v2_parser_uses_named_profile_hash() -> None:
    response_payload = {
        "expires_at": 200,
        "address": "DGB1-ADDRESS",
        "issued_at": 100,
        "context_hash": _CONTEXT_HASH,
    }

    proof = parse_qid_session(payload=_qid_v2_evidence(response_payload), now=150)

    assert proof.subject == "DGB1-ADDRESS"
    assert proof.context_hash == _CONTEXT_HASH
    assert proof.proof_hash == _EXPECTED_HASH


def test_step7_qid_v2_rejects_non_finite_canonical_json_input() -> None:
    response_payload = {
        "address": "DGB1-ADDRESS",
        "issued_at": 100,
        "expires_at": 200,
        "context_hash": _CONTEXT_HASH,
        "risk_score": float("nan"),
    }

    with pytest.raises(AdapterError) as excinfo:
        parse_qid_session(payload=_qid_v2_evidence(response_payload, proof_hash="0" * 64), now=150)

    assert excinfo.value.reason_id is ReasonId.EQC_INVALID_QID_PROOF
    assert "canonicalization failed" in str(excinfo.value)


def test_step7_qid_canonical_json_profile_is_documented_and_indexed() -> None:
    doc = Path("docs/ADAMANTINEOS_QID_CANONICAL_JSON_PROFILE.md").read_text()
    contract = Path("docs/CONTRACTS/qid_linkage_v1.md").read_text()
    index = Path("docs/INDEX.md").read_text()

    assert "# AdamantineOS Q-ID Canonical JSON Profile" in doc
    assert "adamantine-qid-canonical-json-v1" in doc
    assert "sort_keys=True" in doc
    assert "separators=(\",\", \":\")" in doc
    assert "ensure_ascii=True" in doc
    assert "allow_nan=False" in doc
    assert _EXPECTED_HASH in doc
    assert "ADAMANTINEOS_QID_CANONICAL_JSON_PROFILE.md" in contract
    assert "ADAMANTINEOS_QID_CANONICAL_JSON_PROFILE.md" in index
