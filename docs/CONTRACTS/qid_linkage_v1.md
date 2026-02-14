# Q-ID Linkage v1 (Contract) — v1.4.0

**License:** MIT — **Author:** DarekDGB  
**Scope:** Normative linkage rules binding Q-ID session proof to Adamantine execution.

---

## 1. Goal

v1.4.0 hardens the interface so a Q-ID proof cannot be:
- replayed for a different wallet
- replayed across sessions when strict policy is enabled
- detached from its binding inputs
- accepted under ambiguous failure modes

Adamantine remains **pure** and **clock-free**.

---

## 2. Binding Inputs (Normative)

The linkage MUST bind the Q-ID proof to the following canonical inputs:

- `wallet_id`
- `subject`
- `device_binding`
- `proof_hash`
- `session_nonce`

Where:

- `wallet_id` is from the execution envelope.
- `session_nonce` is from the execution envelope (protected call nonce).
- `subject`, `device_binding`, and `proof_hash` are derived from the Q-ID session proof payload.

---

## 3. Canonicalization (Normative)

Before hashing, each binding input MUST be canonicalized:

- Strings: UTF-8 bytes with no surrounding whitespace changes.
- JSON objects: canonical JSON encoding (stable key ordering, no insignificant whitespace).
- Byte fields: base64url in transport; decoded to bytes before hashing.

Any canonicalization failure MUST deterministically deny.

---

## 4. Binding Hash (Normative)

Define:

`binding_hash = H( wallet_id || subject || device_binding || proof_hash || session_nonce )`

Where:

- `H` is the Adamantine-defined deterministic hash (the same family used for `context_hash`).
- `||` is concatenation of canonical byte encodings.
- Domain separation MAY be applied (recommended), but must be stable once introduced.

The binding hash MUST change if any input changes.

---

## 5. Replay Proof (Normative, Policy Controlled)

Replay protection is **clock-free** and **per-wallet**.

If `require_qid_replay_proof = true`, then Q-ID evidence MUST include replay proof that asserts:

- `session_nonce` is **fresh** for the given `wallet_id`
- replay proof is bound to the same `binding_hash`
- replay proof includes a `registry_commitment`

Missing or invalid replay proof MUST deny.

If `require_qid_replay_proof = false`, replay proof MAY be absent without forcing denial.

---

## 6. Failure Modes (Normative)

Adamantine MUST produce distinct deterministic reason IDs for:

- Invalid signature: `QID_INVALID_SIGNATURE`
- Malformed proof: `QID_MALFORMED_PROOF`
- Wallet mismatch: `QID_WALLET_MISMATCH`
- Subject mismatch: `QID_SUBJECT_MISMATCH`
- Device binding mismatch: `QID_DEVICE_MISMATCH`
- Replay proof missing: `QID_REPLAY_PROOF_MISSING`
- Replay proof invalid: `QID_REPLAY_PROOF_INVALID`
- Replay wallet mismatch: `QID_REPLAY_WALLET_MISMATCH`
- Replay nonce mismatch: `QID_REPLAY_NONCE_MISMATCH`
- Replay binding hash mismatch: `QID_REPLAY_BINDING_HASH_MISMATCH`
- Nonce replay: `QID_NONCE_REPLAY`

No generic “validation failed” reasons are permitted for these cases.

---

## 7. Compatibility Rules

- Adding new optional fields is permitted.
- Removing or renaming binding inputs requires a major contract bump.
- Any change to the binding hash inputs requires a major contract bump.

---

## 8. Non-Goals

This contract does not define:
- Q-ID cryptographic algorithm suites
- time-based session expiration
- server-side verification protocols
- network calls

It defines only deterministic linkage rules at the Adamantine boundary.
