# Adamantine Wallet OS — Changelog

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Scope:** Foundation Releases and Contract History

---

## v1.0.0 — Foundation Sealed

**Status:** Locked  
**Type:** Foundation seal (contracts + deterministic reasoning + boundaries)  
**Compatibility:** Additive changes only beyond this point

This release seals the **Adamantine Wallet OS foundation**.

It freezes:
- contract surfaces
- fail-closed adapters
- deterministic decision semantics
- authority enforcement boundaries
- mobile consumption outputs

It intentionally excludes wallet runtime execution, signing, transaction building, and UI.

---

### 1. Decision Core (EQC)

- EQC v1 finalized as deterministic baseline evaluator
- EQC v2 finalized for **multi-evidence reasoning**
  - Q-ID session evidence
  - Shield v3 bundle evidence
  - Adaptive Core v3 oracle evidence
- Deterministic verdict output (no hidden time, randomness, or implicit ordering)
- Stable, ordered `ReasonId` semantics enforced by tests
- Missing or conflicting evidence deterministically denied

**Rule:** EQC produces decisions only. It never grants authority.

---

### 2. Authority & Enforcement (WSQK + TVA)

- WSQK v1 finalized as the **only authority primitive**
  - context-bound (wallet_id, action, context_hash)
  - time-bound (issued_at, expires_at)
  - single-use nonce
- TVA gate enforced as the mandatory final enforcement path
- Replay protection proven via injected nonce store
- Explicit proof that execution is impossible without valid TVA enforcement

**Rule:** Authority is explicit, scoped, and auditable. No inferred permission.

---

### 3. Evidence Interfaces & Fail-Closed Adapters

All external inputs are treated as **non-authoritative evidence**.

- Q-ID adapter hardened:
  - strict schema validation
  - injected time (`now`)
  - validity window enforcement
- Shield v3 evidence contracts frozen:
  - shield_signal_v3
  - shield_bundle_v3
- Shield v3 adapter hardened:
  - rejects unknown layers
  - rejects unknown reasons
  - enforces version pinning
  - fail-closed on missing required signals
- Adaptive Core v3 oracle contract frozen:
  - evidence-only oracle output
  - deterministic fields only
- Adaptive Core v3 oracle adapter hardened:
  - context-hash binding
  - injected time window checks
  - strict external reason mapping

Governance:
- ExternalReasonMap enforced as the only allowed mapping from external reasons → internal `ReasonId`
- PolicyPack enforced as the only allowed source of thresholds and policy rules
- Unknown or unmapped external reasons deterministically denied

**Rule:** Evidence can strengthen DENY. Evidence can never force ALLOW.

---

### 4. Execution Envelopes & Mobile Consumption

- Execution Request Envelope v1 frozen and validated (fail-closed parsing)
- Execution Response Envelope v1 frozen with deterministic allow/deny/error semantics
- Mobile execution boundary v1 frozen
- Mobile decision result contract v1 finalized
- Stable mapping from `ReasonId` → UX-safe categories
- Deterministic mobile result builder (same input → identical output)

---

### 5. Determinism & Security Proofs

- Negative-first tests across all boundaries
- Determinism validated via replay tests
- Proofs for hostile conditions including:
  - expired / future authority
  - timebox invalidity
  - missing evidence
  - context hash mismatch
  - unknown external reasons
  - nonce replay attempts
- CI-locked invariants
- Stable test coverage **>90%** on security-critical paths

---

### 6. Explicitly Out of Scope (By Design)

- wallet runtime implementation
- private key custody or storage
- transaction construction or signing
- network broadcasting
- cloud sync or custodial services
- web/browser execution
- mobile UI or SDK integration

These are intentionally excluded from the sealed foundation.

---

## v0.9.0 — Mobile Execution Boundary Frozen

**Status:** Locked  
**Type:** Boundary sub-freeze

This release froze the **mobile → Adamantine** execution boundary:

- execution_request_v1 / execution_response_v1 locked for mobile consumption
- strict fail-closed validator (unknown fields rejected, strict types enforced)
- stable error semantics (status × flags × reason_id invariants)
- determinism proven at the boundary (replay and snapshot-style tests)
- timebox & nonce safety invariants enforced (nonce consumed only on allow)

---

## Historical Notes (Pre-Seal)

### Foundation Build-Up

- Initial EQC v1 evaluator and context hash specification
- WSQKAuthority primitives
- TVA gate with injected nonce store
- Contract-first documentation and invariant-driven design methodology

---

## Freeze Statement

As of **v1.0.0**, the foundation is **frozen**.

Future changes must:
- be additive
- preserve all contracts
- respect invariants
- never weaken enforcement semantics

Breaking changes require a new major version.
