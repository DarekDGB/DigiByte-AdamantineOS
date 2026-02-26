# Adamantine Wallet OS — Governance (v1)

**License:** MIT  
**Author:** DarekDGB  
**Scope:** Foundation contract governance for the sealed OS (no wallet runtime).

This document defines **non-negotiable governance rules** for evolving the Adamantine Wallet OS foundation.

If a change violates these rules, it is **rejected**.

---

## 1. Core Principles

1. **Fail-closed, deny-by-default**
   - Missing evidence, invalid evidence, or unknown fields MUST result in a deterministic deny.

2. **Determinism is law**
   - Same input → same output.
   - Canonicalization rules are part of the contract.
   - No wall-clock dependence (only injected `now`).

3. **Contracts first**
   - Schemas + invariants define truth.
   - Tests and fixtures are the enforcement mechanism.

4. **No silent fallback**
   - No “best effort” parsing.
   - No implicit defaults for security-critical fields.

---

## 2. Semantic Versioning Rules

Adamantine uses **semantic versioning** for contract surfaces:

- `shield_bundle_version` (Shield Bundle)
- `layer_version` (per shield layer)
- any other explicitly versioned interface field

### 2.1 Allowed changes by version

- **PATCH (X.Y.Z → X.Y.Z+1)**
  - Clarifications in docs
  - Bug fixes that do not change accepted input shapes
  - Additional tests / tighter fixtures (only if still contract-compatible)

- **MINOR (X.Y.Z → X.Y+1.0)**
  - New fields **must be optional**
  - New optional reasons / mappings
  - New fixtures that do not invalidate old fixtures

- **MAJOR (X.Y.Z → X+1.0.0)**
  - Removing any field
  - Making an optional field required
  - Changing meaning of an existing field
  - Any weakening of deny behavior
  - Any change that would cause previously-valid payloads to be rejected

---

## 3. Shield Bundle Governance (v1.3.0+)

### 3.1 Required version fields (strict mode)

When strict enforcement is enabled:

- `shield_bundle_version` is **required** and MUST be SemVer.
- each `shield_signal_v3` MUST include `layer_version` and it MUST be SemVer.

### 3.2 Canonical ordering rules (strict mode)

- `required_layers` MUST follow the canonical order:
  1. `sentinel_ai`
  2. `adn`
  3. `dqsn`
  4. `qwg`
  5. `guardian_wallet`

- `required_layers` MUST NOT contain duplicates.
- `signals` MUST be sorted by `(layer, signal_id)`.

### 3.3 Upgrade compatibility

- Adding a new shield layer requires a **major** bump to the bundle contract.
- Unknown layer names are denied.
- Missing required layer evidence is denied.

---

## 4. External Reason Registry Governance

### 4.1 Deny-by-default registry

- `ExternalReasonRegistryV1` is mandatory.
- Any external `reason_id` not allowlisted for the given layer is denied.

### 4.2 Mapping discipline

- Every allowlisted external reason MUST map to exactly one internal `ReasonId`.
- Missing mappings are denied.

---

## 5. Orchestrator Boundary Mapping

The orchestrator is the **contract boundary**.

### 5.1 Shield adapter failures

- Shield adapter parsing errors that indicate structural invalidity (shape, ordering, version mismatch) MUST surface as:
  - `EQC_INVALID_SHIELD_BUNDLE`

- External reason disallow / unmapped reason MUST surface as:
  - `UNKNOWN_EXTERNAL_REASON`

This keeps wallet-facing behavior stable and prevents internal adapter details from leaking as “generic” denies.

---

## 6. Regression Locks

The following invariants MUST be enforced by tests (no exceptions):

1. **Shield cannot weaken deny**
   - Shield may strengthen deny.
   - Shield must not convert deny → allow.

2. **Canonicalization stability**
   - Shuffled input order must not change the resulting decision hash.

3. **No silent fallback**
   - Invalid payloads never pass “as best effort.”

---

## 7. Change Process

A change is accepted only if:

- It includes the required SemVer bump (when applicable)
- It includes contract tests and/or fixtures that enforce the rule
- It passes CI (including coverage thresholds)
- It does not break determinism

**No merge without proof.**

---

## 9. External Governance Artifacts (Adaptive Core v3)

AdamantineOS may **consume** externally produced governance artifacts such as
`upgrade_proposal_v3` (Adaptive Core v3).

Non-negotiable rules:

1. **Consume-only**
   - AdamantineOS validates and evaluates proposals.
   - AdamantineOS does **not** apply upgrades, modify code, or change configuration.

2. **Human-only apply**
   - Any real upgrade is applied via **human Pull Request** with deterministic tests.
   - Review receipts are human-produced governance signals; they are not automatic upgrades.

3. **Fail-closed**
   - Invalid schema, hash mismatch, missing receipt (when required), or unknown fields MUST deny.

4. **Compatibility locks**
   - Compatibility vectors in `tests/compat_vectors/` and tests under `tests/compat/`
     freeze cross-repo behavior. Any drift MUST break CI.

This preserves correct authority direction:
Adaptive Core proposes → Humans review/apply → Adamantine enforces boundary decisions.
