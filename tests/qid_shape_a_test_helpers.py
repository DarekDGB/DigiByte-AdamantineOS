from __future__ import annotations

from typing import Any

from adamantine.v1.integrations.qid_adapter import compute_qid_shape_a_proof_hash


def bind_shape_a_proof_hash(payload: dict[str, Any]) -> dict[str, Any]:
    bound = dict(payload)
    bound["proof_hash"] = compute_qid_shape_a_proof_hash(
        qid_iface_version=bound["qid_iface_version"],
        subject=bound["subject"],
        issued_at=bound["issued_at"],
        expires_at=bound["expires_at"],
        context_hash=bound.get("context_hash"),
        device_binding=bound.get("device_binding"),
        issuer_version=bound.get("issuer_version"),
    )
    replay_proof = bound.get("replay_proof")
    if isinstance(replay_proof, dict):
        bound["replay_proof"] = {**replay_proof, "proof_hash": bound["proof_hash"]}
    return bound
