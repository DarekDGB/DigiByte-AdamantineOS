# WSQK Authority v2 Contract — Quantum-Aware Authority

**License:** MIT — **Author:** DarekDGB  
**Status:** Phase 1 contract lock  
**Scope:** Normative contract for WSQK v2 quantum-aware authority proofs inside AdamantineOS.

---

## 1. Purpose

WSQK v2 upgrades Wallet-Scoped Quantum Key authority from a time-bound wallet/action/context token into a quantum-aware authority proof.

WSQK v2 does not execute actions, hold keys, generate keys, sign transactions, broadcast transactions, or decide final allow/deny outcomes by itself.

WSQK v2 proves that a declared wallet authority is bound to:

- a wallet identity
- an explicit action
- an execution context hash
- a time window
- a nonce
- required evidence families
- quantum/security posture requirements
- deterministic proof bindings

AdamantineOS consumes WSQK v2 as explicit authority evidence. Final execution decisions remain governed by the Adamantine execution boundary and TVA enforcement.

---

## 2. Contract Name

The normative authority object is named:

`WSQKAuthorityV2`

The normative issuer request object is named:

`WSQKIssueRequestV2`

Future implementation files must preserve this naming unless a major contract version bump is introduced.

---

## 3. Required Authority Fields

A valid `WSQKAuthorityV2` MUST contain the following fields:

| Field | Type | Requirement |
| --- | --- | --- |
| `contract_version` | string | MUST equal `WSQK_AUTHORITY_V2` |
| `wallet_id` | string | non-empty |
| `action` | string | non-empty |
| `context_hash` | string | non-empty deterministic hash |
| `issued_at` | integer | injected time value; no global clock |
| `expires_at` | integer | MUST be greater than `issued_at` |
| `nonce` | string | non-empty; single-use |
| `required_evidence_families` | list[string] | sorted canonical unique set |
| `quantum_posture` | string | explicit posture declaration |
| `proof_bindings_hash` | string | deterministic hash over canonical binding inputs |

Any missing, malformed, ambiguous, or unsupported field MUST deny deterministically.

---

## 4. Required Evidence Families — Locked Invariant

`required_evidence_families` MUST be stored and compared as a sorted canonical set. Order of input is normalized on issuance. Two authorities requiring the same families MUST produce identical `proof_bindings_hash` values regardless of input order.

This is a named Phase 1 invariant and MUST NOT drift in later phases.

### 4.1 Canonical Set Rules

The required evidence family list MUST be:

- explicitly provided
- non-empty
- deduplicated before hashing
- sorted in deterministic lexicographic order before hashing
- compared only after canonicalization
- included in `proof_bindings_hash` only after canonicalization

The following inputs are semantically equivalent and MUST hash identically after canonicalization:

```json
["qid_hybrid", "pqc_signature", "qid_hybrid"]
```

```json
["pqc_signature", "qid_hybrid"]
```

Canonical form:

```json
["pqc_signature", "qid_hybrid"]
```

---

## 5. Evidence Family Failure Rules

AdamantineOS and the WSQK v2 issuer MUST fail closed when evidence families are invalid.

The following conditions MUST deny:

- missing `required_evidence_families`
- empty `required_evidence_families`
- non-list `required_evidence_families`
- non-string family entry
- empty family entry
- unknown family entry
- unsupported family entry
- required family missing from supplied evidence
- any attempt to infer a default family
- any attempt to silently downgrade required families

No implicit fallback evidence family is permitted.

---

## 6. Quantum Posture Semantics

`quantum_posture` declares the minimum authority posture required by the WSQK v2 proof.

Phase 1 defines the semantic categories only. Later phases may implement validators and exact policy enums.

The minimum normative categories are:

| Posture | Meaning |
| --- | --- |
| `classical_only` | classical evidence only; never sufficient when hybrid or PQC is required |
| `hybrid_required` | classical and PQC evidence are both required |
| `pqc_required` | PQC evidence is mandatory |
| `revoked` | authority posture is explicitly invalid |
| `expired` | authority posture is no longer acceptable |

If policy requires `hybrid_required`, then classical-only evidence MUST deny even if the classical signature is otherwise valid.

A valid signature is not equal to valid authority.

---

## 7. Proof Binding Hash

`proof_bindings_hash` MUST be computed only from canonicalized binding inputs.

The minimum Phase 1 binding inputs are:

- `contract_version`
- `wallet_id`
- `action`
- `context_hash`
- `issued_at`
- `expires_at`
- `nonce`
- canonical `required_evidence_families`
- `quantum_posture`

The hash MUST change if any binding input changes after canonicalization.

The hash MUST NOT change when only the input order of `required_evidence_families` changes but the canonical set is identical.

---

## 8. Time and Replay Rules

WSQK v2 remains time-bound and nonce-bound.

The following rules are mandatory:

- `issued_at` and `expires_at` are injected values
- no global clock access is permitted inside the authority contract
- `expires_at` MUST be greater than `issued_at`
- `nonce` MUST be non-empty
- nonce consumption MUST be performed by an injected nonce store
- replay MUST deny deterministically
- future-dated authority MUST deny when evaluated by TVA
- expired authority MUST deny when evaluated by TVA

---

## 9. Authority Boundary Rules

WSQK v2 is authority evidence only.

WSQK v2 MUST NOT:

- execute actions
- sign transactions
- broadcast transactions
- generate private keys
- store private keys
- infer identity evidence
- infer quantum posture
- bypass Q-ID validation
- bypass TVA enforcement
- emit final ALLOW by itself

WSQK v2 may authorize only the exact wallet/action/context/posture binding declared in the authority proof.

---

## 10. Compatibility Rules

WSQK v1 and WSQK v2 are separate contracts.

Compatibility MUST be explicit.

The following are forbidden:

- silently treating v1 authority as v2 authority
- silently treating v2 authority as v1 authority
- accepting v1 when v2 is required
- accepting missing v2 posture fields under a v1 fallback path
- changing binding hash inputs without a major contract version bump
- changing evidence family canonicalization rules without a major contract version bump

---

## 11. Phase 3 Reason IDs

WSQK v2 deny semantics MUST use stable reason IDs rather than freeform strings.
Phase 3 locks the first WSQK-v2-specific reason IDs as contract values:

| Reason ID | Meaning |
| --- | --- |
| `WSQK_V2_INVALID_EVIDENCE_FAMILIES` | evidence-family input is missing, empty, non-iterable, non-string, or contains an empty family |
| `WSQK_V2_UNKNOWN_EVIDENCE_FAMILY` | evidence-family input contains a syntactically valid but unsupported family name |
| `WSQK_V2_INVALID_QUANTUM_POSTURE` | declared quantum posture is missing, unknown, revoked, expired, or unsupported by the v2 issuer |

These reason IDs are a single source of truth for Phase 4 TVA enforcement and later Q-ID binding work.
They MUST NOT be renamed or remapped without a major contract version bump.

---

## 12. Phase Mapping

This contract anchors the full WSQK v2 upgrade path:

| Phase | Dependency on this contract |
| --- | --- |
| Phase 1 | lock authority contract and canonical evidence-family invariant |
| Phase 2 | implement data model and issuer using this contract |
| Phase 3 | add reason IDs for all deterministic deny cases |
| Phase 4 | enforce posture and evidence-family comparison in TVA |
| Phase 5 | bind Q-ID posture/evidence into WSQK v2 |
| Phase 6 | integrate explicit v2 envelope/orchestrator paths |
| Phase 7 | regression-lock canonicalization, hash stability, downgrade denial, and tamper denial |
| Phase 8 | map contract rules to invariants, tests, docs, and CI proof |

---

## 13. Phase 7 Regression Requirement

Phase 7 MUST include a regression test proving:

- two authorities with identical evidence families in different input order produce the same `proof_bindings_hash`
- duplicate evidence families do not alter the final hash
- changing the actual canonical set changes the hash
- missing required families deny
- unknown required families deny
- classical-only posture denies when hybrid is required

The named regression lock for the primary canonical set invariant SHOULD be:

`test_wsqk_v2_required_evidence_families_sorted_set_hash_stability`

---

## 14. Non-Goals

This Phase 1 contract does not implement:

- PQC cryptography
- Q-ID verification
- TVA runtime enforcement
- external network calls
- nonce persistence
- adaptive governance policy updates
- wallet key custody

Those belong to later phases and must build on this contract without weakening it.

---

## 15. Summary

WSQK v2 upgrades authority from simple time-bound wallet permission into deterministic quantum-aware authority proof.

The first locked rule is:

`required_evidence_families = sorted canonical unique set`

Same posture must produce the same proof hash.

Different posture must produce a different proof hash.

Ambiguous posture must deny.
