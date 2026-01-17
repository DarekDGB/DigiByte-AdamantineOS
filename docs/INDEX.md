# Docs Index (Foundation)

This repository is a **fresh rebuild** of Adamantine Wallet OS.

**Status:** foundation-first (contracts + invariants + deterministic fail-closed gates).  
**Not yet implemented:** runtime wallet execution, EQC engine, WSQK TTL/nonce/proof, clients, Shield/Adaptive integration.

## Core documents

- `FOUNDATIONS.md` — definitions of **EQC / WSQK / TVA** and the required sequence.
- `ARCHITECTURE.md` — system boundaries and the minimal foundation architecture.
- `DECISION_AUTHORITY_EXECUTION.md` — the law: Decision ≠ Authority ≠ Execution.
- `TRUST_BOUNDARIES.md` — where trust ends and validation must begin.
- `THREAT_MODEL.md` — what we defend against (foundation-level).
- `INTERFACES.md` — contract surfaces and invariants between components.

## Source of truth

- `INVARIANTS.md` is **normative**.  
  If any doc or code conflicts with `INVARIANTS.md`, the invariants win.
