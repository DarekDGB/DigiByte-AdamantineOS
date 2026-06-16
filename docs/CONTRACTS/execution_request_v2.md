# Execution Request v2 (Contract) — v1.x

**License:** MIT — **Author:** DarekDGB  
**Scope:** Normative request envelope shape for Mobile/Runtime → AdamantineOS.

---

## 1. Purpose

This document freezes the execution request contract used to submit an action for deterministic evaluation.

Adamantine is:
- deterministic
- fail-closed
- contract-first
- pure (no hidden state, no network, no clocks)

---

## 2. High-Level Shape

The request MUST be a single JSON object:

- `envelope_version`
- `wallet_id`
- `action`
- `payload`
- `context`

---

## 3. Evidence (Normative)

The request MAY include evidence in:

`payload.evidence`

Expected evidence blocks:
- `payload.evidence.qid`
- `payload.evidence.oracle`
- `payload.evidence.shield`

### 3.1 Q-ID Evidence (v1.4.0 clarification)

`payload.evidence.qid` represents Q-ID session proof used for protected evaluation.

Starting in **v1.4.0**, Q-ID evidence MAY additionally include **replay/linkage proof** fields that bind the session proof to:
- `wallet_id`
- `subject`
- `device_binding`
- `proof_hash`
- `session_nonce` (must match envelope nonce)

If the policy latch `require_qid_replay_proof` is enabled, replay proof becomes **required** for protected calls (see `DURABLE_NONCE_STORE_INTEGRATION.md` and `qid_linkage_v1.md`).

---


## 3.2 Human Confirmation Binding

`payload.body.ui_confirmed` MUST NOT be treated as authority by itself. Runtime payload fields are untrusted unless bound into the request context.

For a human-confirmed request to pass the final human gate, the request MUST include:

```json
"context": {
  "fields": {
    "ui_confirmed": "true"
  }
},
"payload": {
  "body": {
    "ui_confirmed": true
  }
}
```

The context field is a string because `context.fields` is the canonical hash input. The payload field remains a boolean because it represents the runtime UI event. Both must agree.

If the payload says `ui_confirmed: true` but the context field is missing or not exactly `"true"`, AdamantineOS must deny at the human gate.

## 4. Determinism Requirements

For identical inputs, Adamantine MUST produce:
- identical `reason_id`
- identical `context_hash`
- identical artifacts shape
- identical `protection_mode`

---

## 5. Backward Compatibility

- New request fields MUST be optional.
- Removing fields requires a major contract bump.
- Unknown fields MAY be rejected depending on strict schema mode.

---

## 6. Non-Goals

This contract does not define:
- key custody
- transaction building
- signing
- broadcasting
- network calls

---

## 7. Related Contracts

- `qid_linkage_v1.md`
- `DURABLE_NONCE_STORE_INTEGRATION.md`
