# Architecture (Foundation)

This repo is a **foundation rebuild**. It defines the minimum contract surfaces and enforcement rules required before any wallet execution exists.

## Scope

Built in this repo (today):
- Contract surfaces (`ExecutionContext`, `Verdict`, `ReasonId`, `WSQKAuthority`)
- TVA enforcement gate (fail-closed)
- CI + tests + coverage enforcement
- Invariants and foundational definitions

Not built yet (by design):
- EQC decision engine (rules, scoring, deterministic context hashing)
- WSQK TTL/nonce/single-use proofs
- Any wallet runtime (key mgmt, signing, broadcasting)
- Any client code (iOS/Android/Web)
- Shield v3 / Adaptive Core v3 integration

## Required flow
EQC  →  WSQK  →  TVA  →  Execution

- EQC produces a **Verdict** for a specific context.
- WSQK produces **Authority** bound to that context.
- TVA blocks execution unless the truths align.

## Contracts-first

All cross-component interaction must pass through explicit contracts:
- `ExecutionContext(wallet_id, action, context_hash)`
- `Verdict(ALLOW|DENY|STEP_UP)`
- `WSQKAuthority(wallet_id, action, context_hash)`
- `ReasonId` is the single source of truth for failures.

No silent fallbacks. No hidden authority.
