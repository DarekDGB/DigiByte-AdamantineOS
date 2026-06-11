# AdamantineOS — Threat Model

**License:** MIT License — DarekDGB

---

## 1. Purpose

This document defines the **explicit threat model** for AdamantineOS.

Adamantine is a deterministic execution boundary.  
This threat model exists to clearly state:

- What Adamantine protects against
- What Adamantine deliberately does not protect against
- Where trust boundaries exist
- Which threats are in-scope at the execution boundary

Anything not explicitly listed as mitigated is assumed **unmitigated by design**.

---

## 2. Trust Boundaries

Adamantine operates at a strict boundary between:

- **Untrusted caller input** (mobile wallet applications)
- **Internal deterministic enforcement logic**
- **External systems** (identity layers, signers, hardware, user custody)

Adamantine assumes:
- Callers may be buggy or compromised
- Input may be malicious, replayed, reordered, or malformed
- External systems may fail or be unavailable

Adamantine does **not** assume:
- Honest callers
- Single-device key custody
- Online availability
- Stable clocks beyond explicit timeboxes

---

## 3. In-Scope Threats (Actively Mitigated)

### 3.1 Malformed or Ambiguous Requests
**Threat:** Crafted inputs exploiting parsing ambiguity or permissive decoding.

**Mitigation:**
- Strict schema validation
- Canonicalization before evaluation
- Fail-closed behavior on unknown or malformed fields

---

### 3.2 Replay Attacks
**Threat:** Reuse of a previously valid execution request.

**Mitigation:**
- Single-use nonce enforcement
- Deterministic nonce rejection
- Local nonce persistence scoped to execution context

---

### 3.3 Timebox Manipulation
**Threat:** Execution outside intended validity windows (expired, future-dated, long-lived).

**Mitigation:**
- Explicit issued-at and expiry validation
- Hard rejection outside declared timebox
- No implicit grace periods

---

### 3.4 Authority Confusion
**Threat:** Executing actions under incorrect or escalated authority.

**Mitigation:**
- Explicit authority declaration per request
- TVA gate enforcement
- No inferred or implicit authority

---

### 3.5 Intent Confusion
**Threat:** Supplying a payload for one intent that is interpreted as another.

**Mitigation:**
- Intent-bound payload typing
- Versioned execution envelopes
- Strict intent-to-payload mapping

---

### 3.6 Canonicalization Drift
**Threat:** Semantically identical requests producing different hashes or decisions.

**Mitigation:**
- Deterministic canonicalization rules
- Stable ordering and encoding
- Hashing only canonical representations

---

### 3.7 Multi-Device Key Presence Abuse
**Threat:** Denial or bypass attempts based on keys existing on multiple devices.

**Mitigation:**
- Key custody neutrality
- Adamantine never denies execution solely due to multi-device key presence
- Decisions rely only on context, authority, timebox, nonce, and explicit policy

---

### 3.8 Adapter Misbehavior
**Threat:** External adapters returning malformed or misleading data.

**Mitigation:**
- Adapters are non-authoritative
- Adapter outputs are validated
- Adapter failure results in deterministic rejection

---

### 3.9 Observability Leakage
**Threat:** Sensitive data exposure via logs or metrics.

**Mitigation:**
- Metrics are non-sensitive
- No private key material ever processed
- No stable identifiers emitted unless explicitly declared

---

## 4. Out-of-Scope Threats (Not Mitigated)

Adamantine explicitly does **not** mitigate:

- Compromised operating systems
- Malware or root/jailbreak scenarios
- UI deception or social engineering
- Hardware keystore vulnerabilities
- Side-channel attacks on signing hardware
- Key exfiltration from external custody systems
- Network-level MITM outside the execution boundary

These threats must be addressed by the wallet application, OS, hardware, or user.

---

## 5. Assumptions

Adamantine assumes:

- Execution requests may be hostile
- Determinism is more important than availability
- Denial is safer than permissive execution
- All authority must be explicit

Violation of these assumptions invalidates security guarantees.

---

## 6. Security Invariants

The following are treated as **non-negotiable security laws**:

- Deny-by-default
- Fail-closed on ambiguity
- No hidden authority
- No silent fallback
- Deterministic behavior only
- Explicit versioning of all execution interfaces

Any deviation is considered a security defect.

---

## 7. Evolution of the Threat Model

This threat model evolves only when:

- New execution surfaces are introduced
- Contracts are versioned
- Mitigations are test-locked
- Invariants remain intact

Threat model changes must precede implementation.

---

## 8. Summary

AdamantineOS is secure by **restriction, determinism, and explicitness**.

Anything not explicitly allowed is denied.
Anything not explicitly mitigated is out-of-scope.
