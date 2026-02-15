# Execution Response v2 (Contract)

**License:** MIT — **Author:** DarekDGB  
**Stability level:** **FROZEN** (breaking change requires `execution_response_v3`)  
**Scope:** Adamantine execution response envelope returned by the deterministic decision core.

This document freezes the **execution response envelope** returned by Adamantine when called with `execution_request_v2`.

It is a **pure contract**:
- deterministic
- fail‑closed
- deny‑by‑default
- no hidden clocks
- no hidden authority

If a field is not defined here, it MUST NOT appear in the response.

---

## 1. Version

- **Interface name:** `execution_response_v2`
- **Paired request:** `execution_request_v2`

**Routing rule (normative):**
- If request `v == "execution_request_v2"` → response `v` MUST equal `"execution_response_v2"`.
- No silent downgrade to v1.
- Any mismatch MUST be treated as an integration error (fail‑closed).

---

## 2. Top‑Level Shape (Strict Allowlist)

The response MUST be a JSON object with **only** these keys:

Field | Type | Required | Notes
---|---|---:|---
`v` | `str` | ✅ | Must equal `"execution_response_v2"`
`request_id` | `str` | ✅ | Echo of request
`status` | `str` | ✅ | `"allow"` \| `"deny"` \| `"error"`
`reason_id` | `str` | ✅ | Stable identifier (see §3)
`context_hash` | `str` | ✅ | 64-hex lowercase, stable for identical canonical inputs
`decision` | `object` | ✅ | Decision object (see §4)
`artifacts` | `object` | ❌ | Deterministic, non-sensitive only (see §5)
`metrics` | `object` | ❌ | Deterministic counts only (see §6)

**Unknown top‑level keys MUST be rejected** (or never emitted).

---

## 3. Status + reason_id Invariants

### 3.1 `status`
`status` MUST be one of:
- `"allow"` — action allowed
- `"deny"` — action denied
- `"error"` — contract violation or internal deterministic error

### 3.2 `reason_id`
`reason_id` MUST be a stable string identifier from the reason registry.

**Invariant A (allow):**
- If `status == "allow"`, then `reason_id` MUST equal `OK_ALLOW`.

**Invariant B (deny):**
- If `status == "deny"`, `reason_id` MUST NOT equal `OK_ALLOW`.

**Invariant C (error):**
- If `status == "error"`, `reason_id` MUST be an `ERR_*` reason id (registry-defined) and MUST be stable for the same failure condition.

No generic “UNKNOWN_ERROR”. No silent fallback reasons.

---

## 4. Decision Object (Strict)

`decision` MUST be a JSON object with **only** these keys:

Field | Type | Required | Notes
---|---|---:|---
`intent` | `str` | ✅ | Echo of request.intent
`action` | `str` | ✅ | Echo of request.context.action
`allowed` | `bool` | ✅ | Must match `status` (`allow`→true, `deny`/`error`→false)
`protection_mode` | `str` | ✅ | `"legacy"` \| `"minimal"` \| `"full"` (see §4.1)
`gates` | `object` | ✅ | Gate results (see §4.2)
`timebox` | `object` | ✅ | Timebox evaluation (see §4.3)
`nonce` | `object` | ✅ | Nonce evaluation (see §4.4)
`evidence` | `object` | ✅ | Evidence evaluation summary (see §4.5)
`policy` | `object` | ✅ | Policy outcome summary (see §4.6)

Unknown keys inside `decision` MUST be rejected (or never emitted).

---

### 4.1 `protection_mode` (Required, Normative)

`protection_mode` MUST be one of:
- `"legacy"` — Q-ID missing/invalid OR protected call not requested (unprotected / legacy runtime posture)
- `"minimal"` — Q-ID valid, but Shield/Oracle missing or not required by policy
- `"full"` — Q-ID valid + Shield bundle valid + Oracle evidence valid (as configured)

**No other values are permitted.** Adding a new value requires `execution_response_v3`.

---

### 4.2 `gates` (Strict)

`gates` MUST be an object with **only**:

Field | Type | Required | Notes
---|---|---:|---
`tva` | `object` | ✅ | Truth Vector Authority gate
`eqc` | `object` | ✅ | Evidence Quality Check gate
`wsqk` | `object` | ✅ | Wallet-Scoped Quantum Key gate

Each gate object MUST be:

Field | Type | Required | Notes
---|---|---:|---
`allowed` | `bool` | ✅ | Gate pass/fail
`reason_id` | `str` | ✅ | Stable reason for that gate outcome

Unknown keys MUST be rejected.

---

### 4.3 `timebox` (Strict)

`timebox` MUST be:

Field | Type | Required | Notes
---|---|---:|---
`valid` | `bool` | ✅ | Whether request timebox was valid under injected now
`issued_at` | `str` | ✅ | Echo of request.timebox.issued_at
`expires_at` | `str` | ✅ | Echo of request.timebox.expires_at
`max_skew_seconds` | `int` | ✅ | Echo (default 0 if not present)
`reason_id` | `str` | ✅ | Stable reason for timebox result

Unknown keys MUST be rejected.

---

### 4.4 `nonce` (Strict)

`nonce` MUST be:

Field | Type | Required | Notes
---|---|---:|---
`consumed` | `bool` | ✅ | Whether nonce was consumed (single-use)
`store` | `str` | ✅ | Echo of request.nonce.store
`value` | `str` | ✅ | Echo of request.nonce.value (or redacted form if policy requires; see §5.2)
`reason_id` | `str` | ✅ | Stable reason for nonce result

Unknown keys MUST be rejected.

---

### 4.5 `evidence` (Strict Summary)

`evidence` MUST be an object with **only**:

Field | Type | Required | Notes
---|---|---:|---
`qid` | `object` | ✅ | Q-ID evaluation summary
`shield` | `object` | ✅ | Shield evaluation summary
`oracle` | `object` | ✅ | Oracle evaluation summary

Each evidence summary MUST be:

Field | Type | Required | Notes
---|---|---:|---
`present` | `bool` | ✅ | Evidence block present and non-empty
`valid` | `bool` | ✅ | Evidence block validated
`reason_id` | `str` | ✅ | Stable reason id for evidence validation

Unknown keys MUST be rejected.

---

### 4.6 `policy` (Strict Summary)

`policy` MUST be:

Field | Type | Required | Notes
---|---|---:|---
`mode` | `str` | ✅ | Policy mode label (stable, e.g. `"deny_by_default"`)
`override_allowed` | `bool` | ✅ | Whether an informed override is permitted
`reason_id` | `str` | ✅ | Stable reason for policy outcome

Unknown keys MUST be rejected.

---

## 5. Artifacts (Optional, Deterministic, Non‑Sensitive)

If present, `artifacts` MUST be an object.

Rules:
- Artifacts MUST be deterministic for identical inputs.
- Artifacts MUST NOT include secrets (seed phrases, private keys, raw signing material).
- Artifacts MUST NOT include PII.
- Artifacts MUST be bounded in size (implementation-defined hard cap; deny on overflow with stable reason).

### 5.1 Artifact keys allowlist
Artifact keys MUST be limited to contract-approved names (registry or schema enforced in v1.5.0).

### 5.2 Redaction
If any echoed field is sensitive, it MUST be deterministically redacted (stable redaction), not omitted silently.

---

## 6. Metrics (Optional, Counts Only)

If present, `metrics` MUST be deterministic counts only:
- integers only
- no timers
- no durations
- no host/system identifiers

Unknown keys MUST be rejected.

---

## 7. Determinism Guarantees

For identical canonical request inputs, Adamantine MUST return identical:
- `status`
- `reason_id`
- `context_hash`
- `decision` object (all fields)
- `artifacts` (if present)
- `metrics` (if present)

No environment reads. No hidden time. No randomness.

---

## 8. Change Control

Breaking change examples (require v3):
- adding a new `protection_mode` value
- removing a field
- changing a field type
- changing semantics of required fields

Non-breaking change (allowed only if explicitly optional and schema allows it):
- adding a new optional artifact key in a registry-controlled way (if the schema allows)
- adding optional fields ONLY if schema is updated and older clients remain safe

No silent drift.

---

## 9. Related Contracts

- `docs/CONTRACTS/execution_request_v2.md`
- `docs/CONTRACTS/mobile_execution_call_v2.md`
- `docs/CONTRACTS/mobile_decision_result_v2.md` (UI interpretation contract)
- `docs/CONTRACTS/external_reason_governance_v1.md`
