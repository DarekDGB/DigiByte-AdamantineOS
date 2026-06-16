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

4) Q-ID Replay Registry → Adamantine adapter
- Q-ID replay fields (`fresh`, `registry_commitment`) are trusted only when supplied by a stateful integrator replay registry or nonce authority.
- Runtime glue, wallet UI, and adapter shortcuts remain untrusted and MUST NOT self-assert freshness.
- Missing, stale, ambiguous, or unverifiable replay-registry state must fail closed.


5) Wallet UI → AdamantineOS human gate
- `payload.body.ui_confirmed` is untrusted as a standalone plaintext flag.
- A true payload flag is accepted only when `context.fields.ui_confirmed` is exactly the string `"true"`.
- The bound context field is part of `context_hash`; therefore the confirmation must be covered by the same evidence/authority chain as the rest of the request context.
- Payload-only, missing, mismatched, or unbound confirmation fails closed with `DENY_AUTHORITY_INSUFFICIENT`.

## Non-goals (current)

No runtime boundaries yet (clients, OS keychain, signing devices). Those come later once contracts are locked.
