# Agent Dispatch Prompts

This file contains the shared preamble and all 10 domain-specialist agent specifications used during Phase 2 (DISPATCH).

---

## Shared Preamble

Include this block in every agent prompt:

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

## Agent 1: Function Signatures, Constructors, Configuration

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

## Agent 2: Interfaces, Types, Option[T]

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

## Agent 3: HTTP/API Design

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

## Agent 4: Error Handling

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

## Agent 5: Database and SQL

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

## Agent 6: Testing Patterns

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

## Agent 7: Package Organization, Imports, Comments

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

## Agent 8: Modern Go, Standard Library, Concurrency

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

## Agent 9: Observability, Metrics, Background Jobs

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

## Agent 10: Anti-Patterns, LLM Tells, Community Divergences

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
