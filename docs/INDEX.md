# Adamantine Wallet OS — Documentation Index

**License:** MIT License  
**Author:** DarekDGB  
**Repository:** DigiByte Adamantine Wallet OS  
**Scope:** Foundation Documentation Index

---

## 1. Purpose

This document is the **authoritative index** of all documentation that defines the Adamantine Wallet OS foundation.

The foundation is **contract-first**, **invariant-driven**, and **deterministic**.  
Runtime wallet execution, UI, clients, and integrations are intentionally excluded from this repository.

If a document is not listed here, it is **not part of the foundation contract**.

---

## 2. Foundation Status

**Current status:** v1.4.0 — Q-ID linkage hardened (clock-free replay framework)

Included:
- Contracts
- Deterministic reasoning
- Fail-closed gates
- Authority model
- Execution boundaries
- Proof packs / fixture manifests

Explicitly not included:
- Wallet runtime
- Transaction construction
- Signing or broadcasting
- Client SDKs
- Shield or Adaptive Core implementations (evidence only)

---

## 3. Normative Sources (Highest Authority)

The following documents define **non-negotiable truth**.  
If anything conflicts with these, **these win**.

### 3.1 Execution Boundary and Envelope Contracts
- `docs/CONTRACTS/execution_request_v2.md`
- `docs/CONTRACTS/mobile_execution_call_v1.md` (if present)
- Any additional `docs/CONTRACTS/*` referenced by the orchestrator

### 3.2 Q-ID Linkage and Replay Protection
- `docs/CONTRACTS/qid_linkage_v1.md` (NEW in v1.4.0)
- `docs/DURABLE_NONCE_STORE_INTEGRATION.md` (UPDATED in v1.4.0, clock-free)

### 3.3 Proof Packs
- `docs/OS_PROOF_PACK_v1_2_0.md` (if present)
- `docs/OS_PROOF_PACK_v1_3_0.md` (if present)
- `docs/OS_PROOF_PACK_v1_4_0.md` (NEW)

---

## 4. Non-Normative / Supporting Documents

The following may explain intent, but do not override contracts or tests.

- Architecture overviews
- Diagrams
- Roadmaps
- Release notes

---

## 5. Index Discipline

- Contract changes MUST be reflected here.
- Adding a new contract doc without updating this index is a process failure.
- Tests + fixtures are the ultimate enforcement of these documents.

---

**Adamantine Wallet OS**  
Deterministic. Fail-Closed. Future-Ready.
