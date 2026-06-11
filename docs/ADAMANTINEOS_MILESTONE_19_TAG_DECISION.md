# DigiByte AdamantineOS Milestone 19 — Tag Decision

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Public project name: **DigiByte AdamantineOS**  
Current package version: `v2.2.0`  
Candidate tag: `v3.0.0`  
Decision status: **approved after final copied-repo verification**

---

## 1. Purpose

This document records the Milestone 19 tag decision boundary.

It does not create a tag. It records the verified decision boundary for approving the `v3.0.0` tag after final copied-repo verification.

---

## 2. Candidate tag

The candidate AdamantineOS tag is:

```text
v3.0.0
```

This candidate is under review because the completed Milestone 18 runtime hardening converted AdamantineOS into a live final-policy authority boundary with full per-source evidence-level deny wiring.

---

## 3. Why v3.0.0 is defensible

`v3.0.0` is defensible as a major AdamantineOS release boundary because the repository now contains:

```text
- Shield v3.2.0 baseline evidence through AdamantineOS boundaries
- final AdamantineOS policy engine wired into live runtime execution
- legacy v1 executor path gated by final policy
- per-source deny wiring for Q-ID, Shield, WSQK, wallet_policy/EQC, replay, and human gates
- no-debt red-team closure for F1-F8 and N1-N8
- 925 passing tests
- 100.00% coverage
```

This is a major authority-boundary change compared with the locked `v2.2.0` WSQK v2 release state.

---

## 4. Compatibility boundary

The following compatibility decisions remain locked unless a later controlled refactor explicitly changes them:

```text
Internal package distribution name: adamantine-wallet-os
Python import paths: unchanged
Public project name: DigiByte AdamantineOS
Repository name: DigiByte-AdamantineOS
```

The internal package distribution name is preserved for CI/package compatibility and does not define the public project name.

---

## 5. Decision rule

The tag decision remains blocked until all of the following are true:

```text
[x] Milestone 19 final release gate document copied into the repository
[x] Build ledger updated with Milestone 19 gate state
[x] Final proof-pack index copied into the repository
[x] Fresh post-copy repository ZIP inspected
[x] Tests pass after post-copy inspection
[x] Coverage remains 100.00%
[x] No docs/package/import mismatch is introduced
[x] Maintainer explicitly approves tag creation after final copied-repo verification
```

---

## 6. Current decision

Current decision:

```text
Tag v3.0.0: APPROVED AFTER FINAL COPIED-REPO VERIFICATION
Release: APPROVED AFTER FINAL COPIED-REPO VERIFICATION
Version bump: NOT APPLIED IN THIS DOCUMENTATION-ONLY GATE UPDATE
```

AdamantineOS remains untagged until this approval update is copied into the repository, CI remains green, and the final copied-repo ZIP is inspected. The candidate tag approved by this gate is `v3.0.0`.


---

## 7. Final verified decision evidence

Final source inspected for approval decision:

```text
Fresh repository ZIP inspected: DigiByte-AdamantineOS-main(11).zip
Test command: PYTHONPATH=src python -m pytest -q
Result: 925 passed
Coverage: 100.00%
TOTAL: 4097 statements, 0 missed
```

Decision:

```text
Milestone 19 final release gate: PASSED
Candidate tag: v3.0.0
Tag approval: YES, after this approval update is copied back and verified from a fresh ZIP
Release approval: YES, after this approval update is copied back and verified from a fresh ZIP
Package/import rename: NO
Runtime code change in this gate update: NO
```
