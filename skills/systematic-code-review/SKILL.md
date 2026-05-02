---
name: systematic-code-review
description: "4-phase code review: UNDERSTAND, VERIFY, ASSESS risks, DOCUMENT findings."
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
  pairs_with:
    - forensics
    - verification-before-completion
    - parallel-code-review
---

# Systematic Code Review Skill

4-phase code review: UNDERSTAND changes, VERIFY claims against actual behavior, ASSESS security/performance/architecture risks, DOCUMENT findings with severity. Each phase has a gate that must pass before proceeding.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `go-review-patterns.md` | Loads detailed guidance from `go-review-patterns.md`. |
| tasks related to this reference | `receiving-feedback.md` | Loads detailed guidance from `receiving-feedback.md`. |
| tasks related to this reference | `severity-classification.md` | Loads detailed guidance from `severity-classification.md`. |

## Instructions

### Phase 1: UNDERSTAND

**Goal**: Map all changes and relationships before forming opinions.

**Step 1: Read CLAUDE.md** — Project conventions override default review criteria and may define custom severity rules or scope constraints.

**Step 2: Read every changed file** — Use Read tool on EVERY changed file completely. Map what each file does, how changes affect it, and check affected dependencies for ripple effects.

**Step 3: Identify dependencies** — Grep for all callers/consumers of changed code. Note comments claiming behavior (verify in Phase 2, do not trust).

**Step 3a: Caller Tracing** (mandatory when diff modifies function signatures, parameter semantics, or sentinel values)

1. **Find ALL callers** — Grep with receiver syntax (e.g., `.GetEvents(` not just `GetEvents`). For Go, prefer gopls `go_symbol_references` via ToolSearch("gopls") for type-aware matching.
2. **Trace the VALUE SPACE** — For each parameter source, classify reachable values:
   - Query parameters (`r.FormValue`, `r.URL.Query`): user-controlled — ANY string including sentinels like `"*"`
   - Auth token fields: server-controlled (UUIDs, structured IDs)
   - Constants/enums: fixed set
   - Classify sentinel strings by true source. If reachable from user input, verify the input path.
3. **Verify each caller** — Check parameters are validated before passing. Watch for sentinels (e.g., `"*"` meaning "all/unfiltered") that bypass security filtering.
4. **Report unvalidated paths** — Any caller passing user input to a security-sensitive parameter without validation is BLOCKING.
5. **Verify callers independently** — Confirm the caller set directly in the codebase. The PR author may have forgotten callers or new callers may exist in other branches.

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

**Gate**: All changed files read (not just some), scope fully mapped, callers traced (if applicable). Proceed only when gate passes.

### Phase 2: VERIFY

> **Opus 4.7 override:** Run the command. Do not reason about whether it would pass. Execute the check, paste the exit code and relevant output. A verification without an observed tool result is a guess.

**Goal**: Validate all assertions in code, comments, and PR description against actual behavior.

**Step 1: Run tests** — Execute existing tests for changed files. Capture complete output. Show output rather than describing it. Untested code paths are a SHOULD FIX finding.

**Step 2: Verify claims** — Check every comment claim against code behavior. Comments frequently become outdated. Never accept a comment as truth without inspecting the backing code. Verify edge cases are actually handled. Trace critical code paths manually.

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

**Gate**: All assertions verified against actual behavior. Tests executed with output captured. Proceed only when gate passes.

### Phase 3: ASSESS

**Goal**: Evaluate security, performance, and architectural risks.

**Step 1: Security assessment** — Never skip. Evaluate OWASP top 10 against changes. Explain HOW each vulnerability was ruled out, not just checkboxes. If optionally enabled: extended deep security analysis.

**Step 2: Performance assessment** — Identify performance-critical paths. Check for N+1 queries, unbounded loops, unnecessary allocations. If optionally enabled: benchmark affected code paths.

**Step 3: Architectural assessment** — Compare patterns to existing codebase conventions. Assess breaking change potential. If optionally enabled: historical analysis.

**Step 4: Extraction severity escalation** — If diff extracts inline code into named helpers, re-evaluate all defensive guards. A missing check rated LOW as inline code (1 caller) becomes MEDIUM as a reusable function (N potential callers).

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

**Gate**: Security, performance, and architectural risks explicitly evaluated. Proceed only when gate passes.

### Phase 4: DOCUMENT

**Goal**: Structured review output with clear verdict and rationale.

Report facts without self-congratulation. Show command output rather than describing it. Only flag issues within scope of changed code — no speculative improvements — but DO flag all issues IN the changed code even if fixing them requires touching other files.

Classify severity using the Severity Classification Rules below. Classify UP when in doubt.

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

**Schema Validation (automatic):**
```bash
python3 scripts/validate-review-output.py --type systematic review-output.md
```
Checks: verdict is one of APPROVE/REQUEST-CHANGES/NEEDS-DISCUSSION, risk_level present, findings have file:line references, positives section exists.

After producing the review, remove temporary analysis files, notes, or debug outputs.

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

Three tiers: BLOCKING (cannot merge -- security, correctness, reliability), SHOULD FIX (fix unless urgent -- patterns, tests, debugging), SUGGESTIONS (genuinely optional -- style, naming, micro-optimizations). When in doubt, classify UP.

See `references/severity-classification.md` for full classification tables, decision tree, and common misclassification examples.

### Go-Specific Review Patterns

Watch for: type export design, concurrency patterns (batch+callback, loop variable capture, commit callbacks), resource management (defer placement, connection pool reuse), metrics pre-initialization, testing deduplication, unnecessary function extraction.

For shared org libraries: check for manual SQL row iteration instead of helpers, incorrect assertion depth, raw `sql.Open()` in tests, dead migration files, database-specific naming violations.

See `references/go-review-patterns.md` for full checklists and red flags.

### Receiving Review Feedback

When receiving feedback: read completely, restate requirement, verify against codebase, evaluate technical soundness, respond with reasoning or just fix it. Never performative agreement. Apply YAGNI check. Stop and clarify before implementing anything unclear.

See `references/receiving-feedback.md` for full reception pattern, pushback examples, implementation order, and external vs internal reviewer handling.

---

## Error Handling

### Error: "Incomplete Information"
Cause: Missing context about the change
Solution: Ask for clarification in Phase 1. Do not proceed past UNDERSTAND with unanswered questions. Document gaps in scope assessment.

### Error: "Test Failures"
Cause: Tests fail during Phase 2 verification
Solution: Document in Phase 2. Automatic BLOCKING finding in Phase 4. Cannot APPROVE with failing tests.

### Error: "Unclear Risk"
Cause: Cannot determine severity
Solution: Default to higher risk level. Document uncertainty. REQUEST-CHANGES if critical uncertainty exists.

---

## References

### Examples

#### Example 1: Pull Request Review
User says: "Review this PR"
Actions:
1. Read CLAUDE.md, then all changed files, map scope and dependencies (UNDERSTAND)
2. Run tests, verify claims in comments and PR description (VERIFY)
3. Evaluate security/performance/architecture risks (ASSESS)
4. Produce structured findings with severity and verdict (DOCUMENT)
Result: Structured review with clear verdict and rationale

#### Example 2: Pre-Merge Verification
User says: "Check this before we merge"
Actions:
1. Read CLAUDE.md, then all changes, identify breaking change potential (UNDERSTAND)
2. Run full test suite, verify backward compatibility claims (VERIFY)
3. Assess risk level for production deployment (ASSESS)
4. Document findings with APPROVE/REQUEST-CHANGES verdict (DOCUMENT)
Result: Go/no-go decision with evidence
