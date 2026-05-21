# WSQK v2 Quantum-Aware Proof Pack

**License:** MIT — **Author:** DarekDGB  
**Status:** v2.2.0 release proof-pack lock  
**Scope:** Audit map for the WSQK v2 quantum-aware upgrade inside AdamantineOS.

---

## 1. Purpose

This proof pack closes the WSQK v2 quantum-aware upgrade by mapping the implemented work back to the contract, invariants, tests, and CI proof.

WSQK v2 is not treated as a loose feature. It is treated as a deterministic authority contract with explicit enforcement and regression locks.

The upgrade path proves that WSQK v2 now binds authority to:

- wallet identity
- requested action
- execution context hash
- deterministic nonce/time window
- required evidence families
- declared quantum posture
- deterministic proof-bindings hash
- Q-ID classical/PQC posture requirements
- TVA and orchestrator enforcement boundaries

---

## 2. Contract Source of Truth

Normative contract:

`docs/CONTRACTS/wsqk_authority_v2.md`

Normative objects:

- `WSQKAuthorityV2`
- `WSQKIssueRequestV2`

Normative Phase 1 invariant:

`required_evidence_families` MUST be stored and compared as a sorted canonical set. Order of input is normalized on issuance. Two authorities requiring the same families MUST produce identical `proof_bindings_hash` values regardless of input order.

---

## 3. Implementation Map

| Area | File | Responsibility |
|---|---|---|
| Authority contract models | `src/adamantine/v1/contracts/authority.py` | Defines WSQK v2 authority shape. |
| Reason ID source of truth | `src/adamantine/v1/contracts/reason_ids.py` | Defines stable deterministic deny reasons. |
| WSQK v2 issuer | `src/adamantine/v1/wsqk/issuer_v2.py` | Issues v2 authority and computes canonical proof-bindings hash. |
| Q-ID posture binding | `src/adamantine/v1/wsqk/qid_binding.py` | Enforces strict Q-ID classical/PQC posture requirements. |
| TVA enforcement | `src/adamantine/v1/enforcement/tva_gate.py` | Enforces v2-only requirements and denies mismatches fail-closed. |
| Orchestrator/runtime boundary | `src/adamantine/v1/execution/orchestrator_v2.py` | Propagates WSQK v2 requirements without silent v1 fallback. |

---

## 4. Invariant Map

| Invariant | Enforcement / Proof |
|---|---|
| Deterministic canonical evidence families | `issuer_v2.py`, `test_wsqk_issuer_v2.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| Same evidence set produces same hash regardless of input order | `test_wsqk_v2_phase7_regression_locks.py` |
| Unknown evidence family fails closed | `issuer_v2.py`, `test_wsqk_issuer_v2.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| Missing/extra evidence family denied by TVA | `tva_gate.py`, `test_wsqk_v2_tva_enforcement.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| Tampered proof-bindings hash denied before nonce use | `tva_gate.py`, `test_wsqk_v2_tva_enforcement.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| WSQK v1 cannot satisfy explicit v2 requirements | `tva_gate.py`, `test_wsqk_v2_tva_enforcement.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| Hybrid-required Q-ID posture requires classical AND PQC | `qid_binding.py`, `test_wsqk_qid_binding.py`, `test_wsqk_v2_phase7_regression_locks.py` |
| PQC-required posture requires PQC evidence | `qid_binding.py`, `test_wsqk_qid_binding.py` |
| Runtime must not silently drop v2 requirements | `orchestrator_v2.py`, `test_wsqk_v2_orchestrator_runtime.py` |
| Reason IDs are stable and unique | `reason_ids.py`, `test_wsqk_v2_reason_ids.py` |

---

## 5. Reason ID Map

WSQK v2 issuer validation:

- `WSQK_V2_INVALID_EVIDENCE_FAMILIES`
- `WSQK_V2_UNKNOWN_EVIDENCE_FAMILY`
- `WSQK_V2_INVALID_QUANTUM_POSTURE`

TVA WSQK v2 enforcement:

- `TVA_WSQK_V2_REQUIRED`
- `TVA_WSQK_V2_EVIDENCE_FAMILY_MISMATCH`
- `TVA_WSQK_V2_QUANTUM_POSTURE_MISMATCH`
- `TVA_WSQK_V2_PROOF_BINDINGS_HASH_MISMATCH`

WSQK v2 Q-ID posture binding:

- `WSQK_QID_POSTURE_MISMATCH`
- `WSQK_QID_HYBRID_REQUIRED`
- `WSQK_QID_BINDING_INVALID`

---

## 6. Test Map

| Test file | Proof coverage |
|---|---|
| `tests/test_wsqk_issuer_v2.py` | v2 issuer, canonical families, deterministic hashing, invalid input denial. |
| `tests/test_wsqk_v2_reason_ids.py` | reason ID stability and uniqueness. |
| `tests/test_wsqk_v2_tva_enforcement.py` | TVA v2 posture enforcement and tamper rejection. |
| `tests/test_wsqk_qid_binding.py` | Q-ID posture binding for hybrid and PQC-required modes. |
| `tests/test_wsqk_v2_orchestrator_runtime.py` | orchestrator/runtime requirement propagation and malformed input rejection. |
| `tests/test_wsqk_v2_phase7_regression_locks.py` | negative-first tamperproof regression locks for hashes, downgrade, posture tamper, and family drift. |

---

## 7. Phase Closure Map

| Phase | Closure |
|---|---|
| Phase 1 | Contract and canonical sorted evidence-family invariant locked. |
| Phase 2 | WSQK v2 data model, issuer, and deterministic proof-bindings hash added. |
| Phase 3 | WSQK v2 reason IDs locked as stable contract values. |
| Phase 4 | TVA enforces WSQK v2 quantum posture and denies tampered bindings. |
| Phase 5 | Q-ID classical/PQC posture binding added with strict hybrid AND semantics. |
| Phase 6 | Orchestrator/runtime boundary propagates explicit WSQK v2 requirements. |
| Phase 7 | Tamperproof regression tests lock downgrade, hash, family, context, and posture failures. |
| Phase 8 | This proof pack maps contract, invariants, implementation, tests, and CI proof. |

---

## 8. CI Proof Requirement

This upgrade is considered closed only when GitHub Actions runs the full test suite with the repository coverage gate enabled and passes.

Required proof:

- all tests pass
- coverage remains at the configured repository threshold
- no WSQK v2 test is skipped
- no runtime fallback is introduced to satisfy failing tests

At v2.2.0 release closure, WSQK v2 is auditable as a quantum-aware authority layer rather than only a functional runtime feature.

---

## 9. Non-Goals

WSQK v2 does not:

- generate private keys
- sign DigiByte transactions
- broadcast transactions
- replace Q-ID cryptographic verification
- replace TVA final enforcement
- autonomously approve execution
- infer missing authority
- silently upgrade v1 authority into v2 authority

All final execution decisions remain explicit, deterministic, and fail-closed.
