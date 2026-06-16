# Decision ≠ Authority ≠ Execution (Law)

Adamantine is built around strict separation:

## Decision (EQC)
- Evaluates context and produces a deterministic verdict.
- Does not execute.
- Does not grant authority.

## Authority (WSQK)
- Represents permission bound to wallet + action + context_hash.
- Does not decide policy.
- Does not execute.

## Enforcement (TVA)
- Final gate that refuses execution unless required truths align.
- Does not decide policy.
- Does not mint authority.
- Does not execute.

## Execution (future)
Execution is outside the foundation scope. It must only run after TVA passes.


## Human Confirmation
Human confirmation is a local gate, not upstream authority.

The final allow path requires a runtime UI confirmation event and a matching context-bound confirmation value:

- runtime event: `payload.body.ui_confirmed` is exactly `true`
- bound context: `context.fields.ui_confirmed` is exactly `"true"`

The bound context value participates in `context_hash`. A payload-only flag cannot promote evidence to final approval.

