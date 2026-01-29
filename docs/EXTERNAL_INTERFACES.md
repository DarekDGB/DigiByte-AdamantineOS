# External Interfaces — Q-ID + Adaptive Core (Draft v0)

Author attribution: **DarekDGB**

This document specifies the **external input shapes** that Adamantine accepts at its integration ports.
It is intentionally strict and exists to prevent drift, ambiguity, and silent behavior changes.

Adamantine core contracts remain dependency-free. External payloads are accepted **only** through adapters.

---

## Global rules (apply to all external payloads)

### Determinism
- All timestamps are **integer seconds since Unix epoch (UTC)**.
- No implicit “now” is read from system time inside core logic.
- Adapters MUST accept an injected `now: int` for validation.

### Unknown fields
- Unknown fields MAY be present in external payloads.
- Unknown fields MUST be **ignored** (never trusted, never used for decisions).

### Fail-closed
Adapters MUST reject (DENY) when:
- required fields are missing
- types are invalid
- values are out of allowed range
- binding requirements are not satisfied
- payload is expired or not yet valid (if applicable)

### Versioning
External payloads MUST include a version string so changes are explicit and audit-visible.

---

## Q-ID — Session Assertion Input (external → adapter)

### Purpose
Represents an identity/session proof that can be converted into the internal contract:
`QIDSessionProof(subject, issued_at, expires_at, proof_hash, device_binding?, issuer_version?)`

### Expected external payload shape (dict-like)

Required fields:
- `qid_iface_version: str`  
  - Example: `"qid-session-v0"`
- `subject: str`  
  - A stable subject identifier (DID-like or equivalent).
- `issued_at: int`  
  - Session issuance time (UTC epoch seconds).
- `expires_at: int`  
  - Session expiry time (UTC epoch seconds).
- `proof_hash: str`  
  - A hash string only (no raw secrets). Must be non-empty.

Optional fields:
- `device_binding: str | None`  
  - A device binding identifier (shape-defined, semantics external).
- `issuer_version: str | None`  
  - Q-ID implementation or policy version tag.

Validation rules (adapter MUST enforce):
- `subject` MUST be non-empty.
- `proof_hash` MUST be non-empty.
- `issued_at <= now < expires_at` MUST hold.
- `expires_at - issued_at` MUST be positive and within a reasonable bound (adapter-defined; default deny if absurd).
- If `device_binding` is present, it MUST be a string (may be empty → deny).

Failure behavior:
- Any validation failure MUST produce a deny result with an explicit internal ReasonId.

---

## Adaptive Core — Risk Report Input (external → adapter)

### Purpose
Represents a risk evaluation that can be converted into the internal contract:
`RiskReport(context_hash, signals, overall_score, generated_at, oracle_version?, external_source_id?)`

### Expected external payload shape (dict-like)

Required fields:
- `ac_iface_version: str`  
  - Example: `"adaptive-core-risk-v0"`
- `context_hash: str`  
  - MUST bind to the exact `ExecutionContext.context_hash`.
- `generated_at: int`  
  - Report generation time (UTC epoch seconds).
- `overall_score: int`  
  - Integer 0..100 inclusive.
- `signals: list[object]`  
  - A list of signal objects (may be empty only if explicitly permitted by policy; default deny).

Optional fields:
- `oracle_version: str | None`  
  - Adaptive Core version tag.
- `external_source_id: str | None`  
  - Trace identifier for audit/debug (no secrets).

Signal object shape:
Each entry in `signals` MUST be an object with:

Required:
- `source: str`  
  - One of (recommended set, not enforced by shape): `"sentinel" | "dqsn" | "adn" | "qwg" | "guardian" | "adaptive-core"`
- `severity: int`  
  - Integer 0..100 inclusive.
- `reason_ids: list[str]`  
  - External reason identifiers (strings). Mapping occurs in adapter under fail-closed policy.

Validation rules (adapter MUST enforce):
- `context_hash` MUST be non-empty and MUST match the evaluated context hash.
- `overall_score` MUST be 0..100 inclusive.
- `generated_at` MUST be an int and MUST be within a reasonable window vs `now` (adapter-defined; default deny if stale/future absurdly).
- Each signal MUST satisfy:
  - `source` non-empty string
  - `severity` 0..100 inclusive
  - `reason_ids` is a list of non-empty strings (empty list → deny unless policy permits)

Reason mapping rules (adapter MUST enforce):
- External `reason_ids` MUST be mapped to internal `ReasonId` via an explicit mapping table.
- Unknown external reasons MUST trigger fail-closed behavior (deny), unless policy explicitly specifies otherwise.

Failure behavior:
- Any validation or mapping failure MUST produce a deny result with an explicit internal ReasonId.

---

## Non-goals
- This document does not define cryptographic verification details of Q-ID proofs.
- This document does not define Adaptive Core scoring methodology.
- This document defines only the **adapter input shapes and fail-closed validation boundaries**.
