---
name: review
description: "Code review: systematic single-file, parallel multi-reviewer, full-repo audit, PR diff review."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Agent
routing:
  force_route: true
  not_for: "security scanning (use security), linting (use code-quality), git push/commit/PR (use pr-workflow)"
  triggers:
    - "review code"
    - "code review"
    - "code review methodology"
    - "structured review"
    - "code audit"
    - "review methodology"
    - "comprehensive review"
    - "parallel review"
    - "3-reviewer review"
    - "multi-reviewer"
    - "concurrent review"
    - "full repo review"
    - "review entire repo"
    - "codebase health check"
    - "review all files"
    - "full codebase review"
    - "audit the codebase"
    - "codebase audit"
    - "review whole repo"
    - "sweep all source files"
    - "repo health"
    - "review this PR"
    - "review my PR"
    - "PR review"
    - "diff review"
  category: code-review
  pairs_with:
    - security
    - testing
---

# Review

Three modes. Pick one by request shape, default to systematic.

| Request matches | Mode |
|---|---|
| Review a file, diff, or PR | Systematic (default) |
| "parallel review", "multi-reviewer", "3-reviewer" | Parallel |
| "full repo review", "codebase audit", "repo health", review ALL files | Full-repo |

## Deep References

| Signal | Load | Why |
|---|---|---|
| Reviewing Go code | `references/go-review-patterns.md` | Exports, concurrency, resources, metrics, tests |
| Dispatching Architecture reviewer in parallel mode | `references/architecture-smell-baseline.md` | 12 Fowler smells with language counter-examples and severity cap |
| Writing full-repo report | `references/report-template.md` | Report structure and field definitions |
| Dispatching full-repo wave agents | `references/audit-playbook.md` | 8-category checklists with evidence requirements |
| Receiving review feedback | `references/receiving-feedback.md` | Feedback-handling patterns |

## Severity Classification

Shared across all modes. When in doubt, classify UP.

| Level | Scope | Examples |
|---|---|---|
| BLOCKING | Security, correctness, reliability | Auth bypass, race condition, resource leak, logic error, test failure |
| SHOULD FIX | Material quality, patterns, tests | Missing tests, unhelpful errors, pattern violations, N+1 in hot paths |
| SUGGESTION | Optional, stylistic | Naming preferences, comments, micro-optimizations |

Decision: security/correctness/reliability risk? -> BLOCKING. Violates patterns or creates maintenance burden? -> SHOULD FIX. Purely stylistic? -> SUGGESTION.

## Verdict Rules

| Condition | Verdict |
|---|---|
| Any BLOCKING finding | **REQUEST-CHANGES** (or BLOCK) |
| SHOULD FIX findings, no BLOCKING | **FIX** before merge |
| Only SUGGESTION or clean | **APPROVE** |

Omit empty severity sections. Include review scope, evidence, and limitations. Validate output:

```bash
python3 scripts/validate-review-output.py --type systematic /tmp/review-output.md
```

Exit 0 = valid; 1 = schema errors; 2 = unparseable; 3 = missing jsonschema.

---

## Mode 1: Systematic Review (default)

Single-reviewer, 4-phase review of a named file, diff, or PR.

### Phase 1: UNDERSTAND

Read repository instructions and the complete diff. Read surrounding code to understand each changed path and its consumers. When signatures change, find all callers and interface implementations. Trace parameters to their source: query params may hold any user string; tokens may be server-issued IDs; enums have bounded values. Check validation at each caller.

**Gate:** Every changed path accounted for, callers traced where needed.

### Phase 2: VERIFY

Run relevant tests and required repository checks. Reuse prior results only when they cover current code and environment. Check material claims in comments and PR description against code and tests. Missing tools, skipped checks, and inferred outcomes are not passes.

**Gate:** Claims have supporting evidence; required checks passed or the gap is recorded.

### Phase 3: ASSESS

Assess risks: security (auth, validation, injection, secrets), performance (N+1, unbounded work, allocations on hot paths), architecture (conventions, compatibility, scope, unnecessary abstractions). For extracted helpers, recheck contract and callers.

**Gate:** Relevant risks and remaining uncertainty are explicit.

### Phase 3.5: VERIFY FINDINGS

Before reporting, check each finding's input sequence, existing guards, and proposed fix. Drop unreachable or already-handled claims. Deduplicate when combining reviews; resolve severity from evidence.

### Phase 4: DOCUMENT

```text
Review Summary:
  Files Reviewed: N | Lines Changed: +X/-Y
  Test Status: PASS | FAIL | SKIPPED
  Risk Level: LOW | MEDIUM | HIGH | CRITICAL

BLOCKING:
  1. Issue and consequence — path/file.ext:42
SHOULD FIX:
  1. Issue and consequence — path/file.ext:52
SUGGESTIONS:
  1. Optional improvement — path/file.ext:62

Verdict: APPROVE | REQUEST-CHANGES | NEEDS-DISCUSSION
Rationale: Evidence, scope, and limitations.
```

---

## Mode 2: Parallel Review

Three concurrent reviewers, then aggregate.

### Step 1: Scope

Identify the diff or files. Record the reviewed revision.

```bash
git diff --name-only HEAD
gh pr view --json files -q '.files[].path'
```

Select Architecture reviewer by language: Go -> `golang-general-engineer`; Python -> `python-general-engineer`; TypeScript -> `typescript-frontend-engineer`; mixed -> `Explore`.

### Step 2: Dispatch

Dispatch three reviewers together. Read-only; no code edits.

| Reviewer | Focus |
|---|---|
| Security | Auth, authorization, input validation, secrets, OWASP |
| Business Logic | Requirements, edge cases, state transitions, failure modes |
| Architecture | Design, structure, performance, maintainability, scope |

Pass `references/architecture-smell-baseline.md` verbatim to the Architecture reviewer. Require `[Reviewer] file:line` format with severity and consequence.

### Step 3: Aggregate and Verdict

Deduplicate findings, resolve severity disagreements from evidence. Apply shared verdict rules. Output a single combined report with severity matrix, combined findings, and recommendation.

**Gate:** Every reviewer returned, or missing coverage is explicitly stated without claiming approval.

---

## Mode 3: Full-Repo Review

All source files through a 4-wave comprehensive review. Produces a prioritized backlog, not auto-fixes. Use for quarterly health checks, post-refactor audits, or new codebase onboarding.

Options: `--directory [dir]` (scope to one dir), `--skip-precheck`, `--min-severity [level]`.

### Step 1: Discover and Pre-check

Scan all source files (scripts/, hooks/, skills/, agents/, docs/). Never fall back to git diff.

```bash
python3 ~/.claude/scripts/score-component.py --all-agents --all-skills --json
```

Save scores as triage context. A score alone never determines severity.

### Step 2: Run Comprehensive Review

Call `comprehensive-review` with `--review-only` and the full file list. Run all 4 waves (0-3). Load `references/audit-playbook.md` as prompt context for wave agents.

### Step 3: Report

Merge deterministic scores with LLM findings. Identify systemic patterns (3+ files). Write `full-repo-review-report.md` using `references/report-template.md`.

**Gate:** Report exists with severity sections and deterministic scores.

---

## Error Handling

| Error | Solution |
|---|---|
| Reviewer times out or returns nothing | Report partial findings, note gap, retry on reduced scope |
| Validator script missing | Run review without validation, note gap in verdict |
| score-component.py fails | Proceed with LLM review only, note gap in report |
| Too many files for single session | Split by directory: scripts/, hooks/, agents/, skills/ |
