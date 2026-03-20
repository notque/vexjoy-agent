---
name: systematic-code-review
description: |
  4-phase code review methodology: UNDERSTAND changes, VERIFY claims against
  code, ASSESS security/performance/architecture risks, DOCUMENT findings with
  severity classification. Use when reviewing pull requests, auditing code
  before release, evaluating external contributions, or pre-merge verification.
  Use for "review PR", "code review", "audit code", "check this PR", or
  "review my changes". Do NOT use for writing new code or implementing features.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Systematic Code Review Skill

## Operator Context

This skill operates as an operator for systematic code review, configuring Claude's behavior for thorough, verifiable review processes. It implements the **Iterative Refinement** architectural pattern — understand context, verify claims, assess risks, document findings — with **Domain Intelligence** embedded in severity classification and Go-specific review patterns.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before executing review
- **Over-Engineering Prevention**: Don't suggest features outside PR scope, but DO flag all issues IN the changed code even if fixing them requires touching other files. No speculative improvements.
- **Strict Severity Classification**: Use the Severity Classification Rules below. When in doubt, classify UP not down.
- **NEVER approve without running tests**: Review must include test execution
- **NEVER trust comments without verification**: All claims must be verified against code
- **NEVER skip security assessment**: Security implications must be explicitly evaluated
- **Complete phase gates**: Each phase must complete before proceeding

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative
- **Temporary File Cleanup**: Remove any temporary analysis files, notes, or debug outputs created during review at task completion. Keep only the final review document
- **Read all changed files**: Don't review summaries, read actual code
- **Check affected dependencies**: Identify ripple effects
- **Verify test coverage**: Confirm tests exist for changes
- **Document all findings**: Create structured review output

### Optional Behaviors (OFF unless enabled)
- **Performance profiling**: Benchmark affected code paths
- **Historical analysis**: Check for similar past issues
- **Extended security audit**: Deep security analysis beyond standard checks

## What This Skill CAN Do
- Systematic phase-gated reviews with explicit gates between phases
- Severity classification (BLOCKING / SHOULD FIX / SUGGESTION) with decision tree
- Security, performance, and architecture risk assessment
- Go-specific pattern detection (concurrency, resource management, type exports)
- Go ecosystem pattern validation
- Receiving review feedback patterns (when acting as code author)

## What This Skill CANNOT Do
- Write implementation code or implement features
- Skip phases or bypass phase gates
- Approve without running tests
- Review without reading all changed files
- Make speculative improvements outside PR scope

---

## Instructions

### Phase 1: UNDERSTAND

**Goal**: Map all changes and their relationships before forming any opinions.

**Step 1: Read every changed file**
- Use Read tool on EVERY changed file completely
- Map what each file does and how changes affect it

**Step 2: Identify dependencies**
- Use Grep to find all callers/consumers of changed code
- Note any comments that make claims about behavior

**Step 2a: Caller Tracing** (mandatory when diff modifies function signatures, parameter semantics, or introduces sentinel/special values)

When the change modifies how a function/method is called or what parameters mean:

1. **Find ALL callers** — Grep for the function name with receiver syntax (e.g., `.GetEvents(` not just `GetEvents`) across the entire repo. For Go repos, prefer gopls `go_symbol_references` via ToolSearch("gopls") — it's type-aware and catches interface implementations.
2. **Trace the VALUE SPACE** — For each parameter source, classify what values can flow through:
   - Query parameters (`r.FormValue`, `r.URL.Query`): user-controlled — ANY string including sentinel values like `"*"`
   - Auth token fields: server-controlled (UUIDs, structured IDs)
   - Constants/enums: fixed set
   - Do NOT conclude a sentinel is "unreachable" because no Go code constructs that string. If the source is user input, the user constructs it.
3. **Verify each caller** — For each call site, check that parameters are validated before being passed. Pay special attention to sentinel values (e.g., `"*"` meaning "all/unfiltered") that bypass security filtering.
4. **Report unvalidated paths** — Any caller that passes user input to a security-sensitive parameter without validation is a BLOCKING finding.
5. **Do NOT trust PR descriptions** about who calls the function — verify independently. The PR author may have forgotten about callers, or new callers may have been added in other branches.

This step catches:
- Unchecked paths where user input reaches a security-sensitive parameter
- Callers the PR author forgot about or didn't mention
- Interface implementations that don't enforce the same preconditions

**Step 3: Document scope**

```
PHASE 1: UNDERSTAND

Changed Files:
  - [file1.ext]: [+N/-M lines] [brief description of change]
  - [file2.ext]: [+N/-M lines] [brief description of change]

Change Type: [feature | bugfix | refactor | config | docs]

Scope Assessment:
  - Primary: [what's directly changed]
  - Secondary: [what's affected by the change]
  - Dependencies: [external systems/files impacted]

Caller Tracing (if signature/parameter semantics changed):
  - [function/method]: [N] callers found
    - [caller1:line] — parameter validated: [yes/no]
    - [caller2:line] — parameter validated: [yes/no]
  - Unvalidated paths: [list or "none"]

Questions for Author:
  - [Any unclear aspects that need clarification]
```

**Gate**: All changed files read, scope fully mapped, callers traced (if applicable). Proceed only when gate passes.

### Phase 2: VERIFY

**Goal**: Validate all assertions in code, comments, and PR description against actual behavior.

**Step 1: Run tests**
- Execute existing tests for changed files
- Capture complete test output

**Step 2: Verify claims**
- Check every comment claim against code behavior
- Verify edge cases mentioned are actually handled
- Trace through critical code paths manually

**Step 3: Document verification**

```
PHASE 2: VERIFY

Claims Verification:
  Claim: "[Quote from comment or PR description]"
  Verification: [How verified - test run, code trace, etc.]
  Result: VALID | INVALID | NEEDS-DISCUSSION

Test Execution:
  $ [test command]
  Result: [PASS/FAIL with summary]

Behavior Verification:
  - Expected: [what change claims to do]
  - Actual: [what code actually does]
  - Match: YES | NO | PARTIAL
```

**Gate**: All assertions in code/comments verified against actual behavior. Proceed only when gate passes.

### Phase 3: ASSESS

**Goal**: Evaluate security, performance, and architectural risks specific to these changes.

**Step 1: Security assessment**
- Evaluate OWASP top 10 against changes
- Explain HOW each vulnerability was ruled out (not just checkboxes)

**Step 2: Performance assessment**
- Identify performance-critical paths and evaluate impact
- Check for N+1 queries, unbounded loops, unnecessary allocations

**Step 3: Architectural assessment**
- Compare patterns to existing codebase conventions
- Assess breaking change potential

**Step 4: Extraction severity escalation**
- If the diff extracts inline code into named helper functions, re-evaluate all defensive guards
- A missing check rated LOW as inline code (1 caller, "upstream validates") becomes MEDIUM as a reusable function (N potential callers)
- See `skills/shared-patterns/severity-classification.md` for the full rule

**Step 4: Document assessment**

```
PHASE 3: ASSESS

Security Assessment:
  SQL Injection: [N/A | CHECKED - how verified | ISSUE - details]
  XSS: [N/A | CHECKED - how verified | ISSUE - details]
  Input Validation: [N/A | CHECKED - how verified | ISSUE - details]
  Auth: [N/A | CHECKED - how verified | ISSUE - details]
  Secrets: [N/A | CHECKED - how verified | ISSUE - details]
  Findings: [specific issues or "No security issues found"]

Performance Assessment:
  Findings: [specific issues or "No performance issues found"]

Architectural Assessment:
  Findings: [specific issues or "Architecturally sound"]

Risk Level: LOW | MEDIUM | HIGH | CRITICAL
```

**Gate**: Security, performance, and architectural risks explicitly evaluated. Proceed only when gate passes.

### Phase 4: DOCUMENT

**Goal**: Produce structured review output with clear verdict and rationale.

```
PHASE 4: DOCUMENT

Review Summary:
  Files Reviewed: [N]
  Lines Changed: [+X/-Y]
  Test Status: [PASS/FAIL/SKIPPED]
  Risk Level: [LOW/MEDIUM/HIGH/CRITICAL]

Findings (use Severity Classification Rules - when in doubt, classify UP):

BLOCKING (cannot merge - security/correctness/reliability):
  1. [Issue with file:line reference and category from rules]

SHOULD FIX (fix unless urgent - patterns/tests/debugging):
  1. [Issue with file:line reference and category from rules]

SUGGESTIONS (author's choice - purely stylistic):
  1. [Suggestion with benefit - only if genuinely optional]

POSITIVE NOTES:
  1. [Good practice observed]

Verdict: APPROVE | REQUEST-CHANGES | NEEDS-DISCUSSION

Rationale: [1-2 sentences explaining verdict]
```

**Gate**: Structured review output with clear verdict. Review is complete.

---

## Trust Hierarchy

When conflicting information exists, trust in this order:

1. **Running code** (highest) - What tests show
2. **HTTP/API requests** - Verified external behavior
3. **Grep results** - What exists in codebase
4. **Reading source** - Direct file inspection
5. **Comments/docs** - Claims that need verification
6. **PR description** (lowest) - May be outdated or incomplete

## Severity Classification Rules

**Guiding principle**: When in doubt, classify UP. It's better to require a fix and have the author push back than to let a real issue slip through as "optional."

### BLOCKING (cannot merge without fixing)

These issues MUST be fixed. Never mark these as "needs discussion" or "optional":

| Category | Examples |
|----------|----------|
| **Security vulnerabilities** | Authentication bypass, injection (SQL/XSS/command), data exposure, secrets in code, missing authorization checks |
| **Test failures** | Any failing test, including pre-existing failures touched by the change |
| **Breaking changes** | API breaking without migration, backward incompatible changes without versioning |
| **Missing error handling** | Unhandled errors on network/filesystem/database operations, panics in production paths |
| **Race conditions** | Concurrent access without synchronization, data races |
| **Resource leaks** | Unclosed file handles, database connections, memory leaks in hot paths |
| **Logic errors** | Off-by-one errors, incorrect conditionals, wrong return values |

### SHOULD FIX (merge only if urgent, otherwise fix)

These issues should be fixed unless there's time pressure. Never mark as "suggestion":

| Category | Examples |
|----------|----------|
| **Missing tests** | New code paths without test coverage, untested error conditions |
| **Unhelpful error messages** | Errors that don't include context for debugging (missing IDs, states, inputs) |
| **Pattern violations** | Inconsistent with established codebase patterns (but still functional) |
| **Performance in hot paths** | N+1 queries, unnecessary allocations in loops, missing indexes for frequent queries |
| **Deprecated API usage** | Using APIs marked for removal, outdated patterns with better alternatives |
| **Poor encapsulation** | Exposing internal state unnecessarily, breaking abstraction boundaries |

### SUGGESTIONS (author's choice)

These are genuinely optional - author can reasonably decline:

| Category | Examples |
|----------|----------|
| **Naming preferences** | Variable/function names that are adequate but could be clearer |
| **Comment additions** | Places where a comment would help but code is understandable |
| **Alternative approaches** | Different implementation that isn't clearly better |
| **Style not in CLAUDE.md** | Formatting preferences not codified in project standards |
| **Micro-optimizations** | Performance improvements in cold paths with no measurable impact |

### Classification Decision Tree

```
Is there a security, correctness, or reliability risk?
|- YES -> BLOCKING
|- NO -> Does it violate established patterns or create maintenance burden?
          |- YES -> SHOULD FIX
          |- NO -> Is this purely stylistic or preferential?
                   |- YES -> SUGGESTION (or don't mention)
                   |- NO -> Re-evaluate: probably SHOULD FIX
```

### Common Misclassifications to Avoid

| Issue | Wrong | Correct | Why |
|-------|-------|---------|-----|
| Missing error check on `os.Open()` | SUGGESTION | BLOCKING | Resource leak + potential panic |
| No test for new endpoint | SUGGESTION | SHOULD FIX | Untested code is liability |
| Race condition in cache | NEEDS DISCUSSION | BLOCKING | Data corruption risk |
| Inconsistent naming | BLOCKING | SUGGESTION | No functional impact |
| Missing context in error | SUGGESTION | SHOULD FIX | Debugging nightmare |
| Unused import | BLOCKING | SHOULD FIX | Linter will catch, low impact |

---

## Examples

### Example 1: Pull Request Review
User says: "Review this PR"
Actions:
1. Read all changed files, map scope and dependencies (UNDERSTAND)
2. Run tests, verify claims in comments and PR description (VERIFY)
3. Evaluate security/performance/architecture risks (ASSESS)
4. Produce structured findings with severity and verdict (DOCUMENT)
Result: Structured review with clear verdict and rationale

### Example 2: Pre-Merge Verification
User says: "Check this before we merge"
Actions:
1. Read all changes, identify breaking change potential (UNDERSTAND)
2. Run full test suite, verify backward compatibility claims (VERIFY)
3. Assess risk level for production deployment (ASSESS)
4. Document findings with APPROVE/REQUEST-CHANGES verdict (DOCUMENT)
Result: Go/no-go decision with evidence

---

## Error Handling

### Error: "Incomplete Information"
Cause: Missing context about the change or its purpose
Solution:
1. Ask for clarification in Phase 1
2. Do not proceed past UNDERSTAND with unanswered questions
3. Document gaps in scope assessment

### Error: "Test Failures"
Cause: Tests fail during Phase 2 verification
Solution:
1. Document in Phase 2
2. Automatic BLOCKING finding in Phase 4
3. Cannot APPROVE with failing tests

### Error: "Unclear Risk"
Cause: Cannot determine severity of an issue
Solution:
1. Default to higher risk level (classify UP)
2. Document uncertainty in assessment
3. REQUEST-CHANGES if critical uncertainty exists

---

## Anti-Patterns

### Anti-Pattern 1: Reviewing Without Running Tests

**What it looks like**: "I reviewed the code and it looks good. The logic seems correct."
**Why wrong**: Comments and code may not match actual behavior. Tests reveal edge cases not visible in code reading. Cannot verify claims without execution.
**Do instead**: Run tests in Phase 2. Show complete test output. Verify behavior matches claims.

### Anti-Pattern 2: Accepting Comments as Truth

**What it looks like**: Marking claims as verified just because a comment says so.
**Why wrong**: Comments frequently become outdated. Developers may not understand what "thread-safe" actually means. Claims need verification against actual code.
**Do instead**: Inspect code for every claim. Verify "thread-safe" means mutexes exist. Mark INVALID when comments lie.

### Anti-Pattern 3: Skipping Phase Gates

**What it looks like**: Reading 2 of 5 changed files and saying "I get the gist, moving to VERIFY..."
**Why wrong**: Missing context leads to incorrect conclusions. Dependencies between files may be missed. Cannot assess full impact without complete understanding.
**Do instead**: Read ALL changed files. Complete every gate before proceeding.

### Anti-Pattern 4: Generic Security Checklist Without Context

**What it looks like**: Checking all security boxes without explaining how vulnerabilities were ruled out.
**Why wrong**: Checkbox approach misses context-specific vulnerabilities. Gives false confidence without actual analysis.
**Do instead**: Explain HOW each vulnerability was ruled out. Mark N/A for irrelevant checks. Show evidence for findings.

---

## Go-Specific Review Patterns

When reviewing Go code, watch for these patterns that linters miss:

### Type Export Design
- [ ] Are implementation types unnecessarily exported?
- [ ] Should types be unexported with only constructors exported?
- **Red flag**: `type FooStore struct{}` exported but only implements an interface

### Concurrency Patterns
- [ ] Does batch+callback pattern protect against concurrent writes?
- [ ] Does `commit()` only remove specific items, not clear all?
- [ ] Are loop variables using outdated patterns? (Go 1.22+ doesn't need cloning)
  - [ ] No `i := i` reassignment inside loops
  - [ ] No closure arguments for loop variables: `go func(id int) { }(i)`
- **Red flag**: `s.events = nil` in commit callback
- **Red flag**: `go func(x int) { ... }(loopVar)` - closure argument unnecessary since Go 1.22

### Resource Management
- [ ] Is `defer f.Close()` placed AFTER error check?
- [ ] Are database connection pools shared, not duplicated?
- [ ] Is file traversal done once, not repeated for size calculation?
- **Red flag**: `defer f.Close()` immediately after `os.OpenFile()`

### Metrics & Observability
- [ ] Are Prometheus counter metrics pre-initialized with `.Add(0)`?
- [ ] Are all known label combinations initialized at startup?
- **Red flag**: CounterVec registered but not initialized

### Testing Patterns
- [ ] Are interface implementation tests deduplicated?
- [ ] Do tests use `assert.Equal` (no reflection) for comparable types?
- [ ] Does test setup use `prometheus.NewPedanticRegistry()`?
- **Red flag**: Copy-pasted tests for FileStore, MemoryStore, SQLStore

### Code Organization
- [ ] Is function extraction justified (reuse or complexity hiding)?
- [ ] Are unnecessary helper functions wrapping stdlib calls?
- **Red flag**: Helper that just calls through to another function

## Organization Library Ecosystem Patterns

When reviewing projects that use shared organization libraries, apply these additional checks:

### Library Usage
- [ ] Are optional fields using the organization's preferred option type?
- [ ] Is SQL iteration using helper functions instead of manual `rows.Next()` loops?
- [ ] Are tests using the organization's assertion helpers?
- **Red flag**: Manual SQL row iteration with defer/Next/Scan/Err pattern when helpers exist

### Test Assertions
- [ ] Is the correct assertion function used for the type being compared?
- [ ] Is deep comparison only used for non-comparable types (slices, maps, structs)?
- **Red flag**: Deep comparison used for simple types like int, string, bool

### Test Infrastructure
- [ ] Are DB tests using the organization's test database helpers?
- [ ] Are Prometheus tests using `NewPedanticRegistry()`?
- **Red flag**: Raw `sql.Open()` in test setup instead of test helpers

### Dead Code
- [ ] Are there leftover `*_migration.sql` files without usage?
- [ ] Are there helper functions that just wrap single stdlib calls?
- [ ] Are there redundant checks (e.g., empty string check before regex)?
- **Red flag**: Wrapper functions that add no value over the underlying call

### Database Naming
- [ ] Do functions using database-specific syntax indicate this in names?
- **Red flag**: Generic `SQLStoreFactory` that uses database-specific syntax

---

## Receiving Review Feedback

When YOU are the one receiving code review feedback (not giving it), apply these patterns:

### The Reception Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

### No Performative Agreement

**NEVER:**
- "You're absolutely right!"
- "Great point!" / "Excellent feedback!"
- "Thanks for catching that!"

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

**When feedback IS correct:**
```
"Fixed. [Brief description of what changed]"
"Good catch - [specific issue]. Fixed in [location]."
[Just fix it and show in the code]
```

### YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

### Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
Reviewer: "Fix items 1-6"
You understand 1,2,3,6. Unclear on 4,5.

WRONG: Implement 1,2,3,6 now, ask about 4,5 later
RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

### When to Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code

**Example:**
```
Reviewer: "Remove legacy code"
WRONG: "You're absolutely right! Let me remove that..."
RIGHT: "Checking... build target is 10.15+, this API needs 13+. Need legacy for backward compat. Fix bundle ID or drop pre-13 support?"
```

### Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions
```

### External vs Internal Reviewers

**From external reviewers:**
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I investigate/proceed?"
```

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Anti-Rationalization (Review)](../shared-patterns/anti-rationalization-review.md) - Review-specific rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Severity Classification](../shared-patterns/severity-classification.md) - Issue severity definitions

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Code looks correct to me" | Visual inspection misses runtime issues | Run tests in Phase 2 |
| "Comment says it's thread-safe" | Comments can be wrong or outdated | Verify claims against code |
| "Only a small change" | Small changes cause large regressions | Complete all 4 phases |
| "Tests pass, ship it" | Tests may not cover the changed paths | Verify coverage of changes |
