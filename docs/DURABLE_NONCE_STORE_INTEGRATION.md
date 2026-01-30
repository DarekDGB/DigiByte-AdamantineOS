# Durable Nonce Store Integration (v1)

Author attribution: **DarekDGB**

This document defines how a mobile runtime MUST integrate a durable nonce store
to preserve Adamantine's replay protection guarantees across restarts.

---

## Why this exists

`InMemoryNonceStore` is correct for CI and deterministic tests, but it is NOT safe for production.
Mobile apps restart, get background-killed, and resume frequently. Without persistence, a nonce replay
can become possible after restart.

This repo defines the durable contract:

- `DurableNonceStore.check_and_mark(wallet_id, nonce, expires_at) -> bool`

---

## Security requirements (normative)

A platform `DurableNonceStore` implementation MUST satisfy:

1. **Atomic check-and-mark**
   - Exactly one concurrent call for the same `(wallet_id, nonce)` may succeed.

2. **Crash safety**
   - Once a nonce is marked used, it MUST remain used after process restart.

3. **Fail-closed**
   - If storage is unavailable, corrupt, or cannot confirm correctness,
     the store must refuse acceptance (behave as replay / deny).

4. **No global state**
   - Store must be dependency-injected into the execution pipeline.
   - No module-level singletons.

---

## Integration boundary (injection rule)

The runtime MUST inject a nonce store into:

- `enforce_tva(..., nonce_store=...)`
- `run_with_tva(..., nonce_store=...)`

Production mobile builds MUST use a durable implementation that conforms to `DurableNonceStore`.

Test builds MAY use `InMemoryNonceStore`.

---

## Suggested platform storage (non-normative)

iOS:
- Keychain + monotonic record of used nonces (or SQLite in protected storage)
- Ensure atomicity with a transactional write

Android:
- EncryptedSharedPreferences or SQLCipher/Room in encrypted mode
- Ensure atomicity with transactions

---

## Minimal schema suggestion (non-normative)

Key: `(wallet_id, nonce)`  
Value: `expires_at` (int)

Garbage collection:
- Expired entries MAY be cleaned up lazily
- Cleanup must never invalidate "used" nonces before `expires_at`

---

## Test policy

This repo includes tests to ensure:
- the durable interface exists and is abstract
- production selection logic must not silently use in-memory store
