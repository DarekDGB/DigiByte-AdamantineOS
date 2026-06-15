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

### 5A. Replay Registry Trust Requirement (T-5 Hardening)

The replay proof fields `fresh` and `registry_commitment` are **not cryptographic proof by themselves**. They are trusted only when they originate from a stateful, integrator-controlled replay registry or nonce authority that Adamantine is configured to treat as part of the protected integration boundary.

Adamantine validates the replay proof shape, linkage, wallet/subject/nonce/device bindings, and `fresh == true` when freshness is required. Adamantine does **not** independently prove that a runtime-supplied boolean came from a real registry. A naive or hostile wallet runtime can set `fresh = true` and invent a `registry_commitment` string. That data MUST NOT be considered replay protection unless the integrator can prove it came from a trusted registry.

Production integrations MUST ensure:

- `fresh` is produced by a stateful registry/nonce service, not by UI, wallet glue, or arbitrary runtime input.
- `registry_commitment` identifies the registry state/checkpoint used to decide freshness.
- The replay registry is fail-closed: unavailable, ambiguous, or unverifiable registry state MUST deny.
- Runtime code MUST NOT self-assert `fresh = true` to satisfy Adamantine policy.

If the integrator cannot provide this trusted replay-registry boundary, then the replay proof is advisory shape data only and MUST NOT be described as a real anti-replay guarantee.

---

## 5B. Authenticity Verification Requirement (T-1 Hardening)

`proof_hash` is an integrity hash only. It proves that a payload was not changed after hashing; it does **not** prove that Q-ID issued the payload or that the signature is valid.

For any execution call carrying Q-ID Adamantine evidence v2 (`v="2"`, `kind="qid_login_v2"`), the runtime integrator MUST inject a trusted `qid_verifier` before Adamantine parses the evidence as valid session input. If `qid_verifier` is absent on that v2 evidence path, Adamantine MUST fail closed with:

- `QID_AUTHENTICITY_VERIFIER_MISSING`

The verifier is responsible for checking the external Q-ID signature/key material. Adamantine remains deterministic and does not hold Q-ID private keys or silently trust self-hashed evidence.

The injected verifier MUST be Q-ID's real signed-login verification path, or a wrapper that is cryptographically equivalent to it. A placeholder, no-op, test stub, UI callback, or adapter that returns successfully without checking the Q-ID signature is forbidden in production. The verifier MUST return successfully only after checking the Adamantine evidence envelope, login URI, service/callback binding, response payload, proof hash, context hash, and signature/key material. Any malformed, forged, tampered, or unverifiable evidence MUST raise and therefore fail closed inside Adamantine.

The Q-ID repository provides a purpose-built adapter for this contract: `qid.integration.adamantine.build_adamantineos_qid_verifier(...)`. Integrators SHOULD use that real verifier wrapper instead of hand-writing a permissive callable. Integration tests MUST prove that a valid Q-ID evidence object is accepted and that a tampered signature or tampered signed payload is denied through the Adamantine `qid_verifier` path.

### 5C. Shape-A Trusted-Source Restriction (N-B Hardening)

Legacy Shape-A session proof inputs remain linkage evidence only and are not a substitute for Q-ID v2 signature verification. Shape-A may be supplied only by a trusted in-process boundary that has already established authenticity outside this adapter. Shape-A MUST NOT be accepted directly from untrusted external transport, remote wallet glue, UI input, bridge payloads, or network-facing API requests.

Production integrations SHOULD emit Q-ID v2 evidence and MUST provide a verifier for every Q-ID v2 evidence path. If Shape-A ever becomes externally reachable, the integration MUST either migrate that path to Q-ID v2 evidence with the real verifier or add an equivalent authenticity verifier before Shape-A evidence can influence policy.

Shape-A `proof_hash` is now enforced as a deterministic integrity hash over the normalized Shape-A contract fields only: `qid_iface_version`, `subject`, `issued_at`, `expires_at`, `context_hash`, `device_binding`, and `issuer_version`. Extra keys are intentionally excluded and cannot create authority. A Shape-A payload with an omitted, decorative, stale, or mismatched `proof_hash` MUST fail closed with `EQC_INVALID_QID_PROOF`. This hash is integrity-only; it does not prove issuer authenticity.

### 5D. Q-ID v2 Canonical JSON Profile (AOS-N-001)

Q-ID Adamantine evidence v2 `proof_hash` validation uses the named AdamantineOS profile:

- `adamantine-qid-canonical-json-v1`

AdamantineOS computes the Q-ID v2 response-payload proof hash as:

`sha256(canonical_qid_json_bytes(response_payload)).hexdigest()`

The canonical JSON byte profile is defined in:

- `docs/ADAMANTINEOS_QID_CANONICAL_JSON_PROFILE.md`

The profile sorts object keys, removes insignificant whitespace, uses ASCII JSON escaping, rejects NaN/Infinity, encodes the canonical JSON string as UTF-8 bytes, and emits lowercase SHA-256 hex. The profile applies to the exact Q-ID v2 `response_payload` object. Wrapper fields outside `response_payload` remain part of the real Q-ID verifier responsibility.

Changing this profile, hashing a different object, changing hash casing, or reusing the same profile name for incompatible behavior requires a new contract review and a new profile name.

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
