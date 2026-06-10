# AdamantineOS Milestone 16F - AI Gateway External Baseline Compatibility

Author attribution: **DarekDGB**  
Repository: `DigiByte-Adamantine-Wallet-OS`  
External repository: `adamantine-ai-gateway`  
Status: Milestone 16F scoped compatibility harness  
AdamantineOS version boundary: `v2.2.0` remains unchanged  
AI Gateway version boundary: `v1.0.0` remains unchanged  
Tag status: no AdamantineOS tag

---

## 1. Purpose

Milestone 16F proves the two-sided AI Gateway connection required by the build ledger.

It verifies that external `adamantine-ai-gateway` can produce AdamantineOS-consumable handoff / receipt evidence and that AdamantineOS consumes that evidence through its existing AI Gateway policy evidence boundary.

This milestone does not make AI Gateway an authority source.

AI Gateway remains evidence only.

AdamantineOS remains the final fail-closed execution boundary.

---

## 2. Scope

Repositories touched:

```text
DigiByte-Adamantine-Wallet-OS
adamantine-ai-gateway
```

External-side change:

```text
adamantine-ai-gateway adds a smallest safe AdamantineOS-facing evidence exporter.
```

AdamantineOS-side change:

```text
AdamantineOS adds a scoped Milestone 16F compatibility fixture, test harness, and ledger update.
```

No Shield component repositories are touched.
No Q-ID repository changes are made.
No Adaptive Core repository changes are made.
No version bump is made.
No tag is created.

---

## 3. Accepted external surface

The accepted AI Gateway external surface is:

```text
ai_gateway.integration.adamantine.build_adamantine_ai_gateway_evidence_v1(...)
ai_gateway.integration.adamantine.build_adamantine_ai_gateway_evidence_from_gateway_result_v1(...)
```

The exported evidence bundle contains:

```text
evidence_version
source
evidence_role
expected_context_hash
handoff
receipt
```

The `handoff` and `receipt` are then consumed by:

```text
adamantine.v1.integrations.ai_gateway_policy_evidence.normalize_ai_gateway_policy_evidence(...)
```

---

## 4. Rejected surfaces

Milestone 16F rejects:

```text
raw AI output as authority
missing handoff
missing receipt
context hash mismatch
receipt / handoff mismatch
hidden final approval fields
AI Gateway approval promoted to AdamantineOS final approval
```

AI Gateway can return evidence that continues checks, but it cannot approve signing or execution.

---

## 5. Locked behavior

```text
External AI Gateway AdamantineOS evidence accepts as evidence only.
AI Gateway accepted decision maps to ALLOW_EVIDENCE_CONTINUE_CHECKS, not final approval.
AI Gateway rejected decision denies.
Context hash mismatch denies.
Receipt mismatch denies.
Raw AI output bypass denies.
Hidden authority fields deny.
AdamantineOS remains final fail-closed authority.
```

---

## 6. Files added or updated

AdamantineOS:

```text
docs/ADAMANTINEOS_MILESTONE_16F_AI_GATEWAY_EXTERNAL_BASELINE_COMPATIBILITY.md
docs/ADAMANTINEOS_FULL_INTEGRATION_BUILD_LEDGER.md
tests/fixtures/ai_gateway_external_baseline/ai_gateway_adamantine_evidence_v1.json
tests/integrations/test_milestone_16f_ai_gateway_external_baseline_compatibility.py
```

AI Gateway:

```text
ai_gateway/integration/__init__.py
ai_gateway/integration/adamantine.py
tests/fixtures/adamantine/ai_gateway_adamantine_evidence_v1.json
tests/test_integration_adamantine.py
docs/reports/v1/ADAMANTINEOS_INTEGRATION.md
```

---

## 7. Exit criteria

```text
[x] External AI Gateway AdamantineOS-facing evidence exporter exists.
[x] AdamantineOS AI Gateway receiver exists.
[x] Shared fixture vector proves two-sided compatibility.
[x] AI Gateway remains evidence only.
[x] Raw AI output rejects.
[x] Hidden authority fields reject.
[x] AdamantineOS version remains v2.2.0.
[x] AI Gateway version remains v1.0.0.
[x] No tag is created.
```

Milestone 16F is complete only after both repositories pass their test suites with required coverage.
