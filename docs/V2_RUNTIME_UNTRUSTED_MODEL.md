# V2 Runtime Untrusted Model (v2.0.0+)

**License:** MIT — **Author:** DarekDGB  
**Scope:** Formal model for treating the runtime host as untrusted while keeping Adamantine core authoritative.

This document exists to prevent drift: even as “runtime features” evolve, the core must remain the single source of truth.

---

## 1. Trust Boundaries

### Trusted
- Adamantine core decision logic:
  - envelope parsing (contract-governed)
  - EQC evaluation
  - TVA gate
  - nonce/replay protection enforcement (as defined by contracts)
  - reason_id assignment
  - context_hash computation
  - protection_mode assignment

### Untrusted
- Wallet UI
- Runtime host glue code
- Executor implementation (sign/broadcast/etc)
- Integrator-provided Q-ID verifier wiring until explicitly injected and enforced
- Integrator-provided Q-ID replay registry wiring until explicitly injected and enforced
- Network calls
- OS / device / secure enclave APIs
- Logging, telemetry, analytics

---

## 2. The Only Authority Rule

**Core output is authoritative. Runtime output is not.**

Runtime cannot:
- flip DENY → ALLOW
- weaken protection_mode
- replace reason_id/context_hash
- hide missing evidence
- claim nonce consumption that did not occur in the trusted path

---

## 3. Fail-Closed Requirements

If the runtime host detects any violation attempt (including malformed calls, override attempts, or artifact abuse), it MUST:

- return a deterministic DENY shape (using the existing core error mapping mechanisms), OR
- refuse to execute and surface a deterministic host-level error *without changing core semantics*

There must be:
- no silent fallback
- no “best effort allow”
- no “execute anyway”
- no “temporary compatibility mode” that weakens denial

---

## 4. Execution Rule

- **DENY:** executor is never called
- **ALLOW:** executor is called exactly once

If an executor throws an error:
- core decision remains unchanged
- runtime may emit runtime artifacts (`runtime_artifact_log_v1`)
- wallet UI may handle the failure, but must not reinterpret core decision

---

## 5. Replay/Nonce Rule (Integration-Level)

The runtime host must treat replay protection as a **security gate**, not a UX feature.

- nonce consumption is tied to **successful allow-path execution**
- hostile or buggy runtime must not consume nonces early
- host must not “invent” nonce receipts
- host must not self-assert Q-ID `fresh = true` or invent `registry_commitment` values
- Q-ID replay freshness is meaningful only when produced by a trusted, stateful integrator registry
- unavailable or unverifiable replay-registry state must fail closed, not downgrade to runtime-provided freshness

---

## 6. What v2.0.0 Must Prove (Test-Locked)

A v2.0.0-compliant build must have negative-first tests proving:

- DENY → executor never called (even with hostile runtime inputs)
- ALLOW → executor called exactly once
- runtime cannot override:
  - decision fields (verdict/reason_id/context_hash/protection_mode)
  - authority path (WSQK/Q-ID/Shield/Oracle evidence)
- hostile runtime artifacts are ignored or fail-closed
- any Q-ID v2 evidence without an injected verifier fails closed with `QID_AUTHENTICITY_VERIFIER_MISSING`
- any claimed Q-ID replay freshness is sourced from a trusted registry boundary, not runtime self-assertion
- determinism across repeated runs (50–100 repeats recommended)

---

## Q-ID Verifier and Shape-A Transport Boundaries

The runtime host MUST inject Q-ID's real signature/authenticity verifier for every Q-ID Adamantine evidence v2 path. A callable that simply returns, logs, delegates to UI state, or checks only `proof_hash` is not a verifier. It is a fail-open integration bug. Integrators SHOULD use the Q-ID repository adapter `qid.integration.adamantine.build_adamantineos_qid_verifier(...)` and prove that forged or tampered signatures are denied through the Adamantine `qid_verifier` path.

Legacy Shape-A Q-ID evidence is an integrity-bound local session shape only. It MUST NOT be accepted from untrusted runtime glue, UI input, bridge payloads, external APIs, or network transport. If a future integration needs externally supplied Q-ID evidence, it must use Q-ID evidence v2 with the real verifier or an equivalent authenticity boundary before the data can affect Adamantine policy.
