---
name: comprehensive-review
description: |
  Unified 4-wave code review: Wave 0 auto-discovers packages/modules and
  dispatches one language-specialist agent per package for deep per-package
  analysis. Wave 1 dispatches 12 foundation reviewers in parallel (with Wave 0
  context). Wave 2 dispatches 10 deep-dive reviewers that receive Wave 0+1
  findings as context for targeted analysis. Wave 3 dispatches 4-5 adversarial
  reviewers that challenge Wave 1+2 consensus — contrarian, skeptical senior,
  user advocate, meta-process, and conditionally SAPCC structural. Aggregates
  all findings by severity with wave-agreement labels (unanimous, majority,
  contested), then auto-fixes ALL issues. Covers per-package deep review,
  security, business logic, architecture, error handling, test coverage, type
  design, code quality, comment analysis, language idioms, docs validation,
  newcomer perspective, performance, concurrency, API contracts, dependencies,
  error messages, dead code, naming, observability, config safety, migration
  safety, and adversarial challenge.
  Use for "comprehensive review", "full review", "review everything", "review
  and fix", or "thorough code review".
  Do NOT use for single-concern reviews (use individual agents instead).
effort: high
version: 4.0.0
user-invocable: false
command: /comprehensive-review
model: opus
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - TaskCreate
  - TaskUpdate
  - TaskList
  - EnterWorktree
routing:
  force_route: true
  triggers:
    - comprehensive review
    - full review
    - review everything
    - review and fix
    - thorough review
    - multi-agent review
    - complete code review
    - 20-agent review
    - 25-agent review
    - per-package review
    - 3-wave review
    - 4-wave review
    - adversarial review
    - "full code review"
    - "review all packages"
  pairs_with:
    - systematic-code-review
    - parallel-code-review
    - systematic-code-review
  force_routing: false
  complexity: Complex
  category: review
---

# Comprehensive Code Review v4 — Four-Wave Hybrid Architecture

Four-wave review with per-package deep analysis and adversarial challenge. Wave 0 auto-discovers packages/modules and dispatches one language-specialist agent per package to read ALL code in that package. Wave 1 (12 foundation agents, including newcomer perspective) runs in parallel with Wave 0 context. Wave 2 (10 deep-dive agents) receives Wave 0+1 findings for targeted analysis. Wave 3 (4-5 adversarial agents) challenges Wave 1+2 consensus — are findings actually important? Are tradeoffs justified? Should the PR be split? All findings are aggregated with wave-agreement labels, deduplicated, and auto-fixed.

**How this differs from existing skills**:
- `/parallel-code-review`: 3 agents (security, business, arch) — report only
- `/comprehensive-review`: **25+ agents in 4 waves** — per-package + cross-cutting + adversarial review AND fix everything

---

## Overview

This four-wave review architecture discovers, analyzes, and fixes code issues across multiple dimensions simultaneously. Wave 0 performs deep per-package analysis that single-threaded reviewers miss. Waves 1-2 establish broad cross-cutting coverage. Wave 3 challenges the consensus to surface false positives and overconfident findings. The skill then auto-fixes all confirmed issues on an isolated branch.

**Execution model**: Parallelism is critical. Waves dispatch all agents in single batches for true concurrency. Findings are persisted to disk at each phase to survive context compaction between waves. This guarantees that even on large codebases, no prior context is lost between phases.

**Key outcomes**:
- Per-package deep review (Wave 0) catches internal API misuse, cohesion issues, and package-level design problems
- Cross-cutting analysis (Waves 1-2) catches security, business logic, architecture, test, and type issues
- Adversarial review (Wave 3) reduces false positives and validates that fixing an issue won't create new problems
- Aggregated findings with wave-agreement labels (unanimous, majority, contested) provide confidence scoring
- All issues are auto-fixed (except BLOCKED items where fixing breaks something else) — no deferred debt

---

## Instructions

[Full Instructions with Phases 0.5-5: See phases below for complete workflow-first ordering]

---

## Error Handling

**If context compaction fires between waves**: Wave findings are persisted to `$REVIEW_DIR/` at each phase. Reload prior findings from disk before proceeding. If a file is missing, re-aggregate from raw agent outputs.

**If an agent times out**: Re-dispatch that single agent with fresh context. For Wave 0-2, include the findings file. For Wave 3, include the Wave 0+1+2 summary.

**If tests fail during fix batch**: Stop, analyze regression, roll back that fix batch, proceed to next severity level.

**If a finding is contested by Wave 3**: Include in final report with both perspectives. Apply fix WITH A DOCUMENTED COMMENT.

**If BLOCKED findings cannot be resolved**: Track as GitHub issues or learning.db entries. The review allows up to 10% of total findings to remain BLOCKED.

---

## References

**Agent definitions**:
- `reviewer-security` — OWASP Top 10, auth, input validation, secrets
- `reviewer-business-logic` — Domain logic, edge cases, state transitions
- `reviewer-silent-failures` — Error handling, swallowed errors, empty catches
- `reviewer-test-analyzer` — Test coverage, fragile tests, missing cases
- `reviewer-type-design` — Type safety, invariants, encapsulation
- `reviewer-code-quality` — Convention compliance, style, CLAUDE.md adherence
- `reviewer-comment-analyzer` — Comment rot, misleading documentation, stale TODOs
- `reviewer-language-specialist` — Language idioms, modern stdlib, LLM tells
- `reviewer-docs-validator` — README, CLAUDE.md, dependencies, CI, build system
- `reviewer-adr-compliance` — ADR implementation, scope creep detection
- `reviewer-newcomer` — Documentation gaps, implicit assumptions, onboarding friction
- `reviewer-performance` — Algorithmic complexity, N+1 queries, allocation waste
- `reviewer-concurrency` — Goroutine leaks, race conditions, deadlocks
- `reviewer-api-contract` — Breaking changes, contract violations
- `reviewer-dependency-audit` — CVEs, licenses, deprecated packages
- `reviewer-error-messages` — Error message quality, actionability, consistency
- `reviewer-dead-code` — Unreachable code, unused exports
- `reviewer-naming-consistency` — Naming conventions, cross-package consistency
- `reviewer-observability` — Instrumentation gaps, RED metrics
- `reviewer-config-safety` — Secrets, env var validation, hardcoded values
- `reviewer-migration-safety` — Reversible migrations, deprecation paths, rollback safety
- `reviewer-contrarian` — Challenges false positives, over-severity
- `reviewer-skeptical-senior` — Experience-based skepticism, real-world risks
- `reviewer-user-advocate` — User impact, UX tradeoffs, backward compatibility
- `reviewer-meta-process` — Process validation, PR structure, review focus
- `reviewer-sapcc-structural` — (conditional) SAP Commerce Cloud structural integrity

**Related Skills**:
- `/parallel-code-review` — 3-agent subset (security, business, arch) without fix
- `/systematic-code-review` — Sequential 4-phase methodology
- `/pr-review-address-feedback` — PR comment validation and triage
