# Durable Nonce Store Integration (Clock-Free) — v1.4.0

**License:** MIT — **Author:** DarekDGB  
**Scope:** Normative integration contract for replay protection evidence used by AdamantineOS.

---

## 1. Purpose

AdamantineOS is **pure and deterministic**. It does **not** store mutable state.

Replay protection is enforced via a **Durable Nonce Store** owned by the untrusted runtime/host.
Adamantine **verifies** replay evidence deterministically and **fails closed** when required evidence is missing or invalid.

This document is **clock-free** by contract:
- **No wall-clock timestamps**
- **No expiry semantics**
- **No time-based acceptance logic**

---

## 2. Definitions

- **wallet_id**: Stable identifier for the wallet instance.
- **session_nonce**: The nonce used in the execution envelope for the protected call.
- **binding_hash**: Deterministic hash that binds Q-ID identity proof to the envelope inputs (see `qid_linkage_v1.md`).
- **registry_commitment**: A deterministic commitment to the nonce registry state (implementation-defined, but stable bytes/encoding).
- **fresh**: Boolean statement that `session_nonce` has not been used previously for the given scope.

---

## 3. Scope of Replay Protection

v1.4.0 defines **per-wallet replay scope**:

> A `session_nonce` MUST NOT be accepted more than once for the same `wallet_id`.

A stricter scope (e.g., per-wallet + per-binding_hash) may be introduced only via a **major contract version bump**.

---

## 4. Runtime Interface (Non-Normative Implementation)

Adamantine does not mandate a specific storage backend. A runtime may implement the nonce store using:
- key/value database
- append-only log
- Merkle accumulator
- secure enclave storage

The minimal behavior required is equivalent to **check-and-mark**, but without time:

### 4.1 Minimal behavior (conceptual)

- Input: `(wallet_id, session_nonce)`
- Output: `fresh` (true if not seen before, false if already seen)
- Side-effect: if fresh, mark as used (durably)

**Note:** This is a *conceptual* description. Adamantine never calls this directly.
Instead, the runtime produces **replay evidence** derived from this behavior.

### 4.2 Production store requirement

Production deployments MUST pass `production=True` and inject a `DurableNonceStore`.
The in-memory store is for tests and local development only; it provides no crash-safety, persistence, or cross-process replay protection.

---

## 5. Replay Evidence Required by Adamantine

When replay protection is required by policy, the runtime MUST supply a replay evidence object as part of Q-ID evidence.

### 5.1 Required fields

The following fields MUST be present and canonicalized:

- `proof_version` (string)
- `wallet_id` (string)
- `session_nonce` (string/bytes encoding per Q-ID schema)
- `binding_hash` (bytes, base64url)
- `registry_commitment` (bytes, base64url)
- `fresh` (boolean)

### 5.2 Fail-closed rules

If replay protection is required by policy, Adamantine MUST deterministically deny when:

- replay evidence is missing
- replay evidence fails schema validation
- replay evidence is not bound to the current `wallet_id`
- replay evidence `session_nonce` does not match the envelope nonce
- replay evidence `binding_hash` does not match recomputed `binding_hash`
- `fresh` is false (nonce replay)

---

## 6. Reason IDs (Normative)

When denying due to replay enforcement, Adamantine MUST use stable reason IDs:

- `QID_REPLAY_PROOF_MISSING`
- `QID_REPLAY_PROOF_INVALID`
- `QID_REPLAY_WALLET_MISMATCH`
- `QID_REPLAY_NONCE_MISMATCH`
- `QID_REPLAY_BINDING_HASH_MISMATCH`
- `QID_NONCE_REPLAY`

---

## 7. Policy Latch (Normative)

Replay proof enforcement is controlled by a deterministic policy latch:

- When `require_qid_replay_proof = false`: replay evidence MAY be absent without forcing denial.
- When `require_qid_replay_proof = true`: replay evidence MUST be present and valid, or the call is denied.

This design preserves backward compatibility with older proof packs while enabling strict security profiles.

---

## 8. Security Notes (Normative)

- Adamantine treats the runtime as **untrusted**.
- Therefore, the runtime cannot be allowed to omit required replay evidence without causing denial.
- Replay protection MUST NOT rely on timestamps, system clocks, or time synchronization.

---

## 9. Compatibility

This document is normative for **v1.4.0** and later, until replaced by a major contract version bump.
