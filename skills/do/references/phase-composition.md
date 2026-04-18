# Phase Composition Guide

Load this reference when complexity >= Medium to compose phase sequences for dispatched agents. Simple tasks get agent + skill with no phase wrapping.

## Three Universal Sequences

Every task maps to one of these base sequences. Pick the one that matches the task type.

### 1. Code Modification

```
PLAN → IMPLEMENT → TEST → REVIEW → FIX (if needed) → PR
```

Applies to: feature additions, bug fixes, refactoring, infrastructure changes.

### 2. Information/Content

```
RESEARCH → SYNTHESIZE → GENERATE → VALIDATE → OUTPUT
```

Applies to: articles, documentation, research reports, content publishing.

### 3. Debugging/Investigation

```
OBSERVE → HYPOTHESIZE → TEST → FIX → VERIFY
```

Applies to: bug reports, incident response, performance issues, failing tests.

## Conditional Phases

Add these phases when their trigger condition is present. Each phase has a specific insertion point in the base sequence.

### Before PLAN

| Phase | Trigger | Why |
|-------|---------|-----|
| ADR | Creation requests ("create", "new", "scaffold") | Decisions recorded before implementation prevents drift |
| PREFLIGHT | Git/PR operations | Fail fast: wrong branch, dirty tree, auth issues caught before expensive work |
| DISCOVER | New component creation | Prevents building duplicates of existing components |

### Before IMPLEMENT

| Phase | Trigger | Why |
|-------|---------|-----|
| SCOPE | Research tasks | Precise question prevents unbounded gathering |
| OUTLINE | Documentation tasks | Structure before prose catches gaps cheaply |
| GROUND | Voice content | Emotional anchor before writing prevents mechanical tone |
| DESIGN | Feature/skill creation | Tier + structure decisions before code prevents rework |

### After TEST, Before PR/OUTPUT

| Phase | Trigger | Why |
|-------|---------|-----|
| INTENT VERIFY | Code modifications Medium+ | Tests prove code compiles. This proves code does what was asked. Read-only adversarial check. |
| LIVE VALIDATE | Web projects (Hugo, Next.js, docker) | Playwright validates actual rendering. Skip for non-web. |
| JOY-CHECK | Voice content | Tonal framing. After validation (stylistic fidelity), before output. |
| ANTI-AI CHECK | Voice content | AI-tell detection. Last quality gate before output. |
| CODEX REVIEW | Significant code changes | Cross-model second opinion catches same-family blind spots |

### After REVIEW (conditional loop)

| Phase | Trigger | Why |
|-------|---------|-----|
| FIX + RETEST | CRITICAL findings from review | Fresh agent fixes (not the original). Max 3 iterations. After 3: halt, show findings, ask user. |

### After PR/OUTPUT (always last)

| Phase | Trigger | Why |
|-------|---------|-----|
| ADR RECONCILE | Creation requests with ADR | Compare merged code to ADR decisions. Document deviations. |
| RECORD | All Medium+ tasks | Capture learnings to learning.db. Not optional. |
| CLEANUP | All tasks | Remove temp files only after verification complete |

## Hard Ordering Constraints

These sequences are load-bearing. Reordering them causes specific failures.

1. **Plan before Implement.** Implementation against outdated understanding causes rework. If implementation diverges from plan, update the plan first.

2. **Implement before Test.** Nothing to test without code.

3. **Test before Review.** Reviewers assessing broken code is noise. They need compilable, passing code to evaluate design.

4. **Test before Fix.** Write the failing test first (reproduction), then fix. Proves the fix addresses the actual failure.

5. **Verify before Publish.** No PR, no output, no merge until verification passes. Skippable only with explicit flag.

6. **Research before Generate.** Prose without facts is shallow. Minimum 3 parallel research agents for formal research.

7. **Outline before Generate (docs/content).** Gaps found in outline are cheap. Gaps found after prose is written are expensive.

## Composition by Complexity

### Medium (code modification)
```
PLAN → IMPLEMENT → TEST → REVIEW → PR → RECORD
```
Add ADR at front for creation requests. Add INTENT VERIFY before PR for 5+ file changes.

### Medium (research/content)
```
SCOPE → GATHER (3+ parallel agents) → SYNTHESIZE → VALIDATE → OUTPUT → RECORD
```

### Medium (debugging)
```
OBSERVE (3x reproduction) → HYPOTHESIZE → TEST (refute one-by-one) → FIX → VERIFY → RECORD
```

### Complex (code modification)
```
ADR (if creation) → PLAN → IMPLEMENT → TEST → REVIEW (3 parallel) → INTENT VERIFY → LIVE VALIDATE (if web) → FIX loop (if CRITICAL, max 3) → PR → CODEX REVIEW → ADR RECONCILE → RECORD → CLEANUP
```

### Complex (content)
```
RESEARCH (parallel) → OUTLINE → GENERATE → VALIDATE → REFINE (max 3) → JOY-CHECK → ANTI-AI CHECK → OUTPUT → RECORD
```

## Patterns Earned From Prior Pipelines

### Three-Reviewer Pattern
For code review phases, dispatch 3 parallel reviewers covering different domains (security, business logic, architecture). Multiple specialists catch different failure modes simultaneously.

### Fresh Agent for Fixes
The agent that created a problem should not fix it. Anchoring bias causes the original agent to rationalize its own mistakes. Dispatch a fresh agent with the specific CRITICAL finding text.

### Max 3 Iterations
Every fix/refine loop caps at 3. After 3 failures: surface findings to the user, ask whether to proceed. A pipeline that promises quality must not silently ship known issues.

### Artifact Persistence
Every phase outputs a saved file (plan.md, test-results, review-findings). Context decay destroys unsaved work. Explicit artifact saves survive compaction.

### Performance Gates
Hook development: <50ms measured, not estimated. Blocking gate. A slow hook degrades every tool call permanently.

### Domain Auto-Detection
Language detection (Go, Python, TypeScript) determines which test/lint commands run. Web project detection (Hugo, Next.js, docker-compose) determines whether LIVE VALIDATE applies. Skip phases that don't match the domain.

### Repo Classification
Personal repos: full automation with review-fix loop (3 iterations max).
Protected-org repos: human confirmation required before each git action.
Toolkit repo: extra phases (retro capture, ADR validation) injected into PR flow.
