# Adamantine Wallet OS — Invariants

This repository is rebuilt from first principles.

## Foundation Freeze
- A known-good baseline must be tagged before integration work (e.g. `v0.1.0-foundation`).
- At the frozen foundation baseline, EQC may enforce **minimal presence checks** only.
- Integration evidence (Q-ID session + RiskReport) becomes mandatory only when the integration gate is wired in.

## Core Laws
- No hidden authority
- No privileged maintainer paths
- No silent fallback
- Fail-closed always
- Deterministic behavior only
- Read-only observation before action
- Human-in-the-loop where consequence exists

## Truth Primitives
- EQC — truth extraction
- WSQK — sovereign binding
- TVA — Truth Vector Authority

Only what is aligned is permitted to continue.

## Scope Discipline
- Architecture before implementation
- Contracts before features
- Tests before trust
