---
name: systematic-code-review
description: "4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - "review code"
    - "code review methodology"
    - "structured review"
    - "code audit"
    - "review methodology"
    - "comprehensive review"
  category: code-review
---

# Systematic Code Review Skill

Systematic 4-phase code review: UNDERSTAND changes, VERIFY claims against actual behavior, ASSESS security/performance/architecture risks, DOCUMENT findings with severity classification. Each phase has an explicit gate that must pass before proceeding because skipping phases causes missed context, incorrect conclusions, and incomplete risk assessment.

## Instructions

### Phase 1: UNDERSTAND

**Goal**: Map all changes and their relationships before forming any opinions.

**Step 1: Read CLAUDE.md**
- Read and follow repository CLAUDE.md files first because project conventions override default review criteria and may define custom severity rules, approved patterns, or scope constraints.

**Step 2: Read every changed file**
- Use Read tool on EVERY changed file completely because reviewing summaries or reading partial files misses dependencies between changes and leads to incorrect conclusions.
- Map what each file does and how changes affect it.
- Check affected dependencies and identify ripple effects because changes in one file can break consumers that aren't in the diff.

**Step 3: Identify dependencies**
- Use Grep to find all callers/consumers of changed code.
- Note any comments that make claims about behavior (these are claims to verify in Phase 2, not facts to trust).

**Step 3a: Caller Tracing** (mandatory when diff modifies function signatures, parameter semantics, or introduces sentinel/special values)

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

**Step 4: Document scope**

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

**Gate**: All changed files read (not just some — reading 2 of 5 files and saying "I get the gist" fails this gate), scope fully mapped, callers traced (if applicable). Proceed only when gate passes.

### Phase 2: VERIFY

**Goal**: Validate all assertions in code, comments, and PR description against actual behavior.

**Step 1: Run tests**
- Execute existing tests for changed files because review cannot approve without test execution — visual inspection misses runtime issues that tests catch.
- Capture complete test output. Show the output rather than describing it because facts outweigh narrative.
- Verify test coverage: confirm tests exist for the changed code paths because untested code paths are a SHOULD FIX finding.

**Step 2: Verify claims**
- Check every comment claim against code behavior because comments frequently become outdated and developers may not understand what "thread-safe" actually means — never accept a comment as truth without inspecting the code that backs it.
- Verify edge cases mentioned are actually handled.
- Trace through critical code paths manually.

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

**Gate**: All assertions in code/comments verified against actual behavior. Tests executed with output captured. Proceed only when gate passes.

### Phase 3: ASSESS

**Goal**: Evaluate security, performance, and architectural risks specific to these changes.

**Step 1: Security assessment**
- Never skip this step because security implications must be explicitly evaluated for every review, even when changes appear benign.
- Evaluate OWASP top 10 against changes.
- Explain HOW each vulnerability was ruled out (not just checkboxes) because a checkbox approach misses context-specific vulnerabilities and gives false confidence.
- If optionally enabled: perform extended deep security analysis beyond standard checks.

**Step 2: Performance assessment**
- Identify performance-critical paths and evaluate impact.
- Check for N+1 queries, unbounded loops, unnecessary allocations.
- If optionally enabled: benchmark affected code paths with profiling.

**Step 3: Architectural assessment**
- Compare patterns to existing codebase conventions.
- Assess breaking change potential.
- If optionally enabled: check for similar past issues via historical analysis.

**Step 4: Extraction severity escalation**
- If the diff extracts inline code into named helper functions, re-evaluate all defensive guards.
- A missing check rated LOW as inline code (1 caller, "upstream validates") becomes MEDIUM as a reusable function (N potential callers).

**Step 5: Document assessment**

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

**Gate**: Security, performance, and architectural risks explicitly evaluated (not skipped or hand-waved). Proceed only when gate passes.

### Phase 4: DOCUMENT

**Goal**: Produce structured review output with clear verdict and rationale.

Report facts without self-congratulation. Show command output rather than describing it. Be concise but informative because the review consumer needs actionable findings, not commentary.

Only flag issues within the scope of the changed code because suggesting features outside PR scope is over-engineering — but DO flag all issues IN the changed code even if fixing them requires touching other files. No speculative improvements.

When classifying severity, use the Severity Classification Rules below and classify UP when in doubt because it is better to require a fix and have the author push back than to let a real issue slip through as "optional."

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

After producing the review, remove any temporary analysis files, notes, or debug outputs created during review because only the final review document should persist.

**Gate**: Structured review output with clear verdict. Review is complete.

---

## Reference Material

### Trust Hierarchy

When conflicting information exists, trust in this order:

1. **Running code** (highest) - What tests show
2. **HTTP/API requests** - Verified external behavior
3. **Grep results** - What exists in codebase
4. **Reading source** - Direct file inspection
5. **Comments/docs** - Claims that need verification
6. **PR description** (lowest) - May be outdated or incomplete

### Severity Classification Rules

Three tiers: BLOCKING (cannot merge — security, correctness, reliability), SHOULD FIX (fix unless urgent — patterns, tests, debugging), SUGGESTIONS (genuinely optional — style, naming, micro-optimizations). When in doubt, classify UP.

See `references/severity-classification.md` for full classification tables, the decision tree, and common misclassification examples.

### Go-Specific Review Patterns

Watch for patterns that linters miss: type export design, concurrency patterns (batch+callback, loop variable capture, commit callbacks), resource management (defer placement, connection pool reuse), metrics pre-initialization, testing deduplication, and unnecessary function extraction.

For projects using shared organization libraries: check for manual SQL row iteration instead of helpers, incorrect assertion depth, raw `sql.Open()` in tests, dead migration files, and database-specific naming violations.

See `references/go-review-patterns.md` for full checklists and red flags.

### Receiving Review Feedback

When receiving feedback: read completely, restate requirement to confirm understanding, verify against codebase, evaluate technical soundness, respond with reasoning or just fix it. Never performative agreement. Apply YAGNI check before implementing "proper" features. Stop and clarify before implementing anything unclear — items may be related.

See `references/receiving-feedback.md` for the full reception pattern, pushback examples, implementation order, and external vs internal reviewer handling.

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

## References

### Examples

#### Example 1: Pull Request Review
User says: "Review this PR"
Actions:
1. Read CLAUDE.md, then read all changed files, map scope and dependencies (UNDERSTAND)
2. Run tests, verify claims in comments and PR description (VERIFY)
3. Evaluate security/performance/architecture risks (ASSESS)
4. Produce structured findings with severity and verdict (DOCUMENT)
Result: Structured review with clear verdict and rationale

#### Example 2: Pre-Merge Verification
User says: "Check this before we merge"
Actions:
1. Read CLAUDE.md, then read all changes, identify breaking change potential (UNDERSTAND)
2. Run full test suite, verify backward compatibility claims (VERIFY)
3. Assess risk level for production deployment (ASSESS)
4. Document findings with APPROVE/REQUEST-CHANGES verdict (DOCUMENT)
Result: Go/no-go decision with evidence
