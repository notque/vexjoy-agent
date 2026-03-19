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
user-invocable: true
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

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **Domain-Scoped References**: Each agent loads ONLY its domain-specific reference file (see Reference Loading Strategy). The essential rules are inline in each agent's dispatch prompt.
- **Domain Specialist Model**: Agents are assigned by rule domain (testing, errors, types, etc.), NOT by package. Each agent scans ALL packages for their domain's violations.
- **Code-Level Findings Only**: Every finding must include actual code from the repo and a concrete CORRECT version. Abstract suggestions are forbidden.
- **Cite Rule Source**: Every finding must cite the section number from sapcc-code-patterns.md (e.g., "§30.1: httptest.Handler migration").
- **Directive Review Voice**: Frame findings as the lead reviewer would state them in a PR comment. Use the project's established review phrases where applicable.
- **Audit Only By Default**: READ and REPORT. Do NOT modify code unless `--fix` is specified.
- **Skip Generic Go**: Do NOT report generic Go best practices. Only report patterns that are specifically sapcc/project-convention divergences.

### Default Behaviors (ON unless disabled)
- **gopls MCP Integration**: All review agents MUST use gopls MCP tools when available — `go_workspace` at start, `go_file_context` for dependency analysis, `go_symbol_references` for cross-package impact tracing, `go_diagnostics` for build verification. This gives type-aware analysis instead of text-only grep.
- **Save Report**: Write findings to `sapcc-review-report.md` in repo root
- **Quick Wins Section**: Identify the 5 easiest fixes with highest impact
- **Cross-Repository Reinforcement**: Weight findings higher when the violated rule appears in 4+ repos per §35

### Optional Behaviors (OFF unless enabled)
- **--fix**: Create worktree, apply fixes, run tests, create branch
- **--focus [package]**: Audit only one package (runs 3 agents instead of 10)
- **--severity [critical|high|medium|all]**: Only report findings at or above severity

---

## Reference Loading Strategy

Reference files live at `skills/go-sapcc-conventions/references/` (or `~/.claude/skills/go-sapcc-conventions/references/` globally).

**Key change from v0**: Agents load ONLY their domain-specific reference, NOT the full patterns file. The essential rules are already embedded in each agent's dispatch prompt below. Reference files provide supplementary depth.

**Per-agent reference loading** (included in each agent's dispatch prompt):

| Agent | Domain Reference to Load |
|-------|--------------------------|
| 1 (Signatures/Config) | `review-standards-lead.md` |
| 2 (Types/Option[T]) | `architecture-patterns.md` |
| 3 (HTTP/API) | `api-design-detailed.md` |
| 4 (Error Handling) | `error-handling-detailed.md` |
| 5 (Database/SQL) | (none — rules inline) |
| 6 (Testing) | `testing-patterns-detailed.md` |
| 7 (Pkg Org/Imports) | `architecture-patterns.md` |
| 8 (Modern Go/Stdlib) | (none — rules inline) |
| 9 (Observability/Jobs) | (none — rules inline) |
| 10 (Anti-Patterns/LLM) | `anti-patterns.md` |

**Optional deep-dive** (load only when findings need calibration):
- `sapcc-code-patterns.md` — Comprehensive 35-section reference. Only load specific sections, not the entire file.
- `pr-mining-insights.md` — Review severity calibration
- `library-reference.md` — Approved/forbidden dependency table

**Anti-pattern**: Loading ALL reference files into EVERY agent wastes context and dilutes focus. Each agent should load only what it needs.

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

**CRITICAL**: All 10 agents must be dispatched in ONE message using the Agent tool. Do NOT serialize them.

Each agent receives:
1. The path to sapcc-code-patterns.md to read
2. Their assigned sections to focus on
3. Their domain-specific reference file(s) to read
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

**Sections**: §4 (Interface Patterns), §8 (Type Definitions), §32 (Option[T] Complete Guide)
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

---

#### Agent 7: Package Organization, Imports, Comments

**Sections**: §10 (Package Org), §11 (Import Org), §13 (Comment Style), §28 (CLI Patterns)
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

---

**Gate**: All 10 agents dispatched in single message. Wait for all to complete. Proceed to Phase 3.

---

### Phase 3: AGGREGATE

**Goal**: Compile all agent findings into a single prioritized report.

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
**Reference version**: sapcc-code-patterns.md (comprehensive patterns reference, 35 sections)

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

## Calibration: What Makes This Gold Standard

### Why 10 Domain Specialists > N Package Generalists

| Approach | Strength | Weakness |
|----------|----------|----------|
| **Package generalist** (sapcc-audit) | Understands file-level context | Must remember ALL rules for every file |
| **Domain specialist** (sapcc-review) | Deep expertise in one rule domain | May miss cross-concern interactions |

**Combination is ideal**: Run `/sapcc-review` for comprehensive rule coverage, then `/sapcc-audit` for holistic package-level review.

### Why Read sapcc-code-patterns.md First

The comprehensive reference is the single source of truth. Without reading it, agents default to community Go conventions — which are WRONG for 12+ patterns the project explicitly diverges from (§22). The reference file IS the competitive advantage.

### What "Gold Standard" Means

1. **Complete coverage**: Every section in sapcc-code-patterns.md has a specialist agent checking for it
2. **Low false positives**: Agents skip generic Go advice and only report sapcc-specific divergences
3. **Actionable findings**: Every finding has REJECTED code and CORRECT code
4. **Prioritized output**: Cross-repo reinforcement weights findings by importance
5. **Reproducible**: Same repo + same reference = same findings
6. **Quick Wins first**: Operator can fix 10 easy things immediately for rapid improvement

---

## Anti-Patterns

### AP-1: Not Reading the References
**What it looks like**: Agent starts reviewing without reading sapcc-code-patterns.md
**Why wrong**: Without the reference, agents generate findings based on community Go advice, which diverges from the project's preferences in 12+ areas
**Do instead**: ALWAYS read sapcc-code-patterns.md FIRST. This is hardcoded behavior.

### AP-2: Reporting Generic Go Issues
**What it looks like**: "Add t.Parallel()", "Use context.Context as first param"
**Why wrong**: The lead reviewer doesn't care about these. The focus is on over-engineering, dead code, and error quality.
**Do instead**: Only report patterns that match rules in sapcc-code-patterns.md

### AP-3: Suggesting More Complexity
**What it looks like**: "Add a config validation layer", "Create an error registry"
**Why wrong**: The #1 concern in lead review is over-engineering. Never suggest adding abstraction.
**Do instead**: Suggest REMOVING complexity. "Delete this wrapper" > "Add this wrapper"

### AP-4: Abstract Findings Without Code
**What it looks like**: "Error handling could be improved in package X"
**Why wrong**: Not actionable. Lead reviews always show exact code.
**Do instead**: Show the actual line, the actual code, and the actual fix.

---

## Integration

- **Router**: `/do` routes via "sapcc review", "sapcc lead review", "comprehensive sapcc audit"
- **Complements**: `/sapcc-audit` (package-level generalist) — use both for maximum coverage
- **Prerequisite**: go-sapcc-conventions skill must be installed at `~/.claude/skills/go-sapcc-conventions/`
- **Sync**: After creating, run `cp -r skills/sapcc-review ~/.claude/skills/sapcc-review` for global access
