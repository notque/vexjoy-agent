---
name: go-code-review
description: |
  Go-specific code review with 6-phase methodology: Context, Automated Checks,
  Quality Analysis, Specific Analysis, Line-by-Line, Documentation. Use when
  reviewing Go code, PRs, or auditing Go codebases for quality and best practices.
  Use for "review Go", "Go PR", "check Go code", "Go quality", "review .go".
  Do NOT use for writing new Go code, debugging Go bugs, or refactoring --
  use golang-general-engineer, systematic-debugging, or systematic-refactoring
  for those tasks.
version: 2.0.0
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
command: /go-code-review
routing:
  triggers:
    - review Go
    - Go PR
    - Go code review
    - review .go
    - check Go code
    - Go quality
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - systematic-code-review
  force_routing: true
---

# Go Code Review Skill

## Operator Context

This skill operates as an operator for Go code review workflows, configuring Claude's behavior for systematic, read-only analysis of Go codebases and pull requests. It implements the **Sequential Analysis** architectural pattern -- gather context, run automated checks, analyze quality, report findings -- with **Go Domain Intelligence** embedded in every phase.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before reviewing
- **Over-Engineering Prevention**: Report issues only. Do not suggest speculative improvements or "while reviewing" refactors
- **Read-Only Mode**: NEVER modify code during review. Analyze, identify, report -- do not fix
- **All Phases Required**: Complete all 6 review phases. No skipping, no shortcuts
- **Evidence-Based Findings**: Every issue must reference file, line, and concrete impact
- **Compilation First**: Run `go build ./...` before any linting or analysis commands

### Default Behaviors (ON unless disabled)
- **Automated Checks**: Run go build, go test -race, go vet, and coverage analysis
- **Gopls MCP Analysis**: Use gopls MCP tools when available: `go_workspace` for structure, `go_file_context` for dependencies, `go_symbol_references` for impact analysis, `go_diagnostics` for build errors (fallback to grep/LSP)
- **Priority Classification**: Tag every finding as CRITICAL, HIGH, MEDIUM, or LOW
- **Structured Output**: Use the PR Review Output Template for all reports
- **Cross-Platform Build**: Verify compilation on linux, darwin, and windows
- **Module Verification**: Run go mod verify and check for tidy state

### Optional Behaviors (OFF unless enabled)
- **Security Audit**: Run gosec and perform deep security analysis
- **Benchmark Review**: Evaluate benchmark coverage for performance-critical code
- **API Compatibility Check**: Verify exported API changes against semver expectations
- **Dependency Audit**: Deep review of new or changed dependencies

## Available Scripts

- **`scripts/check-interface-compliance.sh`** — Find exported interfaces missing compile-time `var _ I = (*T)(nil)` checks. Run `bash scripts/check-interface-compliance.sh --help` for options.

## What This Skill CAN Do
- Systematically review Go code across 6 structured phases
- Run automated checks (build, test, vet, staticcheck, coverage)
- Use gopls MCP for semantic analysis (implementations, references, symbols, diagnostics, vulnerability checks)
- Classify findings by severity with actionable recommendations
- Produce structured review reports with executive summary and detailed analysis

## What This Skill CANNOT Do
- Modify, edit, or fix any code (reviewers report, they do not fix)
- Replace domain-specific skills (use go-concurrency for concurrency design, go-error-handling for error patterns)
- Skip phases or approve without completing all analysis areas
- Guarantee security (use dedicated security audit tools for compliance)

---

## Instructions

### Phase 1: Context Understanding

**Goal**: Understand what changed and why before analyzing code.

**Step 1: Review scope analysis**

```markdown
## Review: [PR/Change Title]
- Problem solved: [what]
- Expected behavior change: [what]
- Linked issues: [references]
- Testing strategy: [approach]
```

**Step 2: Change overview**
- List all modified files and packages
- Identify core changes vs supporting changes
- Note deleted code and understand why
- Check for generated or vendored code

**Gate**: Scope understood. Proceed only when clear on intent.

### Phase 2: Automated Checks

**Goal**: Run all automated tools and capture outputs.

**Step 1: Compilation and tests**

```bash
# Verify compilation across platforms
GOOS=linux go build ./...
GOOS=darwin go build ./...
GOOS=windows go build ./...

# Run tests with race detector
go test -race -count=1 -v ./...

# Run tests with coverage
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out | tail -10
```

**Step 2: Static analysis**

```bash
# Static analysis
go vet ./...
staticcheck ./...    # if available
golangci-lint run    # if available

# Module integrity
go mod verify
go mod tidy && git diff go.mod go.sum
```

**Step 3: Gopls-enhanced analysis (MUST use when available)**

**Prefer gopls MCP tools** (available when `.mcp.json` configures gopls):
```
# Detect workspace structure (MUST run first)
go_workspace

# Understand file dependencies after reading .go files (MUST use)
go_file_context({"file": "/path/to/changed_file.go"})

# Find all references before modifying any symbol (MUST use)
go_symbol_references({"file": "/path/to/interface.go", "symbol": "Handler.ServeHTTP"})

# Fuzzy search for symbols
go_search({"query": "Server"})

# Check for build/analysis errors after edits (MUST use)
go_diagnostics({"files": ["/path/to/changed_file.go"]})

# Inspect package public API
go_package_api({"packagePaths": ["example.com/internal/storage"]})
```

**Fallback (when gopls MCP unavailable)** — use LSP tool or CLI:
```bash
# LSP tool: goToDefinition, findReferences, hover, documentSymbol
# CLI fallback:
command -v gopls >/dev/null && echo "gopls available" || echo "gopls not found"
gopls implementation path/to/interface.go:42:10
gopls references path/to/changed_function.go:100:5
gopls symbols path/to/changed_file.go
```

When gopls adds value:
- Interface changes: find all implementations that need updating
- Function signature changes: find all callers that may break
- Renaming proposals: verify safe rename with `go_symbol_references` first
- Post-edit verification: `go_diagnostics` catches errors before running full test suite

Fallback: If neither gopls MCP nor CLI is available, use grep-based searches but warn about potential false positives.

**Step 4: Security checks (if optional behavior enabled)**

```bash
gosec ./...  # if available
```

**Gate**: All automated outputs captured. Proceed with analysis.

### Phase 3: Code Quality Analysis

**Goal**: Evaluate architecture, idioms, and performance.

**Architecture and Design**:
- SOLID principles followed?
- Appropriate abstraction levels?
- Clear separation of concerns?
- Dependency injection used properly?
- Interfaces focused and minimal?

**Go Idioms and Best Practices**:
- Using `any` instead of `interface{}`?
- Proper error handling with context?
- Appropriate use of pointers vs values?
- Channels used correctly?
- Context propagation proper?

**Performance Considerations**:
- Unnecessary allocations in loops?
- String concatenation in loops (use strings.Builder)?
- Improper use of defer in loops?
- Missing buffer pooling for high-frequency allocations?
- Unbuffered channels in producer-consumer patterns?

**Gate**: Quality areas assessed. Proceed to specific analysis.

### Phase 4: Specific Analysis Areas

Review each area relevant to the changed code.

**Concurrency Review**:
- Data races possible?
- Proper synchronization (mutex, channels)?
- Goroutine leaks prevented?
- Context cancellation handled?
- Deadlock potential?

**Error Handling Review**:
- All errors checked or explicitly ignored?
- Error messages provide context?
- Wrapped appropriately with %w?
- Custom error types when needed?
- Sentinel errors properly defined?

**Testing Review**:
- Test coverage adequate (aim for >80%)?
- Table-driven tests used?
- Edge cases covered?
- Error conditions tested?
- Benchmarks for performance-critical code?
- Test helpers marked with t.Helper()?
- No test interdependencies?

**Security Review**:
- Input validation present?
- SQL injection prevented?
- Path traversal prevented?
- Sensitive data not logged?
- Crypto/rand used for security-critical randomness?
- Time-constant comparisons for secrets?

**Gate**: All relevant analysis areas complete.

### Phase 5: Line-by-Line Review

**Goal**: Inspect each significant change individually.

For each significant change, ask:
1. Is the change necessary?
2. Is the implementation correct?
3. Are there edge cases missed?
4. Could this be simpler?
5. Will this be maintainable?
6. Performance implications?
7. Security implications?

**Gate**: All significant changes inspected.

### Phase 6: Documentation Review

- Package comments present and helpful?
- Public APIs documented?
- Complex algorithms explained?
- Examples provided for public APIs?
- README updated if needed?

**Gate**: Documentation assessed. Review complete. Generate report.

---

## Review Output Template

```markdown
## PR Review: [Title]

### Executive Summary
- **Risk Level**: [LOW/MEDIUM/HIGH]
- **Recommendation**: [Approve/Request Changes/Comment]
- **Key Finding**: [Most important discovery]

**Critical Positives:**
- [What was done well]

**Areas for Improvement:**
- [Issues that need attention]

### Detailed Analysis

#### 1. Architecture & Design
**Score: [A/B/C/D/F]**
- [pass/fail] Modern Go patterns
- [pass/fail] Proper package structure
- [pass/fail] Interface design
- [pass/fail] SOLID principles

#### 2. Code Quality
**Score: [A/B/C/D/F]**
[Code snippets showing excellent patterns and improvements needed]

#### 3. Testing Strategy
**Score: [A/B/C/D/F]**
Coverage: X%, Target: 80%+, Gaps: [areas needing tests]

#### 4. Security & Performance
**Score: [A/B/C/D/F]**

### Specific Issues

**[CRITICAL]** Issue Title
- **File**: `path/to/file.go:123`
- **Problem**: [Explanation]
- **Impact**: [What could go wrong]
- **Fix**: [How to fix]

**[HIGH/MEDIUM/LOW]** Issue Title
- **File**: `path/to/file.go:456`
- **Details**: [Explanation]
- **Suggestion**: [Improvement]

### Recommendations
1. **Must Fix Before Merge**: [Critical issues]
2. **Should Address**: [Important improvements]
3. **Consider for Future**: [Nice to have]

### Final Assessment
[Summary with actionable next steps]
```

---

## Review Priority Guidelines

**CRITICAL (Block Merge)**: Security vulnerabilities, data corruption risks, race conditions, memory leaks, breaking API changes, missing critical tests.

**HIGH (Should Fix)**: Performance regressions, error handling gaps, concurrency issues, missing error context, inadequate test coverage.

**MEDIUM (Recommend)**: Code style inconsistencies, missing documentation, suboptimal patterns, minor performance improvements.

**LOW (Suggest)**: Naming improvements, code organization, additional examples, future refactoring opportunities.

---

## Death Loop Prevention

NEVER make changes that cause compilation failures during review:

1. **Channel Direction Changes**: NEVER change `chan Type` to `<-chan Type` without verifying the function does not send or close
2. **Function Signature Changes**: NEVER change return types without updating ALL call sites
3. **Compilation Before Linting**: Run `go build ./...` FIRST. If code does not compile, report compilation errors before linting issues

---

## Error Handling

### Error: "Automated Tool Not Available"
Cause: staticcheck, golangci-lint, gosec, or gopls not installed
Solution:
1. Check tool availability with `command -v`
2. Proceed with available tools (go build, go test, go vet are always present)
3. Note in report which tools were unavailable
4. Use grep-based fallback for gopls queries (warn about false positives)

### Error: "Tests Fail on Current Code"
Cause: Tests were already broken before the PR changes
Solution:
1. Run tests on the base branch to confirm pre-existing failures
2. Distinguish between pre-existing failures and newly introduced ones
3. Report new failures as findings; note pre-existing as context

### Error: "Cannot Determine Change Scope"
Cause: No clear PR description, unclear commit messages, or large diff
Solution:
1. Read all changed files to infer intent
2. Check commit messages for context
3. Ask the user to clarify the change scope before proceeding

---

## Anti-Patterns

### Anti-Pattern 1: Fixing Code During Review
**What it looks like**: Opening Edit tool to "quickly fix" a found issue
**Why wrong**: Reviewer role is read-only. Fixing bypasses author ownership and testing.
**Do instead**: Report the issue with file, line, impact, and suggested fix in the report.

### Anti-Pattern 2: Skipping Automated Checks
**What it looks like**: "I can see the code is fine, no need to run tests"
**Why wrong**: Visual inspection misses race conditions, compilation errors, and edge cases.
**Do instead**: Run ALL Phase 2 checks regardless of how "simple" the change looks.

### Anti-Pattern 3: Severity Downgrading to Avoid Conflict
**What it looks like**: Marking a logic bug as LOW because "the author will be upset"
**Why wrong**: Severity is objective, not social. Logic bugs are HIGH or CRITICAL.
**Do instead**: Classify severity honestly based on impact, not author relationship.

### Anti-Pattern 4: Approving Small PRs Without Full Review
**What it looks like**: "It's only 10 lines, LGTM"
**Why wrong**: Small changes cause large bugs. Config changes affect runtime behavior.
**Do instead**: Complete all 6 phases regardless of PR size.

### Anti-Pattern 5: Reviewing Only Changed Lines
**What it looks like**: Ignoring surrounding context of the changed code
**Why wrong**: Changes may break invariants or assumptions in adjacent code.
**Do instead**: Read enough surrounding context to understand the full impact.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization: Review](../shared-patterns/anti-rationalization-review.md) - Review-specific rationalization prevention
- [Anti-Rationalization: Core](../shared-patterns/anti-rationalization-core.md) - Universal shortcut prevention
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Severity Classification](../shared-patterns/severity-classification.md) - Issue severity standards

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Tests pass, must be fine" | Tests can be incomplete or wrong | Review test coverage and quality too |
| "Small PR, quick review" | Small changes cause big bugs | Full 6-phase review regardless of size |
| "Author explained the logic" | Explanation does not equal correctness | Verify the code itself |
| "Just a refactor" | Refactors change behavior subtly | Verify behavior preserved with tests |
| "Trusted author" | Everyone makes mistakes | Same rigor for all authors |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/common-review-comments.md`: Go code patterns with good/bad examples for error handling, concurrency, and testing
