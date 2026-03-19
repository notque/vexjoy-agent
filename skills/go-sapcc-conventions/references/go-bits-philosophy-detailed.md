# go-bits Library Design Philosophy -- Detailed Reference

go-bits library design rules, per-package design notes for all 17 go-bits subpackages, API surface inventory, contributor patterns, and evolution direction.

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
- `httptest.ReceiveJSONInto` requires a pointer argument; panics otherwise
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

## 2. Per-Package Design Notes -- All 17 go-bits Subpackages

### must/ -- Fatal Error Shorthand

- **Files**: 1 (`must.go`)
- **API surface**: 4 functions, 0 types
- **Exported**: `Succeed(error)`, `SucceedT(*testing.T, error)`, `Return[V](V, error) V`, `ReturnT[V](V, error) func(*testing.T) V`
- **Philosophy**: Eliminate `if err != nil { log.Fatal(...) }` boilerplate. Only for truly fatal errors. Generics preserve type safety in `Return` and `ReturnT`.
- **Design insight**: `ReturnT` has a long comment explaining WHY its signature is `func(V, error) func(*testing.T) V` -- Go generics prevent type args in methods, and multi-return expressions cannot mix with other arguments.
- **Opinionated**: Extremely. Calls `os.Exit(1)`. No recovery possible.

### assert/ -- Test Assertions

- **Files**: 4 (`assert.go`, `http.go`, `values.go`, `assert_test.go`)
- **API surface**: ~12 exported symbols
- **Exported**: `Equal[V comparable]`, `ErrEqual`, `DeepEqual[V any]`, `HTTPRequest` (deprecated), `StringData`, `JSONObject`, `JSONFixtureFile`, `FixtureFile`, `ByteData`, `TestingT` interface
- **Philosophy**: Thin wrappers around `testing.T` with readable error messages. `DeepEqual` uses `reflect.DeepEqual` with `%#v` (explicit comment: must use `%#v` to distinguish all values).
- **Design decision**: Rejected changing `DeepEqual` to `==`: "We cannot change DeepEqual to use `==`. Most types are not within the `comparable` interface."

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
- **API surface**: 4 functions + 1 internal error type
- **Exported**: `JSON`, `ErrorText`, `ObfuscatedErrorText`, `CustomStatus`
- **Philosophy**: Package named to read as English: `respondwith.JSON(w, 200, data)`. Doc: "Its name is like that because it pairs up with the function names."
- **Performance**: `JSON` uses `json.Encoder.Encode` instead of `json.Marshal` to avoid extra buffer allocation.
- **Security**: `ObfuscatedErrorText` generates UUID for 5xx, logs real error server-side. `CustomStatus` does NOT work when wrapped (prevents leaking sensitive data).
- **Dependency consciousness**: `GenerateUUID()` was moved to `package internal` to avoid pulling AMQP into all consumers.

### pluggable/ -- Plugin Factory

- **Files**: 2 (`pluggable.go`, `pluggable_test.go`)
- **API surface**: 1 interface + 1 generic struct + 3 methods
- **Exported**: `Plugin` interface, `Registry[T Plugin]`, `Add`, `Instantiate`, `TryInstantiate`
- **Philosophy**: Tiny plugin factory using `init()` registration. `Add` panics on nil factory, empty type ID, or duplicates -- programming errors, not runtime errors.
- **Evolution**: `TryInstantiate` returns `Option[T]` from `majewsky/gg/option`.

### httpapi/ -- HTTP API Composition

- **Files**: 6 (`doc.go`, `api.go`, `compose.go`, `middleware.go`, `metrics.go`, `pprofapi/`)
- **API surface**: ~8 exported symbols
- **Exported**: `API` interface, `Compose`, `HealthCheckAPI`, `WithoutLogging`, `WithGlobalMiddleware`, `SkipRequestLog`, `IdentifyEndpoint`, `ConfigureMetrics`
- **Philosophy**: Opinionated composition. `Compose(apis...)` builds single `http.Handler` with logging and metrics. Uses gorilla/mux internally but abstracts it away.
- **Out-of-band communication**: Context values for handlers to message middleware. Panics if called outside `Compose()`.

### httptest/ -- Test HTTP Handler

- **Files**: 3 (`handler.go`, `handler_test.go`, `fixtures/`)
- **API surface**: ~15 exported symbols
- **Exported**: `Handler`, `NewHandler`, `RespondTo`, `Response`, `WithBody`, `WithHeader`, `WithHeaders`, `WithJSONBody`, `ReceiveJSONInto`, `RequestOption`
- **Philosophy**: Replaces deprecated `assert.HTTPRequest` with fluent API. `RespondTo(ctx, "GET /v1/info")` combines method+path.
- **Dual-mode**: Supports both `testing.T` and Ginkgo/Gomega.
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

| Package | Exported Symbols | Functions | Types | Interfaces |
|---------|-----------------|-----------|-------|------------|
| must | 4 | 4 | 0 | 0 |
| assert | ~12 | 3 | 6 | 1 |
| logg | 7 | 5 | 0 | 0 |
| errext | ~12 | 2 | 2 | 0 |
| respondwith | 4 | 4 | 0 | 0 |
| pluggable | ~5 | 0 | 1 | 1 |
| httpapi | ~8 | 4 | 1 | 1 |
| httptest | ~15 | 5 | 3 | 0 |
| jobloop | ~12 | 1 | 2 | 1 |
| syncext | 4 | 1 | 1 | 0 |
| httpext | ~6 | 4 | 0 | 0 |
| osext | 5 | 4 | 1 | 0 |
| secrets | 2 | 1 | 1 | 0 |
| sqlext | ~6 | 4 | 0 | 2 |
| regexpext | ~4 | 0 | 2 | 0 |
| mock | ~2 | 1 | 1 | 0 |

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
| `liquidapi` package | Growing | Server runtime for LIQUID protocol |

### Deprecations

- `assert.HTTPRequest` -- soft-deprecated in favor of `httptest.Handler.RespondTo`
- Coveralls removed from CI (Aug 2025)

### Direction

1. **Generics adoption**: New functions consistently use generics (`Return[V]`, `As[T]`, `ProducerConsumerJob[T]`)
2. **Option[T] type**: Increasing use from `majewsky/gg` instead of nil pointers
3. **Fluent test APIs**: Moving from struct-based to method-chain APIs
4. **Security-conscious defaults**: `ObfuscatedErrorText` hides errors, `CustomStatus` only works unwrapped
5. **LIQUID protocol**: Growing `liquidapi` package -- most new development
6. **Concurrency primitives**: `syncext.Semaphore` + `LimitConcurrentRequestsMiddleware`
7. **Test ergonomics**: `SucceedT`, `ReturnT`, `ErrEqual`, `ExpectJSON`

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

### NEVER Use

1. **Library that duplicates go-bits** -- No testify when `go-bits/assert` exists. No logrus when `logg` exists.
2. **Library with heavy transitive deps for small features** -- UUID moved to `internal` to avoid AMQP deps
3. **Library that imposes a framework** -- go-bits wraps stdlib patterns, doesn't replace them

---

## 7. Key Design Patterns Summary

| Pattern | Where Used | Principle |
|---------|-----------|-----------|
| Functional options | jobloop.Option, httptest.RequestOption | Extensible config without breaking changes |
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
