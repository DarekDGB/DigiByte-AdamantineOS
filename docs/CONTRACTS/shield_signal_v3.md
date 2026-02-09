# Shield Signal v3 (Contract Freeze)

**License:** MIT — **DarekDGB**

This document freezes the **Shield v3 → Adamantine** evidence signal format.

A Shield signal is **evidence only**.

- **No authority**
- **No execution**
- **No keys**
- **No UI**
- **No network assumptions**

Adamantine must treat Shield evidence as **untrusted input** and remain **fail-closed**.

---

## 1. Version

- **Interface name:** `shield_signal_v3`
- **Stability level:** **FROZEN**
- **Breaking change rule:** any semantic change requires `shield_signal_v4`

---

## 2. Purpose

A `shield_signal_v3` is a single, self-contained evidence record produced by one Shield layer, describing:

- what layer observed
- the deterministic context it applies to
- the layer’s verdict (allow/deny/unknown) as **evidence**
- stable, versioned reason mapping

It does **not** grant permission. It only informs higher-level reasoning (EQC/TVA/Adamantine policy).

---

## 3. Data model

### 3.1 Top-level object

Field | Type | Required | Notes
---|---|---:|---
`v` | `str` | ✅ | Must equal `"shield_signal_v3"`
`layer` | `str` | ✅ | One of: `sentinel_ai`, `adn`, `dqsn`, `qwg`, `guardian_wallet`
`signal_id` | `str` | ✅ | Caller-generated unique id for this signal (stable per emission)
`context_hash` | `str` | ✅ | 64-char hex. Must match Adamantine context hash spec.
`issued_at` | `int` | ✅ | Unix seconds, deterministic input from producer
`expires_at` | `int` | ✅ | Unix seconds. Must be `>= issued_at`
`verdict` | `str` | ✅ | One of: `allow`, `deny`, `unknown`
`reason_id` | `str` | ✅ | Stable reason code from the producer’s reason namespace
`confidence` | `int` | ✅ | 0..100 (integer). Producer confidence in this evidence
`facts` | `object` | ✅ | Deterministic, contract-safe facts only (see 3.3)
`meta` | `object` | ❌ | Deterministic metadata (no PII). Optional.

### 3.2 Layer enum

Allowed values:

- `sentinel_ai`
- `adn`
- `dqsn`
- `qwg`
- `guardian_wallet`

Unknown layers MUST be rejected by adapters (fail-closed).

### 3.3 Facts object rules (hard)

`facts` is an object with:

- keys: non-empty `str`
- values: **only** `str`, `int`, `bool`, or arrays of those scalar types
- **no floats**
- **no nested objects**
- **no timestamps unless explicitly part of the signal itself**
- **no secrets**
- **no keys**
- **no user PII**

If producer needs richer structure, it must be flattened deterministically.

Unknown/invalid fact shapes MUST be rejected.

### 3.4 Meta object rules (soft but deterministic)

`meta` may include:

- `producer` (str) — e.g., library name/version
- `schema` (str) — optional internal schema label
- `notes` (str) — short deterministic note

`meta` MUST NOT include:

- device identifiers
- IP addresses
- emails / phone numbers
- raw logs / stack traces
- anything nondeterministic

---

## 4. Reason namespace discipline

Shield producers may have their own internal reason ids.  
At the **adapter boundary**, these are mapped into Adamantine `ReasonId` (internal) deterministically.

Hard rules:

- `reason_id` MUST be non-empty string
- adapter MUST reject unknown reasons (`UNKNOWN_EXTERNAL_REASON` mapping is allowed only if the adapter contract explicitly permits it)

This contract defines only the field; mapping rules are defined by the adapter contract (`shield_bundle_v3` + adapter).

---

## 5. Time rules

- `issued_at` and `expires_at` are required.
- `expires_at >= issued_at`
- Signals outside the time window are **stale evidence**.
- Staleness handling is policy-driven; adapters must still validate structure deterministically.

---

## 6. Determinism requirements

Producers MUST ensure:

- same observation + same inputs → byte-identical signal after canonical JSON serialization
- no hidden randomness
- no implicit defaults
- no environment-derived fields (locale, timezone, etc.)

---

## 7. Security invariants

- **Evidence only**: cannot force allow
- **Fail-closed**: unknown fields, unknown enums, unknown reasons → deny at adapter boundary
- **No hidden authority**: signals are untrusted inputs
- **Strict canonicalization**: adapters must validate and normalize deterministically

---

## 8. Example (non-normative)

```json
{
  "v": "shield_signal_v3",
  "layer": "qwg",
  "signal_id": "qwg-000001",
  "context_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "issued_at": 1760000000,
  "expires_at": 1760000300,
  "verdict": "deny",
  "reason_id": "QWG_DEVICE_COMPROMISED",
  "confidence": 92,
  "facts": {
    "device_integrity": "fail",
    "jailbreak_detected": true,
    "risk_score": 97
  },
  "meta": {
    "producer": "qwg-ios/3.0.0"
  }
}
```

---

## 9. Change control

- Additive fields are **not allowed** in v3 signals (deny-by-default).
- New data requires a new contract version.

---

## 10. Attribution

**Author:** DarekDGB  
**License:** MIT
