# Observability Invariants

This document defines **strict, fail-closed observability rules** for Adamantine Wallet OS.

## Core Rule (No-Leak)
- Metrics **MUST ONLY** record **ReasonId counters**.
- Metrics **MUST NEVER** store or log:
  - payloads
  - requests
  - contexts
  - sessions
  - risk reports
  - raw evidence
  - any user or transaction data

## Rationale
- Prevent data exfiltration via observability paths.
- Keep metrics deterministic, minimal, and privacy-safe.
- Ensure mobile and CI environments remain leak-free by design.

## Enforcement
- Tests assert absence of storage fields (deny-by-default).
- Any future metrics implementation **must pass** no-leak tests.
- Violations are treated as **security bugs**.

## Scope
- Applies to all metrics implementations (e.g., InMemoryMetrics, NullMetrics).
- Applies across adapters, EQC, TVA, and execution boundaries.
