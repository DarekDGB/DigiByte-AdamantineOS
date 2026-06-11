# DigiByte AdamantineOS v3.0.0 — Release Notes

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Public project name: **DigiByte AdamantineOS**  
Release tag: `v3.0.0`  
Release type: **major release boundary**

---

## Summary

DigiByte AdamantineOS `v3.0.0` marks the first major release boundary after approximately seven months of building, integrating, hardening, documenting, and red-team reviewing the AdamantineOS protection architecture.

This release records the point where the major protection layers are connected into one deterministic final-policy runtime authority path.

AdamantineOS is not a wallet UI and does not change DigiByte consensus. It is an external fail-closed execution protection boundary that can sit before signing, broadcasting, AI-assisted execution, wallet flows, or other high-risk actions.

---

## What changed from v2.2.0 to v3.0.0

`v2.2.0` locked WSQK v2 quantum-aware authority.

`v3.0.0` locks the integrated runtime authority boundary around all major evidence sources:

```text
Q-ID
Shield v3.2.0 Orchestrator receipts
WSQK v2
Adaptive Core / wallet policy evidence
EQC evaluation
Replay / nonce enforcement
Human gate evidence
Final AdamantineOS policy engine
```

Execution is allowed only after the final engine produces:

```text
ALLOW_FINAL_ADAMANTINEOS_DECISION
```

Any deny, mismatch, authority bypass attempt, missing required evidence, stale/replayed evidence, or unexpected ALLOW inside an already-rejected branch fails closed.

---

## Seven-month completion boundary

This release represents the completed first major AdamantineOS integration arc:

1. Foundation runtime and execution contracts.
2. 100% coverage enforcement.
3. Q-ID replay and posture boundaries.
4. Adaptive Core governance compatibility.
5. WSQK v2 quantum-aware authority.
6. Shield v3.2.0 orchestrator receipt integration.
7. Level 4 full negative-test matrix.
8. Public rebrand to DigiByte AdamantineOS.
9. Authorized Claude AI red-team review and no-debt closure.
10. Milestone 19 final release gate and release stamp.

---

## Red-team closure

Authorized Claude AI red-team findings were accepted where valid and fixed:

```text
F1-F8: fixed or resolved
N1-N2: fixed
N3-N6: closed or superseded
N7: closed
N8: fixed
No HIGH / MEDIUM / LOW / NOTE findings remain open
No known red-team technical debt carried forward
```

The final closure report is archived in both formats:

```text
docs/RED_TEAM/ADAMANTINEOS_MILESTONE_18_FINAL_CLOSURE_REVIEW.docx
docs/RED_TEAM/ADAMANTINEOS_MILESTONE_18_FINAL_CLOSURE_REVIEW.md
```

---

## Test and coverage proof

```text
PYTHONPATH=src python -m pytest -q
925 passed
100.00% coverage
TOTAL 4097 statements, 0 missed
```

---

## Compatibility notes

```text
Public project name: DigiByte AdamantineOS
Repository: DigiByte-AdamantineOS
Internal package distribution name: adamantine-wallet-os
Python import paths: unchanged
Package version: 3.0.0
DigiByte consensus change: no
```

The package distribution name remains unchanged intentionally for compatibility. The public project name is DigiByte AdamantineOS.

---

## Tagging rule

The `v3.0.0` tag must only be created after this release-stamp package is copied into the repository, CI remains green, and one final fresh ZIP is inspected.
