# AdamantineOS Shield Runtime Boundary Lock

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Scope: post-v3.0.0 hardening step `AOS-M-002A`  
Ledger status: **no build ledger update for this post-v3.0.0 hardening phase**

---

## 1. Decision

AdamantineOS production Shield evidence must enter the v2 runtime through the **Shield Orchestrator v3.2 receipt boundary**.

The selected production boundary is:

```text
ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2
```

This means `payload.evidence.shield` must be a Shield Orchestrator receipt with:

```text
schema_version = shield.receipt.v1
contract_version = 3
component_verdicts = strict Shield v3.2 component verdicts
final_approval = never granted by Shield
```

Shield remains **evidence only**. AdamantineOS final approval can only happen after the final policy engine evaluates Shield, WSQK v2, Q-ID, Adaptive Core, AI Gateway, replay, wallet policy, and human confirmation gates.

---

## 2. Legacy bundle status

The old Shield bundle boundary is explicitly named:

```text
ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY
```

This mode exists only to keep pre-hardening compatibility tests and old local fixtures deterministic while the receipt-only runtime route is wired in `AOS-M-002B`.

It must not be described as the production Shield handoff boundary.

---

## 3. AOS-M-002A runtime behavior

When `ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2` is selected:

1. Bundle-shaped Shield evidence is rejected at the Shield runtime boundary.
2. Raw component verdicts are rejected by the receipt verifier.
3. A valid Shield Orchestrator v3.2 receipt can be normalized as accepted Shield evidence only.
4. Receipt acceptance does not become final approval.
5. Until `AOS-M-002B` wires the full continuation route, a verified receipt-only path fails closed after proving evidence acceptance.

This deliberate fail-closed transition prevents integrators from mistaking Shield receipt acceptance for AdamantineOS execution approval.

---

## 4. Step 5 requirement

`AOS-M-002B` must wire the primary v2 runtime continuation path so a valid Shield Orchestrator v3.2 receipt can feed the normal final policy order without reverting to the legacy bundle parser.

The required order remains:

```text
Shield -> WSQK v2 -> Q-ID -> Adaptive Core -> AI Gateway -> replay -> wallet policy -> human -> final AdamantineOS decision
```

No external Shield output may skip replay, wallet policy, human confirmation, or the final AdamantineOS decision gate.

---

## 5. Regression lock

The Step 4 regression tests must prove:

```text
- receipt-only mode rejects legacy bundle-shaped evidence
- receipt-only mode accepts a valid receipt only as evidence
- receipt-only mode never grants final approval from Shield
- legacy bundle mode is explicitly named test-only
```
