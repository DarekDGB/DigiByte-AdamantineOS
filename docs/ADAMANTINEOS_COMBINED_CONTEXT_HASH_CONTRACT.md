# AdamantineOS Combined Context Hash Contract

Author attribution: **DarekDGB**  
Status: **Milestone 1 contract — pre-implementation lock**  
AdamantineOS release boundary: **v2.2.0 — WSQK v2 Quantum-Aware Upgrade**  
External Shield baseline: **Shield v3.2.0 tagged across the six Shield repositories**

## 1. Purpose

This document locks the deterministic contract for the AdamantineOS combined context hash used during full Shield v3 integration.

The combined context hash binds the AdamantineOS execution request to the exact wallet, transaction, Q-ID, WSQK, policy, replay/freshness, and Shield receipt context that was evaluated.

This contract exists before implementation so code cannot invent canonicalization rules later.

## 2. Non-negotiable rules

1. AdamantineOS remains on its own version line: `v2.2.0` until full Shield integration is complete, tested, audited, and approved.
2. Shield v3.2.0 is external evidence. It does not change AdamantineOS versioning.
3. The Shield Orchestrator receipt is evidence only.
4. Shield `ALLOW` is not final AdamantineOS execution approval.
5. Shield `DENY` must fail closed.
6. Unknown, malformed, missing, null, non-canonical, or nondeterministic context input must be rejected.
7. No timestamp, randomness, wall-clock, environment value, locale value, network value, or machine-local value may affect this hash unless it is explicitly present in the contract envelope.

## 3. Contract identifier

```text
contract = adamantineos.combined_context_hash
version = 1
domain = ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1
```

The domain separator is mandatory and must be part of the canonical input envelope.

Any semantic change to this contract requires a new contract version and a new domain separator.

## 4. Hash algorithm

The combined context hash is:

```text
sha256(canonical_json_utf8_bytes).hexdigest()
```

Output format:

```text
^[0-9a-f]{64}$
```

The output must be lowercase hexadecimal.

Uppercase hexadecimal output is invalid.

## 5. Exact input envelope

The v1 input envelope must contain exactly these fields and no others:

| Field | Type | Required | Rule |
|---|---:|---:|---|
| `contract` | string | yes | Must equal `adamantineos.combined_context_hash` |
| `version` | integer | yes | Must equal `1` |
| `domain` | string | yes | Must equal `ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1` |
| `request_id` | string | yes | Stable AdamantineOS request identifier |
| `wallet_context_hash` | string | yes | 64-character lowercase SHA-256 hex |
| `transaction_context_hash` | string | yes | 64-character lowercase SHA-256 hex |
| `qid_auth_context_hash` | string | yes | 64-character lowercase SHA-256 hex |
| `wsqk_posture_context_hash` | string | yes | 64-character lowercase SHA-256 hex |
| `policy_context_hash` | string | yes | 64-character lowercase SHA-256 hex |
| `replay_context_ref` | string | yes | Deterministic replay/freshness reference |
| `shield_receipt_context_hash` | string | yes | 64-character lowercase SHA-256 hex bound to the Shield Orchestrator receipt context |

Canonical field set:

```text
contract
version
domain
request_id
wallet_context_hash
transaction_context_hash
qid_auth_context_hash
wsqk_posture_context_hash
policy_context_hash
replay_context_ref
shield_receipt_context_hash
```

The implementation must reject the envelope if the field set is not exactly equal to the set above.

## 6. Required field validation

### 6.1 `contract`

Must be exactly:

```text
adamantineos.combined_context_hash
```

### 6.2 `version`

Must be integer `1`.

The string `"1"`, float `1.0`, boolean `true`, or null must be rejected.

### 6.3 `domain`

Must be exactly:

```text
ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1
```

### 6.4 `request_id`

Must be a non-empty deterministic ASCII string.

Recommended allowed pattern:

```text
^[A-Za-z0-9._:-]{1,128}$
```

`request_id` must not contain spaces, control characters, slashes, backslashes, hidden Unicode, or user PII.

### 6.5 Hash fields

The following fields must be lowercase 64-character hexadecimal strings:

```text
wallet_context_hash
transaction_context_hash
qid_auth_context_hash
wsqk_posture_context_hash
policy_context_hash
shield_receipt_context_hash
```

Allowed pattern:

```text
^[0-9a-f]{64}$
```

Uppercase hex must be rejected instead of normalized.

### 6.6 `replay_context_ref`

Must be a non-empty deterministic ASCII string that identifies the replay/freshness scope.

Recommended allowed pattern:

```text
^[A-Za-z0-9._:-]{1,160}$
```

`replay_context_ref` is not generated inside the hash function. It is supplied by the AdamantineOS replay/freshness boundary.

## 7. Canonical JSON rules

The canonical JSON serialization for v1 is:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

The serialized string is then encoded as UTF-8 bytes.

Normative requirements:

1. Objects are serialized with keys sorted in ascending lexicographic order.
2. No spaces are emitted after commas or colons.
3. No trailing newline is added.
4. No comments are allowed.
5. No duplicate JSON object keys are allowed. A parser/loader that silently accepts duplicate keys must not be used without duplicate-key rejection before hashing.
6. The input must be a JSON object, not an array, string, number, boolean, or null.

## 8. Field ordering

Input field order must not affect the hash.

The implementation must canonicalize object keys by sorted lexical key order before hashing.

The canonical JSON byte string for the valid v1 vector in section 18 is ordered as:

```text
contract
domain
policy_context_hash
qid_auth_context_hash
replay_context_ref
request_id
shield_receipt_context_hash
transaction_context_hash
version
wallet_context_hash
wsqk_posture_context_hash
```

This is the sorted JSON serialization order, not the human schema order.

## 9. Unknown, forbidden, and missing fields

### 9.1 Unknown fields

Unknown fields are forbidden.

Any top-level field outside the exact v1 field set must be rejected fail-closed.

### 9.2 Forbidden authority fields

The following examples are forbidden and must be rejected if present:

```text
allow
approved
authority
auto_approve
bypass
broadcast
can_sign
decision
execute
final_approval
force_allow
human_approved
override
sign
trusted
```

This list is not exhaustive. The main rule is exact-field-set validation.

### 9.3 Missing fields

Any missing required field must reject fail-closed.

There are no optional fields in v1.

## 10. Null handling

`null` is forbidden for every v1 field.

The implementation must reject null instead of replacing it with an empty string, zero, default hash, default request id, or default replay reference.

## 11. Array handling

The v1 combined context envelope contains no arrays.

If any array is present in the v1 envelope, the envelope must be rejected because it must be an unknown-field or wrong-type violation.

General future rule if a later version explicitly introduces arrays:

1. Array order is significant.
2. Arrays must not be sorted implicitly.
3. Empty arrays must be explicitly permitted by that later contract or rejected.
4. Arrays must not contain mixed types unless a later contract explicitly allows them.

## 12. Object/map ordering

The v1 envelope has only one object: the top-level envelope.

Top-level keys are sorted lexicographically during canonical JSON serialization.

Nested objects are not allowed in v1. Any nested object must be rejected as a wrong-type or unknown-field violation.

Future versions that allow nested objects must sort all object keys recursively before hashing.

## 13. String and Unicode handling

The v1 envelope is ASCII-only by contract.

All string fields must reject:

- non-ASCII characters
- control characters
- invisible Unicode characters
- Unicode normalization ambiguity
- leading or trailing whitespace
- embedded newline, carriage return, tab, or null bytes

The implementation must not normalize strings before hashing. It must reject strings that are outside the allowed ASCII patterns.

This avoids cross-platform Unicode normalization ambiguity.

## 14. Integer, float, decimal, and boolean handling

### 14.1 Integers

Only `version` is an integer in v1.

It must be exactly integer `1`.

No other integer fields are allowed.

### 14.2 Floats and decimals

Floats and decimals are forbidden in the v1 envelope.

The implementation must reject any float/decimal value anywhere in the envelope.

### 14.3 Booleans

Booleans are forbidden in the v1 envelope.

The implementation must reject boolean values anywhere in the envelope.

## 15. Timestamp and randomness policy

No timestamp field exists in the v1 combined context envelope.

No randomness field exists in the v1 combined context envelope.

The hash function must not read:

- current time
- system clock
- timezone
- locale
- random number generator
- process id
- hostname
- environment variables
- network state
- filesystem state

Any freshness/replay state must be represented only by the explicit `replay_context_ref` string supplied to the envelope.

## 16. Exact validation order

Recommended fail-closed validation order:

1. Input is a JSON object / Python dict.
2. Reject duplicate keys if loaded from raw JSON.
3. Field set exactly equals the v1 required field set.
4. `contract` equals the locked contract id.
5. `version` equals integer `1`.
6. `domain` equals the locked domain separator.
7. Validate all hash fields as lowercase 64-character SHA-256 hex.
8. Validate `request_id` and `replay_context_ref` as deterministic ASCII strings.
9. Reject all null, float, decimal, boolean, list, and nested object values.
10. Serialize using canonical JSON.
11. UTF-8 encode.
12. SHA-256 hash.
13. Return lowercase hex digest.

## 17. Security meaning

The combined context hash proves that these context domains were bound together:

```text
request_id
wallet_context_hash
transaction_context_hash
qid_auth_context_hash
wsqk_posture_context_hash
policy_context_hash
replay_context_ref
shield_receipt_context_hash
```

Changing any one of these fields must produce a different combined context hash.

A Shield receipt from one context must not be reusable in another context.

## 18. Valid test vector

### 18.1 Input envelope

```json
{
  "contract": "adamantineos.combined_context_hash",
  "version": 1,
  "domain": "ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1",
  "request_id": "req-000001",
  "wallet_context_hash": "1111111111111111111111111111111111111111111111111111111111111111",
  "transaction_context_hash": "2222222222222222222222222222222222222222222222222222222222222222",
  "qid_auth_context_hash": "3333333333333333333333333333333333333333333333333333333333333333",
  "wsqk_posture_context_hash": "4444444444444444444444444444444444444444444444444444444444444444",
  "policy_context_hash": "5555555555555555555555555555555555555555555555555555555555555555",
  "replay_context_ref": "replay:v1:nonce:000001",
  "shield_receipt_context_hash": "6666666666666666666666666666666666666666666666666666666666666666"
}
```

### 18.2 Canonical JSON string

```json
{"contract":"adamantineos.combined_context_hash","domain":"ADAMANTINEOS_COMBINED_CONTEXT_HASH_V1","policy_context_hash":"5555555555555555555555555555555555555555555555555555555555555555","qid_auth_context_hash":"3333333333333333333333333333333333333333333333333333333333333333","replay_context_ref":"replay:v1:nonce:000001","request_id":"req-000001","shield_receipt_context_hash":"6666666666666666666666666666666666666666666666666666666666666666","transaction_context_hash":"2222222222222222222222222222222222222222222222222222222222222222","version":1,"wallet_context_hash":"1111111111111111111111111111111111111111111111111111111111111111","wsqk_posture_context_hash":"4444444444444444444444444444444444444444444444444444444444444444"}
```

### 18.3 Expected combined context hash

```text
30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a
```

## 19. Positive determinism test vector

The same envelope with fields presented in any different input order must produce the same expected hash:

```text
30926f0e1d86bccce118090dc516b7564cefb226fc397524f2d4430ff28b2d3a
```

## 20. Change-detection test vectors

Each mutation below must produce a different hash from the valid vector.

| Mutation | Expected hash |
|---|---|
| `wallet_context_hash = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `5f37bc650d63a187227222d96b3bab9b8b1e17de23e7ba1ce7f0fc31d0eee663` |
| `transaction_context_hash = bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` | `95110bdca413454f6bc8aa049a850a7d3f1305a1db45b3b7b0ddca9eacd0983f` |
| `qid_auth_context_hash = cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc` | `8c0348a34b587f8544a48a398d616df3dd2ce24d4f7b7f392b35068166ad0b90` |
| `wsqk_posture_context_hash = dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd` | `5b6bf77fb4b30f1f974dba0a4ffff5007f1b9629cae76359fb766150a2fa400d` |
| `policy_context_hash = eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee` | `a9881388d21349d6506a2e124f9fdacdca32ea122f559d643433122fdd1c39d6` |
| `replay_context_ref = replay:v1:nonce:000002` | `65c626260bc95ca40dd46633a51ad49ac0dd72e0e1e1838f4380c3077e93609d` |
| `shield_receipt_context_hash = ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff` | `a37645ddaef009481bf17fcbe75fb13ca77ebff6a2bd253c941a5b055837d278` |
| `request_id = req-000002` | `e92ccfce6c6551731cc6a4a37fd3f4b136decd3279b8761c628b9606380271c8` |

## 21. Fail-closed rejection cases

The implementation must reject all cases below before producing a hash:

| Case | Required result |
|---|---|
| Missing `contract` | reject |
| Missing `version` | reject |
| Missing `domain` | reject |
| Missing `request_id` | reject |
| Missing any context hash field | reject |
| Missing `replay_context_ref` | reject |
| Any unknown top-level field | reject |
| Any forbidden authority-like field | reject |
| Any required field set to `null` | reject |
| `version` as string `"1"` | reject |
| `version` as float `1.0` | reject |
| Uppercase hex in any hash field | reject |
| Short hash in any hash field | reject |
| Non-hex character in any hash field | reject |
| Empty `request_id` | reject |
| Empty `replay_context_ref` | reject |
| Non-ASCII string value | reject |
| Leading/trailing whitespace in string value | reject |
| Embedded newline/tab/control character | reject |
| Any array value | reject |
| Any nested object value | reject |
| Any boolean value | reject |
| Any timestamp field | reject |
| Any randomness field | reject |
| Duplicate JSON key | reject |
| Top-level JSON array instead of object | reject |

## 22. Fixture-first implementation gate

Before implementation code is written, this document must be reviewed and accepted.

The first implementation must be fixture-first and negative-test-first.

Minimum required tests before happy-path expansion:

```text
missing required field rejects
unknown field rejects
null field rejects
wrong type rejects
uppercase hash rejects
short hash rejects
non-hex hash rejects
duplicate key rejects
field order does not change hash
changed wallet context changes hash
changed transaction context changes hash
changed Q-ID context changes hash
changed WSQK context changes hash
changed policy context changes hash
changed replay reference changes hash
changed Shield receipt context changes hash
```

## 23. No implementation before review

No AdamantineOS integration implementation may begin until this contract and `docs/ADAMANTINEOS_INTEGRATION_HARNESS_SCOPE.md` have both been reviewed and approved.

No AdamantineOS tag is allowed from this document alone.
