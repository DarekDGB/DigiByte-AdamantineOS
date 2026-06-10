# AdamantineOS Milestone 16E - Adaptive Core External Baseline Compatibility

Author attribution: **DarekDGB**  
Repository: `DigiByte-Adamantine-Wallet-OS`  
External baseline repository: `DigiByte-Adaptive-Core`  
Status: Milestone 16E compatibility harness  
AdamantineOS version boundary: `v2.2.0` remains unchanged  
Adaptive Core baseline: `v3.0.0` remains the external baseline  
Tag status: no AdamantineOS tag yet

---

## 1. Purpose

Milestone 16E proves that Adaptive Core can participate in the Level 4 integration as advisory evidence only.

This milestone follows the two-sided external adapter / handoff completion rule added to the build ledger before 16E.

Milestone 16E verifies both sides of the Adaptive Core connection:

```text
DigiByte-Adaptive-Core AdamantineOS-facing advisory evidence exporter
        v
AdamantineOS Adaptive Core policy evidence boundary
        v
AdamantineOS final policy engine
```

Adaptive Core does not approve execution.

Adaptive Core does not sign.

Adaptive Core does not override Shield, WSQK, Q-ID, AI Gateway, replay, wallet-policy, or human-gate decisions.

Adaptive Core remains advisory evidence only.

---

## 2. Scope

### Repository modified in AdamantineOS

```text
DigiByte-Adamantine-Wallet-OS
```

### External repository gap identified and patched separately

Inspection found that `DigiByte-Adaptive-Core` had strong v3 advisory/oracle/report surfaces, but did not yet have a clearly named AdamantineOS-facing exporter equivalent to the existing Q-ID AdamantineOS evidence builder.

This was a two-sided connection gap under the ledger rule.

The smallest safe external patch is:

```text
src/adaptive_core/v3/integration/__init__.py
src/adaptive_core/v3/integration/adamantine.py
tests/test_v3_integration_adamantine.py
```

The external patch exports an AdamantineOS-consumable `adaptive_core_oracle_v3` advisory evidence object.

It does not create execution authority.

It does not add final approval.

It does not change Adaptive Core version.

It does not tag Adaptive Core.

---

## 3. Accepted Adaptive Core surface

Milestone 16E accepts the following evidence shape:

```text
ac_iface_version = adaptive_core_oracle_v3
```

Required fields:

```text
context_hash
issued_at
expires_at
generated_at
overall_score
signals
oracle_version
external_source_id
```

The accepted shape is intentionally compatible with the existing AdamantineOS Adaptive Core oracle v3 adapter and policy evidence boundary.

---

## 4. Forbidden Adaptive Core authority

Adaptive Core evidence must reject or fail closed if it attempts to carry authority fields such as:

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

Adaptive Core evidence success means:

```text
ALLOW_EVIDENCE_CONTINUE_CHECKS
```

It does not mean:

```text
FINAL_ALLOW_CONTINUE_TO_SIGNING_FLOW
```

---

## 5. AdamantineOS files added

```text
tests/fixtures/adaptive_core_external_baseline/adaptive_core_adamantine_advisory_evidence_v1.json
tests/integrations/test_milestone_16e_adaptive_core_external_baseline_compatibility.py
docs/ADAMANTINEOS_MILESTONE_16E_ADAPTIVE_CORE_EXTERNAL_BASELINE_COMPATIBILITY.md
docs/ADAMANTINEOS_FULL_INTEGRATION_BUILD_LEDGER.md
```

No AdamantineOS production adapter was duplicated.

The existing AdamantineOS Adaptive Core receiving side remains authoritative:

```text
src/adamantine/v1/integrations/adaptive_core_adapter.py
src/adamantine/v1/integrations/adaptive_core_oracle_v3_adapter.py
src/adamantine/v1/integrations/adaptive_core_policy_evidence.py
```

---

## 6. Locked Milestone 16E behavior

Milestone 16E locks the following behavior:

```text
External Adaptive Core AdamantineOS advisory evidence parses through the existing AdamantineOS Adaptive Core boundary.
External Adaptive Core evidence enters the policy engine as evidence only.
Adaptive Core success returns ALLOW_EVIDENCE_CONTINUE_CHECKS, not final approval.
Adaptive Core evidence alone cannot become final authority.
Hidden authority fields fail closed.
Context mismatch fails closed.
Low score fails closed.
Earlier gate DENY dominates Adaptive Core success.
External import-failure-shaped payload cannot become allow.
Missing or unknown external fields fail closed.
```

---

## 7. External connection proof status

| Connection point | Status |
|---|---|
| Adaptive Core external AdamantineOS-facing exporter | Added in `DigiByte-Adaptive-Core` smallest safe patch |
| AdamantineOS Adaptive Core receiver | Already present |
| AdamantineOS compatibility fixture | Added |
| AdamantineOS compatibility tests | Added |
| External authority bypass | Rejected |
| Final approval from Adaptive Core | Forbidden |

---

## 8. Verification commands

AdamantineOS verification:

```text
PYTHONPATH=src pytest -q
```

Expected AdamantineOS result:

```text
Full suite passes.
Required coverage remains 100%.
AdamantineOS remains v2.2.0.
No AdamantineOS tag is created.
```

Adaptive Core verification:

```text
PYTHONPATH=src pytest -q
```

Expected Adaptive Core result:

```text
Full suite passes.
Required coverage remains 100%.
Adaptive Core remains v3.0.0.
No Adaptive Core tag is created.
```

---

## 9. Milestone 16E completion rule

Milestone 16E is complete only when:

```text
[x] Adaptive Core external AdamantineOS-facing advisory evidence exporter exists
[x] AdamantineOS Adaptive Core receiver remains the single receiving boundary
[x] Adaptive Core evidence remains advisory only
[x] Adaptive Core cannot become final authority
[x] AdamantineOS tests pass
[x] Adaptive Core tests pass
[x] Both repositories maintain 100% coverage
[x] No version bump
[x] No tag
[x] Ledger updated
```

---

## 10. Next safe milestone

After Milestone 16E, the next scoped step is:

```text
Milestone 16F - AI Gateway External Baseline Compatibility
```

Milestone 16F must apply the same two-sided rule:

```text
AI Gateway external AdamantineOS-facing evidence / handoff surface
        v
AdamantineOS AI Gateway policy evidence boundary
        v
AdamantineOS final policy engine
```

AI Gateway output must remain evidence only and must never become execution authority.
