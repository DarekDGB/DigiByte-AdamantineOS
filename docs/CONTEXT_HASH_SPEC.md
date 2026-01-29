# Context Hash Specification (v1)

Author attribution: **DarekDGB**

This document defines the canonical, deterministic computation of `context_hash`
used by Adamantine Wallet OS v1.

The `context_hash` MUST be stable across platforms and implementations.

---

## Inputs

Required:
- `wallet_id: str`
- `action: str`

Optional:
- `fields: dict[str, str] | None`

All field keys and values are treated as UTF-8 text.

---

## Canonical form

The canonical byte string is the UTF-8 encoding of the following newline-joined lines:

1. `wallet_id=<wallet_id>`
2. `action=<action>`
3. For each key `k` in `fields`, in **ascending lexicographic order**:
   - `<k>=<fields[k]>`

The newline separator is a single `\n` (LF).

No trailing newline is appended beyond the newline joins.

If `fields` is `None` or empty, only the first two lines are present.

---

## Hash algorithm

`context_hash` is:

- `sha256(canonical_bytes).hexdigest()`

Output is a lowercase hex string of length 64.

---

## Notes / constraints

- No randomness.
- No time dependency.
- Ordering MUST be stable (sorted by key).
- Unknown fields are included only if present in `fields` input (core does not invent fields).
- Callers MUST ensure `fields` values are strings; adapters must validate this at the boundary.
