---
name: sapcc-review
description: |
  Gold-standard code review for SAP CC Go repositories against the project's
  lead review standards. Dispatches 10 domain-specialist agents in parallel —
  each loads domain-specific references and scans
  ALL packages for violations in their assigned domain. Produces a prioritized
  report with REJECTED/CORRECT code examples. Optional --fix mode applies
  corrections on a worktree branch. This is the definitive "would this code
  pass lead review?" assessment.
version: 1.0.0
user-invocable: false
argument-hint: "[--fix]"
command: /sapcc-review
model: opus
agent: golang-general-engineer
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
  triggers:
    - sapcc review
    - sapcc lead review
    - sapcc compliance review
    - comprehensive sapcc audit
    - full sapcc check
    - review sapcc standards
  pairs_with:
    - golang-general-engineer
    - go-sapcc-conventions
    - sapcc-audit
  force_routing: false
  complexity: Complex
  category: language
---

# SAPCC Comprehensive Code Review v1

10-agent domain-specialist review. Each agent masters one rule domain and scans every package for violations against the comprehensive patterns reference.

**How this differs from /sapcc-audit**: sapcc-audit segments by *package* (generalist per package). sapcc-review segments by *rule domain* (specialist per concern, cross-package). Both are useful; this one catches more because specialists find issues generalists miss.

---

## Overview

This skill executes a gold-standard code review against SAP Converged Cloud Go repository standards through parallel domain specialists. Rather than one generalist reviewing one package, ten specialists review all packages for their specific domain (error handling, testing, types, HTTP APIs, etc.). This catches systemic patterns that package-level reviews miss.

Each specialist loads only its domain-specific reference file to keep context tight and focus deep. Findings are code-level (actual rejected/correct examples, never abstract suggestions) and cite specific sections from sapcc-code-patterns.md.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Map the repository, verify it's an sapcc project, plan the review.

**Step 1: Verify sapcc project**

```bash
cat go.mod | head -5
grep -c "sapcc" go.mod
```

If the module path doesn't contain "sapcc" AND go.mod doesn't import any sapcc packages, warn the user but continue (they may want to check a non-sapcc repo against the project's standards).

**Step 2: Map all Go packages and files**

```bash
# Count .go files (excluding vendor)
find . -name "*.go" -not -path "*/vendor/*" | wc -l

# List packages with file counts
find . -name "*.go" -not -path "*/vendor/*" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn

# Check for test files separately
find . -name "*_test.go" -not -path "*/vendor/*" | wc -l
```

**Step 3: Check for key imports** (determines which rules are most relevant)

```bash
grep -r "go-bits" go.mod               # Uses go-bits?
grep -r "go-api-declarations" go.mod   # Uses API declarations?
grep -r "gophercloud" go.mod           # Uses OpenStack?
grep -r "gorilla/mux" go.mod           # HTTP routing?
grep -r "database/sql" go.mod          # Database?
```

**Step 4: Create task_plan.md**

```markdown
# Task Plan: SAPCC Review — [repo name]

## Goal
Comprehensive code review of [repo] against project standards, dispatching 10 domain-specialist agents.

## Phases
- [x] Phase 1: Discover repo structure
- [ ] Phase 2: Dispatch 10 specialist agents
- [ ] Phase 3: Aggregate findings
- [ ] Phase 4: Write report

## Repo Profile
- Module: [module path]
- Packages: [N]
- Go files: [M] (excluding vendor)
- Test files: [T]
- Key imports: [list]

## Status
**Currently in Phase 2** - Dispatching agents
```

**Gate**: Repo mapped, plan created. Proceed to Phase 2.

---

### Phase 2: DISPATCH

**Goal**: Launch 10 domain-specialist agents in a SINGLE message for true parallel execution.

**CRITICAL**: All 10 agents must be dispatched in ONE message using the Agent tool. Do NOT serialize them. Serializing agents wastes time since domain specialists operate independently on disjoint concerns.

Each agent receives:
1. The path to sapcc-code-patterns.md to read
2. Their assigned sections to focus on
3. Their domain-specific reference file (loaded to avoid context dilution; each agent reads ONLY what it needs because loading all references into every agent wastes context and dilutes focus)
4. Instructions to scan ALL .go files in the repo
5. The exact output format for findings

**All agents share this preamble** (include in each prompt):

```
REFERENCE FILES TO READ FIRST (mandatory):
1. Read ~/.claude/skills/go-sapcc-conventions/references/sapcc-code-patterns.md
   (Focus on sections listed below, but skim all for context)
2. Read [domain-specific reference file]

REPO TO REVIEW: [current working directory]

SCAN METHOD:
- Use Glob to find all .go files: **/*.go (excluding vendor/)
- Use Read to examine each file
- Use Grep to search for specific patterns across all files

OUTPUT FORMAT for each finding:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file.go:LINE`
**Rule**: §[section].[subsection]: [rule name]
**Convention**: "[What the lead reviewer would write in a PR comment]"

REJECTED (current code):
```go
[actual code, 3-10 lines]
```

CORRECT (what it should be):
```go
[fixed code]
```

**Why**: [One sentence]
---

Write ALL findings to: [output file path]
```

---

#### Agent 1: Function Signatures, Constructors, Configuration

**Sections**: §1 (Function Signatures), §2 (Configuration), §3 (Constructor Patterns)
**Extra Reference**: `review-standards-lead.md`

**What to check across ALL packages:**
- Constructor taking option struct or functional options instead of positional params
- Functions with >8 params (should they be split?)
- context.Context in wrong position (should be first only for external calls)
- Config loaded from files/viper instead of env vars via osext.MustGetenv
- Constructors that return errors (should be infallible)
- Missing Override methods for test doubles
- Missing time.Now / ID-generator injection in constructors

---

#### Agent 2: Interfaces, Types, Option[T]

**Sections**: §4 (Interface Patterns), §8 (Type Definitions), §32 (Option[T] Complete Guide), §36 (Contract Cohesion)
**Extra Reference**: `architecture-patterns.md`

**What to check across ALL packages:**
- Interfaces with only one implementation (should be concrete type)
- Interfaces defined in implementation package instead of consumer package
- `*T` used for optional fields instead of `Option[T]` from majewsky/gg/option
- Missing dot-import for option package (`import . "github.com/majewsky/gg/option"`)
- `iota` used for enums instead of typed string constants
- Named types for domain concepts missing (raw `string` where `AccountName` type should exist)
- Pointer receivers where value receiver is appropriate (or vice versa)
- Type exported when only constructor needs to be public
- **Contract cohesion (§36)**: Constants, error sentinels, or validation functions in a different file from the interface/type they belong to. If `ErrFoo` is returned by `FooDriver` methods, both must live in `foo_driver.go`. MEDIUM for new violations, LOW for pre-existing.
- **Interface consumer audit**: When a sentinel value or special parameter is introduced on an interface method, grep for ALL implementations AND all callers of that interface method across the entire repo. Use gopls `go_symbol_references` when available. Verify every caller validates the sentinel before passing it. Do not rely on the PR description's claim about authorization — verify the call chain independently.

---

#### Agent 3: HTTP/API Design

**Sections**: §5 (HTTP/API Patterns), §34 (Architectural Opinions Feb 2026)
**Extra Reference**: `api-design-detailed.md`

**What to check across ALL packages:**
- Auth done as middleware instead of inline at top of handler
- JSON responses not using respondwith.JSON
- Error responses using JSON instead of text/plain (http.Error for 4xx, respondwith.ErrorText for 500)
- Missing DisallowUnknownFields on json.NewDecoder
- Route registration not using httpapi.Compose pattern
- Handler not a method on *API struct
- Handler signature not `handleVerbResource(w, r)`
- Request structs not parsed into purpose-specific types
- API docs in Markdown instead of Go types on pkg.go.dev

---

#### Agent 4: Error Handling

**Sections**: §6 (Error Handling), §26.13 (Error message naming)
**Extra Reference**: `error-handling-detailed.md`

**What to check across ALL packages:**
- Error messages not following "cannot <verb>: %w" format
- "failed to" instead of "cannot" in error messages
- Logging AND returning the same error (must choose one)
- Missing error wrapping (bare `return err` without context)
- Generic error messages ("internal error", "something went wrong")
- logg.Fatal used outside cmd/ packages
- Swallowed errors (err checked but not returned or logged)
- fmt.Errorf with %s when %w is needed (or vice versa)
- Validation functions returning (bool, string) instead of error

---

#### Agent 5: Database and SQL

**Sections**: §7 (Database Patterns), §27 (Database Deep Dive)
**Extra Reference**: (use sapcc-code-patterns.md §7 + §27)

**What to check across ALL packages:**
- SQL queries not declared as package-level `var` with `sqlext.SimplifyWhitespace()`
- Using `?` placeholders instead of `$1, $2` (PostgreSQL style)
- Missing `defer sqlext.RollbackUnlessCommitted(tx)` after `db.Begin()`
- TIMESTAMP used instead of TIMESTAMPTZ
- NULL columns that should be NOT NULL
- Migrations that modify existing migrations (immutable rule)
- Missing down migrations
- App-level validation that should be DB constraints
- Using explicit transaction for single statements
- Not using `sqlext.ForeachRow` for row iteration

---

#### Agent 6: Testing Patterns

**Sections**: §9 (Testing Patterns), §30 (go-bits Testing API Evolution)
**Extra Reference**: `testing-patterns-detailed.md`

**What to check across ALL *_test.go files AND test helpers:**
- Using deprecated `assert.HTTPRequest` instead of `httptest.Handler.RespondTo()`
- Using `assert.DeepEqual` where generic `assert.Equal` works
- Table-driven tests (project convention prefers sequential scenario-driven narrative)
- Missing `t.Helper()` in test helper functions
- Using reflect.DeepEqual instead of assert.DeepEqual
- Test fixtures as large JSON files instead of programmatic builders
- Duplicated test setup across test functions (should extract)
- Using `require` package instead of `must` from go-bits
- Not using `must.SucceedT` / `must.ReturnT` for error-checked returns
- Not using `assert.ErrEqual` for flexible error matching
- **Assertion depth check**: For security-sensitive code (auth, filtering, tenant isolation), presence-only assertions (`NotEmpty`, `NotNil`, `assert.True(t, ok)`) are INSUFFICIENT. Tests must verify the actual VALUE matches the expected input (e.g., `assert.Equal(t, expectedID, filters[0]["term"]["tenant_ids"])`)

---

#### Agent 7: Package Organization, Imports, Comments

**Sections**: §10 (Package Org), §11 (Import Org), §13 (Comment Style), §28 (CLI Patterns), §36 (Contract Cohesion)
**Extra Reference**: `architecture-patterns.md`

**What to check across ALL packages:**
- Import groups not in stdlib / external / internal order (3 groups)
- Dot-import used for anything other than `majewsky/gg/option`
- Missing SPDX license header
- Comments using `/* */` instead of `//` for doc comments
- Missing 80-slash separator comments (`////////////////...`) between type groups
- `//NOTE:` markers missing for non-obvious logic
- Exported symbols without godoc comments
- cmd/ packages using wrong CLI patterns (if CLI repo)
- Package names not reading as English ("package utils" instead of meaningful name)
- **Contract cohesion (§36)**: Files named generically (`interface.go`, `types.go`, `constants.go`) when they should be named for the domain concept (`storage_driver.go`, `rbac_policy.go`). Constants/sentinels in `util.go` that belong to a specific interface's file. The test: if you can name the owning interface, the artifact must live in that interface's file.

---

#### Agent 8: Modern Go, Standard Library, Concurrency

**Sections**: §14 (Concurrency), §15 (Startup/Shutdown), §29 (Modern Go Stdlib)
**Extra Reference**: (use sapcc-code-patterns.md §14, §15, §29)

**What to check across ALL packages:**
- Using `sort.Slice` instead of `slices.SortFunc` (Go 1.21+)
- Using manual `keys := make([]K, 0, len(m)); for k := range m { ... }` instead of `slices.Sorted(maps.Keys(m))`
- Using `strings.HasPrefix + strings.TrimPrefix` instead of `strings.CutPrefix` (Go 1.20+)
- Using manual `if a < b { return a }` instead of `min(a, b)` (Go 1.21+)
- Loop variable capture workaround (`v := v`) in Go 1.22+ code
- Goroutines without proper context cancellation
- Missing SIGINT context handling in main()
- `os.Exit` used instead of proper shutdown sequence
- `sync.Mutex` on struct value instead of per-resource
- Missing `for range N` syntax where applicable (Go 1.22+)

---

#### Agent 9: Observability, Metrics, Background Jobs

**Sections**: §16 (Background Jobs), §17 (HTTP Client), §18 (String Formatting), §20 (Observability)
**Extra Reference**: (use sapcc-code-patterns.md §16-18, §20)

**What to check across ALL packages:**
- Prometheus metrics missing application prefix (e.g., `keppel_` or `logrouter_`)
- Counter metrics not initialized to zero
- Counter metric names not plural
- Gauge used where Counter is appropriate (or vice versa)
- Background jobs not using `jobloop.ProducerConsumerJob` pattern
- HTTP client creating new `http.Client` per request instead of using `http.DefaultClient`
- Custom HTTP transport instead of `http.DefaultTransport`
- Missing jitter in polling/retry loops
- `fmt.Sprintf` for simple string concatenation (use `+`)
- `+` for complex multi-part string building (use `fmt.Sprintf`)

---

#### Agent 10: Anti-Patterns, LLM Tells, Community Divergences

**Sections**: §22 (Divergences), §24 (Anti-Patterns), §25 (LLM Code Feedback), §33 (Portunus Architecture), §35 (Reinforcement Table)
**Extra Reference**: `anti-patterns.md`

**This is the highest-value agent.** It checks for patterns that LLMs generate by default but the project explicitly rejects:

- Functional options pattern (project convention: positional params)
- Table-driven tests (project convention: sequential scenario narrative)
- Interface segregation / many small interfaces (project convention: 1-2 interfaces max per domain)
- Middleware-based auth (project convention: inline at handler top)
- Config validation layer (project convention: no separate validation)
- `*T` for optional fields (project convention: `Option[T]`)
- Config files / viper (project convention: pure env vars)
- Error messages starting with capital letter
- Error messages using "failed to" (project convention: "cannot")
- Helper functions extracted for cyclomatic complexity (project convention: "contrived edit to satisfy silly metrics")
- Exported types when only constructor is public
- Plugin creating its own DB connection (project convention: receive dependencies)
- `errors.New` + `fmt.Sprintf` instead of `fmt.Errorf`
- Manual row scanning instead of `sqlext.ForeachRow`
- Test setup in `TestMain` instead of per-test
- Verbose error checking instead of `assert.ErrEqual` / `must.SucceedT`
- **Extraction without guard transfer**: When inline code is extracted into a named helper, ALL defensive checks that relied on "the caller handles it" must be re-evaluated. A missing guard rated LOW as inline code becomes MEDIUM as a reusable function. Flag extracted helpers that lack self-contained validation.

---

**Gate**: All 10 agents dispatched in single message. Wait for all to complete. Proceed to Phase 3.

---

### Phase 3: AGGREGATE

**Goal**: Compile all agent findings into a single prioritized report.

**Step 0: Full file inventory**

Run `git status --short` (not just `git diff --stat`) to capture both modified AND untracked (new) files. This ensures new files created during the review session are not missed in the report.

**Step 1: Collect all findings**

Read each agent's output. Extract all findings with their severity, file, rule, and code.

**Step 2: Deduplicate**

If two agents flagged the same file:line, keep the higher-severity finding with the more specific rule citation.

**Step 3: Prioritize**

Apply cross-repository reinforcement from §35:

| Pattern Strength | Severity Boost |
|-----------------|----------------|
| NON-NEGOTIABLE (4+ repos) | +1 severity level (MEDIUM->HIGH) |
| Strong Signal (2-3 repos) | No change |
| Context-Specific (1 repo) | -1 severity level (HIGH->MEDIUM) |

**Step 4: Identify Quick Wins**

Mark findings that are:
- Single-line changes (regex replace, import reorder)
- No behavioral change (pure style/naming)
- Low risk of breaking tests

These go in a "Quick Wins" section at the top of the report.

**Step 5: Write report**

Create `sapcc-review-report.md`:

```markdown
# SAPCC Code Review: [repo name]

**Module**: [go module path]
**Date**: [date]
**Packages reviewed**: [N] packages, [M] Go files, [T] test files
**Agents dispatched**: 10 domain specialists
**Reference version**: sapcc-code-patterns.md (comprehensive patterns reference, 36 sections)

---

## Verdict

[2-3 sentences: Would this codebase pass lead review? What are the systemic issues?
Not just "there are problems" — identify the PATTERN of problems.]

## Score Card

| Domain | Agent | Findings | Critical | High | Medium | Low |
|--------|-------|----------|----------|------|--------|-----|
| Signatures/Config | 1 | N | ... | ... | ... | ... |
| Types/Option[T] | 2 | N | ... | ... | ... | ... |
| HTTP/API | 3 | N | ... | ... | ... | ... |
| Error Handling | 4 | N | ... | ... | ... | ... |
| Database/SQL | 5 | N | ... | ... | ... | ... |
| Testing | 6 | N | ... | ... | ... | ... |
| Pkg Org/Imports | 7 | N | ... | ... | ... | ... |
| Modern Go/Stdlib | 8 | N | ... | ... | ... | ... |
| Observability/Jobs | 9 | N | ... | ... | ... | ... |
| Anti-Patterns/LLM | 10 | N | ... | ... | ... | ... |
| **TOTAL** | | **N** | **X** | **Y** | **Z** | **W** |

## Quick Wins (Easy Fixes, High Impact)

[5-10 findings that can be fixed with minimal effort]

## Critical Findings

[Each finding with full REJECTED/CORRECT code]

## High Findings

[Each finding with full REJECTED/CORRECT code]

## Medium Findings

[Each finding]

## Low Findings

[Brief list]

## What's Done Well

[Genuine positives the lead reviewer would note approvingly. This is important for morale
and to show the review isn't blindly negative.]

## Systemic Recommendations

[2-3 big-picture recommendations based on patterns across findings.
E.g., "This repo consistently uses *T for optionals — a bulk migration
to Option[T] would address 15 findings at once."]
```

**Gate**: Report written. Display summary to user. Proceed to Phase 4 if `--fix` specified.

---

### Phase 4: FIX (Optional — only with `--fix` flag)

**Goal**: Apply fixes on an isolated branch.

**Step 1: Create worktree**

Use `EnterWorktree` to create an isolated copy. Name it `sapcc-review-fixes`.

**Step 2: Apply Quick Wins first**

Start with Quick Wins (lowest risk). After each group of fixes:

```bash
go build ./...    # Must still compile
go vet ./...      # Must pass vet
make check 2>/dev/null || go test ./...  # Must pass tests
```

**Step 3: Apply Critical and High fixes**

Apply in order. Run tests between each fix. If a fix breaks tests, revert it and note in the report.

**Step 4: Create commit**

```bash
git add -A
git commit -m "fix: apply sapcc-review findings (N fixes across M files)"
```

**Step 5: Report results**

Update `sapcc-review-report.md` with:
- Which findings were fixed
- Which findings were skipped (and why)
- Test results after fixes

---

### Phase 4: FIX (Optional — only with `--fix` flag)

**Goal**: Apply fixes on an isolated branch.

**Step 1: Create worktree**

Use `EnterWorktree` to create an isolated copy. Name it `sapcc-review-fixes`.

**Step 2: Apply Quick Wins first**

Start with Quick Wins (lowest risk). After each group of fixes:

```bash
go build ./...    # Must still compile
go vet ./...      # Must pass vet
make check 2>/dev/null || go test ./...  # Must pass tests
```

**Step 3: Apply Critical and High fixes**

Apply in order. Run tests between each fix. If a fix breaks tests, revert it and note in the report.

**Step 4: Create commit**

```bash
git add -A
git commit -m "fix: apply sapcc-review findings (N fixes across M files)"
```

**Step 5: Report results**

Update `sapcc-review-report.md` with:
- Which findings were fixed
- Which findings were skipped (and why)
- Test results after fixes

---

## Error Handling

**When an agent fails or produces empty findings**:
1. Verify the repo has Go files (some repos may be non-Go or already pass review completely)
2. Check agent logs for permission errors or gopls MCP connection failures
3. If agent timed out, increase timeout or split the 10 agents into two waves of 5
4. If agent reports "no findings", it has completed successfully — that domain is clean

**When a finding looks wrong** (e.g., false positive):
- Cross-check with sapcc-code-patterns.md section cited in the finding
- If it contradicts the reference, note the discrepancy and file in toolkit issue
- If it applies to pre-existing code older than the rule's introduction, mark as LOW and note in systemic recommendations

**When `--fix` breaks tests**:
1. Revert the failed fix
2. Note in report that this finding needs manual review
3. Document the test failure reason so the maintainer understands the blocker
4. Continue with next fix rather than stopping the whole process

---

## References

- **sapcc-code-patterns.md** — Comprehensive 36-section reference (single source of truth for all review rules)
- **Per-agent reference files** (loaded during dispatch):
  - Agent 1: `review-standards-lead.md`
  - Agent 2: `architecture-patterns.md`
  - Agent 3: `api-design-detailed.md`
  - Agent 4: `error-handling-detailed.md`
  - Agent 5: (none — rules inline in §7 + §27)
  - Agent 6: `testing-patterns-detailed.md`
  - Agent 7: `architecture-patterns.md`
  - Agent 8: (none — rules inline in §14, §15, §29)
  - Agent 9: (none — rules inline in §16-18, §20)
  - Agent 10: `anti-patterns.md`
- **Optional deep-dive references** (load only when findings need calibration):
  - `pr-mining-insights.md` — Review severity calibration across projects
  - `library-reference.md` — Approved/forbidden dependency table

**Integration notes**:
- Complements `/sapcc-audit` (package-level generalist) — use both for maximum coverage
- Prerequisite: go-sapcc-conventions skill must be installed at `~/.claude/skills/go-sapcc-conventions/`
- Sync: After creating, run `cp -r skills/sapcc-review ~/.claude/skills/sapcc-review` for global access
- Router: `/do` routes via "sapcc review", "sapcc lead review", "comprehensive sapcc audit"
