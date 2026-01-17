# Interfaces (Foundation)

This document lists **contract surfaces** that define component boundaries in the Adamantine Wallet OS foundation.

It is intentionally **minimal** and **implementation-agnostic**.

---

## v1 contracts

### Execution Context
Fields:
- `wallet_id: str`
- `action: str`
- `context_hash: str`

### Verdict
Values:
- `ALLOW`
- `DENY`
- `STEP_UP`

### EQC Result (decision output)
Fields:
- `verdict: Verdict`
- `reason_ids: tuple[str, ...]`
- `context_hash: str`

### WSQK Authority (authority token)
Fields:
- `wallet_id: str`
- `action: str`
- `context_hash: str`
- `issued_at: int` *(unix seconds)*
- `expires_at: int` *(unix seconds)*
- `nonce: str` *(single-use)*

---

## v1 gates and makers

### TVA enforce (final gate)
Function:
- `enforce_tva(context, verdict, authority, *, now: int | None = None, nonce_store: NonceStore | None = None) -> None`

Rules:
- Fail-closed on missing inputs.
- Fail-closed unless verdict is `ALLOW`.
- Fail-closed unless authority binds exactly to context (`wallet_id`, `action`, `context_hash`).
- Fail-closed unless time window holds: `issued_at â¤ now â¤ expires_at`.
- Fail-closed unless nonce is accepted as single-use (via injected `nonce_store`).

Determinism:
- `now` must be injected (no global time).
- `nonce_store` must be injected (no global state).

### WSQK issuer (authority maker)
Function:
- `issue_wsqk_authority(WSQKIssueRequest) -> WSQKAuthority`

Notes:
- Inputs are explicit and injected (including `now`, `ttl_seconds`, and `nonce`).
- Issuer does not execute and does not decide policy.
- Output is a context-bound, time-bound, single-use authority token.

---

## Reason IDs

`ReasonId` is the single source of truth for failure codes.  
No magic strings.
