---
name: go-patterns
description: "Go development patterns: testing, concurrency, errors, review, and conventions."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
routing:
  category: language
  force_route: true
  triggers:
    # testing triggers
    - go test
    - "*_test.go"
    - table-driven
    - t.Run
    - t.Helper
    # concurrency triggers
    - goroutine
    - channel
    - chan
    - sync.Mutex
    - sync.WaitGroup
    - worker pool
    - fan-in
    - context.Context
    - "goroutine parallel"
    - "Go parallel"
    - "goroutine fan-out"
    # error handling triggers
    - fmt.Errorf
    - errors.Is
    - errors.As
    - "%w"
    - sentinel error
    # review pattern triggers
    - Go mistake
    - bad Go
    - Go smell
    - "Go anti-pattern"
    - "Go code smell"
    # code review triggers
    - review Go
    - Go PR
    - Go code review
    - review .go
    - check Go code
    - Go quality
    # sapcc conventions triggers
    - sapcc
    - sap-cloud-infrastructure
    - go-bits
    - keppel
    - go-api-declarations
    - go-makefile-maker
    - sapcc/go-bits
    - sap-cloud-infrastructure/go-bits
    # quality gate triggers
    - make check
    - Go lint
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - systematic-code-review
---

# Go Patterns Skill

Umbrella skill for Go development: testing, concurrency, error handling, anti-patterns, code review, SAP CC conventions, and quality gates. Routes to the correct reference based on the task.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Testing | `testing.md` | Writing, fixing, or reviewing Go tests |
| Concurrency | `concurrency.md` | Goroutines, channels, sync primitives, race conditions |
| Error handling | `error-handling.md` | Error wrapping, sentinels, custom types, errors.Is/As |
| Review patterns | `preferred-patterns.md` | Code smells, over-engineering, bad Go patterns |
| Code review | `code-review.md` | Reviewing Go code or PRs |
| SAP CC conventions | `sapcc-conventions.md` | Working in sapcc/* repos with go-bits |
| Quality gate | `quality-gate.md` | make check, linting, pre-commit validation |

## Instructions

### Step 1: Identify the Go Domain

Classify the task, then load the corresponding reference files. Only load what is needed.

| Domain | Load Reference | When |
|--------|---------------|------|
| Testing | `references/testing.md` | Writing, fixing, or reviewing Go tests |
| Concurrency | `references/concurrency.md` | Goroutines, channels, sync primitives, race conditions |
| Error handling | `references/error-handling.md` | Error wrapping, sentinels, custom types, errors.Is/As |
| Review patterns | `references/preferred-patterns.md` | Code smells, over-engineering, bad Go patterns |
| Code review | `references/code-review.md` | Reviewing Go code or PRs |
| SAP CC conventions | `references/sapcc-conventions.md` | Working in sapcc/* repos with go-bits |
| Quality gate | `references/quality-gate.md` | make check, linting, pre-commit validation |

Multiple domains may apply (e.g., reviewing a PR with concurrency code → load both `code-review.md` and `concurrency.md`).

### Step 2: Load and Follow the Reference

Read via `${CLAUDE_SKILL_DIR}/references/<name>.md`. Each reference contains the full methodology, phases, code examples, and error handling. Follow its instructions directly.

### Step 3: Use Domain-Specific Sub-References

Some references point to sub-reference files:

**Testing**: `references/testing/go-test-patterns.md`, `references/testing/go-benchmark-and-concurrency.md`
**Concurrency**: `references/concurrency/concurrency-patterns.md`
**Error handling**: `references/error-handling/patterns.md`
**Review patterns**: `references/preferred-patterns/code-examples.md`
**Code review**: `references/code-review/common-review-comments.md`
**SAP CC conventions**:
- `references/sapcc-conventions/sapcc-code-patterns.md` — primary code patterns
- `references/sapcc-conventions/library-reference.md` — approved/restricted library table
- `references/sapcc-conventions/architecture-patterns.md` — 102-rule architecture spec
- `references/sapcc-conventions/review-standards-lead.md` — 21 lead review comments
- `references/sapcc-conventions/review-standards-secondary.md` — 15 secondary review comments
- `references/sapcc-conventions/preferred-patterns.md` — 20+ quality issues with BAD/GOOD examples
- `references/sapcc-conventions/extended-patterns.md` — security, K8s, PR hygiene
- Plus: `api-design-detailed.md`, `build-ci-detailed.md`, `error-handling-detailed.md`, `go-bits-philosophy-detailed.md`, `pr-mining-insights.md`, `testing-patterns-detailed.md`

**Quality gate**: `references/quality-gate/common-lint-errors.json`, `references/quality-gate/makefile-targets.json`, `references/quality-gate/expert-review-patterns.md`, `references/quality-gate/examples.md`

### Step 4: Execute

Follow the loaded reference methodology. Each reference has its own phases, gates, and completion criteria.

## Available Scripts

- **Testing**: `scripts/gen-table-test.sh`, `scripts/bench-compare.sh`
- **Error handling**: `scripts/check-errors.sh`
- **Code review**: `scripts/check-interface-compliance.sh`
- **SAP CC conventions**: `scripts/check-sapcc-identify-endpoint.sh`, `scripts/check-sapcc-auth-ordering.sh`, `scripts/check-sapcc-json-strict.sh`, `scripts/check-sapcc-time-now.sh`, `scripts/check-sapcc-httptest.sh`, `scripts/check-sapcc-todo-format.sh`
- **Quality gate**: `scripts/quality_checker.py`, `scripts/validate.py`

## Error Handling

Errors are domain-specific. Load the relevant reference file and check its Error Handling section.
