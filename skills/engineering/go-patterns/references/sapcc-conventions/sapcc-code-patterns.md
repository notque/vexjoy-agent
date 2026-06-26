# SAP CC Code Patterns — Extracted from Keppel Source

Concrete rules extracted by reading every package in `sapcc/keppel`. These are not review comments — these are how the project's code is actually written.

**For the LLM generating code**: When this document conflicts with "Go best practices," **this document wins** for sapcc code.

---

## 1. Function Signatures

### Parameter Count

- **Methods**: 1-4 parameters (lean)
- **Constructors**: 7-8 positional parameters (no option structs, no functional options)
- **Never**: variadic params for required dependencies, builder patterns, config structs bundling unrelated params

```go
// CORRECT: 8 positional params for constructor — actual code from keppel
func NewAPI(cfg keppel.Configuration, ad keppel.AuthDriver, fd keppel.FederationDriver,
    sd keppel.StorageDriver, icd keppel.InboundCacheDriver,
    db *keppel.DB, auditor audittools.Auditor, rle *keppel.RateLimitEngine) *API {
    return &API{cfg, ad, fd, sd, icd, db, auditor, rle, time.Now, keppel.GenerateStorageID}
}
// Anti-pattern: option struct or functional options for constructors
```

### context.Context Usage

- Pass as first param **only** for external calls (DB, federation, storage)
- HTTP handlers read context from `r.Context()` instead of taking a `ctx` parameter
- Many internal methods omit context parameter when the method has no context-dependent behavior

### Return Patterns

| Pattern | When |
|---------|------|
| `(T, error)` | Returning data |
| `error` | Side-effect operations |
| `(T, *keppel.RegistryV2Error)` | API-facing where error type matters |
| `(bool, error)` named returns | When `defer` reads/modifies the return |

### Named Returns

**Only** when a `defer` block reads/modifies the return. Never for documentation. Named return vars: `returnErr`, `returnedError`, `returnedErr`.

### Pointer vs Value Receivers

- **Pointer receivers** (`*T`) for all struct methods
- **Value receivers** (`T`) only for tiny data-only types (2-3 fields, no mutation)

### Parameter Naming

Short 2-3 letter abbreviations: `cfg`, `ad`, `fd`, `sd`, `icd`, `db`, `rle`, `amd`, `ctx`, `w`/`r`, `tx`. Struct fields match parameter abbreviations.

---

## 2. Configuration

### Pure Environment Variables — No Config Files

```go
// CORRECT: env-var-only configuration
func ParseConfiguration() Configuration {
    cfg := Configuration{
        APIPublicHostname: osext.MustGetenv("KEPPEL_API_PUBLIC_FQDN"),
        AnycastAPIPublicHostname: os.Getenv("KEPPEL_API_ANYCAST_FQDN"),
    }
}
// Anti-pattern: viper, YAML, TOML, config files — all FORBIDDEN
```

### Env Var Patterns

| Function | When |
|----------|------|
| `osext.MustGetenv("VAR")` | Required — panics if missing |
| `os.Getenv("VAR")` | Optional, empty string OK |
| `osext.GetenvOrDefault("VAR", "default")` | Optional with default |
| `osext.GetenvBool("VAR")` | Boolean flag |

### Driver Selection via JSON Env Vars

```go
ad := must.Return(keppel.NewAuthDriver(ctx, osext.MustGetenv("KEPPEL_DRIVER_AUTH"), rc))
```

---

## 3. Constructor Patterns

### `NewX(deps...) *X` — Never Returns Error

Constructors are infallible. They wire up dependencies with positional struct literals:

```go
func NewAPI(cfg keppel.Configuration, ad keppel.AuthDriver, ...) *API {
    return &API{cfg, ad, fd, sd, icd, db, auditor, rle, time.Now, keppel.GenerateStorageID}
}
// Anti-pattern: constructor returning error, named struct fields in constructor return
```

Driver constructors (`New*Driver`) DO return errors — they parse config and initialize connections.

### The Override Pattern (Fluent Test Doubles)

```go
func (p *Processor) OverrideTimeNow(timeNow func() time.Time) *Processor {
    p.timeNow = timeNow; return p
}
// In tests: processor.OverrideTimeNow(s.Clock.Now).OverrideGenerateStorageID(s.SIDGenerator.Next)
```

---

## 4. Interface Patterns

### When to Use Interfaces

Only for real polymorphism — every interface has 2+ implementations.

| Reason | Example |
|--------|---------|
| Pluggable backends | `StorageDriver`, `AuthDriver`, `FederationDriver` |
| Polymorphism over variants | `UserIdentity` (7 impl), `ParsedManifest` (4 impl) |
| Observer pattern | `ValidationLogger` (noop + real) |

If there's one implementation, it's a concrete struct. No exceptions.

### Interface Location and Size

- Defined in the **consumer package** (`internal/keppel/`), never in implementation packages
- Sizes: 2-3 methods (5 interfaces), 6-8 methods (3), 16 methods (1 — `StorageDriver`)
- Keep large interfaces intact when all implementations need all methods — ISP splitting adds abstraction without value here

### The Pluggable Driver Pattern

```
1. pluggable.Plugin → PluginTypeID() string
2. pluggable.Registry[T] generic registry
3. Package-level: var AuthDriverRegistry pluggable.Registry[AuthDriver]
4. init() self-registration in driver packages
5. Blank import in main.go: _ "github.com/sapcc/keppel/internal/drivers/openstack"
```

---

## 5. HTTP/API Patterns

### Handler Structure

Every handler: `func (a *API) handleVerbResource(w http.ResponseWriter, r *http.Request)`.

```go
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts/:account")  // 1. ALWAYS first
    authz := a.authenticateRequest(w, r, scopes)                  // 2. Auth BEFORE data
    if authz == nil { return }
    account := a.findAccountFromRequest(w, r, authz)              // 3. Load resources
    if account == nil { return }
    // 4. Business logic...
    respondwith.JSON(w, http.StatusOK, map[string]any{"account": rendered})  // 5. Respond
}
// Anti-pattern: missing IdentifyEndpoint, data access before auth
```

### Request Parsing — Strict JSON

```go
decoder := json.NewDecoder(body)
decoder.DisallowUnknownFields()  // REQUIRED — catches typos
err := decoder.Decode(&target)
// Anti-pattern: json.Unmarshal without DisallowUnknownFields
```

### Response Patterns

```go
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": list})  // Collection
if len(items) == 0 { items = []ItemType{} }  // Empty array: [] not null
w.WriteHeader(http.StatusNoContent)           // Delete: bare 204
// Anti-pattern: nil slice marshals to null in JSON
```

### Authentication — Inline, Not Middleware

```go
authz := a.authenticateRequest(w, r, accountScopeFromRequest(r, keppel.CanViewAccount))
if authz == nil { return }
// Anti-pattern: auth as middleware
```

### Error Responses — Three Formats

| API Surface | Format | Helper |
|-------------|--------|--------|
| Registry V2 | `{"errors": [{code, message, detail}]}` | `rerr.WriteAsRegistryV2ResponseTo(w, r)` |
| Keppel V1 | Obfuscated text (5xx get UUID) | `respondwith.ObfuscatedErrorText(w, err)` |
| Auth | `{"details": "..."}` | `rerr.WriteAsAuthResponseTo(w)` |

---

## 6. Error Handling

### Wrapping: `%w` vs `%s`

- **`%w`** when caller may need `errors.Is`/`errors.As`
- **`%s` with `.Error()`** to intentionally break the error chain

### Wrapping Context Prefixes

| Pattern | Example |
|---------|---------|
| `"while <op>: %w"` | `"while parsing chunk object name %q: %w"` |
| `"cannot <op>: %w"` | `"cannot find repo %d for manifest %s: %w"` |
| `"during <method> <url>: %w"` | `"during %s %s: %w"` |

**Never "failed to"** — redundant. Error return already means something failed. Use "cannot" or "while".

### Bare `return err`

Common for DB operation sequences where wrapping would be noise.

### Never Log AND Return the Same Error

- Primary error: returned, never logged
- Secondary/cleanup errors: logged via `logg.Error`, never returned

### Sentinel Errors

- Exported: `var ErrAccountNameEmpty = errors.New("...")`
- Unexported: `var errNoSuchBlob = errors.New("...")`
- API errors: `const ErrBlobUnknown RegistryV2ErrorCode = "BLOB_UNKNOWN"` with `.With()` builder

### Trust stdlib Error Messages

```go
// Anti-pattern: wrapping strconv which already says "strconv.ParseUint: parsing \"hello\": invalid syntax"
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
```

### must.Return / must.Succeed Scope

| Allowed | Not Allowed |
|---------|-------------|
| Startup/bootstrap code | Request handlers |
| Test code (`must.SucceedT`, `must.ReturnT`) | Business logic |
| Package-level var init | Background tasks |

### must vs assert in Tests

| Package | Calls | Use When |
|---------|-------|----------|
| `assert` | `t.Errorf` (non-fatal) | Checking **expected outcome** |
| `must` | `t.Fatal` (fatal) | **Setup/preconditions** where failure means subsequent lines are meaningless |

**Decision tree**: Inside `mustXxx` helper → `must`. Next line depends on this → `must`. Checking tested operation outcome → `assert`. Need return value → `must.ReturnT`.

**The rule: helper = must, assertion = assert.**

### Logging Levels

| Level | When | Where |
|-------|------|-------|
| `logg.Fatal` | Startup failures only | `cmd/` packages only |
| `logg.Error` | Secondary/cleanup errors | Throughout `internal/` |
| `logg.Info` | Operational events | Tasks, processors |
| `logg.Debug` | Diagnostic tracing | Driver selection |

**Never** `log.Printf` or `fmt.Printf`. Always `logg.*`.

### Panic — Only 4 Situations

1. Exhaustive type switches: `panic("unreachable")`
2. Invariant violations: `panic("(why was this not caught by Validate!?)")`
3. Infallible operations: `crypto/rand.Read`, `json.Marshal` on known-good data
4. Driver registration duplicate detection in `init()`

---

## 7. Database Patterns

### gorp + Raw SQL

- **gorp** for simple CRUD (`db.Insert`, `db.Delete`, `db.Update`, `db.SelectOne`, `db.Select`)
- **Raw SQL** for complex queries (JOINs, subqueries, CTEs, UPSERTs)
- **Never** query builders (no squirrel, no gorm)

### SQL Query Style

```go
var blobGetQueryByRepoName = sqlext.SimplifyWhitespace(`
    SELECT b.* FROM blobs b
      JOIN blob_mounts bm ON b.id = bm.blob_id
      JOIN repos r ON bm.repo_id = r.id
     WHERE b.account_name = $1 AND b.digest = $2
       AND r.account_name = $1 AND r.name = $3
`)
```

- SQL keywords UPPERCASED. PostgreSQL `$1`/`$2` params — never `?`.
- SQL queries as package-level `var` with `sqlext.SimplifyWhitespace`.

### Transaction Pattern

```go
tx, err := p.db.Begin()
if err != nil { return err }
defer sqlext.RollbackUnlessCommitted(tx)
// ... work ...
return tx.Commit()  // return directly, no redundant nil check
```

### NULL Handling — Option[T]

`Option[T]` from `github.com/majewsky/gg/option` (dot import), not `*T`:

```go
NextBlobSweepedAt Option[time.Time] `db:"next_blob_sweep_at"`
// Unpack: if gcPolicy, ok := u.GCPolicy.Unpack(); ok { ... }
// Anti-pattern: *time.Time for nullable DB fields
```

### Migrations

Embedded in Go code as `map[string]string`. Naming: `NNN_description.up.sql` / `down.sql`. Every `up` has a corresponding `down`. **Existing migrations are immutable** — never edit deployed ones.

---

## 8. Type Definitions

### Named String Types for Domain Concepts

```go
type AccountName string
type VulnerabilityStatus string
type Permission string
```

### String Enums (NOT iota for domain values)

```go
const CleanSeverity VulnerabilityStatus = "Clean"
// Anti-pattern: iota for values that go to DB/JSON
```

**iota** only for purely internal type discrimination that never touches DB/JSON.

### Model Types

`db:"column_name"` tags for DB. Separate API types with `json:"snake_case"` tags. `omitzero` for `Option[T]`, `omitempty` for regular types.

---

## 9. Testing Patterns

### NOT Table-Driven

Tests are sequential, scenario-driven narratives. Each test reads like a story. **`t.Run` subtests are RARE** — log test case index instead: `t.Logf("----- testcase %d/%d -----")`.

### Test File Organization

- External test packages (`_test` suffix) for API integration tests
- Same-package tests for internal logic
- `shared_test.go` with `TestMain` for shared setup

### Core Testing Stack

| Component | Tool | NOT |
|-----------|------|-----|
| Assertions | `go-bits/assert` | testify |
| DB testing | `easypg.WithTestDB` | manual setup |
| Test setup | `test.NewSetup(t, ...options)` | manual construction |
| HTTP testing | `go-bits/httptest` method chain (`Handler.RespondTo(...).ExpectBody/ExpectHeader/CaptureJSON`) | `httptest.NewRecorder`, removed `assert.HTTPRequest` |
| Time control | `mock.Clock` + `s.Clock.StepBy()` | `time.Now()`, `time.Sleep()` |
| Test doubles | Real interface implementations via `init()` | gomock, mockery |

### TestMain Pattern (REQUIRED for DB tests)

```go
func TestMain(m *testing.M) {
    easypg.WithTestDB(m, func() int { return m.Run() })
}
```

### Canonical HTTP Test Pattern — `httptest.Handler.RespondTo()`

The struct-based `assert.HTTPRequest` builder was **removed** from go-bits in commit 8b79638 along with its helper types (`JSONObject`, `StringData`, `JSONFixtureFile`, `FixtureFile`, `ByteData`). All HTTP tests use the `go-bits/httptest` method chain:

```go
h := httptest.NewHandler(myHandler)

h.RespondTo(ctx, "PUT /keppel/v1/accounts/first",
    httptest.WithHeader("X-Test-Perms", "change:tenant1"),
    httptest.WithJSONBody(map[string]any{
        "account": map[string]any{"auth_tenant_id": "tenant1"},
    }),
).
    ExpectStatus(http.StatusOK).
    ExpectBody(`{"account":{"name":"first"}}`)

// Capture a response body for follow-up assertions
var out struct{ Accounts []string `json:"accounts"` }
h.RespondTo(ctx, "GET /v1/accounts").ExpectStatus(http.StatusOK).CaptureJSON(&out)
```

Legacy `assert.HTTPRequest{}.Check(t, h)` call sites still in downstream code must migrate.

### Assertion Functions

**`assert.Equal[V comparable](t, actual, expected)`** — 3 args, uses `==`. For comparable types (int, string, bool).

**`assert.DeepEqual[V any](t, description, actual, expected)`** — 4 args, uses `reflect.DeepEqual`. For slices, maps, structs.

Common mistake: using `DeepEqual` for `int`/`string` — use `Equal` instead (no reflection).

**`assert.ErrEqual(t, actualErr, expectedErr)`** — flexible: nil, `sql.ErrNoRows`, string, or regexp.

**`must.SucceedT(t, err)`** — abort on error. **`must.ReturnT(val, err)(t)`** — curried, extract value or fail.

### DB Testing

```go
// Full snapshot
easypg.AssertDBContent(t, s.DB.Db, "fixtures/blob-sweep-001.sql")

// Incremental tracking
tr, tr0 := easypg.NewTracker(t, s.DB.Db)
tr0.AssertEqualToFile("fixtures/setup.sql")
tr.DBChanges().AssertEqual(`UPDATE repos SET next_sync_at = 7200 WHERE id = 1;`)
tr.DBChanges().AssertEmpty()
```

### Test Setup with Functional Options

```go
s := test.NewSetup(t,
    test.WithKeppelAPI, test.WithPeerAPI, test.WithAnycast(true),
    test.WithAccount(models.Account{Name: "test1", AuthTenantID: "test1authtenant"}),
    test.WithRepo(models.Repository{AccountName: "test1", Name: "foo"}),
    test.WithQuotas, test.WithTrivyDouble,
)
```

### Test Doubles — Driver Interface Implementations

```go
func init() {
    keppel.AuthDriverRegistry.Add(func() keppel.AuthDriver { return &AuthDriver{} })
}
```

Override methods for test injection: `.OverrideTimeNow(s.Clock.Now)`, `.OverrideGenerateStorageID(s.SIDGenerator.Next)`, `.DisableJitter()`.

### Content Generation

```go
layer := test.GenerateExampleLayer(1)        // 1 MiB gzipped blob
image := test.GenerateImage(layer1, layer2)  // Docker manifest + config
blob := layer.MustUpload(t, s, repoRef)      // Upload through real API
```

### Job Processing Pattern

```go
assert.ErrEqual(t, job.ProcessOne(s.Ctx), nil)           // processed one
assert.ErrEqual(t, job.ProcessOne(s.Ctx), sql.ErrNoRows) // queue drained
easypg.AssertDBContent(t, s.DB.Db, "fixtures/expected.sql")
```

### Test Execution Flags

```bash
go test -shuffle=on -p 1 -covermode=count -coverpkg=... -mod vendor ./...
```

`-shuffle=on`: randomize order. `-p 1`: sequential (shared DB). `-mod vendor`: vendored deps.

### Fixture Patterns

- SQL fixtures: sorted INSERT statements, all non-default columns spelled out
- Sequential naming: `blob-sweep-001.sql`, `002.sql`, `003.sql`
- `.actual` / `.expected` pattern: `make copy-fixtures` promotes `.actual` files
- JSON fixtures for API responses and Trivy reports

---

## 10. Package Organization

```
internal/
├── models/      # Pure data types with db: tags. Zero dependencies.
├── keppel/      # Core: config, DB, driver interfaces, errors, helpers
├── auth/        # Authentication/authorization
├── processor/   # Business logic coordinator. Owns transactions.
├── tasks/       # Background jobs (Janitor). One file per job domain.
├── api/
│   ├── keppel/  # Keppel v1 REST API
│   ├── registry/# OCI Registry V2 API
│   ├── auth/    # Auth API
│   └── peer/    # Peer API
├── drivers/     # Plugin implementations
├── client/      # HTTP clients for peers/upstream
├── test/        # Test infrastructure (NOT test files)
└── stringy/     # String utilities
```

Dependency direction: `models → keppel → processor → api/* → tasks`. Models have zero internal deps.

---

## 11. Import Organization

### Three-Group Strict Order

```go
import (
    "context"                                    // Group 1: stdlib
    "github.com/gorilla/mux"                     // Group 2: external (includes sapcc/go-bits)
    . "github.com/majewsky/gg/option"            // ONLY dot-import allowed
    "github.com/sapcc/keppel/internal/models"    // Group 3: local project
)
```

Enforced by `goimports -local github.com/sapcc/keppel`.

**Dot-import whitelist**: `github.com/majewsky/gg/option`, `ginkgo/v2`, `gomega` — nothing else.

---

## 12. Constants and Package-Level Variables

- Constants live adjacent to the types they describe, not in `constants.go`
- SQL queries as package-level `var` with `sqlext.SimplifyWhitespace`
- Sentinel errors grouped by theme in `var` blocks

---

## 13. Comment Style

### SPDX License Headers (REQUIRED on every .go file)

```go
// SPDX-FileCopyrightText: 2024 SAP SE or an SAP affiliate company
// SPDX-License-Identifier: Apache-2.0
```

### Godoc: `// Name verb...` for exported types/functions

### Inline Comments: Explain WHY, Not WHAT

### Section Dividers: 80 slashes `////////////////`

### `//nolint:gosec // reason` — must specify which linter

---

## 14. Concurrency Patterns

Used **sparingly**. Exactly one `go func` in internal code (Trivy parallelization).

### Worker Pool

```go
inputChan := make(chan models.TrivySecurityInfo, batchSize)
// ... fill and close ...
for range threads {
    wg.Go(func() {
        for securityInfo := range inputChan {
            returnChan <- chanReturnStruct{securityInfo: securityInfo, err: j.doSecurityCheck(ctx, &securityInfo)}
        }
    })
}
```

### Per-Resource Mutex (Not Global Lock)

Each map gets its own `sync.RWMutex`. Read → `RLock`, Write → `Lock`. Always `defer` unlock.

### Ticker + Select for Background Loops

```go
ticker := time.NewTicker(10 * time.Second)
defer ticker.Stop()
for { select { case <-ctx.Done(): return; case <-ticker.C: /* work */ } }
```

---

## 15. Startup and Shutdown

### Subcommand run() Strict Sequence

1. Set task name → 2. Parse config from env → 3. `httpext.ContextWithSIGINT` → 4. Init audit → 5. Connect DB → 6. Init drivers → 7. Start background goroutines → 8. Wire HTTP handlers → 9. `httpext.ListenAndServeContext` (blocks)

### Fatal on Startup Errors

`must.Return()` / `must.Succeed()` in startup. No explicit `os.Exit()` or `signal.Notify()`.

---

## 16. Background Jobs / Task Patterns

### Producer-Consumer via jobloop

```go
func (j *Janitor) BlobSweepJob(registerer prometheus.Registerer) jobloop.Job {
    return (&jobloop.ProducerConsumerJob[models.Account]{
        Metadata: jobloop.JobMetadata{ReadableName: "sweep blobs", CounterOpts: prometheus.CounterOpts{...}},
        DiscoverTask: func(_ context.Context, _ prometheus.Labels) (account models.Account, err error) {
            err = j.db.SelectOne(&account, blobSweepSearchQuery, j.timeNow())
            return
        },
        ProcessTask: j.sweepBlobsInRepo,
    }).Setup(registerer)
}
```

- `DiscoverTask`: SQL query finds next work item. `sql.ErrNoRows` when idle.
- Jitter via `addJitter` (±10%). `DisableJitter()` for tests.
- Fire-and-forget: `go janitor.BlobSweepJob(nil).Run(ctx)`

---

## 17. HTTP Client Patterns

- Global transport via `httpext.WrapTransport(&http.DefaultTransport)`. No custom `http.Client`.
- Always `http.NewRequestWithContext(ctx, method, url, body)`
- Error wrapping: `fmt.Errorf("during %s %s: %w", method, url, err)`

---

## 18-19. String, Slice, and Map Patterns

- `fmt.Sprintf` for construction, concatenation only for simple cases
- `strings.SplitSeq` (Go 1.24+) for iteration
- Nil-vs-empty distinction for JSON: `nil` → `null`, `[]T{}` → `[]`
- `make(map[K]V)` in constructors. `map[string]bool` as set.
- `slices.Contains()`, `slices.Clone()`, `slices.Sorted(maps.Keys())`

---

## 20. Observability and Metrics

- Prometheus metrics as package-level vars with `init()` registration
- `keppel_` prefix, snake_case, `account` + `auth_tenant_id` labels
- CADF audit events via `audittools.Auditor`
- Initialize metrics to 0: `.Set(0)` on all label combinations at init

---

## 21. Project Design Philosophy

| Principle | Summary |
|-----------|---------|
| Radical simplicity | Replace complex systems with small scripts. "As little as possible." |
| Domain-faithful APIs | APIs model the domain, not the transport protocol |
| Backwards compatibility | `*RequestOpts` pointer for extensibility. Stable export surface. |
| Type system as enforcer | `Option[T]` makes optional vs editable unambiguous |
| Trust stdlib | Don't wrap what stdlib says clearly |
| Dependency consciousness | Every import has a cost. Transitive deps matter. |
| Practical over theoretical | "Can you point to a concrete scenario where this fails?" |
| Document the WHY | Design constraints, not just solutions |
| No mutable global state | Functions over global variables |

---

## 22. Where the Project DIVERGES from Standard Go

These are patterns where the project contradicts Go community consensus. An LLM trained on general Go will get these WRONG.

| # | Community Says | Project Convention | Why |
|---|---------------|-------------------|-----|
| 1 | Use field names in struct literals | Positional literals in constructors | Forces compile error when field added |
| 2 | Functional options for many params | 7-8 positional params | Deps are required, not optional |
| 3 | Table-driven tests | Sequential scenario narratives | Integration tests build state across operations |
| 4 | iota for enums | String constants for domain enums | Go directly to DB/JSON without conversion |
| 5 | Middleware for auth | Inline auth at handler top | Different endpoints need different scopes |
| 6 | Small interfaces (1-2 methods) | Large interfaces when domain demands it | All implementations must provide all methods |
| 7 | `*T` for optional values | `Option[T]` from gg/option | Unambiguous: optional vs editable reference |
| 8 | Custom http.Client | Global http.DefaultTransport | One set of settings per service. Context deadlines per-request. |
| 9 | "failed to X" in errors | "cannot X" or "while X" | Error return already means failure. Redundant. |
| 10 | Avoid init() | init() for driver registration | Standard pattern for compile-time-optional modules |
| 11 | Config validation framework | `osext.MustGetenv()` panics | Clear message, no recovery possible |
| 12 | embed.FS for SQL | Migrations as `map[string]string` | Type-checked, version-controlled, no tooling |

---

## 23. go-bits Library Package Guide

| Package | Key Functions | Reads As |
|---------|--------------|----------|
| `must` | `Succeed(err)`, `Return(val, err)` | "must succeed", "must return" |
| `logg` | `Fatal`, `Error`, `Info`, `Debug` | "log fatal" |
| `respondwith` | `JSON(w, code, data)`, `ObfuscatedErrorText(w, err)` | "respond with JSON" |
| `httpapi` | `Compose(apis...)`, `IdentifyEndpoint(r, path)` | "HTTP API compose" |
| `osext` | `MustGetenv(key)`, `GetenvBool(key)` | "OS ext must get env" |
| `sqlext` | `SimplifyWhitespace(sql)`, `RollbackUnlessCommitted(tx)` | "SQL ext rollback unless committed" |
| `assert` | `HTTPRequest{}.Check`, `DeepEqual`, `Equal`, `ErrEqual` | "assert HTTP request" |
| `easypg` | `Connect`, `AssertDBContent`, `NewTracker` | "easy PG connect" |
| `errext` | `ErrorSet`, `IsOfType[T](err)`, `JoinedError` | "error ext" |

Minimal surfaces: `must` = 4 functions, `logg` = 5, `respondwith` = ~6.

---

## 24. Failure Modes That Fail Review

Each entry: CORRECT pattern + failure mode description. Ordered by LLM likelihood.

### AP-1: Types for One-Off JSON
```go
// CORRECT: inline marshaling
storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`, must.Return(json.Marshal(path)))
// Anti-pattern: creating fsParams/fsConfig struct types with json tags for one-time use
```

### AP-2: Wrapping Errors with Existing Context
```go
// CORRECT: trust strconv/constructor error messages
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
// Anti-pattern: fmt.Errorf("failed to parse %q: %w", s, err) when strconv already says it all
```

### AP-3: Manual Dispatch Instead of Cobra
```go
// CORRECT: Cobra subcommands
parent.AddCommand(readManifestCmd, writeBlobCmd)
// Anti-pattern: switch args[0] { case "read-manifest": ... }
```

### AP-4: must.Return in Request Handlers
```go
// CORRECT: proper error handling in handlers
account, err := a.db.FindAccount(name)
if respondwith.ObfuscatedErrorText(w, err) { return }
// Anti-pattern: must.Return in handler — calls os.Exit(1), crashes server
```

### AP-5: Global Mutable Variables
```go
// CORRECT: function that iterates
func ForeachOptionTypeInLIQUID[T any](action func(any) T) []T { ... }
// Anti-pattern: var LiquidOptionTypes = []any{...} — callers can mess with it
```

### AP-6: Handling Theoretical Errors
```go
// CORRECT: ignore stdout write errors (like fmt.Println does)
os.Stdout.Write(data)
// Anti-pattern: error-checking os.Stdout.Write when fmt.Println ignores same issue
```

### AP-7: Defer Close on io.NopCloser
NopCloser's Close is a no-op. Don't add defer. "Irrelevant contrivance."

### AP-8: Manual Error String Building
```go
// CORRECT: use errext.ErrorSet
var errs errext.ErrorSet
errs.Add(validate(item))
if !errs.IsEmpty() { return errs.Join("; ") }
// Anti-pattern: manual concatenation with trailing separator
```

### AP-9: Manual Field Formatting
```go
// CORRECT: marshal the map you already have
payload, _ := json.Marshal(evalInput)
return fmt.Errorf("validation failed for payload: %s", payload)
// Anti-pattern: fmt.Sprintf("mediaType=%s, layers=%d", ...) — breaks when fields change
```

### AP-10: Vague CLI Names
`keppel test-driver storage` not `keppel test`. Specific and extensible.

### AP-11: Smart Defaults That Won't Scale
Explicit `--params <json>` over inferring params from driver name.

### AP-12: Forbidden Libraries
| Forbidden | Use Instead |
|-----------|-------------|
| testify | go-bits/assert |
| zap/zerolog/slog/logrus | go-bits/logg |
| gin/echo/fiber | go-bits/httpapi + gorilla/mux |
| gorm/sqlx/ent | go-gorp/gorp/v3 + go-bits/sqlext |
| viper | osext.MustGetenv / GetenvOrDefault |
| google/uuid / satori/uuid | gofrs/uuid/v5 |
| gomock/mockery | Hand-written doubles |
| ioutil.* | os and io |
| http.DefaultServeMux | http.NewServeMux() |

### AP-13: Missing httpapi.IdentifyEndpoint
Every handler MUST call `httpapi.IdentifyEndpoint(r, path)` first.

### AP-14: Data Access Before Authentication
Authenticate BEFORE any data access. Leaks resource existence otherwise.

### AP-15: Returning null for Empty Collections
`if len(items) == 0 { items = []T{} }` — ensures `[]` not `null` in JSON.

### AP-16: Using httptest.NewRecorder
Use the `go-bits/httptest` method chain: `httptest.NewHandler(h).RespondTo(...).ExpectBody/ExpectHeader/CaptureJSON`. The legacy `assert.HTTPRequest{}.Check(t, h)` builder was removed (commit 8b79638) and is no longer available.

### AP-17: Removing Test Assertions During Refactoring
Assertions that verify behavior must be preserved. Silent removal hides regressions.

### AP-18: time.Now() in Testable Code
Inject `func() time.Time` field, provide `.OverrideTimeNow()` method.

### AP-19: Missing DisallowUnknownFields
Always use on JSON config decoders. Catches typos.

### AP-20: TODOs Without Context
Must include: what, starting-point link, why not done now.

### AP-21: Using Standard log Package
Use `go-bits/logg`. Never `log.Printf`.

### AP-22: Wrong Import Grouping
`sapcc/go-bits` is Group 2 (external), not Group 3 (local).

### AP-23: Not Validating Migration Paths
Check if deprecated env vars still set, abort with clear message.

### AP-24: Panicking on User Input
`must.*` in handlers calls `os.Exit(1)`. Return errors for user input and external failures.

---

## 25. Lead Review on LLM-Generated Code (go-bits)

Actual review comments on LLM-assisted code. Most direct evidence of what LLMs get wrong.

| # | LLM Pattern | Review Correction |
|---|-------------|-------------------|
| 25.1 | Extract helper to reduce cyclomatic complexity | "Contrived edit to satisfy silly metrics" — inline it |
| 25.2 | Export all types | Unexport types when interface is sufficient. Export only constructor. |
| 25.3 | Verbose error checking | `must.SucceedT(t, err)` and `assert.ErrEqual(t, err, nil)` |
| 25.4 | Separate tests per implementation | `testWithEachTypeOfStore` parameterized pattern |
| 25.5 | Option[T] in runtime struct fields | Option only at parse time, `.UnwrapOr()` to concrete |
| 25.6 | Plugin creates own DB connection | Receive dependencies from caller |
| 25.7 | Metrics appear only on first use | `.Set(0)` on all label combinations at init |
| 25.8 | DeepEqual for comparable values | `assert.Equal` preferred (no reflection) |
| 25.9 | Per-type helper functions | Generalize to interface-based helpers |
| 25.10 | Pre-1.22 loop variable capture | Go 1.22+ per-iteration semantics. No more `i := i`. |
| 25.11 | Manual row scanning | `sqlext.ForeachRow` |
| 25.12 | Unnecessary validation wrapper | Use regex directly |
| 25.13 | Docs on concrete type | Document the contract on the interface |
| 25.14 | Plugin hardcodes connection | Factory functions with JSON config |
| 25.15 | Bulk clear in commit | Precise removal of specifically-read items only |

---

## 26. Naming Conventions (Deep Dive)

| # | Rule | Example | Source |
|---|------|---------|--------|
| 26.1 | SQL vars end with "Query" | `getCommitmentQuery` not `getCommitment` | limes |
| 26.2 | Functions describe actual side effects | `buildSplitCommitment` not `splitCommitment` if no DB mutation | limes |
| 26.3 | `Is...` for queries, active verbs for mutations | `IsIgnoredFlavor` not `IgnoreFlavor` for a check | limes |
| 26.4 | `Sorted` = new collection, `Sort` = in-place | Past tense for non-mutating operations | limes |
| 26.5 | Group fields into substruct, drop prefix | `Flavor.Name` not `FlavorName` | limes |
| 26.6 | Counter metrics are plural | `limes_mail_deliveries` | limes |
| 26.7 | Metrics include app prefix | `limes_` prefix | limes |
| 26.8 | Method receiver = actor, not data | `MailClient.Send(info)` not `MailInfo.Send(client)` | limes |
| 26.9 | Short-lived booleans use `ok`/`exists` | Not `fixedCapacityConfigurationExists` | limes |
| 26.10 | Field names use domain terminology | `ShareTypeName` not `NFSType` | castellum |
| 26.11 | No contractions in error messages | "is not" not "isn't" | castellum |
| 26.12 | Error messages read as sentences | "could not parse" not "parse" | limes |
| 26.13 | Preposition precision | "Prometheus query" not "query for Prometheus" | castellum |

---

## 27. Database and SQL Patterns (Deep Dive)

| # | Rule | Fix |
|---|------|-----|
| 27.1 | Existing migrations are immutable | Append new migration, never edit deployed ones |
| 27.2 | DB constraints over app logic | `UNIQUE` constraint, not Go duplicate check |
| 27.3 | TIMESTAMPTZ, never TIMESTAMP | PostgreSQL must include timezone |
| 27.4 | NOT NULL for required fields | Let DB enforce invariants |
| 27.5 | ORM for simple CRUD, raw SQL for complex | `db.Update(&obj)` for single records |
| 27.6 | ExpandEnumPlaceholders for status values | No hardcoded status strings in SQL |
| 27.7 | Return tx.Commit() directly | No redundant nil check |
| 27.8 | Simplest JOIN type | INNER over LEFT OUTER when possible |
| 27.9 | GROUP BY only with aggregates | Remove if no COUNT/SUM/MAX |
| 27.10 | No transactions for single statements | Single statement is already atomic |
| 27.11 | DISTINCT ON for latest-per-group | PostgreSQL feature, not client-side filtering |

```go
// CORRECT: DISTINCT ON (PostgreSQL-specific)
var latestOpsQuery = sqlext.SimplifyWhitespace(`
    SELECT DISTINCT ON (asset_id) o.* FROM finished_operations o
        JOIN assets a ON a.id = o.asset_id WHERE a.resource_id = $1
    ORDER BY o.asset_id, o.finished_at DESC
`)
// Anti-pattern: fetching all rows and filtering in Go
```

### 27.12: Construct url.URL Literals
```go
dbURL := &url.URL{Scheme: "postgres", User: url.UserPassword(user, pass), Host: host+":"+port, Path: name}
// Anti-pattern: fmt.Sprintf then url.Parse
```

---

## 28. CLI Tool Patterns

| # | Rule | Fix |
|---|------|-----|
| 28.1 | CLI args optional when backend has defaults | Let backend infer "current" |
| 28.2 | Regex for input parsing | Not index/substring slicing |
| 28.3 | Compile regex once at package level | `MustCompile` for static, `Compile` for user input |
| 28.4 | time.RFC3339 for all date output | ISO standard, lexically sortable |
| 28.5 | Env var overrides at main() entry point | Set once, not throughout call chain |
| 28.6 | Use library auth discovery | Not manual OS_* enumeration |
| 28.7 | Accept plain names, add prefixes internally | User says "cinder", CLI adds "liquid-" |
| 28.8 | Hyper-specific error messages for admin tools | Grep-friendly error strings |
| 28.9 | Suggest correct command on type mismatch | "this is a domain, try limesctl domain" |
| 28.10 | GET-by-ID first, then filtered list | Never list-all-then-filter for name resolution |
| 28.11 | Flag help states precise constraints | "domain name will not work" not "requires ID" |
| 28.12 | Normalize volatile fields before diffing | Zero out Version/timestamps before compare |
| 28.13 | Validate completeness of set/update inputs | All required fields must be provided |

---

## 29. Modern Go Standard Library Usage

| # | Pattern | Code | Since |
|---|---------|------|-------|
| 29.1 | Sorted map keys | `slices.Sorted(maps.Keys(m))` | 1.23 |
| 29.2 | Key extraction | `slices.Collect(maps.Keys(m))` | 1.23 |
| 29.3 | Slice copying | `slices.Clone(s)` | 1.21 |
| 29.4 | Clone before append to foreign slice | `append(slices.Clone(s), extra)` | 1.21 |
| 29.5 | Membership check | `slices.ContainsFunc(s, pred)` | 1.21 |
| 29.6 | Check-and-remove prefix | `strings.CutPrefix(s, prefix)` | 1.20 |
| 29.7 | Min/max | `min(a, b)` / `max(a, b)` | 1.21 |
| 29.8 | Fixed repetition | `for range N` | 1.22 |
| 29.9 | Loop variables per-iteration | No more `i := i` capture | 1.22 |
| 29.10 | Test context | `t.Context()` | 1.24 |

---

## 30. go-bits Testing API Evolution

### 30.1 httptest.Handler Replaces (Removed) assert.HTTPRequest

`assert.HTTPRequest` was removed from go-bits in commit 8b79638. The canonical HTTP test API is now `go-bits/httptest.Handler`:

```go
h := httptest.NewHandler(myHandler)
h.RespondTo(ctx, "GET /v1/accounts").ExpectJSON(t, http.StatusOK, jsonmatch.Object{...})
h.RespondTo(ctx, "GET /healthcheck").ExpectText(t, http.StatusOK, "ok\n")
```

`CaptureJSON(&target)` and `CaptureHeader(key, &target)` chain on Response.

### 30.2-30.5 Assertion Evolution

- `assert.Equal` (generic, no reflection) for comparable types
- `assert.ErrEqual` supports nil, string, error, regexp
- `must.SucceedT(t, err)` / `must.ReturnT(val, err)(t)` — curried form forced by Go generics

---

## 31. go-bits API Design Principles

| # | Principle | Summary |
|---|-----------|---------|
| 31.1 | Soft-deprecation via docstring | Not `// Deprecated:` annotation (avoids golangci-lint warnings) |
| 31.2 | Add alongside, never replace | Old API stays until migration complete |
| 31.3 | Extract-to-library in three steps | Inline → shared package → core primitive |
| 31.4 | Curried signatures | When Go generics force it: `must.ReturnT(val, err)(t)` |
| 31.5 | errext.JoinedError | Unwrappable error joining for `errors.Is()`/`errors.As()` |
| 31.6 | Verbose parameter names | `expectedErrorOrMessageOrRegexp` for IDE discoverability |
| 31.7 | Callback over acquire/release | `sem.Run(func() { ... })` ensures release |

---

## 32. Option[T] Complete Usage Guide

### Core Rules

| Rule | Example |
|------|---------|
| Always dot-import | `. "github.com/majewsky/gg/option"` — only package that gets dot-imported |
| Replaces `*T` for optionality | `Option[time.Time]` with `omitzero` JSON tag |
| Don't use for non-optional fields | `bool` not `Option[bool]` when always populated |
| Option only at parse time | Resolve with `.UnwrapOr()` before storing in runtime struct |
| `Unpack()` combines check + extract | Not separate `IsNone()` + `UnwrapOrPanic()` |

### Key Methods

```go
val, ok := opt.Unpack()                          // check + extract
canConfirm := opt.IsNoneOr(func(t time.Time) bool { return t.Before(now) })
transformed := options.Map(opt, time.Time.Local)  // transform
legacy := options.FromPointer(ptr).UnwrapOr(0)    // *T → Option[T]
if opt != Some(expected) { /* changed */ }         // value comparison
```

---

## 33. Personal Architecture Patterns (Portunus)

Reveals ideal preferences when free from corporate constraints:

| Pattern | Description |
|---------|-------------|
| State Reducer (Nexus) | All mutations through `nexus.Update(func(db *Database) errext.ErrorSet)`. Clone → apply → validate → commit. |
| Listener pub-sub | `nexus.AddListener(ctx, func(db Database) { writeChan <- db })` for cross-component communication |
| Handler Step chains | `Do(LoadSession, VerifyLogin(n), VerifyPermissions(perms), ...)` — sequential pipeline |
| Deep clone semantics | Manual clone for slices (`append([]T(nil), src...)`), pointers (`val := *ptr; &val`) |
| Generic ObjectList | `Object[Self]` constraint with `Key()` + `Cloned()` methods |
| Composable validation | `ref.Field("name").WrapFirst(MustNotBeEmpty(v), MustNotHaveSpaces(v))` |
| Atomic file writes | Write temp file, then `os.Rename` |
| Fuzz testing parsers | Verify hand-written parsers against regex reference implementation |

---

## 34. Architectural Opinions (2026)

| # | Opinion | Summary |
|---|---------|---------|
| 34.1 | Code as documentation | Go types on pkg.go.dev, not Markdown specs (drift too fast) |
| 34.2 | Package isolation for deletion | v2 package has zero v1 imports. Can delete v1 cleanly. |
| 34.3 | Consumer-oriented API design | "Imagine writing that jq path." Prefer flatter structures. |
| 34.4 | Composable JSON builders | Not static fixture files. Baseline + modifier functions. |
| 34.5 | Eliminate legacy global state | Targeted queries, not `AllXInfo()` |
| 34.6 | Reflection for exhaustive coverage | Over switch statements that drift when fields change |
| 34.7 | Batch atomically | No partial commits that become inconsistent |
| 34.8 | Deep copy when iterating + mutating | Each iteration needs its own copy |
| 34.9 | Ignore inconsistent AI linter noise | If tool flags X but ignores equivalent Y, dismiss |

---

## 35. Cross-Repository Pattern Reinforcement

### Tier 1: 4+ Repos (Non-Negotiable)

| Pattern | Repos |
|---------|-------|
| `must.Return()`/`must.Succeed()` for startup | keppel, limes, portunus, castellum |
| `logg` for all logging | keppel, limes, portunus, castellum |
| `errext.ErrorSet` for multi-error | keppel, limes, portunus, castellum |
| `osext.MustGetenv()` for required env | keppel, limes, portunus, castellum |
| `Option[T]` over `*T` | keppel, limes, castellum, go-bits |
| Three-group imports | keppel, limes, portunus, castellum |
| `assert.Equal`/`DeepEqual` from go-bits | keppel, limes, portunus, go-bits |
| Env vars for config (no files) | keppel, limes, portunus, castellum |
| `internal/` for app code | keppel, limes, portunus, castellum |
| Named return only when defer reads it | keppel, limes, castellum, portunus |
| No "failed to" — use "cannot"/"while" | keppel, limes, castellum, limesctl |
| Trust stdlib errors, don't re-wrap | keppel, limes, limesctl |
| Contract cohesion — artifacts with interface | keppel, limes, castellum, limesctl |

### Tier 2: 2-3 Repos (Strong Signal)

| Pattern | Repos |
|---------|-------|
| `slices.Sorted(maps.Keys())` | limes, castellum |
| `strings.CutPrefix()` | limes, castellum |
| `min()`/`max()` builtins | limes, keppel |
| `for range N` | limes, go-bits |
| Soft-deprecation via docstring | go-bits, limes |
| Constructors infallible | keppel, portunus |
| Positional struct literals | keppel, portunus |
| DB constraints over app checks | limes, castellum |
| Deep copy when iterating + mutating | limes, portunus |

### Tier 3: 1 Repo (Context-Specific)

Handler Step chains (portunus), State Reducer/Nexus (portunus), `httptest.Handler.RespondTo()` (go-bits/limes), composable JSON builders (limes), reflection for exhaustive coverage (limes), `DISTINCT ON` (castellum).

---

## 36. Contract Cohesion

The file defining an interface or contract type MUST also contain:
1. Constants that are part of that contract
2. Error sentinels returned by that interface's methods
3. Validation functions for that interface's parameters

Files named for domain concept (`storage_driver.go`), not generically (`interface.go`, `types.go`).

**Test**: If you can name which interface a constant belongs to, it doesn't belong in `util.go`.

---

## Master Rule Table (N1-N89)

| Rule | Category | One-Line Description |
|------|----------|---------------------|
| N1 | Naming | SQL vars end with "Query" |
| N2 | Naming | Functions describe actual side effects |
| N3 | Naming | `Is...` for queries, active verbs for mutations |
| N4 | Naming | `Sorted` = new collection, `Sort` = in-place |
| N5 | Naming | Group fields into substruct, drop prefix |
| N6 | Metrics | Counter metrics are plural |
| N7 | Metrics | Metrics include app prefix |
| N8 | Design | Method receiver = actor, not data |
| N9 | Naming | Short-lived booleans use `ok`/`exists` |
| N10 | Naming | Field names use domain terminology |
| N11 | Errors | No contractions in error messages |
| N12 | Errors | Error messages read as sentences |
| N13 | Errors | Preposition precision in errors |
| N14 | DB | Existing migrations are immutable |
| N15 | DB | DB constraints over app logic |
| N16 | DB | TIMESTAMPTZ, never TIMESTAMP |
| N17 | DB | NOT NULL for required fields |
| N18 | DB | ORM for simple CRUD, raw SQL for complex |
| N19 | DB | ExpandEnumPlaceholders for status values |
| N20 | DB | Return tx.Commit() directly |
| N21 | DB | Simplest JOIN type that works |
| N22 | DB | GROUP BY only with aggregate functions |
| N23 | DB | No transactions for single statements |
| N24 | DB | DISTINCT ON for latest-per-group |
| N25 | DB | Construct url.URL literals |
| N26 | CLI | CLI args optional when backend has defaults |
| N27 | CLI | Regex for input parsing, not index slicing |
| N28 | CLI | Compile regex once at package level |
| N29 | CLI | time.RFC3339 for all date output |
| N30 | CLI | Env var overrides at main() entry point |
| N31 | CLI | Use library auth discovery |
| N32 | CLI | Accept plain names, add prefixes internally |
| N33 | CLI | Hyper-specific error messages for admin tools |
| N34 | CLI | Suggest correct command on type mismatch |
| N35 | CLI | GET-by-ID first, then filtered list |
| N36 | CLI | Flag help states precise constraints |
| N37 | CLI | Normalize volatile fields before diffing |
| N38 | CLI | Validate completeness of set/update inputs |
| N39 | Modern Go | `slices.Sorted(maps.Keys())` |
| N40 | Modern Go | `slices.Collect(maps.Keys())` |
| N41 | Modern Go | `slices.Clone()` for copying |
| N42 | Modern Go | Clone before appending to foreign slices |
| N43 | Modern Go | `slices.ContainsFunc` for membership |
| N44 | Modern Go | `strings.CutPrefix()` for check-and-remove |
| N45 | Modern Go | Built-in `min()`/`max()` |
| N46 | Modern Go | `for range N` for fixed repetition |
| N47 | Modern Go | Go 1.22+ loop variables per-iteration |
| N48 | Modern Go | `t.Context()` in tests |
| N49 | Testing | `httptest.Handler.RespondTo()` for new tests |
| N49b | Testing | `Response.CaptureJSON(&target)` for JSON capture |
| N49c | Testing | `Response.CaptureHeader(key, &target)` for headers |
| N50 | Testing | `assert.Equal` for comparable types |
| N51 | Testing | `assert.ErrEqual` for flexible error matching |
| N52 | Testing | `must.SucceedT` / `must.ReturnT` in tests |
| N53 | API Design | Soft-deprecation via docstring |
| N54 | API Design | Add alongside, never replace |
| N55 | API Design | Extract-to-library in three steps |
| N56 | API Design | Curried signatures when generics force it |
| N57 | API Design | `errext.JoinedError` for unwrappable joins |
| N58 | API Design | Verbose parameter names for IDE discoverability |
| N59 | API Design | Callback pattern over acquire/release |
| N60 | Option | Dot-import the option package |
| N61 | Option | `Option[T]` replaces `*T` for optionality |
| N62 | Option | Don't use Option for non-optional fields |
| N63 | Option | `Unpack()` combines check and extraction |
| N64 | Option | `IsNoneOr()` for conditional checks |
| N65 | Option | `options.Map()` for transforming values |
| N66 | Option | `options.FromPointer()` for legacy conversion |
| N67 | Option | Option types comparable with `==` |
| N68 | Option | `TryInstantiate` returns `Option[T]` |
| N69 | Architecture | State Reducer / Nexus pattern |
| N70 | Architecture | Listener-based pub-sub |
| N71 | Architecture | Handler Step chains |
| N72 | Architecture | Deep clone semantics on domain types |
| N73 | Architecture | Generic ObjectList with type constraints |
| N74 | Architecture | Validation errors with ObjectRef/FieldRef |
| N75 | Architecture | Atomic file writes (tmp + rename) |
| N76 | Architecture | Fuzz testing for hand-optimized parsers |
| N77 | Architecture | Code as documentation — types on pkg.go.dev |
| N78 | Architecture | Package isolation for clean deletion |
| N79 | Architecture | Consumer-oriented API design |
| N80 | Architecture | Composable JSON builders for test data |
| N81 | Architecture | Eliminate legacy global state |
| N82 | Architecture | Reflection for exhaustive field coverage |
| N83 | Architecture | Batch all related changes atomically |
| N84 | Architecture | Deep copy when iterating + mutating shared data |
| N85 | Process | Ignore inconsistent AI linter suggestions |
| N86 | Organization | Contract cohesion — artifacts with interface |
| N87 | Organization | Files named for domain concept |
| N88 | Organization | util.go only for cross-cutting utilities |
| N89 | Organization | Scattered contract artifacts = review finding |
