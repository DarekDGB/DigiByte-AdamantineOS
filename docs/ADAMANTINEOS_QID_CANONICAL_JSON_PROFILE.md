# AdamantineOS Q-ID Canonical JSON Profile

**License:** MIT — **Author:** DarekDGB  
**Status:** Normative integration profile  
**Profile name:** `adamantine-qid-canonical-json-v1`  
**Scope:** Q-ID Adamantine evidence v2 `response_payload` proof hashing.

---

## 1. Purpose

This document names and freezes the canonical JSON byte profile used by AdamantineOS when validating Q-ID Adamantine evidence v2.

The purpose is cross-repository compatibility. AdamantineOS and DigiByte-Q-ID must hash the same Q-ID `response_payload` into the same `proof_hash`. If either side changes JSON serialization, key ordering, escaping, or byte encoding without an explicit contract update, valid evidence may fail closed or invalid evidence may become ambiguous.

This profile is therefore part of the AdamantineOS / Q-ID boundary contract.

---

## 2. Profile Name

The canonical profile name is:

```text
adamantine-qid-canonical-json-v1
```

The implementation constant is:

```text
ADAMANTINE_QID_CANONICAL_JSON_PROFILE = "adamantine-qid-canonical-json-v1"
```

Any future incompatible change to the canonical JSON byte profile requires a new profile name and a major contract review.

---

## 3. Covered Evidence

This profile applies to Q-ID Adamantine evidence v2 with:

```text
v = "2"
kind = "qid_login_v2"
```

AdamantineOS validates:

```text
proof_hash == sha256(canonical_qid_json_bytes(response_payload)).hexdigest()
```

The covered object is exactly the `response_payload` object, including all keys present in that object. Wrapper fields outside `response_payload`, such as `login_uri`, `signature`, `kind`, and `v`, are not hashed by this AdamantineOS adapter proof-hash check. They remain part of the external Q-ID verifier responsibility.

---

## 4. Canonical JSON Rules

The `adamantine-qid-canonical-json-v1` byte profile is:

```text
json.dumps(
    response_payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=True,
    allow_nan=False,
).encode("utf-8")
```

Normative rules:

- object keys are sorted lexicographically;
- no insignificant whitespace is emitted;
- non-ASCII characters are escaped using JSON ASCII escaping;
- NaN and Infinity are rejected;
- the resulting JSON string is encoded as UTF-8 bytes;
- the final hash is lowercase SHA-256 hex.

---

## 5. Example

Input object:

```json
{
  "expires_at": 200,
  "address": "DGB1-ADDRESS",
  "issued_at": 100,
  "context_hash": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
}
```

Canonical byte string as UTF-8 text:

```json
{"address":"DGB1-ADDRESS","context_hash":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","expires_at":200,"issued_at":100}
```

Proof hash:

```text
00606241b78c5131af309f8db85cb431e159e36dd2902da966d3599b6f4d54e7
```

---

## 6. Security Boundary

The `proof_hash` is an integrity check over the Q-ID `response_payload` canonical bytes. It is not an authenticity proof by itself.

Production Q-ID v2 evidence still requires the real Q-ID authenticity verifier before AdamantineOS accepts it as session evidence. The verifier remains responsible for signature/key validation, login URI binding, service/callback binding, and signed payload validation.

AdamantineOS rejects malformed canonicalization inputs and proof-hash mismatches before the evidence can become accepted Q-ID session proof.

---

## 7. Compatibility Rule

The following changes are contract-affecting and must not be made silently:

- changing key ordering;
- changing JSON separators;
- changing ASCII escaping behavior;
- changing UTF-8 byte encoding;
- allowing NaN or Infinity;
- hashing a different object than `response_payload`;
- changing hash algorithm or hex casing;
- reusing the same profile name for incompatible behavior.

Any incompatible change requires a new profile name, updated tests, updated documentation, and a cross-repository compatibility review with DigiByte-Q-ID.
