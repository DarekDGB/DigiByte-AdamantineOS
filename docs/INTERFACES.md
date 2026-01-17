# Interfaces (Foundation)

This doc lists contract surfaces that define component boundaries.

## v1 contracts

### ExecutionContext
Fields:
- `wallet_id: str`
- `action: str`
- `context_hash: str`

### Verdict
Values:
- `ALLOW`
- `DENY`
- `STEP_UP`

### WSQKAuthority
Fields:
- `wallet_id: str`
- `action: str`
- `context_hash: str`

### TVA enforce
Function:
- `enforce_tva(context, verdict, authority) -> None`

Rules:
- Fail-closed on missing inputs.
- Fail-closed unless verdict is `ALLOW`.
- Fail-closed unless authority binds exactly to context.

## Reason IDs

`ReasonId` is the single source of truth for failure codes. No magic strings.
