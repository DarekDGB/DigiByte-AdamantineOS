# OS Proof Pack v1.4.0 — Q-ID Linkage Hardened

**License:** MIT — **Author:** DarekDGB  
**Scope:** Normative proof-pack documentation for v1.4.0 fixture lock.

---

## 1. Purpose

The OS Proof Pack exists to prove, in CI, that Adamantine evaluation is:

- deterministic
- fail-closed
- contract-stable
- regression-locked

v1.4.0 extends the sealed foundation with **Q-ID linkage hardening** and **clock-free replay enforcement framework**.

---

## 2. What v1.4.0 Adds

- Strong binding rules between Q-ID session proof and execution envelope
- Distinct failure modes for spoof attempts
- Replay-proof enforcement framework (policy latch controlled)
- Stable reason IDs for all replay/linkage failures

---

## 3. Fixture Pack Contents (Expected)

The v1.4.0 fixture pack SHOULD include cases such as:

- **valid linkage**: Q-ID proof binds to envelope inputs
- **wallet mismatch**: same proof used with different `wallet_id` → deny
- **nonce mismatch**: replay proof nonce differs from envelope nonce → deny
- **binding hash mismatch**: replay proof not tied to computed binding hash → deny
- **nonce replay** (strict policy): `fresh=false` → deny with `QID_NONCE_REPLAY`
- **missing replay proof** (strict policy): deny with `QID_REPLAY_PROOF_MISSING`

The exact filenames are implementation-defined, but the **semantics** are contract-bound.

---

## 4. Determinism Requirements

For each fixture, repeated runs MUST produce identical:
- `decision`
- `protection_mode`
- `reason_id`
- `context_hash`
- artifacts shape

CI SHOULD execute multi-run determinism (e.g., 50 repeats).

---

## 5. Manifest Lock

Fixture hashes MUST be recorded in a manifest.
Any fixture mutation MUST fail CI unless the manifest is intentionally updated in the same change.

---

## 6. Related Contracts

- `docs/CONTRACTS/execution_request_v2.md`
- `docs/CONTRACTS/qid_linkage_v1.md`
- `docs/DURABLE_NONCE_STORE_INTEGRATION.md`
