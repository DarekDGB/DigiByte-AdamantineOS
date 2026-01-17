# Threat Model (Foundation)

This threat model applies to the foundation stage: contracts and enforcement gates.

## Primary threats

- **Bypass attempts:** skipping TVA or forging inputs to TVA.
- **Mismatched authority:** authority token not bound to the context being executed.
- **Silent fallback:** execution proceeding on partial truth.
- **Ambiguity drift:** inconsistent reason codes or undocumented behaviors.

## Defenses (foundation)

- Fail-closed TVA gate.
- Explicit `ReasonId` taxonomy (no magic strings).
- Deterministic behavior only.
- Negative-first tests + coverage enforcement.

## Future threats (out of scope today)

- Key theft, signing flow attacks, UI deception, device compromise, network MITM, supply chain, client sandbox escapes.

Those are addressed after contracts + enforcement are locked.
