# Wallet Runtime Boundary v1 (Contract Freeze)

**License:** MIT — **DarekDGB**

This document freezes the **wallet runtime ↔ Adamantine** boundary.

Adamantine is a **pure deterministic policy engine**. It does **not** execute wallet actions, hold keys, sign transactions, store secrets, or talk to networks.

This is a **contract**: it defines responsibilities, invariants, and forbidden behaviors.  
If an integration violates this boundary, it is **non-compliant** by definition.

---

## 1. Version

- **Interface name:** `wallet_runtime_boundary_v1`
- **Decision call contract:** `mobile_execution_call_v1` (execution_request_v1 / execution_response_v1)
- **Stability level:** **FROZEN** (breaking changes require a new major boundary contract)

---

## 2. Scope

This contract covers the **runtime embedding** of Adamantine inside a wallet application (iOS/Android/Web/desktop/backend services that serve a wallet app).

It governs:

- how runtime prepares inputs to Adamantine
- what Adamantine may read/compute
- what runtime may do with Adamantine outputs
- strict separation between **policy** and **execution**

---

## 3. Adamantine MUST NEVER do (Hard Prohibitions)

Adamantine is **not** a wallet. Adamantine MUST NEVER:

### Keys / signing
- generate, import, export, store, or custody private keys / seeds
- request seed phrases or key material
- sign transactions or messages
- derive addresses from private keys
- perform cryptographic operations that require private keys

### Wallet execution
- build transactions
- broadcast transactions
- modify wallet state (balances, UTXOs, accounts)
- submit swaps, bridging, or any on-chain action
- call wallet SDKs that can mutate user assets

### IO / persistence
- write to disk, keychain, secure enclave, database, or local storage
- cache secrets or decisions across calls
- open files or access OS resources

### Network
- make HTTP calls or open sockets
- query chain nodes, explorers, price feeds, or third-party APIs
- perform telemetry/analytics calls

### UI / UX
- display UI dialogs
- request user confirmation
- access contacts, camera, biometrics, or OS permissions
- decide copy strings shown to the user

### Authority
- mint or create authority proofs
- act as an authority source of truth
- accept “trust me” fields without explicit contract evidence

**If any of the above is needed, it belongs in wallet runtime (outside Adamantine).**

---

## 4. Adamantine MAY do

Adamantine MAY:

- validate request/response envelopes strictly (deny-by-default)
- compute deterministic hashes / canonicalizations on provided data
- evaluate policy rules over deterministic inputs
- compose deterministic decisions with stable `reason_id` semantics
- consume injected evidence bundles (as contracts specify), fail-closed on unknowns

---

## 5. Wallet Runtime MUST do (Responsibilities)

Wallet runtime is responsible for everything **outside** policy evaluation.

### 5.1 Provide deterministic inputs
Runtime MUST provide:

- `now` explicitly (unix seconds, integer) when required by contracts
- a stable `request_id` (caller-generated, unique per call)
- complete `context` values (wallet_id, device_id, app_id, session_id, action, fields)
- correct `timebox` (issued_at/expires_at + skew policy)
- correct `nonce` (value + store + mode), and ensure nonce lifecycle is enforced outside Adamantine

### 5.2 Handle authority & proofs (outside Adamantine)
Runtime MUST:

- gather/construct any authority proofs (Q-ID session, biometrics results, hardware attestations, etc.)
- validate proof material at the correct trust boundary (or pass to a dedicated adapter contract)
- maintain and protect any secrets used to produce proofs

### 5.3 Execute wallet actions (never Adamantine)
Runtime MUST:

- build and sign transactions
- broadcast transactions
- update wallet state
- manage UTXO selection and fee estimation
- handle chain/network failures and retries
- enforce user confirmations and UX flows

### 5.4 Persistence and confidentiality
Runtime MUST:

- store secrets only in appropriate OS-secure storage (Keychain/Keystore/Secure Enclave/etc.)
- manage session state (Q-ID sessions, ephemeral tokens, revocations)
- ensure sensitive fields are not logged or leaked in analytics

### 5.5 Present user-safe explanations
Runtime MUST map `reason_id` → user-facing explanations:

- never display raw internal data
- never show stack traces or internal errors
- use stable UX mapping tables, versioned and reviewed

---

## 6. Determinism rules (Hard Requirements)

### 6.1 Adamantine determinism
Given the same input envelope (including explicit `now`), Adamantine MUST produce:

- the same decision structure
- the same `reason_id`
- deterministic outputs (no hidden defaults, no time calls, no randomness)

### 6.2 Runtime determinism obligations
Runtime MUST NOT rely on hidden environment state to “complete” a request:

- no implicit timestamps (always supply `now` / timebox explicitly)
- no implicit nonce generation inside Adamantine
- no implicit field defaults inside Adamantine (missing = deny)

---

## 7. Failure semantics (stable meaning)

Wallet runtime MUST treat response `status` as:

- `allow`: policy permits execution
- `deny`: policy forbids execution (expected failure mode)
- `error`: system failure / unhandled condition (treat as deny from runtime execution perspective)

Runtime MUST:

- never execute wallet actions on `deny` or `error`
- treat unknown/invalid responses as **deny** (fail-closed)

(See `ReasonId` + D3 locks for the stable mapping of status ↔ reason_id ↔ decision flags.)

---

## 8. Security invariants (Non-negotiable)

- **Fail-closed:** unknown fields, unknown versions, unknown reasons → deny
- **No hidden authority:** allow must be backed by explicit contract evidence
- **No silent fallback:** any parsing/validation ambiguity → deny with stable reason_id
- **No side effects:** Adamantine evaluation must be pure (no IO, no network, no storage)
- **Minimal TCB:** keep the trusted computing base small; adapters validate strictly
- **Separation of duties:** Adamantine decides; runtime executes

---

## 9. Integration checklist (Runtime)

Before calling Adamantine, runtime must verify:

- [ ] correct contract version strings (`v` fields)
- [ ] `request_id` unique per evaluation
- [ ] `context` complete and canonicalized
- [ ] `now` supplied where required
- [ ] `timebox` set and valid for user intent
- [ ] nonce `mode` respected (`single_use` means do not reuse)
- [ ] authority evidence present (or explicitly absent and expected to deny)
- [ ] no secrets placed into `context.fields` or other non-secret channels

After receiving a response, runtime must verify:

- [ ] validator accepts response (deny-by-default)
- [ ] status/reason/flags satisfy locks (D3)
- [ ] determinism is preserved for caching/auditing needs
- [ ] `deny/error` never trigger wallet execution
- [ ] user-facing explanation mapping exists for `reason_id`

---

## 10. Change control

- Additive changes may be allowed only if they do not change meaning of existing fields.
- Any semantic change to status/reason mapping or boundary responsibilities requires:
  - a new contract version (e.g., `wallet_runtime_boundary_v2`)
  - a full proof pack (tests + docs + invariant mapping)

---

## 11. Attribution

**Author:** DarekDGB  
**License:** MIT
