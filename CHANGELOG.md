# Changelog

## Execution Boundary Sealed

This release locks the Adamantine Wallet OS execution boundary with deterministic,
fail-closed behavior and end-to-end security guarantees.

### Execution Core
- EQC v1 finalized with deterministic context hashing and strict deny-by-default evaluation
- Stable, ordered reason identifiers enforced and covered by tests
- Deterministic verdict generation (no hidden time, randomness, or ordering effects)

### Authority & Enforcement
- WSQK v1 finalized as the only scoped, time-bound authority primitive
- TVA gate enforced as the mandatory execution path
- Nonce replay protection proven via injected nonce store
- Explicit proof that execution is impossible without valid TVA enforcement

### Adapters & Governance
- Q-ID adapter hardened with strict schema, time window, and type validation
- Adaptive Core adapter hardened with context binding, score thresholds, and reason governance
- ExternalReasonMap and PolicyPack enforced as the only source of external signal mapping
- Explicit denial of unknown or unmapped external reasons
- Proof that adapters cannot inject authority or force execution

### Execution Envelopes
- Execution Request Envelope v1 frozen and validated (fail-closed parsing)
- Execution Response Envelope v1 frozen with deterministic allow/deny/error semantics
- Boundary handler proven to never execute without explicit authority

### End-to-End Security Proofs
- Comprehensive E2E harness covering happy path and hostile inputs
- Proofs for expired/future sessions, missing evidence, context mismatch, replay attempts
- Determinism guarantees validated across repeated evaluations
- CI-locked invariants with high, stable coverage (~97%)

### Out of Scope (By Design)
- Wallet runtime, keys, signing, broadcasting
- Cloud sync or custody
- Web or browser execution
- Mobile UI or SDK integration

---

## Legacy / Historical

### Foundation (Pre-Seal)
- Initial EQC v1 evaluator and context hash
- WSQKAuthority v1 primitives
- TVA gate with injected nonce store
- Negative-first test strategy
