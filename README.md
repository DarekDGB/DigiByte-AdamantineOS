<p align="center">
  <img src="assets/branding/adamantineos-logo-primary.PNG" width="420"/>
</p>

# 🔷 DigiByte AdamantineOS

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-v3.0.0-brightgreen.svg)
![CI](https://github.com/DarekDGB/DigiByte-AdamantineOS/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)

![Q-ID](https://img.shields.io/badge/Q--ID-runtime--verified-0A66C2.svg)
![Adaptive Core v3](https://img.shields.io/badge/Adaptive%20Core-v3%20evidence--only-0052CC.svg)
![Shield v3.2](https://img.shields.io/badge/Shield-v3.2%20orchestrator--receipt-003366.svg)
![Governance](https://img.shields.io/badge/Governance-AC%20v3%20verified-6f42c1.svg)
![WSQK v2](https://img.shields.io/badge/WSQK-v2%20quantum--aware-8A2BE2.svg)
![AI Gateway](https://img.shields.io/badge/AI%20Gateway-evidence--only%20never%20authority-111111.svg)

------------------------------------------------------------------------

## What is AdamantineOS?

DigiByte AdamantineOS is a **deterministic security decision engine for
digital wallets and autonomous systems**.

It is **not a wallet UI** and it does **not** change DigiByte consensus,
block rules, mining, supply, or protocol security.

AdamantineOS sits before execution and connects external evidence layers
into one final fail-closed decision path. External systems provide evidence;
AdamantineOS makes the final allow, deny, or human-review decision.

The `v3.0.0` release connects:

• **Shield v3.2 component evidence** through the Shield Orchestrator receipt\
• **WSQK v2 posture / policy evidence**\
• **Q-ID identity / session evidence**\
• **Adaptive Core advisory policy evidence**\
• **AI Gateway evidence-only input, never final authority**\
• **Replay / nonce freshness enforcement**\
• **Wallet policy / EQC evidence**\
• **Human review bound to exact context**\
• **Final AdamantineOS fail-closed decision authority**

Only after the final AdamantineOS decision engine returns an allow verdict
can execution continue.

------------------------------------------------------------------------

## Why AdamantineOS Exists

Modern wallet systems and autonomous applications rely on multiple
external signals:

• identity proofs\
• oracle intelligence\
• AI security analysis\
• governance proposals\
• runtime policies\
• quantum-aware authority proofs

Most systems **trust these signals blindly**.

AdamantineOS exists to enforce **deterministic trust verification**.

Instead of trusting external inputs, AdamantineOS:

• verifies identity using **Q-ID cryptographic proofs**\
• validates oracle intelligence from **Adaptive Core**\
• evaluates security evidence from **Shield v3 layers**\
• enforces deterministic **fail-closed decision rules**\
• verifies governance proposals through **artifact hashing and receipt
validation**\
• enforces **WSQK v2 quantum-aware authority** through TVA and Q-ID posture binding

Execution is allowed **only when every layer passes verification**.

If any layer fails → execution is deterministically denied.

AdamantineOS therefore acts as a **trust firewall for wallet
execution**.

------------------------------------------------------------------------

## v3.0.0 --- Connected Evidence Architecture Release

**Status:** Release-stamped, CI green, and ready for final tag review after final ZIP inspection\
**Type:** Major release boundary\
**Tests:** 925 passed\
**Coverage:** 100.00%\
**Package distribution name:** `adamantine-wallet-os` unchanged\
**Python import paths:** unchanged

DigiByte AdamantineOS `v3.0.0` marks the first major release boundary after
approximately seven months of building, integration, proof-pack alignment,
red-team hardening, and final release-gate review.

This release is about the full connected system: Shield, WSQK, Q-ID, Adaptive
Core, AI Gateway, replay/nonce checks, wallet policy, human review, and the
final AdamantineOS fail-closed decision engine.

Claude AI is documented only as part of the authorized red-team evidence. The
release itself is the connected deterministic architecture, not the red-team tool.

AdamantineOS does not change DigiByte consensus. It remains an external
deterministic fail-closed execution protection boundary.

------------------------------------------------------------------------

## v2.2.0 --- WSQK v2 Quantum-Aware Upgrade

**Status:** Locked\
**Type:** Quantum-aware authority upgrade\
**Compatibility:** Additive --- legacy/v1 paths remain compatible unless WSQK v2 is explicitly required

This release upgrades WSQK inside AdamantineOS into a quantum-aware authority layer.

### What's locked:

1.  WSQK v2 Authority Contract
    -   `WSQKAuthorityV2` and `WSQKIssueRequestV2`
    -   sorted canonical unique `required_evidence_families`
    -   deterministic `proof_bindings_hash`
2.  Truth Vector Authority (TVA) Enforcement
    -   WSQK v2 posture requirements are enforced fail-closed
    -   tampered bindings are denied before nonce use
    -   WSQK v1 cannot satisfy explicit WSQK v2 requirements
3.  Q-ID Hybrid Posture Binding
    -   `hybrid_required` requires classical AND PQC posture
    -   `pqc_required` requires PQC evidence
    -   posture mismatches deny deterministically
4.  Runtime Boundary Propagation
    -   orchestrator/runtime paths propagate WSQK v2 requirements
    -   no silent v1 fallback when v2 is required
5.  Tamperproof Regression Locks
    -   hash tampering, context tampering, family drift, downgrade attempts,
        and Q-ID posture tamper are covered by tests
    -   WSQK v2 proof pack maps contracts → invariants → implementation → tests → CI proof

Key invariant:

`required_evidence_families` MUST be stored and compared as a sorted canonical set.

------------------------------------------------------------------------

## v2.1.0 --- AC v3 Governance Compatibility Lock

**Status:** Locked\
**Type:** Compatibility lock (Adaptive Core v3 governance path sealed)\
**Compatibility:** Additive --- no production behavior changes

This release locks AdamantineOS compatibility with Adaptive Core v3
`upgrade_proposal_v3` artifacts and seals the first cross-repository
governance evaluation path.

### What's locked:

1.  Adaptive Core v3 Governance Compatibility
    -   Proven compatibility with Adaptive Core v3 `upgrade_proposal_v3`
        artifacts
    -   Stable proposal ingestion and validation path
    -   Deterministic evaluation of governance proposals
2.  Cross-Repository Hash Invariant
    -   Deterministic `proposal_hash` invariant enforced across
        repositories
    -   Hash drift fails CI
    -   Canonical compatibility vector frozen
3.  Governance Receipt Path Frozen
    -   Compatibility vectors frozen in CI (`approve` + receipt path)
    -   First upgrade proposal review path sealed end-to-end
    -   Stable review receipt artifact boundary
4.  Boundary Guarantees Reinforced
    -   No production behavior changes
    -   Governance compatibility locked without expanding runtime trust
    -   Strengthened boundary between proposal artifacts and execution
        behavior

Rule: Any semantic change to Adaptive Core v3 governance artifact
handling requires a new versioned compatibility lock.

------------------------------------------------------------------------

# 🧱 Connected Evidence Architecture

```mermaid
flowchart LR
    subgraph SC[Shield Components]
        GW[Guardian Wallet]
        ADN[ADN]
        SAI[Sentinel AI]
        DQSN[DQSN]
        QWG[QWG]
    end

    SO[Shield Orchestrator]
    SR[Shield Orchestrator v3.2 Receipt]

    GW --> SO
    ADN --> SO
    SAI --> SO
    DQSN --> SO
    QWG --> SO
    SO --> SR

    WSQK[WSQK v2<br/>Posture / policy evidence]
    QID[Q-ID<br/>Identity / session evidence]
    AC[Adaptive Core<br/>Advisory policy evidence]
    AIG[AI Gateway<br/>Evidence only / never final authority]

    subgraph FE[AdamantineOS Final Fail-Closed Decision Engine]
        G1[1. Shield receipt gate]
        G2[2. WSQK gate]
        G3[3. Q-ID gate]
        G4[4. Adaptive Core gate]
        G5[5. AI Gateway gate]
        G6[6. Replay / nonce gate]
        G7[7. Wallet policy gate]
        G8[8. Human gate]
        G9[9. Final AdamantineOS decision]

        G1 --> G2 --> G3 --> G4 --> G5 --> G6 --> G7 --> G8 --> G9
    end

    SR --> G1
    WSQK --> G2
    QID --> G3
    AC --> G4
    AIG --> G5

    G9 --> ALLOW[FINAL ALLOW]
    G9 --> DENY[FINAL DENY]
    G9 --> REVIEW[HUMAN REVIEW REQUIRED]
```

## Architecture rules

- No raw component bypass.
- Shield `ALLOW` is not final approval.
- `DENY` dominates.
- No AI final authority.
- External systems provide evidence only.
- AdamantineOS makes the final decision.
- Deterministic boundaries define behavior.
- Tests define truth.

## What v3.0.0 connects

- Guardian Wallet, ADN, Sentinel AI, DQSN, and QWG evidence through Shield Orchestrator.
- Shield Orchestrator v3.2 receipt verification.
- WSQK v2 posture and policy evidence.
- Q-ID identity and session evidence.
- Adaptive Core advisory policy evidence.
- AI Gateway evidence-only input with no final authority.
- Replay / nonce freshness enforcement.
- Wallet policy / EQC evidence.
- Human review exact-context gate.
- Final AdamantineOS allow / deny / review decision.

------------------------------------------------------------------------

# 📚 Governance Documentation

AdamantineOS v2.1.0 introduces the first deterministic governance
compatibility path with **Adaptive Core v3**.

The governance architecture and artifact contracts are documented here:

-   [Adaptive Core → Adamantine Governance
    Flow](docs/ADAPTIVE_CORE_GOVERNANCE_FLOW.md)\
-   [Governance Artifact Examples (Real
    Artifacts)](docs/GOVERNANCE_ARTIFACT_EXAMPLES.md)\
-   [Governance Review
    Contract](docs/CONTRACTS/upgrade_governance_review_v1.md)\
-   [Governance Compatibility Proof
    Pack](docs/PROOF_v2.1.0_GOVERNANCE_COMPATIBILITY.md)

Governance pipeline:

Adaptive Core\
→ generates `upgrade_proposal_v3`

AdamantineOS\
→ validates proposal artifacts\
→ verifies deterministic `proposal_hash` invariants\
→ evaluates governance policy\
→ emits `ac_review_receipt_v1`\
→ produces deterministic allow / deny decision.

------------------------------------------------------------------------

# 🛡️ WSQK v2 Quantum-Aware Authority

WSQK v2 binds wallet authority to explicit quantum-security posture.

Documented proof path:

-   [WSQK Authority v2
    Contract](docs/CONTRACTS/wsqk_authority_v2.md)\
-   [WSQK v2 Quantum-Aware Proof
    Pack](docs/PROOF_PACKS/wsqk_v2_quantum_aware_proof_pack.md)

WSQK v2 is enforced through:

WSQK v2 authority proof\
→ Q-ID classical/PQC posture binding\
→ Truth Vector Authority (TVA) enforcement\
→ Orchestrator/runtime propagation\
→ deterministic allow / deny decision.

------------------------------------------------------------------------

# 🔐 Protection Modes

Every execution response includes a deterministic security posture.

### 🟢 `legacy`

-   Q-ID missing or invalid
-   Protected execution not requested
-   Baseline evaluation only

### 🟡 `minimal`

-   Q-ID valid
-   Shield or Oracle incomplete
-   Reduced security guarantees

### 🔵 `full`

-   Q-ID valid
-   Shield v3 valid
-   Adaptive Core v3 Oracle valid
-   All layers enforced

Protection mode semantics are regression locked in CI.

------------------------------------------------------------------------

# 🔐 Q-ID Cryptographic Enforcement (Runtime-Verified)

AdamantineOS v2 integrates DigiByte Q-ID with explicit runtime
enforcement.

-   Runtime may inject a `qid_verifier` cryptographic hook
-   If provided, it is invoked **before Q-ID session parsing**
-   Any verifier failure deterministically denies execution
-   No silent downgrade path
-   No implicit trust of unsigned evidence

Coverage remains 100%.

------------------------------------------------------------------------

# 🔒 Core Invariants

Adamantine enforces:

-   Fail‑closed evaluation
-   Canonical Shield ordering
-   No duplicate layers
-   Strict version discipline
-   No silent downgrade under policy
-   Shield evidence can only strengthen deny
-   Deterministic outputs for identical inputs
-   Replay attempts deterministically denied when enforced
-   Manifest drift fails CI
-   Hash drift fails CI
-   Proposal hash drift fails CI across Adaptive Core v3 compatibility
    vectors
-   Governance receipt path remains deterministic once sealed
-   WSQK v2 evidence families remain sorted, canonical, and hash-stable
-   WSQK v2 cannot silently downgrade to v1 when v2 is required

If any invariant weakens, tests fail.

------------------------------------------------------------------------

# 📦 Scope

### Included

-   Execution envelope contracts (v1 + v2)
-   Orchestrator v2
-   EQC evaluator
-   WSQK v2 quantum-aware authority proof
-   Shield v3 adapter
-   Adaptive Core v3 adapter
-   Adaptive Core v3 governance compatibility path
-   Proposal review receipt boundary
-   Q-ID adapter
-   Truth Vector Authority (TVA) boundary enforcement
-   Deterministic proof packs (v1.2.0 → v2.2.0)
-   Compatibility vectors for AC v3 proposal review
-   WSQK v2 quantum-aware proof pack

### Excluded

-   Wallet UI
-   Key custody
-   Transaction building
-   Network broadcasting

Adamantine is a **decision engine**, not a wallet.

------------------------------------------------------------------------

# 🧪 Determinism & Testing

-   100% coverage enforced
-   Fixture hashes locked
-   Canonical JSON duplicate-key rejection
-   Strict manifest enforcement
-   Deterministic replay validation (50-run runtime tests)
-   Adaptive Core v3 compatibility vectors frozen in CI
-   CI rejects silent behavioral drift
-   WSQK v2 tamperproof regression locks remain enforced

Security changes require test changes.

------------------------------------------------------------------------

# 🧭 Version History

-   v2.2.0 --- WSQK v2 Quantum-Aware Upgrade
-   v2.1.0 --- AC v3 Governance Compatibility Lock
-   v2.0.1 --- 100% Coverage Gate + Integrity Lock
-   v2.0.0 --- Runtime Host v2 + Execution Boundary Seal
-   v1.5.0 --- Mobile Contract v2 + Conformance Freeze
-   v1.4.0 --- Q-ID Replay Proof Gate
-   v1.3.0 --- Shield Interfaces Frozen
-   v1.2.0 --- Integration Harness Sealed
-   v1.0.0 --- Foundation Sealed

------------------------------------------------------------------------

**AdamantineOS**\
Deterministic. Fail‑Closed. Quantum‑Aware. Governance‑Compatible.

------------------------------------------------------------------------

## Project Author

Created and maintained by **DarekDGB**

AdamantineOS is part of the broader **DigiByte Quantum Shield
architecture**.

------------------------------------------------------------------------

## License 2025-2026

MIT License --- **DarekDGB**
