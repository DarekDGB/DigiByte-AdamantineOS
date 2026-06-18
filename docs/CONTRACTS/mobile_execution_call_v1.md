# Mobile Execution Call v1 (Draft)

**License:** MIT — **DarekDGB**

This document freezes the **mobile → Adamantine execution boundary** interface.

It is a **pure contract**: no UI, no signing, no key custody, no network calls.
Mobile platforms (iOS / Android) must be able to call Adamantine deterministically and receive a stable, explainable decision.

---

## 1. Version

- **Interface name:** `mobile_execution_call_v1`
- **Request envelope:** `execution_request_v1`
- **Response envelope:** `execution_response_v1`

Adamantine will reject any request/response that does not match these shapes.

---

## 2. Determinism Rules (Hard Requirements)

Mobile MUST:

- Provide **`now`** explicitly (unix seconds, integer) to Adamantine.
- Provide **stable `request_id`** (string) per call.
- Provide **only the fields defined in the contract** (unknown fields are deny-by-default).

Adamantine MUST:

- Be **deny-by-default**.
- Be **fail-closed** on ambiguity.
- Never inject nondeterministic data (no timestamps, random ids, device identifiers).
- Return a stable **`reason_id`** for deny/error outcomes.

---

## 3. Request: `execution_request_v1`

The canonical request shape is documented in:

- `docs/execution_request_v1.md`

In short, mobile sends:

- `v`: `"execution_request_v1"`
- `request_id`: non-empty string
- `intent`: non-empty string (human-readable; stable)
- `context`:
  - `wallet_id`: non-empty string
  - `action`: non-empty string (e.g. `"SEND"`)
  - `fields`: optional `{str: str}` (canonicalized by hashing rules)
- `timebox`:
  - `issued_at`: ISO-8601 with timezone (e.g. `"2026-02-06T12:00:00Z"`)
  - `expires_at`: ISO-8601 with timezone
- `nonce`: non-empty string (single-use)
- `authority`:
  - `proofs.wsqk`: external proof object (WSQKAuthority binding)
- `payload`: opaque object containing **evidence** (e.g. Q-ID session proof, Adaptive Core risk report)

**Key rule:** Adamantine must not mint authority. WSQK proof must be provided in `authority.proofs.wsqk`.

---

## 4. Response: `execution_response_v1`

The canonical response shape is documented in:

- `docs/execution_response_v1.md`

Top-level response fields:

- `v`: `"execution_response_v1"`
- `request_id`: echo of request id
- `status`: one of `{ "allow", "deny", "error" }`
- `reason_id`: stable reason identifier string
- `decision`: object containing the deterministic decision details
- optional `artifacts` (deterministic, non-sensitive only)
- optional `metrics` (counts only; no payloads)

Decision object:

- `intent`: echo
- `action`: echo
- `allowed`: boolean (`status=="allow"`)
- `tva.allowed`: boolean
- `eqc.allowed`: boolean
- `wsqk.allowed`: boolean
- `nonce.consumed`: boolean
- `timebox.valid`: boolean
- `context_hash`: 64-hex string

**Invariant:**  
If `status == "allow"`, then `reason_id` **must** be `OK_ALLOW`.

---

## 5. Security Boundaries (Non-Negotiable)

This interface explicitly forbids:

- Private keys, seeds, mnemonics, signing material
- Cloud sync / remote custody semantics
- Web / browser runtime assumptions
- Hidden bypass flags or debug overrides

Evidence is **input only**. Adamantine consumes evidence (e.g. Q-ID proof, Adaptive Core risk report), evaluates EQC, enforces WSQK + TVA, and returns a deterministic decision.

---

## 6. Implementation Anchors

Code anchors for this legacy contract:

- Request validation: `src/adamantine/v1/execution/envelope_v1.py`
- Response builder: `src/adamantine/v1/execution/response_v1.py`
- Legacy compatibility harness: `src/adamantine/v1/execution/orchestrator_v1.py`
- Contract wrapper validator: `src/adamantine/v1/execution/mobile_call_v1.py` (added in Phase D)

### AOS-RT-004 legacy-entrypoint lock

`orchestrator_v1.py` is retained only for legacy fixture compatibility and regression tests. It is not a production integration entrypoint and must not be presented to wallet integrators as the live AdamantineOS decision boundary.

The v1 harness may synthesize accepted placeholder evidence for absent Shield, Q-ID, Adaptive Core, and AI Gateway inputs (`v1:no_shield_contract`, `v1:qid_absent_allowed`, `v1:risk_absent_allowed`, `v1:ai_gateway_not_required`). This is a legacy compatibility behavior only. It is not active Shield/Q-ID/Adaptive/AI-Gateway protection and must not be used as a production approval path.

Production integrations must use the v2 runtime host and the `orchestrator_v2` final decision boundary.

---

## 7. Change Control

Any breaking change requires a new major version:

- `mobile_execution_call_v2`
- `execution_request_v2`
- `execution_response_v2`

No silent changes. No “temporary” exceptions.
