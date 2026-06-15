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

For policy binding, the Q-ID session proof is also bound to the current Adamantine `context_hash` by the public policy-binding boundary.

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

### 4A. Context Binding Requirement (T-2 Hardening)

The exported `normalize_qid_policy_binding(...)` boundary MUST receive an `expected_context_hash` from the execution/integration caller. The parsed Q-ID session proof MUST carry the same `context_hash`.

If `expected_context_hash` is omitted, or if `session.context_hash != expected_context_hash`, the boundary MUST fail closed with:

- `EQC_QID_CONTEXT_HASH_MISMATCH`

This rule propagates the N-1 context-binding invariant into the public Q-ID policy-binding surface. Q-ID evidence may be accepted only as evidence for the same transaction context that Adamantine is evaluating. Context-less Q-ID evidence MUST NOT reach `ALLOW_EVIDENCE_CONTINUE_CHECKS` through this boundary.

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

## 5A. Authenticity Verification Requirement (T-1 Hardening)

`proof_hash` is an integrity hash only. It proves that a payload was not changed after hashing; it does **not** prove that Q-ID issued the payload or that the signature is valid.

For any execution call carrying Q-ID Adamantine evidence v2 (`v="2"`, `kind="qid_login_v2"`), the runtime integrator MUST inject a trusted `qid_verifier` before Adamantine parses the evidence as valid session input. If `qid_verifier` is absent on that v2 evidence path, Adamantine MUST fail closed with:

- `QID_AUTHENTICITY_VERIFIER_MISSING`

The verifier is responsible for checking the external Q-ID signature/key material. Adamantine remains deterministic and does not hold Q-ID private keys or silently trust self-hashed evidence.

Legacy Shape-A session proof inputs remain linkage evidence only and are not a substitute for Q-ID v2 signature verification. Production integrations SHOULD emit Q-ID v2 evidence and MUST provide a verifier for every Q-ID v2 evidence path.

Shape-A `proof_hash` is now enforced as a deterministic integrity hash over the normalized Shape-A contract fields only: `qid_iface_version`, `subject`, `issued_at`, `expires_at`, `context_hash`, `device_binding`, and `issuer_version`. Extra keys are intentionally excluded and cannot create authority. A Shape-A payload with an omitted, decorative, stale, or mismatched `proof_hash` MUST fail closed with `EQC_INVALID_QID_PROOF`.

---

## 6. Failure Modes (Normative)

Adamantine MUST produce distinct deterministic reason IDs for:

- Verifier missing for Q-ID v2 evidence: `QID_AUTHENTICITY_VERIFIER_MISSING`
- Invalid signature: verifier-specific failure mapped by the injected `qid_verifier`
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
