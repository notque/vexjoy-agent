# SAP CC Architecture Patterns

Complete architectural patterns from `sapcc/keppel` with 102 rules. Organized by concern area.

---

## 1. Directory Structure

```
project/
  main.go                         # Root entry point, Cobra root command
  go.mod / go.sum
  Makefile / Dockerfile
  cmd/                            # Cobra subcommands, one dir per component
    api/main.go                   # Server: keppel-api
    janitor/main.go               # Server: background worker
    healthmonitor/main.go         # Server: health monitoring
    validate/main.go              # CLI: validate images
    test/main.go                  # CLI: test driver harness
  internal/
    api/                          # HTTP handlers by API surface
      auth/                       # Token/auth endpoint
      keppel/                     # Keppel v1 API (CRUD)
      peer/                       # Peer API (replication)
      registry/                   # Registry v2 API (push/pull)
    auth/                         # Authorization logic
    client/                       # Outbound HTTP clients
    drivers/                      # Pluggable driver implementations
      basic/                      # Simple/static drivers
      filesystem/                 # Filesystem storage
      multi/                      # Multi-backend federation
      openstack/                  # Keystone auth + Swift storage
      redis/                      # Redis federation
      trivial/                    # In-memory test doubles
    keppel/                       # Core domain: interfaces, config, DB, errors
    models/                       # Database models (pure data, no logic)
    processor/                    # Business logic (DB + Storage coordination)
    tasks/                        # Background jobs
    test/                         # Test infrastructure, doubles, helpers
  docs/drivers/                   # Driver documentation
  LICENSES/                       # REUSE-compliant license files
  vendor/                         # Vendored dependencies
```

### Rules

- **R1**: Use `internal/` to prevent external imports of all application code
- **R2**: Each `cmd/<component>/main.go` defines one Cobra subcommand via `AddCommandTo(parent *cobra.Command)`
- **R3**: Root `main.go` assembles all subcommands and blank-imports all driver packages
- **R4**: Model structs: `internal/models/` (pure data, `db:` tags, no business logic)
- **R5**: Core interfaces and config: `internal/keppel/` (the domain package)
- **R6**: API handlers: `internal/api/<surface>/` with separate packages per API
- **R7**: Background tasks: `internal/tasks/`
- **R8**: Business logic: `internal/processor/` (coordinates DB and storage)
- **R9**: Test doubles: `internal/test/`
- **R10**: Drivers: `internal/drivers/<driver-name>/`
- **R11**: Fixtures: `fixtures/` subdirectories adjacent to test files

---

## 2. Package Naming

| Directory | Package Name | Convention |
|-----------|-------------|------------|
| `cmd/api/` | `apicmd` | `<name>cmd` suffix for command packages |
| `cmd/janitor/` | `janitorcmd` | Same pattern |
| `internal/api/keppel/` | `keppelv1` | Version-suffixed for versioned APIs |
| `internal/api/registry/` | `registryv2` | Same pattern |
| `internal/api/auth/` | `auth` | Plain name when unambiguous |
| `internal/drivers/openstack/` | `openstack` | Plain name matching directory |
| `internal/keppel/` | `keppel` | Matches module name's last segment |
| `internal/models/` | `models` | Plain name |

- **R12**: Command packages use `<name>cmd` suffix to avoid collisions
- **R13**: API handler packages use `<name>v<N>` suffix for versioned APIs
- **R14**: Test packages use `_test` suffix for black-box tests

---

## 3. Pluggable Driver Architecture

The defining architectural pattern of keppel. 6 driver types, all identical structure.

### Interface Definition

```go
// internal/keppel/storage_driver.go
type StorageDriver interface {
    pluggable.Plugin    // requires PluginTypeID() string
    Init(AuthDriver, Configuration) error
    // domain-specific methods...
    AppendToBlob(ctx context.Context, account models.Account, storageID string, ...) error
    ReadBlob(ctx context.Context, account models.Account, storageID string) (io.ReadCloser, uint64, error)
}

var StorageDriverRegistry pluggable.Registry[StorageDriver]

func NewStorageDriver(configJSON string, ad AuthDriver, cfg Configuration) (StorageDriver, error) {
    callInit := func(d StorageDriver) error { return d.Init(ad, cfg) }
    return newDriver("KEPPEL_DRIVER_STORAGE", StorageDriverRegistry, configJSON, callInit)
}
```

### Implementation Registration

```go
// internal/drivers/openstack/swift.go
func init() {
    keppel.StorageDriverRegistry.Add(func() keppel.StorageDriver { return &swiftDriver{} })
}

type swiftDriver struct {
    ContainerName string `json:"container_name"`  // Config from JSON
    client        *schwift.Account `json:"-"`      // Runtime state excluded from JSON
}

func (d *swiftDriver) PluginTypeID() string { return "swift" }
func (d *swiftDriver) Init(ad keppel.AuthDriver, cfg keppel.Configuration) error { ... }
```

### Activation in main.go

```go
import (
    _ "github.com/sapcc/keppel/internal/drivers/basic"
    _ "github.com/sapcc/keppel/internal/drivers/filesystem"
    _ "github.com/sapcc/keppel/internal/drivers/openstack"
    _ "github.com/sapcc/keppel/internal/drivers/trivial"
)
```

### Driver Configuration Flow

Environment variable contains JSON: `KEPPEL_DRIVER_STORAGE={"type":"swift","params":{"container_name":"keppel"}}`

1. Parse JSON to extract `type` and `params`
2. Look up plugin in registry by `type`
3. `json.Unmarshal` `params` into driver struct
4. Call `Init()` on the driver

### Rules

- **R21**: Every driver interface embeds `pluggable.Plugin`
- **R22**: Every driver has a corresponding `XxxDriverRegistry` var
- **R23**: Every driver has a `NewXxxDriver()` factory function
- **R24**: Implementations register via `init()` functions
- **R25**: Blank-imported in `main.go` to trigger registration
- **R26**: Config is JSON via struct tags on the driver struct
- **R27**: Runtime state uses `json:"-"` to exclude from config
- **R28**: `Init()` validates driver compatibility
- **R29**: Implementation comments: `// MethodName implements the keppel.XxxDriver interface.`

---

## 4. Cobra Command Pattern

### Root Command

```go
func main() {
    logg.ShowDebug = osext.GetenvBool("KEPPEL_DEBUG")
    keppel.SetupHTTPClient()

    rootCmd := &cobra.Command{
        Use:     "keppel",
        Short:   "Multi-tenant Docker registry",
        Version: bininfo.VersionOr("unknown"),
        Args:    cobra.NoArgs,
        Run:     func(cmd *cobra.Command, args []string) { cmd.Help() },
    }

    validatecmd.AddCommandTo(rootCmd)
    testcmd.AddCommandTo(rootCmd)

    serverCmd := &cobra.Command{Use: "server <subcommand>", ...}
    apicmd.AddCommandTo(serverCmd)
    janitorcmd.AddCommandTo(serverCmd)
    rootCmd.AddCommand(serverCmd)

    must.Succeed(rootCmd.Execute())
}
```

### Subcommand Pattern

```go
package apicmd

func AddCommandTo(parent *cobra.Command) {
    cmd := &cobra.Command{
        Use:   "api",
        Short: "Run the keppel-api server component.",
        Long:  "... Configuration is read from environment variables.",
        Args:  cobra.NoArgs,
        Run:   run,
    }
    parent.AddCommand(cmd)
}

func run(cmd *cobra.Command, args []string) {
    keppel.SetTaskName("api")
    cfg := keppel.ParseConfiguration()
    ctx := httpext.ContextWithSIGINT(cmd.Context(), 10*time.Second)
    // ... bootstrap drivers, DB, handlers ...
}
```

### Rules

- **R30**: Each `cmd/<name>/` exports only `AddCommandTo(parent *cobra.Command)`
- **R31**: `run()` is unexported, handles all bootstrapping
- **R32**: `keppel.SetTaskName(name)` called first in each server command
- **R33**: Graceful shutdown via `httpext.ContextWithSIGINT(cmd.Context(), timeout)`

---

## 5. Bootstrap Sequence

Every server command follows this order:

```
1. SetTaskName()           -- configure component identity
2. ParseConfiguration()    -- read env vars into Configuration struct
3. Context setup           -- ContextWithSIGINT for graceful shutdown
4. InitAuditTrail()        -- optional audit event pipeline
5. Database connection     -- easypg.Connect + InitORM
6. Driver initialization   -- NewAuthDriver, NewFederationDriver, etc.
7. API/handler setup       -- httpapi.Compose(apis...)
8. Background goroutines   -- go job.Run(ctx) for janitor tasks
9. HTTP server             -- httpext.ListenAndServeContext
```

- **R34**: Config is env-var-driven. `osext.MustGetenv()` for required, `GetenvOrDefault()` for optional
- **R35**: `must.Return()` / `must.Succeed()` for fatal bootstrap errors (not at request time)
- **R36**: Drivers initialized in dependency order: Auth first, then Storage, Federation, etc.

---

## 6. Configuration Pattern

All configuration via environment variables prefixed with `KEPPEL_`:

| Category | Variables | Pattern |
|----------|-----------|---------|
| API identity | `KEPPEL_API_PUBLIC_FQDN` | Required string |
| Database | `KEPPEL_DB_HOSTNAME`, `KEPPEL_DB_PORT`, etc. | With defaults |
| Drivers | `KEPPEL_DRIVER_AUTH`, `KEPPEL_DRIVER_STORAGE`, etc. | JSON config string |
| Feature flags | `KEPPEL_DEBUG`, `KEPPEL_INSECURE` | Boolean via `GetenvBool()` |

- **R37**: All config via env vars. No config files, no CLI flags for config
- **R38**: `Configuration` struct contains only non-driver-specific settings
- **R39**: `ParseConfiguration()` is the single entry point
- **R40**: Use osext helpers: `MustGetenv()`, `GetenvOrDefault()`, `GetenvBool()`

---

## 7. Database Patterns

### ORM: gorp v3 with PostgreSQL

```go
type DB struct { gorp.DbMap }

func InitORM(dbConn *sql.DB) *DB {
    result := &DB{DbMap: gorp.DbMap{Db: dbConn, Dialect: gorp.PostgresDialect{}}}
    result.DbMap.AddTableWithName(models.Account{}, "accounts").SetKeys(false, "name")
    return result
}
```

### Query Pattern

```go
var reducedAccountGetByNameQuery = sqlext.SimplifyWhitespace(`
    SELECT auth_tenant_id, upstream_peer_hostname
      FROM accounts
     WHERE name = $1
`)
```

- **R41**: Model structs use `db:"column_name"` tags
- **R42**: Models are pure data (no business logic methods)
- **R43**: DB helpers accept `gorp.SqlExecutor` (works with `*DB` and `*Transaction`)
- **R44**: PostgreSQL `$1`, `$2` placeholders (not `?`)
- **R45**: Migrations use sequential numbering with `.up.sql`/`.down.sql`
- **R46**: Migrations embedded as Go string constants
- **R47**: `FindXxx()` returns `nil, nil` for "not found"
- **R48**: Complex SQL in package-level `var` with `SimplifyWhitespace()`

---

## 8. API Handler Pattern

```go
type API struct {
    cfg        keppel.Configuration
    authDriver keppel.AuthDriver
    db         *keppel.DB
    timeNow    func() time.Time      // injectable for tests
}

func NewAPI(...) *API { return &API{...} }
func (a *API) OverrideTimeNow(f func() time.Time) *API { a.timeNow = f; return a }

func (a *API) AddTo(r *mux.Router) {
    r.Methods("GET").Path("/keppel/v1/accounts").HandlerFunc(a.handleGetAccounts)
    r.Methods("PUT").Path("/keppel/v1/accounts/{account:[a-z0-9][a-z0-9-]{0,47}}").HandlerFunc(a.handlePutAccount)
}
```

- **R49**: API structs hold all deps as unexported fields
- **R50**: `NewAPI()` constructor; `OverrideTimeNow()` for test doubles
- **R51**: `httpapi.IdentifyEndpoint(r, pattern)` FIRST in every handler
- **R52**: Route patterns use gorilla/mux regex constraints inline
- **R53**: Handler methods unexported, named `handle<Verb><Resource>`
- **R54**: Auth done inline at top of handler (not middleware)
- **R55**: Errors written directly, function returns immediately
- **R56**: JSON responses via `respondwith.JSON(w, status, body)`
- **R57**: Request decoding uses `DisallowUnknownFields()`
- **R58**: API composition via `httpapi.Compose(apis...)`

---

## 9. Error Response System

### RegistryV2Error Builder

```go
keppel.ErrBlobUnknown.With("blob does not exist in this repository")
keppel.ErrDenied.With("access denied").WithStatus(http.StatusForbidden)
keppel.ErrTooManyRequests.With("").WithHeader("Retry-After", retryAfterStr)
keppel.AsRegistryV2Error(err).WithStatus(http.StatusUnprocessableEntity).WithDetail(msg)
```

### Three Output Methods

| Method | API | Format |
|--------|-----|--------|
| `WriteAsRegistryV2ResponseTo(w, r)` | Registry v2 | JSON `{"errors": [...]}` |
| `WriteAsAuthResponseTo(w)` | Auth | JSON `{"details": "..."}` |
| `WriteAsTextTo(w)` | Keppel v1 | Plain text |

### Guard Clause Pattern

```go
if respondWithError(w, r, err) { return }         // Registry v2
if respondwith.ObfuscatedErrorText(w, err) { return }  // Keppel v1
```

- **R59**: Typed error codes with HTTP status mappings
- **R60**: Fluent builder: `.With()`, `.WithStatus()`, `.WithDetail()`, `.WithHeader()`
- **R61**: `AsRegistryV2Error(err)` wraps unknown errors in `ErrUnknown`
- **R62**: 5xx errors use `ObfuscatedErrorText` (UUID-masked response, real error logged)

---

## 10. Processor Pattern (Business Logic)

```go
type Processor struct {
    cfg     keppel.Configuration
    db      *keppel.DB
    sd      keppel.StorageDriver
    timeNow func() time.Time
    generateStorageID func() string
}
```

- **R63**: Wraps DB + StorageDriver to keep them in lockstep
- **R64**: Non-deterministic functions are injectable struct fields
- **R65**: Both API handlers and Janitor tasks create Processor instances
- **R66**: `WithLowlevelAccess()` provides escape hatch for direct DB/storage

---

## 11. Background Job Pattern

```go
type Janitor struct {
    cfg     keppel.Configuration
    db      *keppel.DB
    timeNow func() time.Time
    addJitter func(time.Duration) time.Duration
}

// Starting jobs
go janitor.BlobSweepJob(nil).Run(ctx)
go janitor.ManifestGarbageCollectionJob(nil).Run(ctx)
```

- **R67**: Each task is a separate method returning a runnable job
- **R68**: Jobs started as goroutines in `run()`
- **R69**: Jitter applied to scheduled intervals
- **R70**: Test doubles can disable jitter and inject deterministic time

---

## 12. Test Infrastructure

```go
s := test.NewSetup(t,
    test.WithKeppelAPI,
    test.WithQuotas,
    test.WithAccount(models.Account{Name: "test1", AuthTenantID: "tenant1"}),
    test.WithRepo(models.Repository{AccountName: "test1", Name: "foo"}),
)
```

- **R71**: Functional options for test setup
- **R72**: `TestMain` with `easypg.WithTestDB` required for DB packages
- **R73**: Test doubles register as regular drivers via `init()`
- **R74**: Time injectable via `mock.Clock`
- **R75**: SQL fixtures use raw INSERT statements
- **R76**: In-memory `RoundTripper` for testing peer communication

---

## 13. Type Conventions

```go
// Typed string enums
type Permission string
const CanViewAccount Permission = "view"

// Typed int enums
type ClaimResult int
const ClaimSucceeded ClaimResult = iota

// Newtype for IDs
type AccountName string

// Option type for nullable fields
NextBlobSweepedAt Option[time.Time] `db:"next_blob_sweep_at"`
```

- **R81**: String enums: `type X string` with `const` block
- **R82**: Integer enums: `type X int` with `iota`
- **R83**: Semantic newtypes for IDs: `type AccountName string`
- **R84**: `Option[T]` instead of `*T` for nullable DB fields
- **R85**: Error sentinels: `var ErrXxx = errors.New(...)`

---

## 14. Comment Conventions

```go
// Interface methods: detailed godoc
// AuthenticateUser authenticates the user identified by the given username
// and password. Note that usernames may not contain colons.
AuthenticateUser(ctx context.Context, userName, password string) (UserIdentity, *RegistryV2Error)

// Implementation comments
// PluginTypeID implements the keppel.AuthDriver interface.
func (d *driver) PluginTypeID() string { return "keystone" }

// Section separators
////////////////////////////////////////////////////////////////////////////////
// section title
```

- **R88**: Interface methods have detailed godoc
- **R89**: Implementations use `// Method implements the pkg.Interface interface.`
- **R90**: Section separators: `////////////////////////////////////////////////////////////////////////////////`

---

## 15. File Naming

| Pattern | Example | Usage |
|---------|---------|-------|
| `<entity>.go` | `account.go` | Model or domain type |
| `<entity>_driver.go` | `auth_driver.go` | Driver interface |
| `<entity>s.go` | `accounts.go` | API handlers or task implementations |
| `shared_test.go` | `shared_test.go` | Test infrastructure (TestMain) |
| `api.go` | `api.go` | API struct, constructor, router |
| `config.go` | `config.go` | Configuration parsing |
| `database.go` | `database.go` | Schema, ORM setup, migrations |
| `errors.go` | `errors.go` | Error types and codes |

- **R77**: One file per major entity
- **R78**: Driver interface files named `<concern>_driver.go`
- **R79**: Shared test setup in `shared_test.go`
- **R80**: Constants live adjacent to their types, not in `constants.go`

---

## 16. Dependency Injection

```go
type API struct {
    timeNow func() time.Time  // default: time.Now
}

func (a *API) OverrideTimeNow(f func() time.Time) *API {
    a.timeNow = f
    return a
}
```

- **R91**: Non-deterministic functions are struct fields with production defaults
- **R92**: `OverrideXxx()` methods return `*Self` for chaining
- **R93**: Defaults use stdlib: `time.Now`, `keppel.GenerateStorageID`

---

## 17. SPDX License Headers

```go
// SPDX-FileCopyrightText: 2024 SAP SE or an SAP affiliate company
// SPDX-License-Identifier: Apache-2.0
```

- **R86**: Every `.go` file must have SPDX headers as first two comment lines
- **R87**: Year reflects file creation or last substantial modification

---

## 18. API Response Patterns

### DB Model vs API Model

```go
// DB model (internal/models/)
type Account struct {
    Name           AccountName `db:"name"`
    GCPoliciesJSON string      `db:"gc_policies_json"`  // JSON string in DB
}

// API model (internal/keppel/)
type Account struct {
    Name       models.AccountName `json:"name"`
    GCPolicies []GCPolicy         `json:"gc_policies,omitempty"`  // Parsed in API
}

// Conversion
func RenderAccount(dbAccount models.Account) (Account, error) { ... }
```

- **R99**: DB models use `db:` tags; API models use `json:` tags. Separate structs.
- **R100**: `RenderXxx()` functions convert DB to API models
- **R101**: JSON responses wrap in named keys: `{"account": {...}}`, `{"accounts": [...]}`
- **R102**: Empty collections: `[]`, never `null`
