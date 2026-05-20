"""
WSQK (Wallet-Scoped Quantum Key) — authority issuer (foundation).

This module issues WSQKAuthority tokens from explicit injected inputs.
No randomness, no global time, no side effects.
"""

from adamantine.v1.wsqk.issuer_v2 import (
    WSQK_AUTHORITY_V2,
    WSQKIssueRequestV2,
    canonical_required_evidence_families,
    compute_wsqk_v2_proof_bindings_hash,
    issue_wsqk_authority_v2,
)

__all__ = [
    "WSQK_AUTHORITY_V2",
    "WSQKIssueRequestV2",
    "canonical_required_evidence_families",
    "compute_wsqk_v2_proof_bindings_hash",
    "issue_wsqk_authority_v2",
]
