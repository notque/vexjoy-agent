---
name: go-sapcc-conventions
description: |
  SAP Converged Cloud Go coding conventions extracted from sapcc/keppel and
  sapcc/go-bits PR reviews. Enforces architecture
  patterns, library usage rules, error handling conventions, testing patterns,
  and anti-over-engineering principles. Use when working in sapcc/* repos,
  when code imports github.com/sapcc/go-bits, or when targeting SAP CC
  code review standards. Do NOT use for general Go projects without
  sapcc dependencies.
version: 1.0.0
user-invocable: false
agent: golang-general-engineer
routing:
  triggers:
    - sapcc
    - sap-cloud-infrastructure
    - go-bits
    - keppel
    - go-api-declarations
    - go-makefile-maker
    - sapcc/go-bits
    - sap-cloud-infrastructure/go-bits
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - go-testing
    - go-error-handling
  force_routing: true
  complexity: Comprehensive
  category: language
---

# SAP Converged Cloud Go Conventions

Coding standards extracted from extensive PR review analysis across `sapcc/keppel` and `sapcc/go-bits`. These are the real rules enforced in code review by the project's lead review standards.

## Tool Integration

**gopls MCP (MUST use when available)**: Use `go_workspace` at session start, `go_file_context` after reading .go files, `go_symbol_references` before modifying any symbol (critical for sapcc — lead review checks cross-package impact), `go_diagnostics` after every edit, `go_vulncheck` after go.mod changes. This gives type-aware analysis that catches issues grep cannot.

**Modern Go Guidelines**: Detect Go version from go.mod. Sapcc projects typically target Go 1.22+. Use version-appropriate features: `t.Context()` (1.24+), `b.Loop()` (1.24+), `strings.SplitSeq` (1.24+), `wg.Go()` (1.25+), `errors.AsType[T]` (1.26+).

---

## 1. Anti-Over-Engineering Rules (Strongest Project Opinions)

This section comes first because it is the defining characteristic of SAP CC Go code. The most frequent review theme (10 of 38 comments) is rejecting unnecessary complexity.

### 1.1 When NOT to Create Types

Do not create throwaway struct types just to marshal a simple JSON payload:

```go
// BAD: Copilot suggested this. Rejected as "overengineered."
type fsParams struct { Path string `json:"path"` }
type fsConfig struct { Type string `json:"type"`; Params fsParams `json:"params"` }
config, _ := json.Marshal(fsConfig{Type: "filesystem", Params: fsParams{Path: path}})

// GOOD: project convention
storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`,
  must.Return(json.Marshal(filesystemPath)))
```

### 1.2 When NOT to Wrap Errors

Do not add error context that the called function already provides. The Go stdlib's `strconv` functions include the function name, input value, and error reason:

```go
// BAD: redundant wrapping
val, err := strconv.ParseUint(s, 10, 32)
if err != nil {
    return fmt.Errorf("failed to parse chunk number %q: %w", s, err)
}

// GOOD: strconv already says "strconv.ParseUint: parsing \"hello\": invalid syntax"
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
```

> "ParseUint is disciplined about providing good context in its input messages... So we can avoid boilerplate here without compromising that much clarity."

### 1.3 When NOT to Handle Errors

Do not handle errors that are never triggered in practice. Apply the standard consistently:

```go
// BAD: handling os.Stdout.Write errors
n, err := os.Stdout.Write(data)
if err != nil {
    return fmt.Errorf("failed to write to stdout: %w", err)
}

// GOOD: if fmt.Println ignoring errors is OK everywhere, so is os.Stdout.Write
os.Stdout.Write(data)
```

> "I'm going to ignore this based purely on the fact that Copilot complains about `os.Stdout.Write()`, but not about the much more numerous instances of `fmt.Println` that theoretically suffer the same problem."

### 1.4 When NOT to Add Defer Close

Do not add `defer Close()` on `io.NopCloser` just for theoretical contract compliance:

> "This is an irrelevant contrivance. Either `WriteTrivyReport` does it, or the operation fails and we fatal-error out, in which case it does not matter anyway."

### 1.5 Dismiss Copilot/AI Suggestions That Add Complexity

Lead review evaluates AI suggestions on merit and frequently simplifies them:
- If a Copilot suggestion is inconsistent (complains about X but not equivalent Y), dismiss it
- If a Copilot suggestion creates types for one-off marshaling, simplify it
- Ask: "Can you point to a concrete scenario where this fails?" If not, don't handle it

### 1.6 When NOT to Build Smart Inference

When a known future design change is coming, don't build abstractions that will break:

```
# BAD: inferring params from driver name (won't work for future "multi" driver)
--driver swift  (auto-generates swift params)

# GOOD: explicit and future-proof
--driver swift --params '{"container":"foo"}'
```

> "I appreciate the logic behind inferring storage driver params automatically... But this will not scale beyond next month."

But also: do NOT preemptively solve the future problem. Just don't build something that blocks the future solution.

### 1.7 No Hidden Defaults for Niche Cases

If a default value only applies to a subset of use cases, make the parameter required for everyone:

> "This is, in effect, a default value that only applies to two specific storage drivers. These are not widely used enough to justify the undocumented quirk."

---

## 2. Lead Review Rules

The lead review style is directive. Statements, not suggestions. Top concerns: simplicity, API design, error handling. See [references/review-standards-lead.md](references/review-standards-lead.md) for all 21 PR comments with full context.

### Core Principles

| Rule | Summary |
|------|---------|
| Trust the stdlib | Don't wrap errors that `strconv`, constructors, etc. already describe well |
| Use Cobra subcommands | Never manually roll argument dispatch that Cobra handles |
| CLI names: specific + extensible | `keppel test-driver storage`, not `keppel test` |
| Marshal structured data for errors | If you have a `map[string]any`, `json.Marshal` it instead of manually formatting fields |
| Tests must verify behavior | Never silently remove test assertions during refactoring |
| Explain test workarounds | Add comments when test setup diverges from production patterns |
| Use existing error utilities | Use `errext.ErrorSet` and `.Join()`, not manual string concatenation |
| TODOs need context | Include what, a starting point link, and why not done now |
| Documentation stays qualified | When behavior changes conditionally, update docs to state the conditions |
| Understand value semantics | Value receiver copies the struct, but reference-type fields share data |
| Variable names don't mislead | Don't name script vars as if the application reads them |

### How Lead Review Works

- **Reads Copilot suggestions critically** -- agrees with principle, proposes simpler alternatives
- **Dismisses inconsistent AI complaints** -- if tool flags X but not equivalent Y, the concern is invalid
- **Thinks about forward compatibility** -- command names and API shapes evaluated for extensibility
- **Values brevity when stdlib provides clarity** -- removes wrappers that duplicate error info
- **Approves simple PRs quickly** -- doesn't manufacture concerns
- **Corrects misconceptions directly** -- states correct behavior without softening
- **Pushes fixes directly** -- sometimes pushes commits to address review concerns directly

---

## 3. Secondary Review Rules

The secondary review style is inquisitive. Questions where lead review makes statements. Top concerns: configuration safety, migration paths, test completeness. See [references/review-standards-secondary.md](references/review-standards-secondary.md) for full details.

### Core Principles

| Rule | Summary |
|------|---------|
| Error messages must be actionable | "Internal Server Error" is unacceptable when the cause is knowable |
| Know the spec, deviate pragmatically | Reference RFCs, but deviate when spec is impractical |
| Guard against panics with clear errors | Check nil/empty before indexing, use `fmt.Errorf("invalid: %q", val)` |
| Strict configuration parsing | Use `DisallowUnknownFields()` on JSON decoders for config |
| Test ALL combinations | When changing logic with multiple inputs, test every meaningful combination |
| Eliminate redundant code | Ask "This check is now redundant?" when code is refactored |
| Comments explain WHY | When something non-obvious is added, request an explanatory comment |
| Domain knowledge over theory | Dismiss concerns that don't apply to actual domain constraints |
| Smallest possible fix | 2-line PRs are fine. Don't bundle unrelated changes |
| Respect ownership hierarchy | "LGTM but lets wait for lead review, we are in no hurry here" |
| Be honest about mistakes | Acknowledge errors quickly and propose fix direction |
| Validate migration paths | "Do we somehow check if this is still set and then abort?" |

---

## 4. Architecture Rules

Keppel uses a strict layered architecture. See [references/architecture-patterns.md](references/architecture-patterns.md) for the complete 102-rule set with code examples.

### Directory Structure

```
project/
  main.go                    # Root: assembles Cobra commands, blank-imports drivers
  cmd/<component>/main.go    # AddCommandTo(parent *cobra.Command) pattern
  internal/
    api/<surface>/           # HTTP handlers per API surface (keppelv1, registryv2)
    auth/                    # Authorization logic
    client/                  # Outbound HTTP clients
    drivers/<name>/          # Pluggable driver implementations (register via init())
    keppel/                  # Core domain: interfaces, config, DB, errors
    models/                  # DB model structs (pure data, db: tags, no logic)
    processor/               # Business logic (coordinates DB + storage)
    tasks/                   # Background jobs
    test/                    # Test infrastructure, doubles, helpers
```

### Key Patterns

**Pluggable Driver Pattern** (6 driver types in keppel):
```go
// Interface in internal/keppel/
type StorageDriver interface {
    pluggable.Plugin    // requires PluginTypeID() string
    Init(...) error
    // domain methods...
}
var StorageDriverRegistry pluggable.Registry[StorageDriver]

// Implementation in internal/drivers/<name>/
func init() {
    keppel.StorageDriverRegistry.Add(func() keppel.StorageDriver { return &myDriver{} })
}

// Activation in main.go
_ "github.com/sapcc/keppel/internal/drivers/openstack"
```

**Cobra Command Pattern**:
```go
// cmd/<name>/main.go
package apicmd

func AddCommandTo(parent *cobra.Command) {
    cmd := &cobra.Command{Use: "api", Short: "...", Args: cobra.NoArgs, Run: run}
    parent.AddCommand(cmd)
}

func run(cmd *cobra.Command, args []string) {
    keppel.SetTaskName("api")
    cfg := keppel.ParseConfiguration()
    ctx := httpext.ContextWithSIGINT(cmd.Context(), 10*time.Second)
    // ... bootstrap drivers, DB, handlers ...
}
```

**Configuration**: Environment variables only. No config files, no CLI flags for config. JSON params only for driver internals.

```go
// Required vars
host := osext.MustGetenv("KEPPEL_API_PUBLIC_FQDN")
// Optional with defaults
port := osext.GetenvOrDefault("KEPPEL_DB_PORT", "5432")
// Boolean flags
debug := osext.GetenvBool("KEPPEL_DEBUG")
```

---

## 5. Error Handling Rules

See [references/architecture-patterns.md](references/architecture-patterns.md) for the complete 27-rule error handling specification.

### Error Wrapping Conventions

```go
// "while" for operations in progress
return fmt.Errorf("while finding source repository: %w", err)

// "cannot" for failed actions
return fmt.Errorf("cannot parse digest %q: %w", digestStr, err)

// "during" for HTTP operations
return fmt.Errorf("during %s %s: %w", r.Method, uri, err)

// "could not" for background jobs
return fmt.Errorf("could not get ManagedAccountNames(): %w", err)
```

All error messages: lowercase, no trailing punctuation, include identifying data with `%q`, descriptive action prefix.

### must.Return / must.Succeed Scope

```go
// ALLOWED: startup/bootstrap code (fatal errors)
must.Succeed(rootCmd.Execute())
var celEnv = must.Return(cel.NewEnv(...))

// ALLOWED: test code
must.SucceedT(t, s.DB.Insert(&record))
digest := must.ReturnT(rc.UploadBlob(ctx, data))(t)

// FORBIDDEN: request handlers, business logic, background tasks
// Never use must.* where errors should be propagated
```

### must vs assert in Tests: When to Use Which

In test code, `must` and `assert` serve different roles:

| Package | Calls | Use When |
|---------|-------|----------|
| `assert` | `t.Errorf` (non-fatal) | Checking the **expected outcome** of the operation being tested |
| `must` | `t.Fatal` (fatal) | **Setup/preconditions** where failure means subsequent lines are meaningless |

**Decision tree:**
1. Inside a `mustXxx` helper? -> `must.SucceedT` / `must.ReturnT`
2. Next line depends on this succeeding? -> `must.SucceedT` / `must.ReturnT`
3. Checking the outcome of the tested operation? -> `assert.ErrEqual(t, err, nil)`
4. Need a return value? -> `must.ReturnT` (no assert equivalent)

```go
// Setup (fatal) — next lines depend on this
must.SucceedT(t, store.UpdateMetrics())
families := must.ReturnT(registry.Gather())(t)

// Assertion (non-fatal) — checking expected outcome
assert.ErrEqual(t, err, nil)
assert.Equal(t, len(families), 3)
```

**The rule: helper = must, assertion = assert.**

### assert.Equal vs assert.DeepEqual

| Type supports `==`? | Use | Args |
|---------------------|-----|------|
| Yes (int, string, bool) | `assert.Equal(t, actual, expected)` | 3 |
| No (slices, maps, structs) | `assert.DeepEqual(t, "label", actual, expected)` | 4 |

Common mistake flagged in review: `assert.DeepEqual(t, "count", len(events), 3)` — `len` returns `int` which is comparable, so use `assert.Equal(t, len(events), 3)`.

### Logging Level Selection

| Level | When | Example |
|-------|------|---------|
| `logg.Fatal` | Startup/CLI only, never in handlers | `logg.Fatal("failed to read key: %s", err.Error())` |
| `logg.Error` | Cannot bubble up (cleanup, deferred, advisory) | `logg.Error("rollback failed: " + err.Error())` |
| `logg.Info` | Operational events, graceful degradation | `logg.Info("rejecting overlong name: %q", name)` |
| `logg.Debug` | Diagnostic, gated behind `KEPPEL_DEBUG` | `logg.Debug("parsing configuration...")` |

### Panic Rules

Panic ONLY for:
- Programming errors / unreachable code: `panic("unreachable")`
- Invariant violations: `panic("(why was this not caught by Validate!?)")`
- Infallible operations: `crypto/rand.Read`, `json.Marshal` on known-good data
- Init-order violations: `panic("called before Connect()")`

NEVER panic for: user input, external services, database errors, request handling.

### HTTP Error Response Formats (3 distinct)

| API Surface | Format | Helper |
|-------------|--------|--------|
| Registry V2 (`/v2/`) | JSON `{"errors": [{code, message, detail}]}` | `rerr.WriteAsRegistryV2ResponseTo(w, r)` |
| Keppel V1 (`/keppel/v1/`) | Obfuscated text (5xx get UUID-masked) | `respondwith.ObfuscatedErrorText(w, err)` |
| Auth (`/keppel/v1/auth`) | JSON `{"details": "..."}` | `rerr.WriteAsAuthResponseTo(w)` |

5xx errors use `respondwith.ObfuscatedErrorText` which logs the real error with a UUID and returns `"Internal Server Error (ID = <uuid>)"` to the client.

---

## 6. API Design Rules

### Handler Pattern (Every handler follows this sequence)

```go
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    // 1. ALWAYS first: identify for metrics
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts/:account")

    // 2. Authenticate BEFORE any data access
    authz := a.authenticateRequest(w, r, accountScopeFromRequest(r, keppel.CanViewAccount))
    if authz == nil {
        return  // error already written
    }

    // 3. Load resources
    account := a.findAccountFromRequest(w, r, authz)
    if account == nil {
        return  // error already written
    }

    // 4. Business logic...

    // 5. Respond
    respondwith.JSON(w, http.StatusOK, map[string]any{"account": rendered})
}
```

### Strict JSON Parsing

```go
// ALWAYS use DisallowUnknownFields for request bodies
decoder := json.NewDecoder(r.Body)
decoder.DisallowUnknownFields()
err := decoder.Decode(&req)
if err != nil {
    http.Error(w, "request body is not valid JSON: "+err.Error(), http.StatusBadRequest)
    return
}
```

### Response Conventions

```go
// Single resource: wrap in named key
respondwith.JSON(w, http.StatusOK, map[string]any{"account": rendered})

// Collection: wrap in plural named key
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": list})

// Empty list: MUST be [], never null
if len(items) == 0 {
    items = []ItemType{}
}
```

---

## 7. Testing Rules

### Core Testing Stack

- **Assertion library**: `go-bits/assert` (NOT testify, NOT gomock)
- **DB testing**: `easypg.WithTestDB` in every `TestMain`
- **Test setup**: Functional options via `test.NewSetup(t, ...options)`
- **HTTP testing**: `assert.HTTPRequest{}.Check(t, handler)`
- **Time control**: `mock.Clock` (never call `time.Now()` directly)
- **Test doubles**: Implement real driver interfaces, register via `init()`

### assert.HTTPRequest Pattern

```go
assert.HTTPRequest{
    Method:       "PUT",
    Path:         "/keppel/v1/accounts/first",
    Header:       map[string]string{"X-Test-Perms": "change:tenant1"},
    Body: assert.JSONObject{
        "account": assert.JSONObject{"auth_tenant_id": "tenant1"},
    },
    ExpectStatus: http.StatusOK,
    ExpectHeader: map[string]string{
        test.VersionHeaderKey: test.VersionHeaderValue,
    },
    ExpectBody: assert.JSONObject{
        "account": assert.JSONObject{
            "name": "first", "auth_tenant_id": "tenant1",
        },
    },
}.Check(t, h)
```

### DB Testing Pattern

```go
// In shared_test.go -- REQUIRED for every package with DB tests
func TestMain(m *testing.M) {
    easypg.WithTestDB(m, func() int { return m.Run() })
}

// Full DB snapshot assertion
easypg.AssertDBContent(t, s.DB.Db, "fixtures/blob-sweep-001.sql")

// Incremental change tracking
tr, tr0 := easypg.NewTracker(t, s.DB.Db)
tr0.AssertEqualToFile("fixtures/setup.sql")
// ... run operation ...
tr.DBChanges().AssertEqual(`UPDATE repos SET next_sync_at = 7200 WHERE id = 1;`)
tr.DBChanges().AssertEmpty()  // nothing else changed
```

### Test Execution Flags

```bash
go test -shuffle=on -p 1 -covermode=count -coverpkg=... -mod vendor ./...
```

- `-shuffle=on`: Randomize test order to detect order-dependent tests
- `-p 1`: Sequential packages (shared PostgreSQL database)
- `-mod vendor`: Use vendored dependencies

### Test Anti-Patterns

| Anti-Pattern | Correct Pattern |
|-------------|----------------|
| `testify/assert` | `go-bits/assert` |
| `gomock` / `mockery` | Hand-written test doubles implementing real interfaces |
| `httptest.NewRecorder` directly | `assert.HTTPRequest{}.Check(t, h)` |
| `time.Now()` in testable code | Inject `func() time.Time`, use `mock.Clock` |
| `t.Run` subtests (rare in keppel) | Log test case index: `t.Logf("----- testcase %d/%d -----")` |

---

## 8. Library Usage Rules

### APPROVED Libraries

| Library | Purpose | Key Pattern |
|---------|---------|-------------|
| `sapcc/go-bits` | Core framework (170+ files) | `logg.Info`, `must.Return`, `assert.HTTPRequest` |
| `majewsky/gg/option` | `Option[T]` (45 files) | `Some(v)`, `None[T]()`, dot-import ONLY for this |
| `majewsky/schwift/v2` | Swift storage client | OpenStack storage driver only |
| `gorilla/mux` | HTTP routing | `r.Methods("GET").Path("/path").HandlerFunc(h)` |
| `spf13/cobra` | CLI framework | `AddCommandTo(parent)` pattern |
| `go-gorp/gorp/v3` | SQL ORM | `db:"column_name"` struct tags |
| `gophercloud/gophercloud/v2` | OpenStack SDK | Keystone auth, Swift storage |
| `prometheus/client_golang` | Metrics | Application + HTTP middleware metrics |
| `redis/go-redis/v9` | Redis client | Rate limiting, token caching |
| `gofrs/uuid/v5` | UUID generation | NOT google/uuid, NOT satori/uuid |
| `golang-jwt/jwt/v5` | JWT tokens | Auth token handling |
| `alicebob/miniredis/v2` | Testing only | In-memory Redis for tests |

### Related Libraries

| Library | Purpose | Key Pattern |
|---------|---------|-------------|
| `majewsky/gg/option` | `Option[T]` (45 files) | `Some(v)`, `None[T]()`, dot-import ONLY for this |
| `majewsky/schwift/v2` | Swift storage client | OpenStack storage driver only |

### FORBIDDEN Libraries

| Library | Reason | Use Instead |
|---------|--------|-------------|
| `testify` (assert/require/mock) | SAP CC has own testing framework | `go-bits/assert` + `go-bits/must` |
| `zap` / `zerolog` / `slog` / `logrus` | SAP CC standardized on simple logging | `go-bits/logg` |
| `gin` / `echo` / `fiber` | SAP CC uses stdlib + gorilla/mux | `go-bits/httpapi` + `gorilla/mux` |
| `gorm` / `sqlx` / `ent` | Lightweight ORM preference | `go-gorp/gorp/v3` + `go-bits/sqlext` |
| `viper` | No config files; env-var-only config | `go-bits/osext` + `os.Getenv` |
| `google/uuid` / `satori/uuid` | Different UUID library chosen | `gofrs/uuid/v5` |
| `gomock` / `mockery` | Manual test double implementations | Hand-written doubles via driver interfaces |
| `ioutil.*` | Deprecated since Go 1.16 | `os` and `io` packages |
| `http.DefaultServeMux` | Global mutable state | `http.NewServeMux()` |
| `gopkg.in/square/go-jose.v2` | Archived, has CVEs | `gopkg.in/go-jose/go-jose.v2` |

See [references/library-reference.md](references/library-reference.md) for the complete table with versions and usage counts.

### Import Grouping Convention

Three groups, separated by blank lines. Enforced by `goimports -local github.com/sapcc/keppel`:

```go
import (
    // Group 1: Standard library
    "context"
    "encoding/json"
    "fmt"
    "net/http"

    // Group 2: External (includes sapcc/go-bits, NOT local project)
    "github.com/gorilla/mux"
    . "github.com/majewsky/gg/option"  // ONLY dot-import allowed
    "github.com/sapcc/go-bits/httpapi"
    "github.com/sapcc/go-bits/logg"

    // Group 3: Local project
    "github.com/sapcc/keppel/internal/keppel"
    "github.com/sapcc/keppel/internal/models"
)
```

**Dot-import whitelist** (only these 3 packages):
- `github.com/majewsky/gg/option`
- `github.com/onsi/ginkgo/v2`
- `github.com/onsi/gomega`

---

## 9. Build and CI Rules

### go-makefile-maker

All build config is generated from `Makefile.maker.yaml`. Do NOT edit these files directly:
- `Makefile`
- `.golangci.yaml`
- `REUSE.toml`
- `.typos.toml`
- GitHub Actions workflows

### License Headers (REQUIRED on every .go file)

```go
// SPDX-FileCopyrightText: 2024 SAP SE or an SAP affiliate company
// SPDX-License-Identifier: Apache-2.0
```

### golangci-lint v2 Configuration

35+ enabled linters. Key settings:

| Setting | Value | Rationale |
|---------|-------|-----------|
| `errcheck.check-blank` | `true` | `_ = err` is flagged |
| `goconst.min-occurrences` | `5` | Only flag strings repeated 5+ times |
| `whitespace.multi-func` | `true` | Blank line after multi-line function signatures |
| `nolintlint.require-specific` | `true` | `//nolint` must specify which linter |
| `usestdlibvars` | all enabled | `http.StatusOK` not `200`, `http.MethodGet` not `"GET"` |
| `govet.fieldalignment` | disabled | Not worth the churn |

**errcheck excluded functions** (return values may be ignored):
- `encoding/json.Marshal`
- `(net/http.ResponseWriter).Write`
- `(*github.com/spf13/cobra.Command).Help`

### revive Linter (REQUIRED — check on every sapcc repo)

As of 2026-03-20, go-makefile-maker supports `revive` as an optional linter. **All sapcc repos should enable it.** When working in an sapcc repo, check `Makefile.maker.yaml` for `reviveRules`. If absent, recommend adding:

```yaml
golangciLint:
  reviveRules:
    - name: exported
      arguments:
        - checkPrivateReceivers
        - disableChecksOnConstants
```

This catches:
- Exported functions/types/methods without doc comments
- Private receivers on exported methods

After adding, run `go-makefile-maker` to regenerate `.golangci.yaml`, then `make run-golangci-lint` to verify.

### Build Commands

```bash
make build-all              # Build binary
make check                  # Static checks + tests + build
make static-check           # Lint + shellcheck + license checks
make run-golangci-lint      # Lint only
make goimports              # Format imports
make vendor                 # go mod tidy + vendor + verify
```

---

## 10. go-bits Design Philosophy

The go-bits library design rules that govern all of `sapcc/go-bits`. Understanding these rules helps predict what code will pass review.

### Rule 1: One Package = One Concept
`must` = fatal errors. `logg` = logging. `respondwith` = HTTP responses. No package does two things.

### Rule 2: Minimal API Surface
`must` has 4 functions. `logg` has 5. `syncext` has 1 type with 3 methods. Fewer, more general functions beat many specific ones.

### Rule 3: Names That Read as English
```go
must.Succeed(err)           // "must succeed"
must.Return(os.ReadFile(f)) // "must return"
respondwith.JSON(w, 200, d) // "respond with JSON"
logg.Fatal(msg)             // "log fatal"
errext.As[T](err)           // "error extension: as T"
```

### Rule 4: Document the WHY, Not Just the WHAT
Extensive comments explaining design constraints and rejected alternatives. `must.ReturnT` has three paragraphs explaining why the signature is the only one that works given Go generics limitations.

### Rule 5: Panics for Programming Errors, Errors for Runtime Failures
- **Panic**: nil factory in `pluggable.Add`, calling API outside `Compose`, mixing incompatible options
- **Error return**: missing env var, failed SQL query, JSON marshal failure
- **Fatal (os.Exit)**: `must.Succeed` for genuinely unrecoverable startup errors

### Rule 6: Concrete Before/After Examples in Docs
Every function's godoc shows the exact code it replaces.

### Rule 7: Enforce Correct Usage Through Type System
`jobloop.Setup()` returns a private type wrapping the struct, enforcing that Setup was called.

### Rule 8: Dependency Consciousness
Actively prevents unnecessary dependency trees. Importing UUID from `audittools` into `respondwith` was rejected because it would pull in AMQP dependencies. Solution: move to internal package.

### Rule 9: Prefer Functions Over Global Variables
> "I don't like having a global variable for this that callers can mess with."

Use `ForeachOptionTypeInLIQUID[T any](action func(any) T) []T` instead of `var LiquidOptionTypes = []any{...}`.

### Rule 10: Leverage Go Generics Judiciously
Use generics where they eliminate boilerplate or improve type safety:
- `must.Return[V]` preserves return type
- `errext.As[T]` eliminates pointer-to-pointer pattern
- `pluggable.Registry[T Plugin]` constrains plugin types

Do NOT use generics where they add complexity without clear benefit.

### Rule 11: Graceful Deprecation
`assert.HTTPRequest` is deprecated but not removed. The deprecation notice includes a complete migration guide. No forced migration.

### Rule 12: Defense in Depth with Documentation
Handle theoretically impossible cases with branches that behave the same, and document the invariant reasoning.

---

## Error Handling

### Error: "Cannot find go-bits dependency"
**Cause**: Project does not import `github.com/sapcc/go-bits`
**Solution**: This skill only applies to sapcc projects. Check `go.mod` first.

### Error: "Linter reports forbidden import"
**Cause**: Using a FORBIDDEN library (testify, zap, gin, etc.)
**Solution**: Replace with the SAP CC equivalent. See the FORBIDDEN table in Section 8.

### Error: "Missing SPDX license header"
**Cause**: `.go` file missing the required two-line SPDX header
**Solution**: Add `// SPDX-FileCopyrightText: <year> SAP SE or an SAP affiliate company` and `// SPDX-License-Identifier: Apache-2.0` as the first two lines.

### Error: "Import groups out of order"
**Cause**: Imports not in the three-group order (stdlib / external / local)
**Solution**: Run `goimports -w -local github.com/sapcc/keppel <file>`.

### Error: "Test uses testify/assert"
**Cause**: Mixing assertion libraries
**Solution**: Replace `assert.Equal(t, expected, actual)` (testify) with `assert.DeepEqual(t, "desc", actual, expected)` (go-bits). Note the parameter order difference.

---

## Anti-Patterns

See [references/anti-patterns.md](references/anti-patterns.md) for the full catalog with BAD/GOOD examples.

### AP-1: Creating Types for One-Off JSON Marshaling
**What it looks like**: Struct types with json tags used once for `json.Marshal`
**Why wrong**: This is considered "overengineered" by project convention
**Do instead**: `fmt.Sprintf` with `must.Return(json.Marshal(dynamicPart))`

### AP-2: Wrapping Errors That Already Have Context
**What it looks like**: `fmt.Errorf("parse error: %w", strconv.ParseUint(...))`
**Why wrong**: strconv already includes function name, input, and error type
**Do instead**: `must.Return(strconv.ParseUint(s, 10, 32))`

### AP-3: Manual Argument Dispatch Instead of Cobra
**What it looks like**: Switch statement on `args[0]` to dispatch to code paths
**Why wrong**: Cobra subcommands handle this with better UX
**Do instead**: Change argument order if needed to allow Cobra subcommands

### AP-4: Using must.Return in Request Handlers
**What it looks like**: `val := must.Return(someOperation())` inside an HTTP handler
**Why wrong**: `must.Return` calls `os.Exit(1)` on error, crashing the server
**Do instead**: Return errors properly; `must.*` is for startup code and tests only

### AP-5: Global Mutable Variables for Configuration
**What it looks like**: `var Config = map[string]string{...}` at package level
**Why wrong**: Callers can modify the map, creating inconsistent state
**Do instead**: Functions that produce values: `func GetConfig() map[string]string`

---

## Available Scripts

Deterministic checks for sapcc-specific patterns that no linter covers. Run these during code review or as part of quality gates. All support `--help`, `--json`, `--limit`, and meaningful exit codes (0 = clean, 1 = violations, 2 = error).

| Script | What It Checks |
|--------|---------------|
| `scripts/check-sapcc-identify-endpoint.sh` | HTTP handlers missing `httpapi.IdentifyEndpoint` call |
| `scripts/check-sapcc-auth-ordering.sh` | Data access before authentication in handlers |
| `scripts/check-sapcc-json-strict.sh` | `json.NewDecoder` without `DisallowUnknownFields()` |
| `scripts/check-sapcc-time-now.sh` | Direct `time.Now()` in testable code (inject clock instead) |
| `scripts/check-sapcc-httptest.sh` | `httptest.NewRecorder` instead of `assert.HTTPRequest` |
| `scripts/check-sapcc-todo-format.sh` | Bare TODO comments without context/links |

These scripts only apply to sapcc repos (detected by `github.com/sapcc/go-bits` in go.mod).

---

## Anti-Rationalization

### SAP CC Domain-Specific Rationalizations

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Tests pass, the error wrapping is fine" | Lead review checks error message quality in review | Verify error context matches project standards |
| "Copilot suggested this approach" | Lead review frequently rejects Copilot suggestions as overengineered | Evaluate on merit, simplify where possible |
| "I need a struct for this JSON" | One-off JSON can be `fmt.Sprintf` + `json.Marshal` | Only create types if reused or complex |
| "Better safe than sorry" (re: error handling) | "Irrelevant contrivance" -- handle only practical concerns | Ask "concrete scenario where this fails?" |
| "Standard library X works fine here" | SAP CC has go-bits equivalents that are expected | Use go-bits (logg, assert, must, osext, respondwith) |
| "testify is the Go standard" | SAP CC projects use go-bits/assert exclusively | Never introduce testify in sapcc repos |
| "I'll add comprehensive error wrapping" | Trust well-designed functions' error messages | Check if the called function already provides context |
| "This needs a config file" | SAP CC uses env vars only | Use osext.MustGetenv, GetenvOrDefault, GetenvBool |

---

## References (MUST READ)

**NON-NEGOTIABLE**: Before working on ANY sapcc Go code, you MUST read these reference files. Do NOT skip them. Do NOT rely on your training data for sapcc conventions — read the actual references. These contain the real rules from actual PR reviews.

**Load order** (read in this sequence):
1. **sapcc-code-patterns.md** — Read FIRST. This is the definitive reference with actual code patterns
2. **library-reference.md** — Read SECOND. Know which libraries are approved/forbidden before writing imports
3. **architecture-patterns.md** — Read THIRD if working on architecture, HTTP handlers, or DB access
4. Then load others as needed for the specific task

| File | What It Contains | When to Read |
|------|-----------------|--------------|
| [references/sapcc-code-patterns.md](${CLAUDE_SKILL_DIR}/references/sapcc-code-patterns.md) | **Actual code patterns** — function signatures, constructors, interfaces, HTTP handlers, error handling, DB access, testing, package organization | **ALWAYS** — this is the primary reference |
| [references/library-reference.md](${CLAUDE_SKILL_DIR}/references/library-reference.md) | Complete library table: 30 approved, 10+ forbidden, with versions and usage counts | **ALWAYS** — need to know approved/forbidden imports |
| [references/architecture-patterns.md](${CLAUDE_SKILL_DIR}/references/architecture-patterns.md) | Full 102-rule architecture specification with code examples | When working on architecture, handlers, DB access |
| [references/review-standards-lead.md](${CLAUDE_SKILL_DIR}/references/review-standards-lead.md) | All 21 lead review comments with full context and quotes | For reviews and understanding lead review reasoning |
| [references/review-standards-secondary.md](${CLAUDE_SKILL_DIR}/references/review-standards-secondary.md) | All 15 secondary review comments with PR context | For reviews and understanding secondary review patterns |
| [references/anti-patterns.md](${CLAUDE_SKILL_DIR}/references/anti-patterns.md) | 20+ SAP CC anti-patterns with BAD/GOOD code examples | For code review and avoiding common mistakes |
| [references/extended-patterns.md](${CLAUDE_SKILL_DIR}/references/extended-patterns.md) | **Extended patterns from related repos** — security micro-patterns, visual section separators, copyright format, K8s namespace isolation, PR hygiene (sort lists, clean orphans, document alongside), changelog format. Pipeline-generated. | For security-conscious code, K8s helm work, or PR hygiene |
