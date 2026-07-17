# AI Gateway Policy-Bound Evidence V2 Consumer

Author attribution: **DarekDGB**  
License: MIT  
Consumer entry point: `consume_ai_gateway_policy_bound_evidence_v2`  
Evidence identifier: `adamantine_ai_gateway_evidence_v2`  
Canonical profile: `ai_gateway_canonical_json_v1`  
Status: V4.9-D3B independent AdamantineOS consumer boundary

## 1. Purpose

This contract defines how AdamantineOS consumes raw policy-bound evidence from
Adamantine AI Gateway. The consumer independently parses, canonicalizes, hashes,
and links the evidence. It does not import or trust Gateway runtime code.

The boundary can accept a valid artifact chain only as evidence for later
AdamantineOS checks. It cannot approve an operation, rescue a denial, authorize
execution, or replace the final AdamantineOS policy and execution boundary.

## 2. Security boundary

The following inputs are untrusted:

- every byte in the AI Gateway evidence document;
- every declared version, role, policy identity, digest, decision, and reason;
- every receipt, handoff, and policy-binding field; and
- any producer-side claim that the evidence is authentic, fresh, or safe.

The following inputs must come from verifier-controlled trusted local
configuration:

- `expected_context_hash`;
- expected PolicyPack ID;
- expected PolicyPack version ID; and
- expected complete PolicyPack hash.

The expected policy is represented by `AIGatewayExpectedPolicyV1`. It is a
Gateway policy identity commitment only. It is not AdamantineOS's unrelated
internal risk `PolicyPack`, and those two types and trust domains must not be
reused or treated as interchangeable.

The caller must supply:

```text
consume_ai_gateway_policy_bound_evidence_v2(
    raw_evidence: bytes,
    *,
    expected_context_hash: str,
    expected_policy: AIGatewayExpectedPolicyV1,
    prior_gate_results: Sequence[Any] | None = None,
)
```

`raw_evidence` must be exact bytes. An already decoded mapping is not accepted,
because it cannot prove that duplicate raw JSON keys were rejected.

## 3. Trusted expectation rules

Before untrusted evidence can continue:

- `expected_context_hash` must be an exact lowercase 64-character SHA-256 hex
  string;
- `expected_policy` must be the exact verifier-controlled
  `AIGatewayExpectedPolicyV1` type;
- `policy_pack_id` and `policy_pack_version_id` must be non-empty strings of at
  most 256 Unicode scalar values each; and
- `policy_pack_hash` must be an exact lowercase 64-character SHA-256 hex string.

Invalid trusted configuration fails closed as
`DENY_EXPECTED_POLICY_INVALID`. The consumer must never replace a missing or
invalid trusted expectation with a value declared by the evidence.

The V2 bundle does not include the source PolicyPack snapshot. AdamantineOS
therefore cannot recompute `policy_pack_hash` from the bundle. It compares the
declared hash with the independently controlled expected hash. That comparison
is meaningful only when the expected value is supplied through a trusted local
configuration boundary.

## 4. Earlier-denial dominance

Earlier gate denials are evaluated before trusted-expectation validation and
before any raw evidence parsing. If one or more prior gate results have
`outcome == "DENY"`:

- the result must be `DENY_EARLIER_GATE_DENIED`;
- all earlier denial reason IDs must remain in deterministic input order in
  `dominant_reason_ids`;
- malformed, duplicated, downgraded, or otherwise hostile AI Gateway bytes
  cannot replace or rescue those denials; and
- no earlier ALLOW-like result can upgrade a denial.

When supplied, `prior_gate_results` must be an exact list or tuple whose
members expose an `outcome` attribute or are exact dictionaries with an
`outcome` key. Mapping subclasses and attribute/key hybrid representations are
rejected so conflicting views cannot hide a denial. The outcome must be an
exact string equal to `DENY` or `ALLOW_EVIDENCE`; any other value fails closed.
A malformed container or member fails closed instead of being treated as an
empty set of earlier gates.

This ordering preserves replay, authentication, Shield, Q-ID, policy, and other
fail-closed gates that ran before this consumer. Failure while reading earlier
gate results itself fails closed as `DENY_INTERNAL_ERROR`.

## 5. Strict raw JSON boundary

The earliest parser for `raw_evidence` must:

- accept exact bytes only;
- reject input larger than 1,048,576 bytes;
- decode strict UTF-8;
- reject a UTF-8 BOM;
- consume exactly one JSON value;
- reject trailing data;
- reject malformed syntax and malformed escapes;
- reject lone surrogate code points;
- reject duplicate object keys at every nesting level after escape decoding;
- therefore treat `"a"` and `"\u0061"` as the same duplicate key;
- reject float, decimal, exponent, NaN, and infinity grammar; and
- enforce all governed resource limits before the value is accepted.

Default last-key-wins parsing is prohibited. Duplicate decoded keys fail as
`DENY_DUPLICATE_KEY`. Other malformed wire input fails as
`DENY_INVALID_WIRE`. Governed resource exhaustion fails as
`DENY_RESOURCE_LIMIT`.

## 6. Independent canonical JSON profile

AdamantineOS independently implements `ai_gateway_canonical_json_v1`. It must
not call the AI Gateway serializer or structured hash helper.

### 6.1 Supported values

The profile accepts only:

- JSON null;
- exact booleans;
- mathematical integers within the governed width;
- strings containing valid Unicode scalar values;
- exact arrays; and
- exact objects with unique string keys.

Floats, byte strings, tuples, sets, arbitrary host objects, container
subclasses, cycles, malformed Unicode, and non-string object keys fail closed.

### 6.2 Closed byte algorithm

Literals and integers:

- null is `null`;
- booleans are `false` and `true`;
- zero is `0`;
- integers use minimal base-10 ASCII;
- negative integers use one leading `-`; and
- plus signs, leading zeroes, decimal points, and exponents never appear in
  canonical output.

Raw JSON integer `-0` canonicalizes to `0`.

Strings begin and end with ASCII quotation marks. The encoder must:

- encode quotation mark as `\"`;
- encode reverse solidus as `\\`;
- use `\b`, `\t`, `\n`, `\f`, and `\r` for U+0008, U+0009, U+000A, U+000C,
  and U+000D;
- encode every other U+0000 through U+001F scalar as `\u` followed by exactly
  four lowercase hexadecimal digits; and
- emit every other valid Unicode scalar as raw UTF-8.

Solidus, U+007F, U+0080 through U+009F, U+2028, U+2029, BMP scalars, and
astral scalars remain raw UTF-8. No Unicode normalization is applied. NFC and
NFD spellings remain distinct.

Arrays preserve input order, use commas without whitespace, and are enclosed
by `[` and `]`.

Object keys are sorted lexicographically by Unicode scalar-value sequence. A
shorter prefix sorts before the longer key. Each key and value is encoded with
the same closed algorithm. Members use `:` and `,` without whitespace and are
enclosed by `{` and `}`.

The complete output is one UTF-8 byte sequence with no BOM, leading or trailing
whitespace, or trailing newline.

### 6.3 Hash operation

Receipt and handoff digests are:

```text
lowercase_hex(SHA-256(ai_gateway_canonical_json_v1_bytes(artifact)))
```

The algorithm and profile are contract-fixed. There is no caller-selectable
hash algorithm, canonical profile, or per-artifact domain prefix in this
version. A different algorithm, profile, or prefix requires a new contract.

### 6.4 Governed limits

| Resource | Maximum |
|---|---:|
| Raw JSON input | 1,048,576 bytes |
| Container depth, root at zero | 10 |
| Keys in one object | 1,000 |
| Items in one array | 1,000 |
| One string or object key | 10,000 Unicode scalar values |
| Absolute integer width | 4,096 bits |
| Value nodes, including root | 20,000 |
| Cumulative string/key UTF-8 and integer-text preflight | 1,048,576 bytes |
| Canonical value output | 1,048,576 bytes |
| Canonical policy-binding artifact | 4,096 bytes |

Object keys are not nodes. Repeated container aliases are counted at each
occurrence, while an active cycle is rejected. Integer width is
`bit_length(abs(value))`; zero has width zero. The 10,000-character limit is a
Unicode scalar-value count, not UTF-8 bytes, UTF-16 units, graphemes, or display
width.

The preflight byte budget includes UTF-8 bytes for every string and key and the
minimal decimal text for every integer occurrence. Structural punctuation,
quotes, escape expansion, booleans, and null count only toward the final
canonical byte limit.

## 7. Exact V2 evidence shape

The top-level value must be an exact object with exactly these seven fields:

| Field | Required value or rule |
|---|---|
| `evidence_version` | Exact `adamantine_ai_gateway_evidence_v2` |
| `source` | Exact `adamantine-ai-gateway` |
| `evidence_role` | Exact `evidence_only` |
| `expected_context_hash` | Exact trusted expected context hash |
| `handoff` | Exact handoff object from section 8 |
| `receipt` | Exact receipt object from section 9 |
| `policy_binding` | Exact binding object from section 10 |

Unknown or missing fields fail closed. Every key is case-sensitive.

Authority-bearing field names are forbidden recursively at every depth:

```text
allow
approve
approved
authority
authorization
bypass
final_approval
grant_execution
handoff_allowed
override
```

The presence of one of these fields fails as
`DENY_HIDDEN_AUTHORITY_FIELD`, regardless of its value.

## 8. Exact handoff shape

`handoff` must contain exactly:

```text
handoff_version
adapter
task_type
policy_decision
reason_id
envelope_hash
output_hash
context_hash
```

Rules:

- `handoff_version` must equal `ai_gateway_handoff_v1`;
- `adapter` and `task_type` must be non-empty strings;
- `envelope_hash`, `output_hash`, and `context_hash` must be lowercase
  64-character SHA-256 hex strings;
- `context_hash` must equal the verifier-controlled expected context hash;
- `context_hash` must equal `envelope_hash`; and
- decision and reason semantics must satisfy section 11.

## 9. Exact receipt shape

`receipt` must contain exactly:

```text
receipt_version
gateway_version
adapter_id
adapter_version
envelope_hash
output_hash
policy_decision
reason_id
created_from_contract
determinism_profile
```

Rules:

- `receipt_version` must equal `ai_gateway_receipt_v1`;
- `created_from_contract` must equal `ai_gateway_output_v1`;
- `determinism_profile` must equal `canonical_sha256_no_time_v1`;
- `gateway_version`, `adapter_id`, and `adapter_version` must be non-empty
  strings;
- `envelope_hash` and `output_hash` must be lowercase 64-character SHA-256 hex
  strings; and
- decision and reason semantics must satisfy section 11.

Any algorithm or profile confusion is a version mismatch and fails closed. The
receipt profile is not caller selectable.

## 10. Exact policy-binding shape

`policy_binding` must contain exactly:

```text
policy_binding_version
policy_pack_contract_version
policy_pack_id
policy_pack_version_id
policy_pack_hash
receipt_hash
handoff_hash
```

Rules:

- `policy_binding_version` must equal `ai_gateway_policy_binding_v1`;
- `policy_pack_contract_version` must equal `policy_pack_v1`;
- `policy_pack_id` and `policy_pack_version_id` must be non-empty strings of at
  most 256 Unicode scalar values;
- `policy_pack_hash`, `receipt_hash`, and `handoff_hash` must be lowercase
  64-character SHA-256 hex strings; and
- the canonical binding must not exceed 4,096 bytes.

Under the current exact shape and the two 256-scalar ID ceilings, the largest
valid binding is 2,451 bytes when both IDs contain only four-byte UTF-8
scalars. The 4,096-byte check is a forward defensive ceiling; current field
limits dominate it. Tests lock the reachable 2,451-byte maximum and exercise
the defensive failure branch with an injected lower ceiling.

On this policy-bound path, a missing or null binding fails as
`DENY_MISSING_POLICY_BINDING`. It must never be treated as unbound V1 evidence.

## 11. Decision and reason semantics

`policy_decision` must be exactly `accepted` or `rejected`.

An accepted decision must use reason `ACCEPTED`.

A rejected decision must use one of these registered Gateway reasons:

```text
ADAPTER_NOT_REGISTERED
ADAPTER_VALIDATION_FAILED
CANONICALIZATION_FAILED
HASHING_FAILED
INTERNAL_ERROR
INVALID_ENVELOPE
INVALID_OUTPUT
MISSING_REQUIRED_FIELD
NON_DETERMINISTIC_OUTPUT
POLICY_DENIED
SCHEMA_VIOLATION
UNSUPPORTED_MODEL
UNSUPPORTED_TASK
```

The handoff and receipt must carry the same decision and the same reason. A
valid, fully linked upstream rejection remains a denial. It returns
`DENY_AI_GATEWAY_REJECTED`; it cannot be rescued by a valid policy binding.

## 12. Artifact-chain verification

After exact-shape validation, AdamantineOS must independently verify all of the
following:

1. Evidence context equals the trusted expected context.
2. Handoff context equals both the trusted expected context and handoff
   envelope hash.
3. Receipt `adapter_id` equals handoff `adapter`.
4. Receipt and handoff envelope hashes are identical.
5. Receipt and handoff output hashes are identical.
6. Receipt and handoff decisions are identical.
7. Receipt and handoff reason IDs are identical.
8. Binding `receipt_hash` equals independently computed canonical SHA-256 of
   the complete validated receipt object.
9. Binding `handoff_hash` equals independently computed canonical SHA-256 of
   the complete validated handoff object.
10. Binding policy ID equals the trusted expected policy ID.
11. Binding policy version ID equals the trusted expected policy version ID.
12. Binding policy hash equals the trusted expected complete policy hash.

A policy substitution, receipt splice, handoff splice, context splice,
decision splice, reason splice, version downgrade, or digest mutation must
deny. A structurally valid but semantically mismatched chain is not partial
success.

The V2 bundle does not include the source envelope, output, or PolicyPack
snapshot. This consumer verifies linkage among the supplied commitments and
trusted expectations; it does not independently reconstruct those three
omitted source artifacts.

## 13. No V1 fallback

The existing V1 AI Gateway evidence consumer is a separate legacy boundary.
The V2 policy-bound consumer must not:

- call the V1 normalizer as a fallback;
- remove, ignore, or default a missing binding;
- accept `adamantine_ai_gateway_evidence_v1` on this entry point;
- reinterpret a V1 receipt and handoff pair as policy-bound evidence; or
- silently drop unknown binding fields.

An unsupported evidence version fails as `DENY_VERSION_MISMATCH`. A missing or
null binding fails as `DENY_MISSING_POLICY_BINDING`. No V1 outcome can rescue
either failure.

## 14. Consumer result contract

Every result has these fields:

```text
source
state
outcome
reason_id
accepted_as_evidence
final_approval
policy_binding_verified
context_hash
policy_pack_id
policy_pack_version_id
policy_pack_hash
receipt_hash
handoff_hash
dominant_reason_ids
```

For a fully valid accepted chain:

```text
source = ai_gateway
state = ALLOW_EVIDENCE_CONTINUE_CHECKS
outcome = ALLOW_EVIDENCE
accepted_as_evidence = true
final_approval = false
policy_binding_verified = true
```

`ALLOW_EVIDENCE` means only that later AdamantineOS checks may continue. It is
not `ALLOW`, approval, or permission to execute.

For every denial:

```text
outcome = DENY
accepted_as_evidence = false
final_approval = false
```

A valid upstream rejected chain may report verified binding metadata while
remaining denied. All malformed, mismatched, unsupported, or internal-error
paths fail closed and do not produce final approval.

## 15. Stable consumer states

These state identifiers are part of the D3B integration surface:

| State | Meaning |
|---|---|
| `ALLOW_EVIDENCE_CONTINUE_CHECKS` | Valid evidence may continue later checks; never final approval |
| `DENY_EARLIER_GATE_DENIED` | One or more earlier denials remain dominant |
| `DENY_EXPECTED_POLICY_INVALID` | Trusted expected context or policy configuration is invalid |
| `DENY_UNSUPPORTED_INPUT` | Raw evidence is not exact bytes |
| `DENY_INVALID_WIRE` | Raw JSON or UTF-8 is malformed or prohibited |
| `DENY_DUPLICATE_KEY` | A duplicate decoded JSON key was found |
| `DENY_RESOURCE_LIMIT` | A governed resource ceiling was exceeded |
| `DENY_SCHEMA_INVALID` | Required shape or value semantics are invalid |
| `DENY_UNKNOWN_FIELD` | An exact object contains an unknown field |
| `DENY_VERSION_MISMATCH` | Evidence, artifact, contract, or fixed profile version is unsupported |
| `DENY_MISSING_POLICY_BINDING` | Required V2 binding is absent or null |
| `DENY_HIDDEN_AUTHORITY_FIELD` | A forbidden authority-bearing field or role was found |
| `DENY_CONTEXT_HASH_MISMATCH` | Trusted context and artifact linkage do not match |
| `DENY_RECEIPT_MISMATCH` | Receipt and handoff semantics do not match |
| `DENY_BINDING_HASH_MISMATCH` | Recomputed receipt or handoff digest does not match the binding |
| `DENY_POLICY_ID_MISMATCH` | Bound policy ID differs from trusted configuration |
| `DENY_POLICY_VERSION_MISMATCH` | Bound policy version differs from trusted configuration |
| `DENY_POLICY_HASH_MISMATCH` | Bound complete policy hash differs from trusted configuration |
| `DENY_AI_GATEWAY_REJECTED` | A valid linked Gateway rejection remains a denial |
| `DENY_INTERNAL_ERROR` | An unexpected dependency or internal failure failed closed |

State strings must remain deterministic. Changing their meaning or removing a
state requires a new consumer contract version.

## 16. Trust-domain separation

This consumer must keep these domains separate:

- AI Gateway policy identity commitments;
- AdamantineOS internal risk policy;
- Q-ID identity and authentication evidence;
- Shield decision evidence and verifier keys; and
- execution authority.

Q-ID identity keys must not authenticate, sign, or authorize AI Gateway
policy-bound evidence. Shield decision-evidence keys must not authenticate,
sign, or authorize it either. AI Gateway policy IDs and hashes must not be used
as Q-ID identity or Shield key-role identifiers.

No Q-ID key, Shield key, AdamantineOS internal PolicyPack key, or policy object
may be reused to manufacture trust in the Gateway bundle. Each separate
boundary must perform its own contract-defined verification.

## 17. Security and authority limits

Successful D3B consumption proves only that:

- the raw JSON passed the fixed strict parser and governed limits;
- the supplied receipt and handoff reproduce the binding's content hashes;
- their declared context, decision, reason, and linkage are internally
  coherent; and
- the declared policy identity equals verifier-controlled expected values.

It does not provide or prove:

- producer authentication;
- source provenance or remote attestation;
- a digital signature;
- freshness or replay protection;
- honest execution;
- possession or enforcement of the declared policy snapshot;
- transaction signing;
- transaction broadcast;
- a DigiByte consensus change;
- policy override, downgrade, bypass, or rescue authority; or
- final execution authority.

Replay and freshness remain responsibilities of the appropriate earlier
trusted gates. Transport authentication or a future signature layer must be a
separate contract. A canonical hash is deterministic content identity, not
authentication.

Shield v4 does not sign transactions, broadcast, or change DigiByte consensus.
Shield evidence remains verify-only at AdamantineOS, and AdamantineOS remains
the authoritative fail-closed policy and execution boundary.

## 18. Frozen external baseline fixtures

The D3B tests copy and pin these external Gateway baseline files:

| Fixture | SHA-256 |
|---|---|
| `tests/fixtures/ai_gateway_external_baseline/ai_gateway_adamantine_evidence_v2.json` | `deaa523cd28a1f8d2a97dbf681bfbc94ee7b682aa62d5c3c5747fbe244e13843` |
| `tests/fixtures/ai_gateway_external_baseline/ai_gateway_canonical_json_v1_vectors.json` | `b14b240cd3f0bd5c9c8e7a55698a92609bcbf5ebb19dfe913514dad8802b4733` |

The canonical fixture carries a portable ordered `required_vector_ids`
inventory. Its exact vector counts are:

| Section | Count |
|---|---:|
| Golden vectors | 24 |
| Equivalence pairs | 8 |
| Injective pairs | 10 |
| Rejected-wire vectors | 17 |
| Boundary vectors | 17 |
| Total IDs | 76 |

Tests must verify each complete fixture hash before using the file, must require
the exact ordered portable inventory, and must reject missing, extra,
duplicated, truncated, or reordered vector IDs. Expected canonical bytes and
hashes remain literal fixture data and must not be regenerated from this
consumer at test time.

## 19. Required conformance and security matrix

| Area | Required evidence |
|---|---|
| Accepted baseline | Frozen V2 fixture accepts only as `ALLOW_EVIDENCE`, with verified linkage and `final_approval == false` |
| Valid Gateway rejection | Coherent rejected chain remains `DENY_AI_GATEWAY_REJECTED`; a valid binding cannot rescue it |
| Independent bytes | Every golden, equivalence, injective, rejected-wire, and boundary vector is enforced without importing Gateway code |
| Portable inventory | Both fixture hashes, exact 76-ID order, section counts, and literal expected data are pinned |
| Duplicate keys | Top-level, nested, and escape-equivalent duplicate keys deny before mapping construction |
| Wire grammar | BOM, invalid UTF-8, trailing values, malformed escapes, lone surrogates, floats, exponents, NaN, and infinities deny |
| Resource limits | Exact accepted and rejected fixture boundaries for depth, collection size, scalar length, integer width, node count, and canonical bytes; exact raw-byte ceiling acceptance plus over-limit raw/preflight enforcement; reachable binding maximum plus defensive-cap injection |
| Exact shapes | Missing and unknown fields at top level and in every nested artifact deny deterministically |
| Version/profile confusion | Wrong evidence, handoff, receipt, output-contract, binding, PolicyPack-contract, or determinism-profile identifier denies |
| Downgrade | V1 evidence, missing binding, and null binding deny with no V1 fallback |
| Context substitution | Evidence, handoff, expected context, and envelope-hash mismatches deny |
| Receipt splice | Adapter, envelope, output, decision, and reason mismatches deny |
| Binding splice | Independently recomputed receipt and handoff hashes must match the binding |
| Policy substitution | Policy ID, version ID, and complete hash are compared separately with trusted expectations |
| Reason semantics | Accepted requires `ACCEPTED`; rejected requires a registered Gateway denial reason |
| Authority injection | Every recursively forbidden authority field and a non-evidence role denies |
| Earlier denial | Replay and every other earlier DENY remain dominant even when Gateway bytes are otherwise valid or malformed |
| Dependency exceptions | Parser, canonicalizer, hashing, prior-result access, and unexpected backend exceptions fail closed without leaking exception text |
| Result authority | Every result has `final_approval == false`; only the final AdamantineOS boundary can authorize execution |
| Domain separation | Tests lock non-reuse of V1 fallback, Q-ID canonicalization/keys, Shield keys, and internal risk PolicyPack |

Every negative case must assert the stable state, `outcome == "DENY"`,
`accepted_as_evidence == false`, and `final_approval == false`. Tests passing
only by comparing one Python serializer with itself are insufficient.

## 20. Change control

This contract is exact and deny-by-default. Any change to:

- raw parser acceptance;
- canonical bytes or key order;
- resource accounting;
- evidence, handoff, receipt, or binding fields;
- fixed algorithm or profile identifiers;
- trusted expectation semantics;
- stable result states;
- failure ordering;
- V1 fallback policy; or
- authority limits

requires explicit review, negative-first tests, fixture impact analysis, and a
new version when compatibility would change.

No compatibility claim for a non-Python consumer is permitted until an
independent implementation passes the frozen literal vectors and byte-first
differential fuzzing. Default serializer parity is not sufficient.

---

MIT - DarekDGB
