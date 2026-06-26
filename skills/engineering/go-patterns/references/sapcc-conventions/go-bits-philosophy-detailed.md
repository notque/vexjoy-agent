# go-bits Library Design Philosophy -- Detailed Reference

go-bits library design rules, per-package design notes for all **23 go-bits subpackages** (verified against `sapcc/go-bits@b9734b4`, 2026-06-23), API surface inventory, contributor patterns, and evolution direction. The 17-package picture in older revisions of this doc predates the additions of `audittools`, `easypg`, `gopherpolicy`, `gophercloudext`, `liquidapi`, `promquery`, and `vault` to the public surface.

---

## 1. go-bits Library Design Rules

### Rule 1: One Package = One Concept

Every package addresses exactly one concern. `must` = fatal errors. `logg` = logging. `respondwith` = HTTP responses. No package tries to do two things. Even when closely related (httpapi vs httpext vs httptest), they are separate packages.

### Rule 2: Minimal API Surface

Packages export the fewest symbols possible:
- `must` has 4 functions
- `logg` has 5 log functions + 2 config symbols
- `syncext` has 1 type with 3 methods

The bias is always toward fewer, more general functions rather than many specific ones.

### Rule 3: Names That Read as English

Package names are chosen so that qualified usage reads naturally:

```go
must.Succeed(err)                    // "must succeed"
must.Return(os.ReadFile(...))        // "must return"
respondwith.JSON(w, 200, data)       // "respond with JSON"
respondwith.ErrorText(w, err)        // "respond with error text"
logg.Fatal(msg)                      // "log fatal"
errext.As[T](err)                    // "error extension: as T"
```

### Rule 4: Document the WHY, Not Just the WHAT

Extensive internal comments explaining design constraints and rejected alternatives:

- **`must.ReturnT`**: Three paragraphs explaining why the signature is the only one that works given Go generics limitations
- **`assert.ErrEqual`**: Two NOTEs explaining why `any` is used and why the parameter name is verbose (`expectedErrorOrMessageOrRegexp` -- "intended to help users who see only the function signature in their IDE autocomplete")
- **`assert.DeepEqual`**: Comment block: "We HAVE TO use %#v here, even if it's verbose"
- **`respondwith.CustomStatus`**: Explains why wrapped errors lose their custom status (security)
- **`respondwith.error.go`** nolint: "I won't put 'error' at the end because 'customStatusHavingError' sounds stupid"

### Rule 5: Panics for Programming Errors, Errors for Runtime Failures

- **Panic**: nil factory in `pluggable.Add`, calling `SkipRequestLog` outside `Compose`, mixing `WithBody` and `WithJSONBody`
- **Error return**: Missing env var, failed SQL query, JSON marshal failure
- **Fatal (os.Exit)**: `must.Succeed` for genuinely unrecoverable startup errors

### Rule 6: Concrete Before/After Examples in Docs

Almost every function's godoc shows the exact code it replaces:

```go
// must.Succeed replaces:
if err != nil {
    logg.Fatal(err.Error())
}
// with:
must.Succeed(err)

// errext.As replaces:
var rerr *keppel.RegistryV2Error
if errors.As(err, &rerr) { ... }
// with:
if rerr, ok := errext.As[*keppel.RegistryV2Error](err); ok { ... }
```

### Rule 7: Enforce Correct Usage Through Type System

- `jobloop.Setup()` returns a `Job` interface wrapping a private type -- cannot skip initialization
- `pluggable.Registry[T Plugin]` constrains the type parameter to `Plugin` interface
- `Response.CaptureJSON` requires a pointer argument; panics otherwise
- `respondwith.CustomStatus` only works unwrapped -- prevents information leakage

### Rule 8: Dependency Consciousness

Unnecessary dependency trees are actively prevented:
- Rejected importing UUID from `audittools` into `respondwith` because it would pull in AMQP dependencies. Solution: move to `package internal`
- Refused to add Ginkgo to go.mod just for a compile test, "to avoid putting additional noise on Renovate"
- External dependencies are minimal: gorilla/mux, prometheus, gophercloud, lib/pq, go-diff

### Rule 9: Defense in Depth with Documentation

Functions have branches that handle theoretically impossible cases:
- `assert.ErrEqual`: Has branches for `nil` in the `error` case that "should have been covered by the previous case branch"
- Comment: "I could swear that, in earlier Go versions, this only matched the plain `nil` value... I'm assuming this to be undefined behavior and thus took care to make those branches behave the same"

### Rule 10: Graceful Deprecation

- `assert.HTTPRequest` is deprecated but not removed. Deprecation includes complete migration guide with code examples
- `httptest` package was added as a replacement before the old API was deprecated
- No forced migration -- old code continues to work

### Rule 11: Prefer Functions Over Global Variables

Convention: Rejected `var LiquidOptionTypes = []any{...}` because "I don't like having a global variable for this that callers can mess with." Instead: `func ForeachOptionTypeInLIQUID[T any](action func(any) T) []T` -- encapsulates data, prevents mutation.

### Rule 12: Leverage Go Generics Judiciously

Generics are used where they eliminate boilerplate or improve type safety:
- `must.Return[V]` preserves the return type
- `errext.As[T]` eliminates pointer-to-pointer pattern
- `ProducerConsumerJob[T]` parameterizes the task type
- `pluggable.Registry[T Plugin]` constrains plugin types
- `ConfigSet[K, V]` parameterizes both key and value types

Generics are NOT used where they would add complexity without clear benefit.

---

## 2. Per-Package Design Notes -- 17 Core go-bits Subpackages

The 17 packages below are the core utility subpackages reviewed by Rule 1 ("one package = one concept"). The remaining 6 packages on the public surface — `audittools`, `easypg`, `gopherpolicy`, `gophercloudext`, `liquidapi`, `promquery`, `vault` — are integration packages (each wraps an external system) and are documented in `library-reference.md`.

### must/ -- Fatal Error Shorthand

- **Files**: 1 (`must.go`)
- **API surface**: 8 functions (Succeed, SucceedT, Return, ReturnT, BeOK, BeOKT, NotBeOK, NotBeOKT), 0 types
- **Exported**: `Succeed(error)`, `SucceedT(testing.TB, error)`, `Return[V](V, error) V`, `ReturnT[V](V, error) func(testing.TB) V`, `BeOK[V](V, bool) V`, `BeOKT[V](V, bool) func(testing.TB) V`, `NotBeOK[V](V, bool) V`, `NotBeOKT[V](V, bool) func(testing.TB) V`
- **Philosophy**: Eliminate `if err != nil { log.Fatal(...) }` boilerplate. Only for truly fatal errors. Generics preserve type safety in `Return` and `ReturnT`.
- **Design insight**: `ReturnT` has a long comment explaining WHY its signature is `func(V, error) func(*testing.T) V` -- Go generics prevent type args in methods, and multi-return expressions cannot mix with other arguments.
- **Opinionated**: Extremely. Calls `os.Exit(1)`. No recovery possible.

### assert/ -- Test Assertions (thin forwarder as of 2026-06)

- **Files**: 1 (`assert.go`) plus tests. The 3 prior files (`http.go`, `values.go`, `assert_test.go`) collapsed when the package was rewritten as a forwarder.
- **API surface**: 3 exported functions
- **Exported**: `Equal[V comparable](TestingTB, actual, expected V) bool`, `ErrEqual(TestingTB, actual error, expectedErrOrMessageOrRegexp any) bool`, `DeepEqual[V any](TestingTB, variable string, actual, expected V) bool`
- **Removed (2026-06, commit 8b79638)**: `HTTPRequest`, `StringData`, `JSONObject`, `JSONFixtureFile`, `FixtureFile`, `ByteData`. Migrate HTTP tests to the `httptest` method-chain API.
- **Philosophy**: As of commit 90af602 the package is a thin forwarder to `go.xyrillian.de/gg/assert v1.10.1`. The original wrappers stayed compatible to spare downstream consumers (Limes, Keppel) a forced migration; the plan is to migrate downstream code to `gg/assert` directly, then deprecate this package.
- **New-code rule**: prefer `gg/assert` imports for code written today; old call sites are not required to migrate.

### logg/ -- Structured Logging

- **Files**: 1 (`log.go`)
- **API surface**: 5 log functions + 2 config symbols
- **Exported**: `Fatal`, `Error`, `Info`, `Debug`, `Other`, `ShowDebug`, `SetLogger`
- **Philosophy**: Printf-or-Println auto-detection. Always prefixes with level. Forces single-line output (`\n` -> `\\n`). Deliberately simple -- no structured logging, no JSON, no log levels as integers.
- **Concurrency**: Thread-safe via `sync.Mutex`.

### errext/ -- Error Handling Extensions

- **Files**: 3 (`errext.go`, `errorset.go`, `errext_test.go`)
- **API surface**: 2 generic functions + 1 collection type + 1 joined error type
- **Exported**: `As[T error]`, `IsOfType[T error]`, `ErrorSet`, `JoinedError`
- **Philosophy**: Fill gaps in `errors` package using generics. `As[T]` makes `errors.As` idiomatic Go (comma-ok pattern). `IsOfType[T]` named differently from `errors.Is` to avoid confusion.
- **ErrorSet**: Accumulate errors. Methods: `Add`, `Addf`, `Append`, `IsEmpty`, `Join`, `JoinedError`, `LogFatalIfError`.
- **JoinedError**: Wraps errors with separator, implements `Unwrap() []error` for Go 1.20+ multi-error.

### respondwith/ -- HTTP Response Helpers

- **Files**: 2 (`pkg.go`, `error.go`)
- **API surface**: 5 functions + a `CustomOption` option type
- **Exported**: `JSON`, `ErrorText`, `ObfuscatedErrorText`, `CustomStatus`, `CustomHeader`, `CustomOption`
- **Philosophy**: Package named to read as English: `respondwith.JSON(w, 200, data)`. Doc: "Its name is like that because it pairs up with the function names."
- **Performance**: `JSON` uses `json.Encoder.Encode` instead of `json.Marshal` to avoid extra buffer allocation.
- **Security**: `ObfuscatedErrorText` generates UUID for 5xx, logs real error server-side. `CustomStatus` does NOT work when wrapped (prevents leaking sensitive data).
- **`CustomHeader` (added 2026-05, commit ef7eeca)**: a `CustomOption` that attaches HTTP headers to error responses built by `CustomStatus`, so 4xx flows can carry e.g. `WWW-Authenticate` headers without a separate `w.Header().Set` step.
- **Dependency consciousness**: `GenerateUUID()` was moved to `package internal` to avoid pulling AMQP into all consumers.

### pluggable/ -- Plugin Factory

- **Files**: 2 (`pluggable.go`, `pluggable_test.go`)
- **API surface**: 1 interface + 1 generic struct + 3 methods
- **Exported**: `Plugin` interface, `Registry[T Plugin]`, `Add`, `Instantiate`, `TryInstantiate`
- **Philosophy**: Tiny plugin factory using `init()` registration. `Add` panics on nil factory, empty type ID, or duplicates -- programming errors, not runtime errors.
- **Evolution**: `TryInstantiate` returns `Option[T]` from `majewsky/gg/option`.

### httpapi/ -- HTTP API Composition

- **Files**: 6 (`doc.go`, `api.go`, `compose.go`, `middleware.go`, `metrics.go`, `pprofapi/`)
- **API surface**: ~10 exported symbols
- **Exported**: `API` interface, `Compose`, `HealthCheckAPI`, `WithoutLogging`, `WithGlobalMiddleware`, `SkipRequestLog`, `IdentifyEndpoint`, `IdentifyUser`, `ConfigureMetrics`
- **Philosophy**: Opinionated composition. `Compose(apis...)` builds a single `http.Handler` with logging and metrics. Uses gorilla/mux internally but abstracts it away.
- **`IdentifyUser` (added 2026-04, commit f63acfb)**: lets a handler attach a user identity (opaque string) to the REQUEST log line for the current request; pairs with `IdentifyEndpoint`. No tight coupling to gopherpolicy — any auth scheme can supply a string.
- **Out-of-band communication**: Context values for handlers to message middleware. Panics if called outside `Compose()`.

### httptest/ -- Test HTTP Handler (canonical HTTP test pattern as of 2026-06)

- **Files**: 3 (`handler.go`, `handler_test.go`, `fixtures/`)
- **API surface**: ~20 exported symbols
- **Exported**: `Handler`, `NewHandler`, `RespondTo`, `Response`, `MergeRequestOptions`, request-option helpers (`WithBody`, `WithHeader`, `WithHeaders`, `WithJSONBody`, `RequestOption`), and the `Response` chain methods `ExpectBody`, `ExpectHeader`, `ExpectHeaders`, `CaptureJSON`, `CaptureHeader`.
- **Philosophy**: Fluent API for HTTP test assertions. `RespondTo(ctx, "GET /v1/info")` combines method+path. `RequestOption`s configure the request side; `Response` methods handle the response side via chaining.
- **Replaces `assert.HTTPRequest`** (removed in commit 8b79638). The method-chain style is now the only supported pattern: `h.RespondTo(ctx, "GET /v1/assets").ExpectStatus(200).ExpectBody(expected).CaptureJSON(&out)`.
- **Dual-mode**: Supports both `testing.TB` (broadened from `testing.T` in commit 6042f07) and Ginkgo/Gomega.
- **Error philosophy**: Never returns errors -- fabricated 999 status for marshal failures.

### jobloop/ -- Worker Loop Abstraction

- **Files**: 7
- **API surface**: ~12 exported symbols
- **Exported**: `Job` interface, `CronJob`, `ProducerConsumerJob[T]`, `ProcessMany`, `JobMetadata`, `Option`, `NumGoroutines`, `WithLabel`
- **Philosophy**: Two implementations: `CronJob` (time-interval) and `ProducerConsumerJob[T]` (poll-and-process).
- **Setup pattern**: `.Setup(registerer)` returns `Job` interface wrapping private type -- enforces init.
- **Error handling**: `sql.ErrNoRows` = 3s sleep, other errors = 5s sleep (backpressure).
- **Prometheus**: Auto-counts tasks with `success|failure` labels. Pre-initialized for absence alerts.

### syncext/ -- Sync Extensions

- **Files**: 1 (`semaphore.go`)
- **API surface**: 1 type + 3 methods
- **Exported**: `Semaphore`, `NewSemaphore`, `Run`, `RunFallible`
- **Philosophy**: Channel-based counting semaphore. Recent addition (Dec 2025). Minimal: `Run(func())` and `RunFallible(func() error)`.

### httpext/ -- HTTP Extensions

- **Files**: 4
- **API surface**: ~6 functions/vars
- **Exported**: `GetRequesterIPFor`, `ListenAndServeContext`, `ListenAndServeTLSContext`, `ContextWithSIGINT`, `ShutdownTimeout`, `LimitConcurrentRequestsMiddleware`
- **Philosophy**: Context-aware HTTP server lifecycle. Graceful shutdown. `ContextWithSIGINT` accepts delay for reverse-proxy awareness.

### osext/ -- OS Extensions

- **Files**: 3
- **API surface**: 4 functions + 1 error type
- **Exported**: `MustGetenv`, `NeedGetenv`, `GetenvOrDefault`, `GetenvBool`, `MissingEnvError`
- **Philosophy**: Env var access with sensible defaults. `MissingEnvError` is a named type for `errors.As`.

### secrets/ -- Credential Handling

- **Files**: 2
- **API surface**: 1 type + 1 function
- **Exported**: `FromEnv`, `GetPasswordFromCommandIfRequested`
- **Philosophy**: `FromEnv` unmarshals from plain string or `{ fromEnv: "ENV_VAR_NAME" }`. Shared `unmarshalImpl` for JSON and YAML (DRY).

### sqlext/ -- SQL Extensions

- **Files**: 3
- **API surface**: 2 interfaces + 4 functions
- **Exported**: `Executor` interface, `Rollbacker` interface, `ForeachRow`, `RollbackUnlessCommitted`, `SimplifyWhitespace`, `WithPreparedStatement`
- **Philosophy**: Common SQL patterns as functions. `Executor` abstracts `*sql.DB` vs `*sql.Tx`. `ForeachRow` eliminates rows-iterate-scan-close boilerplate.
- **Interface verification**: `var _ Executor = &sql.DB{}` at package level.

### regexpext/ -- Regex Extensions

- **Files**: 4
- **API surface**: 1 type + 1 generic struct
- **Exported**: `BoundedRegexp`, `ConfigSet[K, V]`
- **Philosophy**: `ConfigSet` is a map with regex keys. `PickAndFill` supports capture group expansion.
- **Evolution**: Moving toward `Option[T]` from `majewsky/gg` for nullable values.

### mock/ -- Test Doubles

- **Files**: 5
- **API surface**: Small
- **Exported**: `Clock`, `NewClock`
- **Philosophy**: Deterministic test doubles. `Clock` starts at Unix epoch, only advances via `StepBy`.

### easypg/ (audittools/) -- Audit and DB Testing

- Part of go-bits ecosystem, used extensively in keppel tests
- `audittools.MockAuditor` captures and asserts CADF audit events
- `easypg` provides `WithTestDB`, `AssertDBContent`, `NewTracker`, `DBChanges`

---

## 3. API Surface Inventory

Counts reflect `sapcc/go-bits@b9734b4` (2026-06-23). The first 17 rows are the core utility packages; the trailing 6 rows are integration packages (deferred to `library-reference.md` for detailed APIs).

| Package | Exported Symbols | Functions | Types | Interfaces |
|---------|-----------------|-----------|-------|------------|
| must | 8 | 8 | 0 | 0 |
| assert | 3 (forwards to gg/assert) | 3 | 0 | 0 |
| logg | 7 | 5 | 0 | 0 |
| errext | ~12 | 2 | 2 | 0 |
| respondwith | 6 | 5 (incl. CustomHeader) | 1 | 0 |
| pluggable | ~5 | 0 | 1 | 1 |
| httpapi | ~10 | 5 (incl. IdentifyUser) | 1 | 1 |
| httptest | ~20 | 6 (incl. MergeRequestOptions, ExpectBody, ExpectHeader, CaptureJSON, CaptureHeader) | 3 | 0 |
| jobloop | ~12 | 1 | 2 | 1 |
| syncext | 4 | 1 | 1 | 0 |
| httpext | ~7 | 4 (incl. ListenAndServeTLSContext) | 0 | 0 |
| osext | 6 | 5 (incl. NeedGetenv) | 1 | 0 |
| secrets | 2 | 1 | 1 | 0 |
| sqlext | ~6 | 4 | 0 | 2 |
| regexpext | ~6 | 0 | 4 | 0 |
| mock | ~3 | 1 | 1 | 0 |
| **(integration packages — see library-reference.md)** | | | | |
| audittools | ~15 | several | 5+ | 2 |
| easypg | ~12 | 4 | 4 | 0 |
| gopherpolicy | ~15 | 4 (incl. Enforce) | 3 | 1 |
| gophercloudext | ~6 | 3 | 1 | 0 |
| liquidapi | ~10 | 4 | 2 | 1 |
| promquery | ~8 | 3 | 2 | 0 |
| vault | 1 | 1 | 0 | 0 |

---

## 4. Secondary Reviewer's Contribution Patterns

### Infrastructure and Operational Focus

The secondary reviewer's contributions tend toward infrastructure and operational improvements:
- Increase max_connections (database configuration)
- Speed up tests (CI efficiency)
- Recreate postgres db when a major update was done (operational safety)
- Revert of a file cleanup change (quick response to regression)
- Remove resolved TODO (code hygiene)

### Review Style

Pragmatic, implementation-focused:
- Suggests `cmp.Equal` over human-readable diff for performance
- Asks whether `DeepEqual` can be simplified to `==`
- Suggests code structure improvements with concrete snippets
- Approves with humor: "gotta go fast"

### Patterns

1. **Operational pragmatism** -- focuses on what works in production
2. **Quick iteration** -- rapid reverts when something breaks
3. **Clean-up tendency** -- removes TODOs, fixes lints
4. **Simplification bias** -- prefers `==` over `DeepEqual`, `cmp.Equal` over human-readable diff

---

## 5. go-bits Evolution and Direction

### Recent Additions (2025-2026)

| Package/Feature | Date | Purpose |
|----------------|------|---------|
| `syncext.Semaphore` | Dec 2025 | Counting semaphore for concurrency limiting |
| `httptest` package | Jan 2025 | New fluent API for HTTP test assertions |
| `httpext.LimitConcurrentRequestsMiddleware` | Aug 2025 | Uses the new Semaphore |
| `respondwith.CustomStatus` | Jul 2025 | Error status code customization |
| `respondwith.ObfuscatedErrorText` | Jul 2025 | Security-conscious error responses |
| `errext.JoinedError` | Nov 2025 | Multi-error unwrapping (Go 1.20+) |
| `must.SucceedT`, `must.ReturnT` | Oct 2025 | Test-specific must variants |
| `assert.ErrEqual` | Oct 2025 | Flexible error assertion |
| `pluggable.TryInstantiate` | Nov 2025 | Option[T] return for plugin lookup |
| `Response.CaptureJSON` | Apr 2026 | JSON response capture as chained method on Response |
| `Response.CaptureHeader` | Apr 2026 | Response header capture in method-chain style |
| `httpapi.IdentifyUser` | Apr 2026 (f63acfb) | Tag REQUEST log line with opaque user identity |
| `audittools.MockAuditor.ExpectEvents` MIME-aware diffs | May 2026 (42a3e06) | Structural compare of nested JSON inside audit attachments |
| `respondwith.CustomHeader` | May 2026 (ef7eeca) | `CustomOption` to attach headers to error responses |
| `must.BeOK` / `BeOKT` | May 2026 (89cf13f) | Comma-ok extraction analogue of `must.Return` |
| `must.NotBeOK` / `NotBeOKT` | May 2026 (0e5c058) | Inverse: fatal if the bool is true |
| `gopherpolicy.Token.Enforce` (error-returning) | May 2026 | Composes with `respondwith.CustomStatus`/`ErrorText` for 401/403 |
| `audittools` durable-queue config refactor | Jun 2026 (7cd042d) | Durability determined by queue name (`dataplaneAuditQueueName` durable, others transient); `AuditorOpts.QueueDurable` field removed |
| `assert` → `gg/assert` forwarder | Jun 2026 (90af602) | `go-bits/assert` is now a thin wrapper around `go.xyrillian.de/gg/assert v1.10.1` |
| `liquidapi` package | Growing | Server runtime + fair-distribution helpers for the LIQUID protocol |

### Deprecations and Removals

- **`assert.HTTPRequest` and its helper types (`StringData`, `JSONObject`, `JSONFixtureFile`, `FixtureFile`, `ByteData`) — REMOVED in commit 8b79638.** Migrate to the `httptest.Handler` + `RespondTo` + method-chain `Response.ExpectBody`/`ExpectHeader`/`CaptureJSON` API. This is no longer a soft deprecation.
- **`go-bits/assert` package — soft-superseded by `go.xyrillian.de/gg/assert`.** The package now forwards calls and stays import-compatible to spare downstream code a forced migration; prefer `gg/assert` imports in new code.
- **`AuditorOpts.QueueDurable` — REMOVED in commit 7cd042d.** Durability is now governed by the queue name. `internal/testutil.mockt` removed (was always internal). `testing.T` replaced with `testing.TB` in public signatures (commit 6042f07).
- Coveralls removed from CI (Aug 2025).

### Direction

1. **Generics adoption**: New functions consistently use generics (`Return[V]`, `BeOK[V]`, `As[T]`, `ProducerConsumerJob[T]`).
2. **Option[T] type**: Increasing use from `majewsky/gg/option` instead of nil pointers.
3. **Fluent test APIs**: The method-chain `httptest.Response` API is now the canonical HTTP test pattern; struct-based builders have been removed, not merely deprecated.
4. **Security-conscious defaults**: `ObfuscatedErrorText` hides errors; `CustomStatus` only works unwrapped; `CustomHeader` adds 401/403 headers cleanly.
5. **LIQUID protocol**: Growing `liquidapi` package — most new development.
6. **Concurrency primitives**: `syncext.Semaphore` + `LimitConcurrentRequestsMiddleware`.
7. **Test ergonomics**: `SucceedT`, `ReturnT`, `BeOK`/`NotBeOK` variants, MIME-aware audit diffs.
8. **Cross-org alignment**: assertion library converging on `go.xyrillian.de/gg`; downstream migration is gradual.
9. **Go version floor**: `go.mod` requires Go 1.26.

### What's NOT Changing

- Package structure: one concept per package, minimal API surface
- Dependency conservatism
- Documentation standards: before/after examples, design constraint explanations
- Error philosophy: panics for programming errors, errors for runtime failures

---

## 6. When to Use go-bits vs stdlib vs External Libraries

### Use go-bits When

1. **Pattern repeated across 3+ sapcc apps** -- go-bits is "extracted from original applications for reusability" (README)
2. **stdlib requires 3+ lines of boilerplate** -- `must.Succeed` replaces 3 lines, `sqlext.ForeachRow` replaces ~8
3. **SAP-specific integration** -- OpenStack token validation, LIQUID API, RabbitMQ audit trails
4. **SAP operational conventions** -- Prometheus metric names, HTTP logging format, PostgreSQL migration
5. **Type-safe wrappers around stdlib** -- `errext.As[T]`, `must.Return[V]`, `assert.Equal[V comparable]`

### Use stdlib When

1. **stdlib is already clear and concise** -- Don't wrap `fmt.Sprintf`, `strings.Contains`
2. **Abstraction would hide important details** -- Don't wrap `http.Client` config
3. **Pattern only used once** -- go-bits is for shared patterns

### Use External Libraries When

1. **Problem domain is complex and well-solved** -- gorilla/mux, prometheus, golang-migrate
2. **Library is actively maintained**
3. **Dependency is acceptable** -- consider dependency tree impact

### Deprecated Functions

1. **Library that duplicates go-bits** -- No testify when `go-bits/assert` exists. No logrus when `logg` exists.
2. **Library with heavy transitive deps for small features** -- UUID moved to `internal` to avoid AMQP deps
3. **Library that imposes a framework** -- go-bits wraps stdlib patterns, doesn't replace them

---

## 7. Key Design Patterns Summary

| Pattern | Where Used | Principle |
|---------|-----------|-----------|
| Functional options | jobloop.Option, httptest.RequestOption | Extensible config without breaking changes (request-side only; response-side uses method chaining) |
| Setup-then-use | jobloop.CronJob.Setup() | Enforce initialization via type system |
| Private impl wrapping | cronJobImpl, producerConsumerJobImpl | Hide impl, enforce Setup() |
| Compose pattern | httpapi.Compose(apis...) | Assemble complex from simple |
| PseudoAPI trick | WithoutLogging(), WithGlobalMiddleware() | Config disguised as API argument |
| Panic on programmer error | pluggable.Add(nil) | Fast failure for misuse |
| Named package = English | must.Succeed, respondwith.JSON | Readable qualified names |
| Concrete godoc examples | Every function in must/, errext/ | Show before/after |
| Interface verification | sqlext: `var _ Executor = &sql.DB{}` | Compile-time compliance |
| Defense in depth | assert.ErrEqual nil branches | Handle impossible cases |
| Option[T] over nil | pluggable.TryInstantiate | Explicit absence over nil |
| Generic wrappers | errext.As[T], must.Return[V] | Type safety without boilerplate |
