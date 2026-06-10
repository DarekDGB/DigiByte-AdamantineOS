# AdamantineOS Milestone 16G - Full Level 4 Negative-Test Matrix

Author attribution: **DarekDGB**  
Repository: `DigiByte-Adamantine-Wallet-OS`  
Status: Milestone 16G complete  
AdamantineOS version boundary: `v2.2.0` remains unchanged  
Tag status: no AdamantineOS tag created  

---

## 1. Purpose

Milestone 16G completes the Level 4 integration sub-phase by attacking the full connected evidence order.

Previous Milestone 16 work locked each evidence boundary individually:

```text
16B - Shield Orchestrator receipt contract harness
16C - Shield component baseline compatibility through Orchestrator only
16D - Q-ID external baseline compatibility
16E - Adaptive Core external baseline compatibility
16F - AI Gateway external baseline compatibility
```

Milestone 16G proves those connected evidence paths fail closed together through the final AdamantineOS policy engine.

This milestone does not add a new external adapter.

It tests the full local decision order:

```text
1. Shield receipt gate
2. WSQK v2 gate
3. Q-ID gate
4. Adaptive Core gate
5. AI Gateway gate
6. replay / nonce gate
7. wallet policy gate
8. human gate
9. final AdamantineOS decision
```

---

## 2. Repository scope

Repository modified:

```text
DigiByte-Adamantine-Wallet-OS
```

External repositories were not modified by Milestone 16G.

The external evidence paths were already connected or hardened by earlier sub-phases:

```text
Shield Orchestrator and Shield components through Orchestrator only: complete and hardened
Q-ID external evidence: complete
Adaptive Core external advisory evidence: complete and hardened
AI Gateway external evidence: complete
```

---

## 3. 16G hardening found and fixed

The 16G negative matrix identified one final-engine hardening gap:

```text
A normalized-looking evidence object could carry extra authority-shaped fields such as:

sign=True
broadcast=True
grant_execution=True
metadata={"override": True}
metadata={"nested": {"trusted": True}}
```

Earlier adapter boundaries already reject these patterns, but Milestone 16G locks an additional final fail-closed guard inside the final policy engine.

The final policy engine now rejects hidden authority signals before accepting evidence as eligible to continue.

---

## 4. Locked 16G behavior

Milestone 16G locks the following behavior:

```text
Missing required evidence fails closed at the correct evidence gate.
DENY dominates in the locked evidence order.
HUMAN_REVIEW_REQUIRED from any evidence source never becomes autonomous allow.
Replay / nonce DENY blocks final approval after all evidence allows.
Wallet policy DENY blocks final approval after replay passes.
Human gate DENY blocks final approval.
Human review required at a local gate never becomes autonomous allow.
Upstream final_approval attempts fail closed.
Hidden signing / execution / override authority fields fail closed at the final policy engine.
Evidence with handoff_allowed=False fails closed before local gates.
Invalid local gate shape cannot be reused as human approval.
External dependency failure-shaped evidence cannot become allow.
All evidence ALLOW still requires replay, wallet-policy, and human gates before final approval.
```

---

## 5. Files added or updated

```text
src/adamantine/v1/policy/final_policy_engine.py
tests/integrations/test_milestone_16g_full_level4_negative_matrix.py
docs/ADAMANTINEOS_MILESTONE_16G_FULL_LEVEL4_NEGATIVE_TEST_MATRIX.md
docs/ADAMANTINEOS_FULL_INTEGRATION_BUILD_LEDGER.md
```

---

## 6. Verification

Milestone 16G verification target:

```text
PYTHONPATH=src pytest tests/integrations/test_milestone_16g_full_level4_negative_matrix.py -q --no-cov
PYTHONPATH=src pytest -q
```

Verified result:

```text
16G targeted negative matrix: passed
Full suite: passed
Required coverage: 100.00%
AdamantineOS version: v2.2.0 unchanged
AdamantineOS tag: not created
```

---

## 7. Release status

Milestone 16G completes Milestone 16 Level 4 integration matrix work.

It does not authorize release or tagging.

Remaining build-strategy milestones:

```text
17 - Proof pack and docs alignment
18 - Authorized red-team review
19 - Final release gate
```

AdamantineOS must remain untagged until all later release gates pass.

