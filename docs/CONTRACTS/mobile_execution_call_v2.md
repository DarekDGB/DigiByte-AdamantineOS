# Mobile Execution Call v2 (Contract)

**License:** MIT — **Author:** DarekDGB  
**Stability level:** **FROZEN** (breaking change requires `mobile_execution_call_v3`)  
**Scope:** Mobile (iOS/Android) → Adamantine Wallet OS execution boundary call contract.

This document freezes the **mobile → Adamantine** call interface.

It is a **pure contract**:
- no UI
- no key custody
- no signing
- no networking
- no hidden clocks

Mobile platforms must be able to call Adamantine deterministically and receive a stable, explainable decision.

---

## 1. Version

- **Interface name:** `mobile_execution_call_v2`
- **Request envelope:** `execution_request_v2`
- **Response envelope:** `execution_response_v1` *(current; response v2 is future)*

Adamantine MUST reject any request/response that does not match these shapes.

---

## 2. API Surface (Normative)

The mobile boundary call MUST supply:

- `payload`: JSON object matching `execution_request_v2`
- `now`: unix seconds, integer *(explicitly injected by caller)*

Normative signature (conceptual):

```text
execution_response_v1 = adamantine_mobile_call_v2(payload: object, now: int)
```

**Determinism rule:** `now` is not read from the environment. It is caller-injected.

---

## 3. Determinism Rules (Hard Requirements)

Mobile MUST:

- Provide `now` explicitly (`int`, unix seconds).
- Provide a stable `request_id` (non-empty string) per call.
- Provide only contract-defined fields at each level (unknown fields are rejected).
- Use stable JSON field ordering when producing the raw payload (Adamantine canonicalizes for hashing, but callers MUST NOT rely on non-deterministic map ordering).

Adamantine MUST:

- Be deny-by-default.
- Be fail-closed on ambiguity.
- Never inject nondeterministic data (no timestamps, random ids, device identifiers).
- Return stable `reason_id` and `context_hash` for identical inputs.

---

## 4. Request Envelope: `execution_request_v2`

### 4.1 Top-level shape

The payload MUST be a JSON object with the following keys:

Field | Type | Required | Notes
---|---|---:|---
`v` | `str` | ✅ | Must equal `"execution_request_v2"`
`request_id` | `str` | ✅ | Non-empty string (caller-provided)
`intent` | `str` | ✅ | Human-readable, stable intent label
`context` | `object` | ✅ | Execution context (see §4.2)
`authority` | `object` | ✅ | Authority declaration (see §4.3)
`timebox` | `object` | ✅ | ISO-8601 issued/expires (see §4.4)
`nonce` | `object` | ✅ | Single-use nonce declaration (see §4.5)
`payload` | `object` | ✅ | Evidence wiring + body (see §4.6)
`audit` | `object` | ❌ | Optional metadata (strict allowlist; see §4.7)

**Unknown top-level keys MUST be rejected**.

---

### 4.2 `context` (strict)

Field | Type | Required | Notes
---|---|---:|---
`wallet_id` | `str` | ✅ | Non-empty
`device_id` | `str` | ✅ | Non-empty (present for linkage; not currently bound into context_hash v1)
`app_id` | `str` | ✅ | Non-empty (present for linkage; not currently bound into context_hash v1)
`session_id` | `str` | ✅ | Non-empty (present for linkage; not currently bound into context_hash v1)
`action` | `str` | ✅ | Non-empty (e.g. `"SEND"`, `"SIGN"`, `"EXPORT_KEY"`)
`fields` | `object` | ✅ | Map of **string → string** only

Rules:
- `fields` keys MUST be non-empty strings.
- `fields` values MUST be strings.
- Unknown keys inside `context` MUST be rejected.

**Context hashing rule (v1.x):** `context_hash = H(wallet_id, action, fields)`.

---

### 4.3 `authority` (strict)

Field | Type | Required | Notes
---|---|---:|---
`class` | `str` | ✅ | Non-empty (declares authority type)
`scope` | `object` | ✅ | Object (opaque; shape validated elsewhere)
`proofs` | `object` | ❌ | Object if present (opaque; shape validated elsewhere)

Rules:
- Unknown keys inside `authority` MUST be rejected.
- Adamantine MUST NOT mint authority. Authority is **input-only**.

---

### 4.4 `timebox` (strict)

Field | Type | Required | Notes
---|---|---:|---
`issued_at` | `str` | ✅ | ISO-8601 with timezone (e.g. `"2026-02-06T12:00:00Z"`)
`expires_at` | `str` | ✅ | ISO-8601 with timezone
`max_skew_seconds` | `int` | ❌ | Non-negative integer (default 0)

Rules:
- `expires_at` MUST be strictly greater than `issued_at`.
- Adamantine MUST enforce timebox against injected `now`:
  - if `now < issued_at - max_skew_seconds` → deny
  - if `now > expires_at + max_skew_seconds` → deny
- Unknown keys inside `timebox` MUST be rejected.

---

### 4.5 `nonce` (strict)

Field | Type | Required | Notes
---|---|---:|---
`value` | `str` | ✅ | Non-empty
`store` | `str` | ✅ | Non-empty (declares nonce store integration name)
`mode` | `str` | ✅ | Must equal `"single_use"`

Rules:
- `mode` MUST equal `"single_use"` (any other value is rejected).
- Unknown keys inside `nonce` MUST be rejected.

**Note:** Nonce *validation + consumption* behavior is enforced by the foundation boundary. v1.4.0 adds replay/linkage hardening (see `qid_linkage_v1.md`).

---

### 4.6 `payload` (strict evidence wiring + body)

`payload` MUST be an object with:

Field | Type | Required | Notes
---|---|---:|---
`evidence` | `object` | ✅ | Strict wiring for evidence blocks (see below)
`body` | `object` | ✅ | Intent-specific object (schema enforced elsewhere)

Unknown keys inside `payload` MUST be rejected.

#### 4.6.1 `payload.evidence` (strict wiring)

`payload.evidence` MUST be an object with these required keys:

Field | Type | Required | Notes
---|---|---:|---
`qid` | `object` | ✅ | **Must be a non-empty object**
`oracle` | `object` | ✅ | **Must be a non-empty object**
`shield` | `object` | ✅ | **Must be a non-empty object**

Rules:
- All three evidence blocks are required and MUST be non-empty objects.
- Unknown keys inside `payload.evidence` MUST be rejected.

Normative evidence contracts (deep validation happens in adapters/EQC):
- Q-ID: `qid_linkage_v1.md`
- Shield bundle: `shield_bundle_v3.md`
- Shield signals: `shield_signal_v3.md`
- Oracle/Adaptive Core: (evidence shape validated in its adapter contract)

---

### 4.7 `audit` (optional, strict allowlist)

If present, `audit` MUST be an object with **only** these keys:

Allowed keys:
- `client_version` (str)
- `platform` (str)
- `locale` (str)
- `notes` (str)

Any other key MUST be rejected.

---

## 5. Response Envelope: `execution_response_v1`

The mobile call returns `execution_response_v1` (see foundation response contract).

Top-level response keys (strict allowlist):
- `v` = `"execution_response_v1"`
- `request_id` (echo)
- `status` ∈ `{ "allow", "deny", "error" }`
- `reason_id` (stable string)
- `decision` (deterministic decision object)
- optional `artifacts` (deterministic; non-sensitive only)
- optional `metrics` (counts only)

### 5.1 Decision object requirements

The response `decision` object MUST include:
- `intent` (echo)
- `action` (echo)
- `allowed` (boolean)
- `protection_mode` ∈ `{ "legacy", "minimal", "full" }`
- gate booleans:
  - `tva.allowed`
  - `eqc.allowed`
  - `wsqk.allowed`
- `nonce.consumed` (boolean)
- `timebox.valid` (boolean)
- `context_hash` (64-hex)

**Invariant:** if `status == "allow"`, then `reason_id` MUST be `OK_ALLOW`.

---

## 6. Security Boundaries (Non‑Negotiable)

This interface explicitly forbids:
- private keys, seeds, mnemonics, signing material
- cloud custody semantics
- hidden bypass flags / debug overrides
- network calls
- hidden state or time reads

Evidence is **input-only**. Adamantine consumes evidence, evaluates deterministically, enforces deny-by-default, and returns a deterministic decision.

---

## 7. Change Control

Any breaking change requires a new major version:
- `mobile_execution_call_v3`
- `execution_request_v3` and/or `execution_response_v2/v3` as applicable

No silent changes. No “temporary” exceptions.

---

## 8. Related Contracts

- `execution_request_v2.md`
- `mobile_decision_result_v1.md` *(presentation contract; separate from execution response)*
- `qid_linkage_v1.md`
- `shield_bundle_v3.md`
- `shield_signal_v3.md`
- `external_reason_governance_v1.md`
