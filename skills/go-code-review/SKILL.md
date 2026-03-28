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
  force_route: true
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
---

# Go Code Review Skill

Systematic, read-only analysis of Go codebases and pull requests across 6 structured phases. Every phase is mandatory because small changes cause large bugs and skipping phases misses race conditions, compilation errors, and edge cases that visual inspection alone cannot catch. This skill gathers context, runs automated checks, analyzes quality, and reports findings -- it never modifies code.

## Available Scripts

- **`scripts/check-interface-compliance.sh`** -- Find exported interfaces missing compile-time `var _ I = (*T)(nil)` checks. Run `bash scripts/check-interface-compliance.sh --help` for options.

## Instructions

### Phase 1: Context Understanding

**Goal**: Understand what changed and why before analyzing code.

**Step 1: Read project conventions**

Read the repository CLAUDE.md first because project conventions override default review expectations. Note any project-specific linting rules, naming conventions, or architectural decisions that should inform the review.

**Step 2: Review scope analysis**

Complete all 6 phases regardless of PR size because small changes cause large bugs and config changes affect runtime behavior.

```markdown
## Review: [PR/Change Title]
- Problem solved: [what]
- Expected behavior change: [what]
- Linked issues: [references]
- Testing strategy: [approach]
```

Do not shortcut scope analysis based on author reputation because everyone makes mistakes and the same rigor must apply to all authors.

**Step 3: Change overview**
- List all modified files and packages
- Identify core changes vs supporting changes
- Note deleted code and understand why
- Check for generated or vendored code

Read enough surrounding context to understand the full impact because changes may break invariants or assumptions in adjacent code.

**Gate**: Scope understood. Proceed only when clear on intent.

### Phase 2: Automated Checks

**Goal**: Run all automated tools and capture outputs. Run every check listed here regardless of how "simple" the change looks because visual inspection misses race conditions, compilation errors, and edge cases.

**Step 1: Compilation (run first)**

Run `go build ./...` before any linting or analysis because compilation errors invalidate all downstream analysis and linter output becomes noise against broken code.

```bash
# Verify compilation across platforms because cross-platform bugs
# are invisible on a single OS
GOOS=linux go build ./...
GOOS=darwin go build ./...
GOOS=windows go build ./...
```

**Step 2: Tests and coverage**

```bash
# Run tests with race detector
go test -race -count=1 -v ./...

# Run tests with coverage
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out | tail -10
```

**Step 3: Static analysis and module integrity**

```bash
# Static analysis
go vet ./...
staticcheck ./...    # if available
golangci-lint run    # if available

# Module integrity
go mod verify
go mod tidy && git diff go.mod go.sum
```

**Step 4: Gopls-enhanced analysis (use when available)**

Prefer gopls MCP tools (available when `.mcp.json` configures gopls) because they provide semantic analysis that grep-based searches cannot:
```
# Detect workspace structure (run first)
go_workspace

# Understand file dependencies after reading .go files
go_file_context({"file": "/path/to/changed_file.go"})

# Find all references before assessing symbol impact
go_symbol_references({"file": "/path/to/interface.go", "symbol": "Handler.ServeHTTP"})

# Fuzzy search for symbols
go_search({"query": "Server"})

# Check for build/analysis errors
go_diagnostics({"files": ["/path/to/changed_file.go"]})

# Inspect package public API
go_package_api({"packagePaths": ["example.com/internal/storage"]})
```

Fallback (when gopls MCP unavailable) -- use LSP tool or CLI:
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

If neither gopls MCP nor CLI is available, use grep-based searches but warn about potential false positives in the report.

**Step 5: Security checks (optional -- run when security audit is requested)**

```bash
gosec ./...  # if available
```

**Gate**: All automated outputs captured. Proceed with analysis.

### Phase 3: Code Quality Analysis

**Goal**: Evaluate architecture, idioms, and performance. Do not suggest speculative improvements or "while reviewing" refactors because the reviewer role is to identify real issues, not propose hypothetical enhancements.

**Architecture and Design**:
- SOLID principles followed?
- Appropriate abstraction levels?
- Clear separation of concerns?
- Dependency injection used properly?
- Interfaces focused and minimal?

Treat refactors with the same scrutiny as new code because refactors change behavior subtly and require test verification that behavior is preserved.

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

Review each area relevant to the changed code. Enable optional analysis (benchmarks, API compatibility, dependency audit) when the PR scope warrants it.

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

Do not accept passing tests as sufficient evidence of correctness because tests can be incomplete or wrong -- review test coverage and quality alongside pass/fail status.

**Security Review**:
- Input validation present?
- SQL injection prevented?
- Path traversal prevented?
- Sensitive data not logged?
- Crypto/rand used for security-critical randomness?
- Time-constant comparisons for secrets?

**Gate**: All relevant analysis areas complete.

### Phase 5: Line-by-Line Review

**Goal**: Inspect each significant change individually. NEVER modify code during review because the reviewer role is read-only -- analyze, identify, report, but do not fix. Fixing bypasses author ownership and testing.

For each significant change, ask:
1. Is the change necessary?
2. Is the implementation correct?
3. Are there edge cases missed?
4. Could this be simpler?
5. Will this be maintainable?
6. Performance implications?
7. Security implications?

Every issue must reference file, line, and concrete impact because evidence-based findings are actionable while vague observations are not. Do not accept author explanations at face value -- verify the code itself because explanation does not equal correctness.

Tag every finding with a severity level (CRITICAL, HIGH, MEDIUM, LOW) because priority classification drives merge decisions. Classify severity honestly based on impact, not author relationship, because severity is objective and downgrading to avoid conflict misrepresents risk.

**Gate**: All significant changes inspected.

### Phase 6: Documentation and Report

**Goal**: Assess documentation and produce the structured review report.

- Package comments present and helpful?
- Public APIs documented?
- Complex algorithms explained?
- Examples provided for public APIs?
- README updated if needed?

Use the Review Output Template below for all reports because structured output ensures consistent, actionable review deliverables.

**Gate**: Documentation assessed. Review complete. Generate report.

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

## Review Priority Guidelines

**CRITICAL (Block Merge)**: Security vulnerabilities, data corruption risks, race conditions, memory leaks, breaking API changes, missing critical tests.

**HIGH (Should Fix)**: Performance regressions, error handling gaps, concurrency issues, missing error context, inadequate test coverage.

**MEDIUM (Recommend)**: Code style inconsistencies, missing documentation, suboptimal patterns, minor performance improvements.

**LOW (Suggest)**: Naming improvements, code organization, additional examples, future refactoring opportunities.

## Error Handling

### Death Loop Prevention

NEVER make changes that cause compilation failures during review:

1. **Channel Direction Changes**: NEVER change `chan Type` to `<-chan Type` without verifying the function does not send or close
2. **Function Signature Changes**: NEVER change return types without updating ALL call sites
3. **Compilation Before Linting**: Run `go build ./...` FIRST. If code does not compile, report compilation errors before linting issues

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

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/common-review-comments.md`: Go code patterns with good/bad examples for error handling, concurrency, and testing
