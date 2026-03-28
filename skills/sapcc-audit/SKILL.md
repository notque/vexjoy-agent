---
name: sapcc-audit
description: |
  Full-repo SAP Converged Cloud Go compliance audit. Reviews every package
  against established review standards — focusing on over-engineering,
  error message quality, dead code, interface contracts, copy-paste structs,
  and pattern consistency with keppel. Dispatches parallel agents by package
  group, each reading ALL sapcc rules. Produces code-level findings with
  actual before/after diffs. Invoked via "/sapcc-audit" or through /do.
version: 2.0.0
user-invocable: false
command: /sapcc-audit
agent: golang-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - sapcc audit
    - sapcc compliance
    - check sapcc rules
    - full repo audit
    - sapcc secondary review
    - sapcc standards check
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - go-sapcc-conventions
  force_route: false
  complexity: Complex
  category: language
---

# SAPCC Full-Repo Compliance Audit v2

Review every package against established review standards. Not checklist compliance — **code-level review** that finds over-engineering, dead code, interface violations, and inconsistent patterns.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Map the repository and plan the package segmentation.

**Step 1: Verify this is an sapcc project**

```bash
head -5 go.mod  # Check module path
grep "sapcc" go.mod  # Check for sapcc imports
```

If not an sapcc project, stop immediately.

**Step 2: Map all packages**

```bash
find . -name "*.go" -not -path "./vendor/*" | sed 's|/[^/]*$||' | sort -u
```

Count files per package. This determines how to segment for parallel agents.

**Step 3: Plan agent segmentation**

Group packages so each agent gets 5-15 files (sweet spot for thorough review).

Example for a repo with `cmd/`, `internal/api/`, `internal/config/`, `internal/storage/`, `internal/router/`, etc.:

| Agent | Packages | Focus |
|-------|----------|-------|
| 1 | `cmd/` + `main.go` files | Startup patterns, CLI structure |
| 2 | `internal/api/` | HTTP handlers, error responses, routing |
| 3 | `internal/config/` + `internal/auth/` | Configuration, auth patterns |
| 4 | `internal/storage/` + `internal/wal/` | Storage, persistence, error handling |
| 5 | `internal/router/` + `internal/source/` | Core logic, concurrency |
| 6 | `internal/integrity/` + `internal/limiter/` + remaining | Crypto, rate limiting |
| 7 | All `*_test.go` files | Testing patterns, assertions |

Adjust based on actual package sizes. Aim for 5-8 agents.

**Gate**: Packages mapped, agents planned. Proceed to Phase 2.

### Phase 2: DISPATCH

**Goal**: Launch parallel agents that review packages against project standards.

**Principle: Read the actual code.** Agents MUST use the Read tool to read every .go file in their assigned packages. Do not guess based on file names or grep output. Use gopls MCP tools when available: `go_workspace` to detect workspace structure, `go_file_context` after reading each .go file for intra-package dependency understanding, `go_symbol_references` to verify type usage across packages (critical for export decisions), `go_package_api` to inspect package APIs, `go_diagnostics` to verify any fixes.

**Principle: Real review, not checklists.** The primary question for every function is: "Would this pass review?" not "does it follow a checklist." A real reviewer reads code holistically and reacts to architectural issues, not just mechanical patterns.

**Principle: Segment by package, not by concern.** Dispatch agents by package groups, NOT by concern area. Each agent reviews its packages holistically (errors + architecture + patterns + tests together), exactly like a real PR review. Real code review reads a file holistically — an error handling issue might actually be an architecture issue. Segmenting by concern produces shallow findings.

**Code-level findings only.** Every finding MUST include the actual code snippet and a concrete fix showing what it should become. Abstract suggestions like "consider using X" are forbidden. Show current code and what it should become.

**Each agent gets this dispatch prompt:**

```
You are reviewing code in an SAP Converged Cloud Go project against established
review standards. Your job is to find things that would actually be commented on
or rejected in a PR.

PACKAGES TO REVIEW: [list of packages with full paths]

Read EVERY .go file in these packages using the Read tool. For each file:

1. **Over-engineering** (Lead Reviewer's #1 Concern)
   - Interfaces with only one implementation? → "Just use the concrete type." Project convention: only create interfaces when there are 2+ real implementations.
   - Wrapper function that adds nothing? → "Delete this, call the real function"
   - Struct for one-time JSON? → "Use fmt.Sprintf + json.Marshal" (per project convention)
   - Option struct for constructor? → "Just use positional params." Project convention uses 7-8 positional params, never option structs.
   - Config file/viper? → "Use osext.MustGetenv." Project convention never uses config files. Pure env vars only.

2. **Dead code**
   - Exported functions with no callers outside the package? Use Grep to check: `grep -r "FunctionName" --include="*.go"`. If no callers exist, flag it.
   - Interface methods never called
   - Fields set but never read
   - Entire packages imported but barely used
   - "TODO: remove" comments on code that should already be gone

3. **Error messages** (Secondary Reviewer's #1 Concern)
   - `http.Error(w, "internal error", 500)` — useless to the caller
   - Error wrapping: uses %w when caller needs errors.Is/As, %s with .Error() to intentionally break chain
   - Message format: "cannot <operation>: %w" or "while <operation>: %w" with relevant identifiers
   - Would a user/operator reading this know what to do?
   - "internal error" with no context = CRITICAL
   - Never log AND return the same error. Primary error returned, secondary/cleanup errors logged.

4. **Constructor patterns**
   - Constructor should be `NewX(deps...) *X` — never returns error (construction is infallible)
   - Uses positional struct literal init: `&API{cfg, ad, fd, sd, ...}` (no field names)
   - Injects default functions for test doubles: `time.Now`, etc.
   - Override pattern for test doubles: fluent `OverrideTimeNow(fn) *T` methods

5. **Interface contracts**
   - If the package implements an interface from another package: Read the interface definition
   - Check if the implementation actually satisfies the contract
   - Does it return correct error types? Default values where errors are expected?
   - Interfaces should be defined in the consumer package, not the implementation package

6. **Copy-paste structs**
   - Two structs with the same fields (one for internal, one for API response)?
   - Handler functions that are 90% identical (extract the common pattern)
   - Duplicated validation logic

7. **HTTP handler patterns** (Must match keppel patterns)
   - Handlers: methods on *API with `handleVerbResource(w, r)` signature
   - Auth: called inline at top of handler, NOT middleware
   - JSON decode: `json.NewDecoder` + `DisallowUnknownFields()`
   - Responses: `respondwith.JSON(w, status, map[string]any{"key": val})`
   - Internal errors: `respondwith.ObfuscatedErrorText(w, err)` — hides 500s from clients
   - Route registration: one `AddTo(*mux.Router)` per API domain, composed via `httpapi.Compose`

8. **Database patterns**
   - SQL queries as package-level `var` with `sqlext.SimplifyWhitespace()`
   - PostgreSQL `$1, $2` params (never `?`)
   - gorp for simple CRUD, raw SQL for complex queries
   - Transactions: `db.Begin()` + `defer sqlext.RollbackUnlessCommitted(tx)`
   - NULL: `Option[T]` (from majewsky/gg/option), not `*T` pointers

9. **Type patterns**
   - Named string types for domain concepts: `type AccountName string`
   - String enums with typed constants (NOT iota): `const CleanSeverity VulnerabilityStatus = "Clean"`
   - Model types use `db:"column"` tags; API types use `json:"field"` tags — separate types
   - Pointer receivers for all struct methods (value receivers only for tiny data-only types)

10. **Logging patterns**
    - `logg.Fatal` ONLY in cmd/ packages for startup failures
    - `logg.Error` for secondary/cleanup errors (never for primary errors)
    - `logg.Info` for operational events
    - Never log.Printf or fmt.Printf for logging
    - Panics only for impossible states, annotated with "why was this not caught by Validate!?"

11. **Mixed approaches** (Pattern consistency)
    - Some handlers return JSON errors, others return text/plain
    - Some constructors panic on nil args, others return errors
    - Some packages use logg, others use log

For EACH finding, output:

### [MUST-FIX / SHOULD-FIX / NIT]: [One-line summary]
**File**: `path/to/file.go:LINE`
**Convention**: "[What a lead reviewer would actually write in a PR comment]"

**Current code**:
\`\`\`go
[actual code from the file, 3-10 lines]
\`\`\`

**Should be**:
\`\`\`go
[what the code should look like after fixing]
\`\`\`

**Why**: [One sentence explaining the principle]

---

SEVERITY GUIDE:
- MUST-FIX: Would block the PR (data loss, interface violation, wrong behavior)
- SHOULD-FIX: Would get a strong review comment (dead code, copy-paste, bad errors)
- NIT: Would get a comment but not block (style, naming, minor simplification)

DO NOT report:
- Generic Go best practices (t.Parallel, DisallowUnknownFields, context.Context first)
- Things that are actually fine but could theoretically be "better"
- Suggestions that add complexity without clear benefit

DO report:
- Real over-engineering (lead reviewer's #1 concern)
- Actually useless error messages (secondary reviewer's #1 concern)
- Dead code that should be deleted
- Interface contract bugs
- Constructor/config patterns that don't match keppel
- Inconsistent patterns within the same repo
```

**Dispatch all agents in a single message using the Task tool with subagent_type=golang-general-engineer.**

**Gate**: All agents dispatched. Proceed to Phase 3.

### Phase 3: COMPILE REPORT

**Goal**: Aggregate findings into a code-level compliance report.

**Step 1: Collect and deduplicate**

Some findings may overlap (e.g., dead code agent and architecture agent flag the same unused function). Deduplicate by file:line.

**Step 2: Write the report**

Create `sapcc-audit-report.md`:

```markdown
# SAPCC Code Review: [repo name]

**Reviewed by**: Lead & secondary reviewer standards (simulated)
**Date**: [date]
**Packages**: [N] packages, [M] Go files

## Verdict

[One paragraph: Would this pass review? What's the overall impression?]

## Must-Fix (Would Block PR)

[Each finding with current/should-be code]

## Should-Fix (Strong Review Comments)

[Each finding with current/should-be code]

## Nits

[Each finding, brief]

## What's Done Well

[Genuine positives — things a reviewer would note approvingly]

## Package-by-Package Summary

| Package | Files | Must-Fix | Should-Fix | Nit | Verdict |
|---------|-------|----------|-----------|-----|---------|
| internal/api | N | X | Y | Z | [emoji] |
| ... | | | | | |
```

**Step 3: Display summary**

Show the verdict, must-fix count, and top 5 findings inline. Point to the full report file.

**Gate**: Report complete.

---

## Error Handling

### Failure modes and recovery

| Scenario | Response |
|----------|----------|
| Not an sapcc project | Stop immediately. Print message: "This does not appear to be an SAP CC Go project (no sapcc imports in go.mod)." |
| Agents cannot read a file | Log and continue. File may be binary or inaccessible. Flag in the report under "Warnings." |
| gopls MCP tools unavailable | Fall back to manual grep-based analysis. Note in the report that type-aware analysis was unavailable. |
| Too many packages (>30) | Split into >8 agents. Ensure each still gets 5-15 files for depth. |
| Agent finds no violations | Report is valid. Not every package has violations. Output empty sections for unused severity levels. |

### Principles

- **Audit only**: READS and REPORTS. Does NOT modify code unless explicitly asked with `--fix`.
- **Skip generic findings**: Do NOT report `DisallowUnknownFields`, `t.Parallel()`, or other generic Go best practices unless they are genuinely wrong in context. Focus on sapcc-specific patterns.
- **Rationalization guard**: Avoid "could theoretically be better" findings. Focus on things that would actually be commented on in a real PR review.

---

## References

### Per-agent reference loading (included in each agent's dispatch prompt based on assigned packages)

| Package Type | Reference to Load |
|-------------|-------------------|
| HTTP handlers (`internal/api/`) | `api-design-detailed.md` |
| Test files (`*_test.go`) | `testing-patterns-detailed.md` |
| Error handling heavy packages | `error-handling-detailed.md` |
| Architecture/drivers | `architecture-patterns.md` |
| Build/CI config | `build-ci-detailed.md` |
| Import-heavy files | `library-reference.md` |

### Always available for calibration (load only when needed)

- `anti-patterns.md` — Quick-check findings against known anti-patterns
- `review-standards-lead.md` — Calibrate review tone and severity

**Note**: Do NOT tell every agent to read the full sapcc-code-patterns.md. The rules are already inline in the dispatch prompt. Load reference files only for domain-specific depth.

### Integration

- **Router**: `/do` routes via "sapcc audit", "sapcc compliance", "sapcc lead review"
- **Pairs with**: `go-sapcc-conventions` (the rules), `golang-general-engineer` (the executor)
- **Prerequisite**: `go-sapcc-conventions` must be loaded so agents have the rules
