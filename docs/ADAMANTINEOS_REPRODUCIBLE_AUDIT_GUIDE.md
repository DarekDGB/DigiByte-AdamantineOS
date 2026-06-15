# AdamantineOS Reproducible Audit Guide

Author attribution: **DarekDGB**  
Repository: `DigiByte-AdamantineOS`  
Scope: reproducible verification for audits, hardening reviews, release candidates, and downstream integrations  
Ledger status: **no build ledger update for this post-v3.0.0 hardening phase**

---

## 1. Purpose

This guide defines the minimum reproducible verification procedure for AdamantineOS security reviews.

It exists so maintainers, reviewers, auditors, and downstream integrators can base conclusions on the exact source tree under review, complete test execution, and coverage-verified results.

AdamantineOS is a deterministic security boundary. Its verification process should be equally deterministic: the reviewed source, command set, and result evidence must be clear enough for another reviewer to reproduce the same conclusion.

---

## 2. Source under review

Each audit or integration review should identify the exact source being inspected.

Acceptable source references include:

```text
- a clean checkout of a named commit
- a release tag
- a source archive whose filename and origin are recorded in the review notes
```

The source reference should be recorded before conclusions are written.

When the inspected source cannot be tied to a specific commit, release tag, or source archive, the review should state:

```text
not verified from the reviewed source
```

This protects the audit trail from accidental conclusions based on stale folders, partial copies, cached files, or mixed source trees.

---

## 3. Environment preparation

From the repository root, install the development test dependency set:

```bash
python -m pip install -e ".[dev]"
```

The repository is expected to run with Python 3.11 or later, matching the project metadata.

---

## 4. Full verification command

The final verification command for an AdamantineOS source review is:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest -q
```

This command uses the repository pytest configuration, including coverage enforcement:

```text
--cov=adamantine
--cov-report=term-missing
--cov-fail-under=100
```

A passing final proof should include both:

```text
- the complete pytest pass result
- the 100% coverage result from the reviewed source
```

---

## 5. Optional pass-count check

A pass-count-only run may be used as supporting evidence:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest --no-cov
```

This command is useful for confirming the raw number of passing tests without coverage reporting.

It does not satisfy final coverage proof by itself.

---

## 6. Targeted tests

Targeted test runs are useful during development and patch review.

Examples:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest tests/test_step4_shield_runtime_boundary_lock.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src pytest tests/integrations/test_qid_adapter.py -q
```

Targeted runs do not replace the full verification command in section 4.

A targeted run proves only the selected scope. A release, audit closure, or integration-ready conclusion should still use the full verification command.

---

## 7. Evidence expected in review notes

A complete review note should record:

```text
- source reference inspected
- command used
- pytest pass result
- coverage result
- any deviations from this guide
```

If a reviewer cannot verify one of these items, the note should explicitly mark that item as unverified.

---

## 8. Security interpretation

A green test result is necessary but not sufficient for final trust.

AdamantineOS reviews should also check:

```text
- docs match code
- tests prove the intended invariant
- fail-closed paths remain fail-closed
- external evidence remains evidence only
- no external component receives final approval authority
- no replay, wallet policy, or human confirmation gate is bypassed
```

The final security conclusion should be based on source inspection, tests, coverage, and architectural review together.
