# Trust Boundaries (Foundation)

Everything outside a contract boundary is **untrusted input**.

## Boundary rules

- Inputs crossing boundaries must be validated.
- Validation must be deterministic.
- Failure must be explicit and fail-closed with `ReasonId`.

## Boundaries (current)

1) Caller → TVA
- TVA treats `context`, `verdict`, and `authority` as untrusted until validated.

2) Decision (EQC) → Authority (WSQK)
- Authority must bind to the same `ExecutionContext`.

3) Authority → Enforcement (TVA)
- TVA verifies binding before any execution may happen.

## Non-goals (current)

No runtime boundaries yet (clients, OS keychain, signing devices). Those come later once contracts are locked.
