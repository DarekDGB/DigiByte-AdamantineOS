# Contributing

**License:** MIT — **Author:** DarekDGB  
**Repository:** DigiByte AdamantineOS  
**Scope:** Contract-first, deterministic foundation

Thanks for your interest in contributing.

AdamantineOS is a **decision engine** and a **contract-first foundation**.  
Most “feature requests” belong in *downstream wallets* or in companion repos. This repo prioritizes:

- Deterministic behavior (same inputs → same outputs)
- Fail-closed execution boundaries
- Contract / schema discipline
- Governance-controlled upgrades
- Strong negative / toxic-input testing

If you’re unsure whether something belongs here, open an Issue first.

---

## 1. Ground Rules (Non-Negotiable)

A PR will be rejected if it introduces any of the following:

- Silent fallback behavior (must fail-closed with explicit reason_id)
- Non-determinism (time/randomness/order dependence)
- Hidden authority (implicit privileges, bypass paths, undeclared trust)
- Contract drift (behavior changes without contract + version updates)
- “Fix without a test” (every fix must include a regression test)

---

## 2. Development Workflow

### Issues first
For anything non-trivial:
1. Open an Issue describing the change and why it belongs in this repo.
2. Wait for maintainer guidance before implementing.

### Tests required
- Add/extend tests for every change.
- Prefer **negative-first** tests (abuse/tamper/toxic inputs).
- Keep fixtures stable and intentional.

### Contract version discipline
- If behavior or interface changes: **bump the contract version**.
- If you change fixtures: update the manifest/hash checks (no silent changes).

---

## 3. Pull Request Checklist

Before opening a PR, confirm:

- [ ] CI passes locally (or via GitHub Actions)
- [ ] Change is deterministic (no time/randomness/order dependence)
- [ ] No silent fallbacks; failure paths return explicit reason_id
- [ ] Contracts/schemas updated if interface/behavior changes
- [ ] Regression tests added (including negative/tamper cases)
- [ ] Docs updated only if the change is contract-visible

---

## 4. Security

If you discover a security issue, do **not** open a public Issue.

Follow **SECURITY.md** and report privately:
📧 **adamantinewalletos@gmail.com**
