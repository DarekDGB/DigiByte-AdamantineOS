# AdamantineOS Shield Runtime Boundary Lock

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Scope: post-v3.0.0 hardening steps `AOS-M-002A` and `AOS-M-002B`  
Ledger status: **no build ledger update for this post-v3.0.0 hardening phase**

---

## 1. Decision

AdamantineOS production Shield evidence must enter the v2 runtime through the **Shield Orchestrator v3.2 receipt boundary**.

The selected production boundary is:

```text
ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2
```

As of the `AOS-RT-002` post-v3.0.0 hardening fix, this is also the default selected by plain `RiskPolicy()`. Production callers no longer receive the legacy bundle route unless they explicitly request the test-only boundary.

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

This mode exists only to keep pre-hardening compatibility tests and old local fixtures deterministic. It is not the default and must be selected explicitly with `shield_runtime_boundary=ShieldRuntimeBoundary.LEGACY_BUNDLE_V3_TEST_ONLY`.

It must not be described as the production Shield handoff boundary, and integrators must not construct production execution policies that rely on this legacy bundle route.

---

## 3. AOS-M-002A runtime behavior

When `ShieldRuntimeBoundary.ORCHESTRATOR_RECEIPT_V3_2` is selected:

1. Bundle-shaped Shield evidence is rejected at the Shield runtime boundary.
2. Raw component verdicts are rejected by the receipt verifier.
3. A valid Shield Orchestrator v3.2 receipt is normalized as accepted Shield evidence only.
4. Receipt acceptance does not become final approval.
5. Hidden Shield authority cannot skip AdamantineOS replay, wallet policy, human confirmation, or final policy gates.

This lock prevents integrators from mistaking Shield receipt acceptance for AdamantineOS execution approval.

---

## 4. AOS-M-002B runtime continuation route

`AOS-M-002B` wires the primary v2 runtime continuation path so a valid Shield Orchestrator v3.2 receipt can feed the normal final policy order without reverting to the legacy bundle parser.

The runtime route status for this path is:

```text
receipt_verified_runtime_route_wired
```

The required order remains:

```text
Shield -> WSQK v2 -> Q-ID -> Adaptive Core -> AI Gateway -> replay -> wallet policy -> human -> final AdamantineOS decision
```

No external Shield output may skip replay, wallet policy, human confirmation, or the final AdamantineOS decision gate.

---

## 5. Regression lock

The Step 4 and Step 5 regression tests must prove:

```text
- receipt-only mode rejects legacy bundle-shaped evidence
- receipt-only mode accepts a valid receipt only as evidence
- receipt-only mode never grants final approval from Shield
- verified receipt evidence can continue to WSQK, EQC, TVA, human, and final policy gates
- verified receipt evidence does not call the legacy Shield bundle parser in receipt-only mode
- legacy bundle mode is explicitly named test-only
- plain RiskPolicy() selects ORCHESTRATOR_RECEIPT_V3_2
- RiskPolicy(policy_pack=...) without an explicit boundary still rejects legacy bundle-shaped Shield evidence
```
