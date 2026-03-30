# SAP CC Code Patterns — Extracted from Keppel Source

Concrete rules extracted by reading every package in `sapcc/keppel`. These are not review comments — these are how the project's code is actually written, derived from reading the implementations.

**For the LLM generating code**: This document exists because standard Go training data teaches patterns the project convention rejects. When this document conflicts with "Go best practices," **this document wins** for sapcc code.

---

## 1. Function Signatures

### Parameter Count

- **Methods**: 1-4 parameters (lean)
- **Constructors**: 7-8 positional parameters (no option structs, no functional options for constructors)
- **Never**: variadic params for required dependencies, builder patterns for construction, config structs bundling unrelated params

```go
// CORRECT: 8 positional params for constructor — actual code from keppel
func NewAPI(cfg keppel.Configuration, ad keppel.AuthDriver, fd keppel.FederationDriver,
    sd keppel.StorageDriver, icd keppel.InboundCacheDriver,
    db *keppel.DB, auditor audittools.Auditor, rle *keppel.RateLimitEngine) *API {
    return &API{cfg, ad, fd, sd, icd, db, auditor, rle, time.Now, keppel.GenerateStorageID}
}

// WRONG: Option struct for constructor
type APIOptions struct {
    Config  keppel.Configuration
    Auth    keppel.AuthDriver
    // ...
}
func NewAPI(opts APIOptions) *API { ... }  // review standard rejects this

// WRONG: Functional options
func NewAPI(opts ...Option) *API { ... }  // review standard rejects this
```

### context.Context Usage

- Pass as first param **only** when the operation involves external calls (DB queries to upstream, federation calls, storage operations)
- HTTP handlers read context from `r.Context()` — they do NOT take `ctx` as a parameter
- Many internal methods do NOT take context at all

```go
// CORRECT: context for external operation
func (p *Processor) GetPlatformFilterFromPrimaryAccount(ctx context.Context, peer models.Peer, account models.Account) (models.PlatformFilter, error)

// CORRECT: no context for simple DB lookup via request
func (a *API) findAccountFromRequest(w http.ResponseWriter, r *http.Request, _ *auth.Authorization) *models.Account {
    // uses r.Context() internally, not passed in
}
```

### Return Patterns

| Pattern | When |
|---------|------|
| `(T, error)` | Returning data |
| `error` | Side-effect operations (delete, update, mark) |
| `(T, *keppel.RegistryV2Error)` | API-facing operations where error type matters |
| `(bool, error)` named returns | When `defer` needs to inspect/modify the return |

### Named Returns

**Only** when a `defer` block needs to inspect or modify the return value. Never for documentation purposes.

```go
// CORRECT: named return because defer reads it
func (j *Janitor) syncManifestsInReplicaRepo(ctx context.Context, repo models.Repository, _ prometheus.Labels) (returnedError error) {
    defer func() {
        if returnedError != nil {
            timeUntilNextSync = 5 * time.Minute
        }
    }()
    // ...
}

// WRONG: named returns for "documentation"
func GetUser(id int) (user *User, err error) { ... }
```

Named return variables are always `returnErr`, `returnedError`, or `returnedErr` — never bare `err`.

### Pointer vs Value Receivers

- **Pointer receivers** (`*T`) for all struct methods
- **Value receivers** (`T`) only for tiny data-only types (2-3 fields, no mutation)

```go
// Pointer: all API, Processor, Janitor, Driver methods
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request)
func (p *Processor) GetQuotas(authTenantID string) (*QuotaResponse, error)

// Value: only tiny data wrappers
func (b BytesWithDigest) Bytes() []byte { return b.bytes }
func (info anycastRequestInfo) AsPrometheusLabels() prometheus.Labels { ... }
```

### Parameter Naming

Short 2-3 letter abbreviations, consistent everywhere:

| Name | Meaning |
|------|---------|
| `cfg` | Configuration |
| `ad` | AuthDriver |
| `fd` | FederationDriver |
| `sd` | StorageDriver |
| `icd` | InboundCacheDriver |
| `db` | Database |
| `rle` | RateLimitEngine |
| `amd` | AccountManagementDriver |
| `ctx` | Context |
| `w`, `r` | http.ResponseWriter, *http.Request |
| `tx` | Transaction |

Struct fields match parameter abbreviations exactly.

---

## 2. Configuration

### No Viper. No Config Files. Pure Environment Variables.

The project convention **never** uses viper, YAML, TOML, or config files. Configuration is 100% environment variables.

```go
// CORRECT: established config parsing pattern
func ParseConfiguration() Configuration {
    cfg := Configuration{
        APIPublicHostname: osext.MustGetenv("KEPPEL_API_PUBLIC_FQDN"),
        AnycastAPIPublicHostname: os.Getenv("KEPPEL_API_ANYCAST_FQDN"),
    }
    // ...
}

// WRONG: Any of these
viper.ReadInConfig()           // FORBIDDEN
yaml.Unmarshal(configBytes)    // FORBIDDEN
toml.DecodeFile("config.toml") // FORBIDDEN
```

### Env Var Patterns

| Function | When |
|----------|------|
| `osext.MustGetenv("VAR")` | Required — panics if missing |
| `os.Getenv("VAR")` | Optional, empty string acceptable |
| `osext.GetenvOrDefault("VAR", "default")` | Optional with default value |
| `osext.GetenvBool("VAR")` | Boolean flag from env (e.g., debug mode) |

### Driver Selection via JSON Env Vars

Drivers are configured by JSON environment variables: `KEPPEL_DRIVER_AUTH='{"type":"keystone","params":{"oslo_policy_path":"/etc/policy.json"}}'`

```go
ad := must.Return(keppel.NewAuthDriver(ctx, osext.MustGetenv("KEPPEL_DRIVER_AUTH"), rc))
fd := must.Return(keppel.NewFederationDriver(ctx, osext.MustGetenv("KEPPEL_DRIVER_FEDERATION"), ad, cfg))
```

### Database Config

Also pure env vars with sensible defaults:

```go
dbName = osext.GetenvOrDefault("KEPPEL_DB_NAME", "keppel")
// via easypg.URLFrom(easypg.URLParts{
//     HostName: osext.GetenvOrDefault("KEPPEL_DB_HOSTNAME", "localhost"),
//     Port:     osext.GetenvOrDefault("KEPPEL_DB_PORT", "5432"),
//     UserName: osext.GetenvOrDefault("KEPPEL_DB_USERNAME", "postgres"),
//     Password: os.Getenv("KEPPEL_DB_PASSWORD"),
// })
```

---

## 3. Constructor Patterns

### `NewX(deps...) *X` — Never Returns Error

Constructors are infallible by design. They just wire up dependencies.

```go
// CORRECT: Constructor returns *T, no error, positional struct init
func NewAPI(cfg keppel.Configuration, ad keppel.AuthDriver, fd keppel.FederationDriver,
    sd keppel.StorageDriver, icd keppel.InboundCacheDriver,
    db *keppel.DB, auditor audittools.Auditor, rle *keppel.RateLimitEngine) *API {
    return &API{cfg, ad, fd, sd, icd, db, auditor, rle, time.Now, keppel.GenerateStorageID}
}

// WRONG: Constructor returning error
func NewAPI(cfg Config) (*API, error) { ... }
```

Key details:
- **Positional struct literal** — `&API{cfg, ad, fd, sd, ...}` (no field names)
- **Never return error** — construction is infallible
- **Inject default functions** for test-replaceable behavior: `time.Now`, `keppel.GenerateStorageID`

### Driver Constructors ARE Different

`New*Driver` functions DO return errors because they parse config and initialize external connections:

```go
func NewAuthDriver(ctx context.Context, configJSON string, rc *redis.Client) (AuthDriver, error)
```

### The Override Pattern (Fluent Test Doubles)

The project convention replaces non-deterministic functions with fluent `Override*` methods:

```go
func (p *Processor) OverrideTimeNow(timeNow func() time.Time) *Processor {
    p.timeNow = timeNow
    return p
}

func (j *Janitor) DisableJitter() {
    j.addJitter = func(d time.Duration) time.Duration { return d }
}

// Used in tests for chaining:
processor.New(cfg, db, sd, icd, auditor, fd, s.Clock.Now).
    OverrideTimeNow(s.Clock.Now).
    OverrideGenerateStorageID(s.SIDGenerator.Next)
```

The struct stores function fields for non-deterministic operations. Constructors set production defaults. Override methods replace them for testing.

---

## 4. Interface Patterns

### When to Use Interfaces

The project creates interfaces ONLY for real polymorphism. Every interface in keppel has 2+ implementations.

| Reason | Example |
|--------|---------|
| Pluggable backends (multiple drivers) | `StorageDriver`, `AuthDriver`, `FederationDriver` |
| Polymorphism over known variants | `UserIdentity` (7 implementations), `ParsedManifest` (4 implementations) |
| Observer pattern | `ValidationLogger` (noop + real) |

### When NOT to Use Interfaces

If there's one implementation, it's a concrete struct. No exceptions.

```go
// These are ALL concrete types — no interfaces:
keppel.Configuration    // one implementation, passed by value
keppel.DB               // one implementation, passed as *keppel.DB
keppel.RateLimitEngine  // one implementation
processor.Processor     // one implementation
models.Account          // data type
```

### Interface Location

Interfaces are defined in the **consumer package** (`internal/keppel/`), never in the implementation packages (`internal/drivers/*`).

### Interface Size

| Size | Count | Examples |
|------|-------|---------|
| 2-3 methods | 5 | `RateLimitDriver`, `ValidationLogger`, `AccountManagementDriver`, `AuthDriver`, `InboundCacheDriver` |
| 6-8 methods | 3 | `FederationDriver`, `UserIdentity`, `ParsedManifest` |
| 16 methods | 1 | `StorageDriver` (large because the domain demands it) |

The project does NOT split large interfaces into tiny composed interfaces for ISP purity. When an interface is large, it's because every implementation must provide all methods.

### Interface Method Documentation

Interface methods get thorough multi-paragraph godoc — they ARE the contract:

```go
// ClaimAccountName is called when creating a new account, and returns nil if
// and only if this Keppel is allowed to use `account.Name` for the given new
// `account`.
//
// For some drivers, creating a replica account requires confirmation from the
// Keppel hosting the primary account. This is done by issuing a sublease
// token secret on the primary account using IssueSubleaseTokenSecret(), then
// presenting this `subleaseTokenSecret` to this method.
//
// The implementation MUST be idempotent.
ClaimAccountName(ctx context.Context, account models.Account, subleaseTokenSecret string) (ClaimResult, error)
```

### Implements-Interface Comments

Formulaic, always the same format:

```go
// PluginTypeID implements the keppel.UserIdentity interface.
func (uid janitorUserIdentity) PluginTypeID() string {
```

### The Pluggable Driver Pattern

```
1. pluggable.Plugin base interface → PluginTypeID() string
2. pluggable.Registry[T] generic registry
3. Package-level registry var: var AuthDriverRegistry pluggable.Registry[AuthDriver]
4. init() self-registration: keppel.AuthDriverRegistry.Add(func() keppel.AuthDriver { return &AuthDriver{} })
5. Generic newDriver[P] handles instantiation + JSON config parsing
6. Type-specific constructors are one-liners calling newDriver
```

---

## 5. HTTP/API Patterns

### Structure

One `API` struct per domain package, each implementing `AddTo(*mux.Router)`. Composed at top level via `httpapi.Compose(api1, api2, ...)`.

### Handler Signatures

Every handler is `func (a *API) handleVerbResource(w http.ResponseWriter, r *http.Request)`:

```go
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request)
func (a *API) handlePutAccount(w http.ResponseWriter, r *http.Request)
func (a *API) handleDeleteAccount(w http.ResponseWriter, r *http.Request)
```

Naming: `handle` + HTTP method + Resource name.

### Endpoint Identification

Every handler starts with endpoint identification for metrics/tracing:

```go
httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts/:account")
```

### Request Parsing

JSON body: `json.NewDecoder` + `DisallowUnknownFields()`:

```go
func decodeJSONRequestBody(w http.ResponseWriter, body io.Reader, target any) (ok bool) {
    decoder := json.NewDecoder(body)
    decoder.DisallowUnknownFields()
    err := decoder.Decode(&target)
    if err != nil {
        http.Error(w, "request body is not valid JSON: "+err.Error(), http.StatusBadRequest)
        return false
    }
    return true
}
```

Decode into anonymous struct for request bodies:

```go
var req struct {
    Account keppel.Account `json:"account"`
}
ok := decodeJSONRequestBody(w, r.Body, &req)
if !ok { return }
```

Query params: parsed manually inline. URL params: `mux.Vars(r)["name"]`, validated by route regex.

### Response Patterns

```go
// JSON response with ad-hoc envelope
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": accountsRendered})

// One-off response shape
respondwith.JSON(w, http.StatusOK, struct {
    AuthDriverName string `json:"auth_driver"`
}{
    AuthDriverName: a.authDriver.PluginTypeID(),
})

// Delete: bare 204
w.WriteHeader(http.StatusNoContent)

// Empty arrays: ensure [] not null in JSON
if result.Repos == nil { result.Repos = []Repository{} }

// Raw JSON from DB passed through without re-parsing
respondwith.JSON(w, http.StatusOK, map[string]any{"policies": json.RawMessage(account.SecurityScanPoliciesJSON)})
```

### Authentication

Auth is NOT middleware. Called inline at top of each handler:

```go
authz := a.authenticateRequest(w, r, accountScopeFromRequest(r, keppel.CanViewAccount))
if authz == nil { return }
```

### Error Responses

Three formats depending on API surface:

| API Surface | Format |
|-------------|--------|
| Registry V2 | `{"errors": [{"code": "NAME_UNKNOWN", "message": "..."}]}` |
| Auth | `{"details": "error message"}` |
| Keppel v1 | Plain text via `http.Error()` |

Internal errors use `respondwith.ObfuscatedErrorText(w, err)` — logs real error, returns generic 500.

---

## 6. Error Handling

### Wrapping: `%w` vs `%s`

- **`%w`** when the caller might need `errors.Is`/`errors.As`
- **`%s` with `.Error()`** to intentionally break the error chain
- **`%v`** almost never (2 uses total, both for non-error values)

```go
// %w: caller may need to inspect
return fmt.Errorf("while parsing chunk object name %q: %w", name, err)

// %s: intentionally NOT wrapping (breaking the chain)
return fmt.Errorf("cannot parse blob digest: %s", err.Error())
```

### Wrapping Context Format

| Pattern | Example |
|---------|---------|
| `"while <operation>: %w"` | `"while parsing chunk object name %q: %w"` |
| `"cannot <operation>: %w"` | `"cannot find repo %d for manifest %s: %w"` |
| `"during <method> <url>: %w"` | `"during %s %s: %w"` |

Always includes relevant identifiers (account names, digests, URLs, UUIDs).

**Do NOT use "failed to"** — it's redundant. The error return already means something failed. The project convention uses "cannot" or "while" instead.

### Bare `return err`

Common and deliberate for DB operation sequences where wrapping would be noise:

```go
_, err := j.db.Exec(blobMarkQuery, account.Name, canBeDeletedAt)
if err != nil { return err }
_, err = j.db.Exec(blobUnmarkQuery, account.Name)
if err != nil { return err }
```

### Never Log AND Return the Same Error

- **Primary error**: returned, never logged
- **Secondary/cleanup errors**: logged, never returned

```go
err = p.AppendToBlob(ctx, account, &upload, blobReader, &blobLengthBytes)
if err != nil {
    abortErr := p.sd.AbortBlobUpload(ctx, account, upload.StorageID, upload.NumChunks)
    if abortErr != nil {
        logg.Error("additional error encountered when aborting upload %s into account %s: %s",
            upload.StorageID, account.Name, abortErr.Error())
    }
    return err  // original error returned, cleanup error logged
}
```

### Sentinel Errors

- Exported: `var ErrAccountNameEmpty = errors.New("account name cannot be empty string")`
- Unexported: `var errNoSuchBlob = errors.New("no such blob")`
- API errors: `const ErrBlobUnknown RegistryV2ErrorCode = "BLOB_UNKNOWN"` with fluent `.With()` builder

Sentinel error naming:
- Exported: `Err` prefix (e.g., `ErrIncompatibleReplicationPolicy`)
- Unexported: `err` prefix (e.g., `errNoSuchBlob`, `errNoSuchManifest`, `errAppendToBlobAfterFinalize`)

### Trust the stdlib's Error Messages

The project convention avoids redundant error wrapping when the stdlib already provides good context:

> "ParseUint is disciplined about providing good context in its input messages... So we can avoid boilerplate here without compromising that much clarity in the error messages." — lead review standard

### Logging Levels

| Level | When | Where |
|-------|------|-------|
| `logg.Fatal` | Startup failures only | `cmd/` packages only, never in library code |
| `logg.Error` | Secondary/cleanup errors, response already written | Throughout `internal/` |
| `logg.Info` | Operational events (sweeps, GC, state changes) | Tasks, processors |
| `logg.Debug` | Diagnostic tracing | Driver selection, existence checks |

**Never** `log.Printf` or `fmt.Printf` for logging. Always `logg.*`.

### Panic Usage

Only 4 situations:
1. **Exhaustive type switches** — `panic("unreachable")`
2. **Invariant violations** — `panic("unexpected ... (why was this not caught by Validate!?)")`
3. **Test helpers** — `panic(err.Error())` in test setup code for impossible-in-practice errors
4. **Driver registration** — duplicate detection in `init()`

---

## 7. Database Patterns

### gorp + Raw SQL

- **gorp** for simple CRUD (`db.Insert`, `db.Delete`, `db.Update`, `db.SelectOne`, `db.Select`)
- **Raw SQL** for anything complex (JOINs, subqueries, CTEs, UPSERTs)
- **Never** query builders (no squirrel, no gorm)

### SQL Query Style

Package-level `var` constants with `sqlext.SimplifyWhitespace()`:

```go
var blobGetQueryByRepoName = sqlext.SimplifyWhitespace(`
    SELECT b.*
      FROM blobs b
      JOIN blob_mounts bm ON b.id = bm.blob_id
      JOIN repos r ON bm.repo_id = r.id
     WHERE b.account_name = $1 AND b.digest = $2
       AND r.account_name = $1 AND r.name = $3
`)
```

- SQL keywords UPPERCASED
- PostgreSQL positional parameters (`$1`, `$2`) — never `?`
- Inline comments with `--`

### Dynamic WHERE Clauses

Uses string replacement tokens, not string concatenation:

```go
query := strings.Replace(q.SQL, `$LIMIT`, strconv.FormatUint(limit+1, 10), 1)

if marker == "" {
    query = strings.Replace(query, `$CONDITION`, `TRUE`, 1)
} else {
    query = strings.Replace(query, `$CONDITION`, q.MarkerField+` > $2`, 1)
}
```

### Transaction Pattern

```go
tx, err := p.db.Begin()
if err != nil { return err }
defer sqlext.RollbackUnlessCommitted(tx)
// ... work ...
err = tx.Commit()
```

Or via `insideTransaction` helper for processor operations. Transactions are used surgically — the project explicitly comments when they're NOT needed.

### NULL Handling

`Option[T]` from `github.com/majewsky/gg/option` (dot import), not `*T` pointers:

```go
NextBlobSweepedAt Option[time.Time] `db:"next_blob_sweep_at"`
```

Unpacked with `.Unpack()`:
```go
if gcPolicy, ok := u.GCPolicy.Unpack(); ok { ... }
```

The Option library exists explicitly because pointers have semantic ambiguity — `*int32` could mean "editable value" OR "optional value." `Option[int32]` is unambiguous.

### JSON Stored in DB as Text Columns

Many fields store JSON as `TEXT NOT NULL DEFAULT ''` or `DEFAULT '[]'`. Parsing always checks for empty/default:

```go
func ParseGCPolicies(account models.Account) ([]GCPolicy, error) {
    if account.GCPoliciesJSON == "" || account.GCPoliciesJSON == "[]" {
        return nil, nil
    }
    var policies []GCPolicy
    err := json.Unmarshal([]byte(account.GCPoliciesJSON), &policies)
    return policies, err
}
```

### Database Migrations

Migrations are embedded in Go code as a `map[string]string`:

```go
var sqlMigrations = map[string]string{
    "035_rollup.up.sql": `CREATE TABLE accounts (...)`,
    "035_rollup.down.sql": `DROP TABLE accounts;`,
    "036_add_accounts_rbac_policies_json.up.sql": `ALTER TABLE accounts ADD COLUMN ...`,
    "036_add_accounts_rbac_policies_json.down.sql": `ALTER TABLE accounts DROP COLUMN ...`,
}
```

Naming: `NNN_description.up.sql` / `NNN_description.down.sql` with zero-padded 3-digit numbers.

Migrations are rolled up periodically — old migrations 1-35 were collapsed into `035_rollup` with a note:

```go
//NOTE: Migrations 1 through 35 have been rolled up into one at 2024-02-26
// to better represent the current baseline of the DB schema.
```

Every `up` has a corresponding `down`. Performance-critical index changes get explanatory comments:

```go
// Re 039: These indices are used when selecting tasks for BlobValidationJob
// and ManifestValidationJob. Before we added indices here, those queries
// were consistently the most expensive by total execution time.
```

Passed to the library via configuration:

```go
func DBConfiguration() easypg.Configuration {
    return easypg.Configuration{
        Migrations: sqlMigrations,
    }
}
```

### DB Connection Limits

Explicitly set to prevent resource starvation:

```go
dbConn.SetMaxOpenConns(16)
```

---

## 8. Type Definitions

### Named String Types for Domain Concepts

```go
type AccountName string
type VulnerabilityStatus string
type Permission string
type RegistryV2ErrorCode string
```

### String Enums (NOT iota for domain values)

```go
const (
    ErrorVulnerabilityStatus VulnerabilityStatus = "Error"
    PendingVulnerabilityStatus VulnerabilityStatus = "Pending"
    CleanSeverity VulnerabilityStatus = "Clean"
)
```

String values because they go directly into DB columns and JSON. No `iota` for domain enums.

### iota IS Used for Internal Enums

When the enum is internal and never serialized, `iota` is fine:

```go
const (
    RegularUser UserType = iota
    AnonymousUser
    PeerUser
    TrivyUser
    JanitorUser
)
```

The rule: **string constants** for anything that touches DB or JSON. **iota** only for purely internal type discrimination.

### Model Types: `db:` Tags

```go
type Manifest struct {
    RepositoryID int64         `db:"repo_id"`
    Digest       digest.Digest `db:"digest"`
    MediaType    string        `db:"media_type"`
    SizeBytes    uint64        `db:"size_bytes"`
    PushedAt     time.Time     `db:"pushed_at"`
}
```

API representation types use `json:` tags and are separate types. `time.Time` in DB models becomes `int64` (unix timestamp) in API types.

### JSON Tag Patterns

- `json:"field_name"` — always snake_case
- `json:"field_name,omitempty"` — for zero-value suppression
- `json:"field_name,omitzero"` — for `Option[T]` types specifically
- Never `json:"-"` on model fields (just don't include them in the API type)

### Optional JSON Fields with Option[T]

```go
type GCStatus struct {
    ProtectedByGCPolicy    Option[GCPolicy] `json:"protected_by_policy,omitzero"`
    ProtectedByTagPolicy   Option[TagPolicy] `json:"protected_by_tag_policy,omitzero"`
    RelevantGCPolicies     []GCPolicy        `json:"relevant_policies,omitempty"`
}
```

### Custom JSON Marshaling for Polymorphic Types

Uses `json.RawMessage` for discriminated unions:

```go
func (r *ReplicationPolicy) UnmarshalJSON(buf []byte) error {
    var s struct {
        Strategy ReplicationStrategy `json:"strategy"`
        Upstream json.RawMessage     `json:"upstream"`
    }
    err := json.Unmarshal(buf, &s)
    // ...
    switch r.Strategy {
    case OnFirstUseStrategy:
        return json.Unmarshal(s.Upstream, &r.UpstreamPeerHostName)
    case FromExternalOnFirstUseStrategy:
        return json.Unmarshal(s.Upstream, &r.ExternalPeer)
    }
}
```

### Reduced Struct Pattern

For performance, a `ReducedAccount` carries only frequently-needed fields, with a `.Reduced()` method on the full type.

---

## 9. Testing Patterns

### NOT Table-Driven

The project does NOT use table-driven tests. Tests are sequential, scenario-driven narratives. Each test reads like a story: set up state, make a request, assert the response, advance time, make another request, assert the changes.

### HTTP Testing

```go
assert.HTTPRequest{
    Method:       "GET",
    Path:         "/keppel/v1/accounts",
    Header:       map[string]string{"X-Test-Perms": "view:tenant1"},
    ExpectStatus: http.StatusOK,
    ExpectBody:   assert.JSONObject{"accounts": []any{}},
}.Check(t, h)
```

### DB State Testing

`easypg.AssertDBContent(t, s.DB.Db, "fixtures/blob-sweep-001.sql")` — compare DB state against SQL fixture files containing INSERT statements.

`easypg.NewTracker` for incremental change tracking.

### Assertions

- `assert.HTTPRequest{}.Check(t, h)` — HTTP endpoint testing
- `assert.ErrEqual(t, err, expected)` — error comparison
- `assert.DeepEqual(t, label, actual, expected)` — struct comparison
- `must.SucceedT(t, err)` — fatal on error
- **No testify, no gomock, no mockery**

### Test Setup

Functional options pattern: `test.NewSetup(t, test.WithKeppelAPI, test.WithAccount(...))`.

Real PostgreSQL via `easypg.ConnectForTest(t)`. Mock drivers are hand-written concrete types in `internal/test/`.

Time control via `mock.Clock` with `s.Clock.StepBy(1 * time.Hour)`.

---

## 10. Package Organization

```
internal/
├── models/      # Pure data types with db: tags. Zero dependencies. One file per table/concept.
├── keppel/      # Core: config, DB wrapper, driver interfaces, errors, helpers
├── auth/        # Authentication/authorization
├── processor/   # Business logic coordinator (wraps DB + drivers). Owns transactions.
├── tasks/       # Background jobs (Janitor). One file per job domain.
├── api/
│   ├── keppel/  # Keppel v1 REST API. One file per resource.
│   ├── registry/# OCI Registry V2 API
│   ├── auth/    # Auth API
│   └── peer/    # Peer API
├── drivers/     # Plugin implementations (openstack, trivial, basic, filesystem, redis)
├── client/      # HTTP clients for peers/upstream
├── test/        # Test infrastructure (mocks, helpers, setup). NOT test files.
└── stringy/     # String utilities
```

### File Organization Within Packages

- One file per resource/concept: `accounts.go`, `repos.go`, `manifests.go`
- Shared helpers in `api.go`
- Tests alongside source: `accounts_test.go`
- Shared test setup in `shared_test.go`
- SQL fixtures in `fixtures/` subdirectories

### Dependency Direction

```
models → keppel → processor → api/* → tasks
                             ↗         ↗
                    drivers/          test/
```

Models have zero internal dependencies. Everything imports models. Core logic lives in keppel/ and processor/.

---

## 11. Import Organization

### Three-Group Strict Order

The project uses a strict three-group import style with blank line separators:

```go
import (
    // Group 1: stdlib
    "context"
    "encoding/json"
    "fmt"
    "net/http"

    // Group 2: third-party (external dependencies)
    "github.com/gorilla/mux"
    "github.com/sapcc/go-bits/respondwith"

    // Group 3: internal (same project)
    "github.com/sapcc/keppel/internal/keppel"
    "github.com/sapcc/keppel/internal/models"
)
```

### Dot Import: Only for Option

Dot import is used exclusively for `github.com/majewsky/gg/option` — a dedicated Option type library. This appears in 30+ files:

```go
import (
    . "github.com/majewsky/gg/option"
)
```

This enables `Option[T]`, `Some()`, `None[T]()` without package prefix. No other package gets dot-imported.

### Named Imports for Internal Package Disambiguation

When multiple internal packages share a name, use named imports:

```go
import (
    auth "github.com/sapcc/keppel/internal/api/auth"
    keppelv1 "github.com/sapcc/keppel/internal/api/keppel"
    peerv1 "github.com/sapcc/keppel/internal/api/peer"
    registryv2 "github.com/sapcc/keppel/internal/api/registry"
)
```

For cobra subcommands in main:

```go
import (
    anycastmonitorcmd "github.com/sapcc/keppel/cmd/anycastmonitor"
    apicmd "github.com/sapcc/keppel/cmd/api"
    janitorcmd "github.com/sapcc/keppel/cmd/janitor"
)
```

### Blank Imports for Driver Registration

Only in `main.go` for init()-based driver registration:

```go
// include all known driver implementations
_ "github.com/sapcc/keppel/internal/drivers/basic"
_ "github.com/sapcc/keppel/internal/drivers/filesystem"
_ "github.com/sapcc/keppel/internal/drivers/openstack"
_ "github.com/sapcc/keppel/internal/drivers/trivial"
```

---

## 12. Constants and Package-Level Variables

### Placement: Adjacent to Types

Constants live near the types they describe, not in a separate `constants.go` file:

```go
// In models/blob.go, near the Blob type:
const (
    BlobValidationInterval           = 7 * 24 * time.Hour
    BlobValidationAfterErrorInterval = 10 * time.Minute
)
```

With explanatory comments when placement is non-obvious:

```go
// ManifestValidationInterval is how often each manifest will be validated by ManifestValidationJob.
// This is here instead of near the job because package processor also needs to know it.
ManifestValidationInterval = 24 * time.Hour
```

### SQL Queries as Package-Level Vars

All SQL queries are package-level `var` declarations with `sqlext.SimplifyWhitespace`:

```go
var blobSweepSearchQuery = sqlext.SimplifyWhitespace(`
    SELECT * FROM accounts
        WHERE next_blob_sweep_at IS NULL OR next_blob_sweep_at < $1
    ORDER BY next_blob_sweep_at IS NULL DESC, next_blob_sweep_at ASC
    LIMIT 1
`)
```

Never inline SQL strings in function bodies.

### Sentinel Errors as Package-Level Vars

Grouped by theme in `var` blocks:

```go
var (
    errNoSuchBlob                   = errors.New("no such blob")
    errNoSuchManifest               = errors.New("no such manifest")
    errNoSuchTrivyReport            = errors.New("no such Trivy report")
    errAppendToBlobAfterFinalize    = errors.New("AppendToBlob() was called after FinalizeBlob()")
    errAbortBlobUploadAfterFinalize = errors.New("AbortBlobUpload() was called after FinalizeBlob()")
)
```

---

## 13. Comment Style

### SPDX License Headers on Every File

```go
// SPDX-FileCopyrightText: 2020 SAP SE or an SAP affiliate company
// SPDX-License-Identifier: Apache-2.0
```

No exceptions. Every `.go` file starts with this.

### Godoc Format

Exported types/functions always have godoc. Format: `// Name verb...`

```go
// Janitor contains the toolbox of the keppel-janitor process.
type Janitor struct {

// NewJanitor creates a new Janitor.
func NewJanitor(...) *Janitor {

// BlobSweepJob is a job. Each task finds one account where blobs need to be
// garbage-collected, and performs the GC.
func (j *Janitor) BlobSweepJob(...)
```

### Inline Comments: Explain WHY, Not WHAT

Comments explain business logic, edge cases, and ordering constraints:

```go
// delete each blob from the DB *first*, then clean it up on the storage
//
// This order is important: The DELETE statement could fail if some concurrent
// process created a blob mount in the meantime. If that happens, and we have
// already deleted the blob in the backing storage, we've caused an
// inconsistency that we cannot recover from.
```

```go
// ^ NOTE: It's not a problem if there are blob_mounts in this repo. When the
// repo is deleted, its blob mounts will be deleted as well, and the janitor
// will then clean up any blobs without any remaining mounts.
```

### Section Dividers

80 slashes separate logical sections within a file:

```go
////////////////////////////////////////////////////////////////////////////////
// janitorUserIdentity
```

### NOTE and nolint Markers

```go
//NOTE: We use HasPrefix here because the actual Content-Type is usually
// "application/json; charset=utf-8".

//nolint:gosec // This is not crypto-relevant, so math/rand is okay.
r := rand.Float64()
```

### Lead Review Standard on Naming

The review standard will reject naming that creates false impressions:

> "I won't put 'error' at the end because 'customStatusHavingError' sounds stupid"
> "Because I don't want to create the impression that Keppel reads this variable."

---

## 14. Concurrency Patterns

### Sparingly and Deliberately

Keppel uses concurrency **sparingly**. There is exactly one `go func` in internal code (Trivy parallelization). Goroutines are almost entirely launched at startup.

### Worker Pool for Batch Operations

```go
inputChan := make(chan models.TrivySecurityInfo, batchSize)
for _, securityInfo := range securityInfos {
    inputChan <- securityInfo
}
close(inputChan)

returnChan := make(chan chanReturnStruct, threads)
var wg sync.WaitGroup

for range threads {
    wg.Go(func() {
        for securityInfo := range inputChan {
            err := j.doSecurityCheck(ctx, &securityInfo)
            returnChan <- chanReturnStruct{securityInfo: securityInfo, err: err}
        }
    })
}

go func() {
    wg.Wait()
    close(returnChan)
}()

var errs errext.ErrorSet
for returned := range returnChan {
    // collect results
}
```

### Per-Resource Mutex (Not One Global Lock)

```go
type StorageDriver struct {
    blobs                map[string][]byte
    blobsMutex           sync.RWMutex
    blobChunkCounts      map[string]uint32
    blobChunkCountsMutex sync.RWMutex
    manifests            map[string][]byte
    manifestMutex        sync.RWMutex
}
```

Each map gets its own mutex. Read operations use `RLock`, write operations use `Lock`. Always `defer` the unlock:

```go
d.blobsMutex.RLock()
defer d.blobsMutex.RUnlock()
contents, exists := d.blobs[blobKey(account, storageID)]
```

### Ticker + Select for Background Loops

```go
go func() {
    ticker := time.NewTicker(10 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            err := tryIssueNewPasswordForPeer(ctx, cfg, db)
            if err != nil {
                logg.Error("cannot issue new peer password: " + err.Error())
            }
        }
    }
}()
```

---

## 15. Startup and Shutdown Sequences

### Entry Point Structure

```go
func main() {
    logg.ShowDebug = osext.GetenvBool("KEPPEL_DEBUG")
    keppel.SetupHTTPClient()

    rootCmd := &cobra.Command{...}
    // mount subcommands
    must.Succeed(rootCmd.Execute())
}
```

### Subcommand run() Follows Strict Sequence

1. Set task name
2. Parse configuration from env
3. Create context with SIGINT handling
4. Initialize audit trail
5. Connect to database + register metrics
6. Initialize drivers (auth, federation, storage, etc.)
7. Start background goroutines
8. Wire up HTTP handlers (metrics + health check)
9. Start HTTP server with context (blocks until shutdown)

```go
func run(cmd *cobra.Command, args []string) {
    keppel.SetTaskName("janitor")

    cfg := keppel.ParseConfiguration()
    ctx := httpext.ContextWithSIGINT(cmd.Context(), 10*time.Second)
    auditor := must.Return(keppel.InitAuditTrail(ctx))

    dbURL, dbName := keppel.GetDatabaseURLFromEnvironment()
    dbConn := must.Return(easypg.Connect(dbURL, keppel.DBConfiguration()))
    prometheus.MustRegister(sqlstats.NewStatsCollector(dbName, dbConn))
    db := keppel.InitORM(dbConn)

    // initialize drivers...
    ad := must.Return(keppel.NewAuthDriver(ctx, osext.MustGetenv("KEPPEL_DRIVER_AUTH"), rc))
    fd := must.Return(keppel.NewFederationDriver(ctx, osext.MustGetenv("KEPPEL_DRIVER_FEDERATION"), ad, cfg))

    // start task loops
    janitor := tasks.NewJanitor(cfg, fd, sd, icd, db, amd, auditor)
    go janitor.AccountFederationAnnouncementJob(nil).Run(ctx)
    go janitor.AbandonedUploadCleanupJob(nil).Run(ctx)
    // ... more jobs ...

    // start HTTP server (blocks until context cancelled)
    must.Succeed(httpext.ListenAndServeContext(ctx, listenAddress, mux))
}
```

### Signal Handling

Uses `httpext.ContextWithSIGINT(cmd.Context(), 10*time.Second)` — cancels the context on SIGINT with a 10-second grace period. All background jobs receive this context and exit cleanly.

### Fatal on Startup Errors

Uses `must.Return()` and `must.Succeed()` instead of manual error checking during initialization. Crashes immediately if something fails during startup (acceptable because recovery is impossible at startup).

**No explicit `os.Exit()` or `signal.Notify()`** — delegated to library code.

---

## 16. Background Jobs / Task Patterns

### Producer-Consumer via jobloop

All background jobs use the `jobloop` library:

```go
func (j *Janitor) BlobSweepJob(registerer prometheus.Registerer) jobloop.Job {
    return (&jobloop.ProducerConsumerJob[models.Account]{
        Metadata: jobloop.JobMetadata{
            ReadableName: "sweep blobs",
            CounterOpts: prometheus.CounterOpts{
                Name: "keppel_blob_sweeps",
                Help: "Counter for garbage collections on blobs in an account.",
            },
        },
        DiscoverTask: func(_ context.Context, _ prometheus.Labels) (account models.Account, err error) {
            err = j.db.SelectOne(&account, blobSweepSearchQuery, j.timeNow())
            return account, err
        },
        ProcessTask: j.sweepBlobsInRepo,
    }).Setup(registerer)
}
```

Structure:
- `DiscoverTask`: SQL query that finds the next piece of work. Returns `sql.ErrNoRows` when idle.
- `ProcessTask`: Method that processes the discovered work item.
- `Metadata`: Human-readable name + Prometheus counter definition.
- `Setup(registerer)`: Registers metrics and returns the job.

### Job Launch Pattern

Fire-and-forget goroutines from the startup function:

```go
go janitor.BlobSweepJob(nil).Run(ctx)
go janitor.ManifestGarbageCollectionJob(nil).Run(ctx)
```

### Discover Query Pattern

"Find the next item needing work, ordered by oldest-first, limit 1":

```go
var blobSweepSearchQuery = sqlext.SimplifyWhitespace(`
    SELECT * FROM accounts
        WHERE next_blob_sweep_at IS NULL OR next_blob_sweep_at < $1
    ORDER BY next_blob_sweep_at IS NULL DESC, next_blob_sweep_at ASC
    LIMIT 1
`)
```

### Done Queries Update Next-Check Timestamp

```go
_, err = j.db.Exec(blobSweepDoneQuery, account.Name, j.timeNow().Add(j.addJitter(1*time.Hour)))
```

### Jitter to Prevent Thundering Herd

All scheduled intervals get `addJitter` (plus/minus 10%):

```go
func addJitter(duration time.Duration) time.Duration {
    // returns random duration within +/- 10% of requested value
}
```

Testability: `DisableJitter()` method for deterministic tests.

---

## 17. HTTP Client Patterns

### Global Transport Wrapping

```go
func SetupHTTPClient() {
    wrap = httpext.WrapTransport(&http.DefaultTransport)
    wrap.SetInsecureSkipVerify(osext.GetenvBool("KEPPEL_INSECURE"))
    wrap.SetOverrideUserAgent(bininfo.Component(), bininfo.VersionOr("rolling"))
}
```

### Uses http.DefaultClient

No custom `http.Client` instances. The transport is modified globally. Timeouts are handled via context deadlines, not client timeouts:

```go
resp, err := http.DefaultClient.Do(req)
```

### Request Construction

Always uses `http.NewRequestWithContext`:

```go
req, err := http.NewRequestWithContext(ctx, method, url, body)
```

### Auth Challenge/Retry Flow

1. Send request
2. If 401, parse auth challenge from response headers
3. Get token from challenge endpoint
4. Re-seek body if present
5. Resend with Bearer token

### Error Wrapping with Request Context

```go
return nil, fmt.Errorf("during %s %s: %w", method, url, err)
```

---

## 18. String Formatting Patterns

### fmt.Sprintf for String Construction

Not string concatenation. Used for error messages, keys, and URLs:

```go
func blobKey(account models.ReducedAccount, storageID string) string {
    return fmt.Sprintf("%s/%s", account.Name, storageID)
}
```

### String Concatenation Only for Simple Cases

```go
creds := userName + ":" + password
return "Basic " + base64.StdEncoding.EncodeToString([]byte(creds))
```

### Modern Go String Features

Uses `strings.SplitSeq` (Go 1.24+):

```go
for pathComponent := range strings.SplitSeq(name, `/`) {
    if !models.RepoPathComponentRx.MatchString(pathComponent) {
        return false
    }
}
```

---

## 19. Slice and Map Patterns

### Slice Initialization

```go
// Pre-allocated with known length
scopes := make([]auth.Scope, len(accounts))

// Nil slice, grown by append
var accountsFiltered []models.Account

// Empty slice for JSON serialization (ensures [] not null)
if len(accountsFiltered) == 0 {
    accountsFiltered = []models.Account{}
}
```

The nil-vs-empty distinction matters for JSON: `nil` → `null`, `[]T{}` → `[]`.

### Map Initialization

Always `make(map[K]V)` in constructors:

```go
d.blobs = make(map[string][]byte)
d.blobChunkCounts = make(map[string]uint32)
```

### Map as Set

```go
isPeerHostName := make(map[string]bool)
grantsPerm := make(map[RBACPermission]bool)
```

### Iteration

Standard `for _, x := range items` and `for key := range map`. Uses `slices.Contains()` from stdlib:

```go
if !slices.Contains(dbPolicies, policy) {
```

---

## 20. Observability and Metrics

### Prometheus Metrics as Package-Level Vars

```go
var (
    BlobBytesPulledCounter = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "keppel_pulled_blob_bytes",
            Help: "Counts blob content bytes that are pulled from Keppel.",
        },
        []string{"account", "auth_tenant_id", "method"},
    )
)

func init() {
    prometheus.MustRegister(BlobBytesPulledCounter)
}
```

### Metrics Naming

`keppel_` prefix, snake_case, descriptive. Labels always include `account` and `auth_tenant_id` for multi-tenant attribution.

### CADF Audit Events

Events use the OpenStack CADF format via `audittools.Auditor`:

```go
if userInfo := authz.UserIdentity.UserInfo(); userInfo != nil {
    a.auditor.Record(audittools.Event{
        Time:       time.Now(),
        Request:    r,
        User:       userInfo,
        ReasonCode: http.StatusOK,
        Action:     "create/security-scan-policy",
        Target:     AuditSecurityScanPolicy{Account: *account, Policy: policy},
    })
}
```

Audit targets implement the `audittools.Target` interface with a `Render() cadf.Resource` method.

### Conditional Audit Initialization

```go
func InitAuditTrail(ctx context.Context) (audittools.Auditor, error) {
    if os.Getenv("KEPPEL_AUDIT_RABBITMQ_QUEUE_NAME") == "" {
        return audittools.NewMockAuditor(), nil
    } else {
        return audittools.NewAuditor(ctx, audittools.AuditorOpts{...})
    }
}
```

### Background Job Identity for Audit

A special `janitorUserIdentity` type implements `UserIdentity` for audit events emitted by background jobs (which have no real user):

```go
type janitorUserInfo struct {
    TaskName string
    GCPolicy Option[keppel.GCPolicy]
}
```

### SQL Connection Metrics

```go
prometheus.MustRegister(sqlstats.NewStatsCollector(dbName, dbConn))
```

---

## 21. Project Design Philosophy

### Radical Simplicity

The project philosophy emphasizes replacing complex distributed systems with small shell scripts. Configuration management tools are "radically simple," relying as much as possible on existing package management. Build tooling is based on the idea "to have as many options as necessary but as little as possible."

### Domain-Faithful APIs

From schwift (a Swift client library): "Schwift improves on Gophercloud by providing an object-oriented API that respects and embraces Swift's domain model and API design." The critique: "Gophercloud is modeled around the 'JSON-in, JSON-out' request-response-based design that all OpenStack APIs share -- all of them, except for Swift."

**Principle**: APIs should model the domain, not the transport protocol.

### Backwards Compatibility as Design Constraint

From schwift: uses `*RequestOpts` pointer in every method so new fields can be added without breaking callers. From gg/option: "To avoid backwards incompatibilities, at least throughout the 1.x series, newer versions of this package will never export any more names than it currently does."

From PR reviews on CLI naming: "Command names must clearly describe what they do and leave room for siblings without renaming. `keppel test` → `keppel test-driver storage`."

### Type System as Enforcer

From gg/option: "The purpose of the Option type is to more clearly distinguish the two situations that standard Go uses pointer types for: to provide a way to edit the inside of a value without changing the value itself, and to allow for a value to be either present or absent."

**Principle**: Use the type system to make invalid states unrepresentable.

### Trust the Standard Library

From PR review: "ParseUint is disciplined about providing good context in its input messages... So we can avoid boilerplate here without compromising that much clarity in the error messages."

**Principle**: Don't wrap what the stdlib already says clearly.

### Dependency Consciousness

From PR review: "This would mean that a lot of applications will pull in go-bits/audittools that previously didn't, which then pulls the amqp library dependencies into those app's vendor directories. To avoid this, please move the GenerateUUID() function into package internal."

**Principle**: Every import has a cost. Transitive dependencies matter.

### Practical Over Theoretical

Verbatim quotes from reviews:
- "There is no practical reason to run this outside the repo root. All the alternatives are significant complications that are not worth it."
- "I'm going to ignore this based purely on the fact that Copilot complains about os.Stdout.Write(), but not about the much more numerous instances of fmt.Println that theoretically suffer the same problem."
- "This is an irrelevant contrivance."

**Principle**: If you can't point to a concrete scenario where it fails, don't handle it.

### Minimal API Surface

go-bits packages: 4 functions in `must`, 5 in `logg`. Package names read as English: `must.Succeed`, `respondwith.JSON`, `logg.Fatal`.

### Document the WHY, Not the WHAT

The `must.ReturnT` function includes three paragraphs explaining why its unusual signature is the only one that works given Go generics limitations. The project documents design constraints, not just solutions.

### No Mutable Global State

From PR review: "I don't like having a global variable for this that callers can mess with."

---

## 22. Where the Project DIVERGES from Standard Go Community Wisdom

This section is **the most important for LLM code generation**. These are patterns where the project's actual practice contradicts what Go style guides, blog posts, and community consensus recommend. An LLM trained on general Go content will get these WRONG unless explicitly overridden.

### Divergence 1: Positional Struct Literals in Constructors

| Community Says | Project Convention |
|----------------|-------------|
| "Use field names when initializing structs: `Foo{Bar: "x"}` not `Foo{"x"}`" (Uber Style Guide) | Positional struct literals in constructors: `&API{cfg, ad, fd, sd, icd, db, auditor, rle, time.Now, keppel.GenerateStorageID}` |

**Why the project diverges**: In constructors, the positional literal ensures that adding a new field to the struct causes a compile error in the constructor — it FORCES you to update the constructor. Named fields would silently zero-initialize the new field.

### Divergence 2: Many Constructor Parameters (No Functional Options)

| Community Says | Project Convention |
|----------------|-------------|
| "For constructors with many optional parameters, use the functional options pattern" (Uber Style Guide) | 7-8 positional parameters, no options pattern for constructors |

**Why the project diverges**: Constructor dependencies are NOT optional. They're required. Functional options add indirection for no benefit when every parameter is mandatory. The type system already validates that all dependencies are provided.

### Divergence 3: Tests Are NOT Table-Driven

| Community Says | Project Convention |
|----------------|-------------|
| "Use table-driven tests for functions with multiple input/output scenarios" (Go Wiki) | Sequential, scenario-driven narrative tests |

**Why the project diverges**: sapcc tests are integration tests that build up state across multiple operations. Each step depends on the previous one. Table-driven tests are for pure functions with independent inputs — they don't model stateful scenarios well.

### Divergence 4: String Enums, Not iota for Domain Values

| Community Says | Project Convention |
|----------------|-------------|
| "Start enums at a non-zero value, use iota" (Uber Style Guide) | String constants for all domain enums: `const CleanSeverity VulnerabilityStatus = "Clean"` |

**Why the project diverges**: String enums go directly into DB columns and JSON without conversion. There's no mapping layer to maintain. What you see in the code is what's in the database.

### Divergence 5: Auth is Inline, Not Middleware

| Community Says | Project Convention |
|----------------|-------------|
| Use middleware for cross-cutting concerns like auth | Auth called inline at top of each handler |

**Why the project diverges**: Different endpoints have different auth requirements (different scopes, different permissions). Making auth a middleware forces you into a one-size-fits-all model or creates complex middleware configuration. Inline auth is explicit about what each endpoint requires.

### Divergence 6: No Interface Segregation for Large Interfaces

| Community Says | Project Convention |
|----------------|-------------|
| "Keep interfaces small, prefer 1-2 methods" / "If your interface has more than 3-4 methods, break it up" (Effective Go, 100 Go Mistakes) | `StorageDriver` has 16 methods. No splitting. |

**Why the project diverges**: Every storage driver implementation MUST provide all 16 methods. Splitting into small interfaces would create false optionality — you can't implement "just reads" or "just writes." The domain demands a complete implementation.

### Divergence 7: Option[T] Instead of *T for Nullable

| Community Says | Project Convention |
|----------------|-------------|
| Use `*T` for optional values / "Pointers to signal optionality" | `Option[T]` from `github.com/majewsky/gg/option` |

**Why the project diverges**: `*T` is semantically ambiguous — it could mean "editable reference" OR "optional value." `Option[T]` is unambiguous. The library was written specifically to resolve this ambiguity.

### Divergence 8: Global HTTP Transport, Not Per-Client

| Community Says | Project Convention |
|----------------|-------------|
| Create custom `http.Client` with timeouts | Modify `http.DefaultTransport` globally, use `http.DefaultClient` |

**Why the project diverges**: In a service with one set of TLS/proxy/user-agent settings, configuring the default transport once is simpler than passing custom clients everywhere. Context deadlines handle timeouts per-request.

### Divergence 9: No "failed to" in Error Messages

| Community Says | Project Convention |
|----------------|-------------|
| "failed to get user: %w" is acceptable context | "cannot get user: %w" or "while getting user: %w" — never "failed to" |

**Why the project diverges**: The error return already means something failed. "Failed to" is redundant. "Cannot" or "while" are more precise about what the code was trying to do.

### Divergence 10: init() for Driver Registration

| Community Says | Project Convention |
|----------------|-------------|
| "Avoid init() where possible" (Uber Style Guide) | `init()` for driver self-registration: `keppel.AuthDriverRegistry.Add(...)` |

**Why the project diverges**: The pluggable driver pattern requires compile-time-optional modules that register themselves. `init()` with blank imports in `main.go` is the standard Go pattern for this (same as `database/sql` drivers). This is one of the few legitimate uses of `init()`.

### Divergence 11: No Config Validation Layer

| Community Says | Project Convention |
|----------------|-------------|
| Validate config at startup, return structured errors | `osext.MustGetenv()` panics if missing. No validation framework. |

**Why the project diverges**: If a required env var is missing, the program can't run. A panic with a clear message ("required environment variable KEPPEL_API_PUBLIC_FQDN is not set") is more useful than a validation framework that adds complexity to report the same thing.

### Divergence 12: Embed SQL in Go, Not External Files

| Community Says | Project Convention |
|----------------|-------------|
| Use `embed.FS` for SQL files, or external migration tools (goose, migrate) | Migrations as `map[string]string` in Go code |

**Why the project diverges**: Keeping migrations in Go code means they're type-checked at compile time, version-controlled alongside the code that uses them, and don't require external tooling. The map keys provide ordering.

---

## 23. go-bits Library Package Guide

The go-bits libraries are designed to read as English. Package names pair with function names:

| Package | Key Functions | Reads As |
|---------|--------------|----------|
| `must` | `must.Succeed(err)`, `must.Return(val, err)` | "must succeed", "must return" |
| `logg` | `logg.Fatal(msg)`, `logg.Error(msg)`, `logg.Info(msg)` | "log fatal", "log error" |
| `respondwith` | `respondwith.JSON(w, code, data)`, `respondwith.ObfuscatedErrorText(w, err)` | "respond with JSON" |
| `httpapi` | `httpapi.Compose(apis...)`, `httpapi.IdentifyEndpoint(r, path)` | "HTTP API compose" |
| `osext` | `osext.MustGetenv(key)`, `osext.GetenvBool(key)` | "OS ext must get env" |
| `sqlext` | `sqlext.SimplifyWhitespace(sql)`, `sqlext.RollbackUnlessCommitted(tx)` | "SQL ext rollback unless committed" |
| `assert` | `assert.HTTPRequest{}.Check(t, h)`, `assert.DeepEqual(t, label, a, b)` | "assert HTTP request check" |
| `easypg` | `easypg.Connect(url, cfg)`, `easypg.AssertDBContent(t, db, fixture)` | "easy PG connect" |
| `errext` | `errext.ErrorSet`, `errext.IsOfType[T](err)` | "error ext error set" |

### Minimal API Surfaces

- `must`: 4 functions total
- `logg`: 5 functions total
- `respondwith`: ~6 functions total

Each package does one thing. If you need something the package doesn't provide, that's intentional — use the stdlib directly.

---

## 24. Anti-Patterns That Will Get Code Rejected

These are the specific patterns that the lead review standard will reject in PR review. They're ordered by how likely an LLM is to generate them.

### AP-1: Generating Wrapper Functions

```go
// REJECTED: Wrapper that adds nothing
func (s *Service) GetDB() *DB {
    return s.db
}

// Review standard says: "Delete this, just access s.db directly"
```

### AP-2: Creating Interfaces Before They're Needed

```go
// REJECTED: Interface with one implementation
type AccountRepository interface {
    GetAccount(id string) (*Account, error)
    CreateAccount(a *Account) error
}

// Review standard says: "Just use the concrete type. You can add an interface later if
// you actually get a second implementation."
```

### AP-3: Using viper or Config Files

```go
// REJECTED: Any config file approach
viper.SetConfigFile("config.yaml")
viper.ReadInConfig()

// Review standard says: "Use osext.MustGetenv. We don't use config files."
```

### AP-4: Option Structs for Constructors

```go
// REJECTED: Option struct
type ServerConfig struct {
    Host string
    Port int
    DB   *sql.DB
}
func NewServer(cfg ServerConfig) *Server { ... }

// Review standard says: positional params, even if there are 8 of them
func NewServer(host string, port int, db *sql.DB, ...) *Server {
    return &Server{host, port, db, ...}
}
```

### AP-5: Using testify or gomock

```go
// REJECTED: testify assertions
assert.Equal(t, expected, actual)
require.NoError(t, err)

// Project convention uses go-bits/assert, not testify
assert.DeepEqual(t, "accounts", actual, expected)
```

### AP-6: Table-Driven Tests for Integration Scenarios

```go
// REJECTED: Table-driven for stateful scenarios
tests := []struct{ name string; ... }{
    {"create account", ...},
    {"list accounts", ...},
}

// Project convention: sequential narrative tests
// Step 1: create account
assert.HTTPRequest{Method: "PUT", ...}.Check(t, h)
// Step 2: verify it appears in list
assert.HTTPRequest{Method: "GET", ...}.Check(t, h)
```

### AP-7: Constructor Returns Error

```go
// REJECTED: Fallible constructor
func NewAPI(cfg Config) (*API, error) {
    if cfg.Host == "" {
        return nil, errors.New("host required")
    }
    return &API{cfg: cfg}, nil
}

// Review standard says: constructors are infallible. Validate config at parse time.
func NewAPI(cfg Config, db *DB, ad AuthDriver) *API {
    return &API{cfg, db, ad}
}
```

### AP-8: "failed to" in Error Messages

```go
// REJECTED
return fmt.Errorf("failed to create account: %w", err)

// CORRECT
return fmt.Errorf("cannot create account %q: %w", name, err)
```

### AP-9: Logging AND Returning the Same Error

```go
// REJECTED
if err != nil {
    log.Printf("error creating account: %v", err)
    return err
}

// CORRECT: return only, let the caller decide whether to log
if err != nil {
    return err
}
```

### AP-10: Using log Instead of logg

```go
// REJECTED
log.Printf("starting server on %s", addr)

// CORRECT
logg.Info("starting server on %s", addr)
```

### AP-11: MySQL-Style Placeholders

```go
// REJECTED
db.Query("SELECT * FROM accounts WHERE name = ?", name)

// CORRECT: PostgreSQL positional params
db.Query("SELECT * FROM accounts WHERE name = $1", name)
```

### AP-12: Named Struct Fields in Constructor Return

```go
// REJECTED
return &API{
    config:  cfg,
    db:      db,
    auth:    ad,
    storage: sd,
}

// CORRECT: positional
return &API{cfg, db, ad, sd}
```

### AP-13: Using *T for Optional DB Fields

```go
// REJECTED
type Account struct {
    NextSweepAt *time.Time `db:"next_sweep_at"`
}

// CORRECT
type Account struct {
    NextSweepAt Option[time.Time] `db:"next_sweep_at"`
}
```

### AP-14: Query Builders

```go
// REJECTED
sq.Select("*").From("accounts").Where(sq.Eq{"name": name})

// CORRECT: raw SQL as package-level var
var accountQuery = sqlext.SimplifyWhitespace(`
    SELECT * FROM accounts WHERE name = $1
`)
```

### AP-15: Middleware for Auth

```go
// REJECTED
r.Use(authMiddleware)

// CORRECT: inline at top of handler
authz := a.authenticateRequest(w, r, scopeFromRequest(r, keppel.CanViewAccount))
if authz == nil { return }
```

### AP-16: Over-Engineering Error Types

```go
// REJECTED: Custom error types for one-off errors
type AccountNotFoundError struct {
    Name string
}
func (e *AccountNotFoundError) Error() string { ... }

// CORRECT: Simple sentinel or fmt.Errorf
var errAccountNotFound = errors.New("account not found")
// or
return fmt.Errorf("cannot find account %q: %w", name, sql.ErrNoRows)
```

### AP-17: Adding Abstractions "For Future Use"

```go
// REJECTED: Repository pattern when there's one storage
type AccountRepository struct { db *DB }
func (r *AccountRepository) Get(id string) (*Account, error) { ... }

// Review standard says: "Just call db.SelectOne directly. You don't need a repository
// layer when there's one database."
```

---

## 25. Lead Review Comments on LLM-Generated Code (go-bits backing store feature)

This section contains **actual review comments** from a go-bits PR where LLM-assisted code was reviewed for a backing store feature. These comments are the most direct evidence of what LLMs get wrong in this codebase.

### 25.1: Don't Extract Functions Just to Reduce Complexity Metrics

Review comment on an extracted helper function:
> "Why does this need to be a separate function? Code should only be in its own function if it's reused, or if it's a long-winded implementation of details that distract from the main purpose of the overall function. Both do not apply here as far as I can see, so this feels like a **contrived edit to satisfy silly metrics like cyclomatic complexity**."

**Rule**: Only extract functions when they're reused or when they hide complex implementation details. Never extract to satisfy linter metrics.

### 25.2: Don't Export Types When Only the Constructor Is Public

Review comment on exported `InMemoryBackingStore` and `FileBackingStore` structs:
> "Why does this type need to be exported? Clients should only need `NewInMemoryBackingStore`."
> "Same as for InMemoryBackingStore: All the public methods on this type are the ones that implement BackingStore, so this type does not need to be public."

**Rule**: If a type's only public methods are interface implementations, keep the type unexported. Export only the constructor function.

```go
// REJECTED: Exported type when interface is sufficient
type FileBackingStore struct { ... }
func NewFileBackingStore(...) *FileBackingStore { ... }

// CORRECT: Unexported type, exported constructor returns interface
type fileBackingStore struct { ... }
func NewFileBackingStore(...) BackingStore { ... }
```

### 25.3: Use go-bits Assertion Helpers (assert.ErrEqual, must.SucceedT)

The review consistently corrected verbose error checking to use go-bits helpers:

```go
// REJECTED: Verbose error checking in tests
if err != nil {
    t.Fatalf("unexpected error: %v", err)
}

// CORRECT: Use must.SucceedT
must.SucceedT(t, store.UpdateMetrics())

// REJECTED: Verbose nil check
if err != nil {
    t.Fatalf("...")
}

// CORRECT: Use assert.ErrEqual
assert.ErrEqual(t, err, nil)

// For return values:
files := must.ReturnT(store.ListFiles())(t)
```

### 25.4: Deduplicate Tests Across Implementations

Strongest structural comment — deduplicate tests that work the same across all BackingStore implementations:

```go
// REJECTED: Separate test functions per implementation
func TestMemoryBackingStoreFIFO(t *testing.T) { ... }
func TestFileBackingStoreFIFO(t *testing.T) { ... }
func TestSQLBackingStoreFIFO(t *testing.T) { ... }

// CORRECT: One test, parameterized across all implementations
func TestBackingStoreFIFO(t *testing.T) {
    testWithEachTypeOfStore(t, func(t *testing.T, store BackingStore) {
        // test logic here
    })
}

func testWithEachTypeOfStore(t *testing.T, action func(*testing.T, BackingStore)) {
    t.Run("with file store", func(t *testing.T) {
        action(t, newTestFileBackingStore(...))
    })
    t.Run("with memory store", func(t *testing.T) {
        action(t, newTestMemoryBackingStore(...))
    })
    t.Run("with PostgreSQL store", func(t *testing.T) {
        action(t, newTestSQLBackingStore(...))
    })
}
```

### 25.5: Option[T] at Parse Time, Not in Struct Fields

Review comment on `Option[int64]` fields in the backing store struct:
> "Having `Option` here means that each method of FileBackingStore needs to handle the None case, even though you are removing the None case during Init. I suggest having just `int64` here, and only having Option at params parsing time."

```go
// REJECTED: Option in the runtime struct
type FileBackingStore struct {
    MaxFileSize  Option[int64]
    MaxTotalSize Option[int64]
}

// CORRECT: Option only at parse time, concrete values in struct
var cfg struct {
    MaxFileSize  Option[int64] `json:"max_file_size"`
    MaxTotalSize Option[int64] `json:"max_total_size"`
}
if err := json.Unmarshal(params, &cfg); err != nil { ... }
store := fileBackingStore{
    MaxFileSize:  cfg.MaxFileSize.UnwrapOr(10 << 20),
    MaxTotalSize: cfg.MaxTotalSize.UnwrapOr(0),
}
```

### 25.6: No Redundant Connection Logic in Plugins

Review comment on SQLBackingStore having its own DB connection:
> "This should not contain its own connection logic. Not only would this mean that each process would hold two different connection pools to the same database, which is confusing. It would also break with the test setup in `easypg.ConnectForTest()`."

**Rule**: Plugins receive their dependencies from the caller. They don't create their own connections.

### 25.7: Initialize Prometheus Metrics to Zero

Review comment on metrics that only appear after the first error:
> "Init should `.Set(0)` on all relevant metrics to ensure that the metrics are explicitly reported at 0 even if no errors have occurred yet. (This is particularly relevant for our org because the absent-metrics-operator will otherwise complain about this metric family missing if it is referenced in alerts.)"

```go
// REJECTED: Metrics only appear when incremented
store.errorCounter.WithLabelValues("write").Inc()

// CORRECT: Pre-initialize all label combinations to 0
func (s *fileBackingStore) Init(registry prometheus.Registerer) error {
    // ... register metrics ...
    for _, op := range []string{"write", "read", "delete"} {
        s.errorCounter.WithLabelValues(op).Set(0)
    }
}
```

### 25.8: Use assert.Equal for Comparable Values

Review comment on using DeepEqual for simple comparisons:
> "For comparable values like this one (i.e. values that Go allows to compare with `==`), `assert.Equal` is to be preferred because it does not require reflection."

### 25.9: Don't Duplicate Helper Functions Per Type

Review corrected separate `mustReadBatchMemory` and `mustReadBatchSQL` helpers:
> "Several of these helper functions only use methods from the BackingStore interface, and so can be deduplicated by generalizing to that interface."

```go
// REJECTED: Per-type helpers
func mustReadBatchMemory(t *testing.T, store *InMemoryBackingStore) []Event { ... }
func mustReadBatchSQL(t *testing.T, store *SQLBackingStore) []Event { ... }

// CORRECT: Interface-based helper
func mustReadBatch(t *testing.T, store BackingStore) []Event { ... }
```

### 25.10: Use Modern Go Features (Go 1.22+ Loop Variables)

Review pointed out LLM-generated code that worked around pre-1.22 loop variable capture:
> "The thing where you need to pass a loop iteration variable as an explicit argument to a closure to avoid it from being overwritten in subsequent iterations is not necessary anymore since Go 1.22."

```go
// REJECTED: Pre-1.22 workaround (LLMs generate this from old training data)
for i := 0; i < 10; i++ {
    i := i  // capture loop variable
    go func() { use(i) }()
}

// CORRECT: Go 1.22+ — loop variables are per-iteration
for i := range 10 {
    go func() { use(i) }()
}
```

Also: use `wg.Go(func() { ... })` instead of manual `wg.Add(1)` + `go func() { defer wg.Done(); ... }()`.

### 25.11: Use sqlext.ForeachRow, Not Manual Row Scanning

Review comment on boilerplate row scanning:
> "Boilerplate can be replaced with `sqlext.ForeachRow`."

### 25.12: Don't Create Unnecessary Validation Functions

Review comment on a regex validation helper:
> "This helper function is not needed. The regex already returns false for an empty-string input, and then the function call can be replaced with `sqlIdentifierRegex.MatchString()` to make it easier to follow the code along."

**Rule**: If the stdlib or a regex already handles the edge case, don't wrap it in a helper.

### 25.13: Separate Interface Documentation from Implementation

Review comment on documentation placed on a concrete type:
> "This line should be in the documentation for type BackingStore."

**Rule**: Document the contract on the interface, not on the implementation.

### 25.14: Design for Pluggable Backing Stores via Factories

Architectural guidance — use factory functions with JSON config, matching the keppel driver pattern:

```go
type BackingStoreFactory func(params json.RawMessage, opts AuditorOpts) (BackingStore, error)

// Application provides factories for each store type
auditor := must.Return(audittools.NewAuditor(ctx, audittools.AuditorOpts{
    EnvPrefix: "LIMES_AUDIT_RABBITMQ",
    BackingStoreFactories: map[string]audittools.BackingStoreFactory{
        "fs":  audittools.NewFileBackingStore,
        "db":  func(params json.RawMessage, opts audittools.AuditorOpts) (BackingStore, error) {
            return newDBBackingStore(dbConnection, params, opts.Registry)
        },
    },
}))
```

### 25.15: Commit Must Be Precise (Race Condition)

Review comment on a commit function that cleared all events:
> "This should only remove specifically those events that are returned from the ReadBatch call. As it stands, if new events are enqueued between the return of the ReadBatch call and the call to `commit`, those events will be discarded without ever having been read."

**Rule**: Operations must be precise about which items they affect. Don't use bulk clear when targeted removal is needed.

### Summary of LLM Patterns Rejected in This Review

| LLM Pattern | Review Correction |
|-------------|---------------------|
| Extract helper to reduce cyclomatic complexity | "Contrived edit to satisfy silly metrics" — inline it |
| Export all types | Unexport types when interface is sufficient |
| Verbose error checking | `must.SucceedT(t, err)` and `assert.ErrEqual(t, err, nil)` |
| Separate tests per implementation | `testWithEachTypeOfStore` parameterized pattern |
| Option[T] in runtime struct fields | Option only at parse time, `.UnwrapOr()` to concrete |
| Plugin creates own DB connection | Receive dependencies from caller |
| Metrics appear only on first use | `.Set(0)` on all label combinations at init |
| Pre-1.22 loop variable capture | Go 1.22+ per-iteration semantics |
| Manual row scanning loops | `sqlext.ForeachRow` |
| Unnecessary validation wrapper | Use regex directly |
| Bulk clear in commit | Precise removal of read items only |

---

## 26. Naming Conventions (Deep Dive)

Rules from limes reviews and limesctl reviews that go beyond the naming basics in sections 1 and 13. These are the patterns most likely to trip up an LLM because they involve the project's semantic precision about English.

### 26.1 SQL Query Variables Must End With "Query"

> "These variable names read like function names. I usually put 'Query' at the end to nounify them."
> — lead review, limes

```go
// REJECTED: reads like a function call
getCommitmentWithMatchingTransferToken = sqlext.SimplifyWhitespace(`...`)
findTargetAZResourceIDBySourceID = sqlext.SimplifyWhitespace(`...`)

// CORRECT: clearly a data variable, not a function
getCommitmentWithMatchingTransferTokenQuery = sqlext.SimplifyWhitespace(`...`)
findTargetAZResourceIDBySourceIDQuery = sqlext.SimplifyWhitespace(`...`)
```

### 26.2 Function Names Must Describe Actual Side Effects

> "This does not actually 'do' anything to the database, as the name implies."
> — lead review, limes

```go
// REJECTED: implies DB mutation when it only builds a struct
func (p *v1Provider) splitCommitment(dbCommitment db.ProjectCommitment, amount uint64) db.ProjectCommitment {

// CORRECT: "build" clarifies it's a pure computation
func (p *v1Provider) buildSplitCommitment(dbCommitment db.ProjectCommitment, amount uint64) db.ProjectCommitment {
```

### 26.3 Query Methods Use "Is..." or Past Tense; Mutating Methods Use Active Verbs

> "Present tense in a method name implies an activity, but this method does not cause anyone to ignore anything; it just checks whether something is already ignored."
> — lead review, limes

```go
// REJECTED: implies the method causes ignoring
func (l *Logic) IgnoreFlavor(flavorName string) bool {

// CORRECT: past tense = checking state
func (l *Logic) IsIgnoredFlavor(flavorName string) bool {
```

### 26.4 "Sort" vs "Sorted": Active Verb = In-Place, Past Tense = New Collection

> "I forgot to nitpick this before... but `Sort` implies that this function operates in-place, which it does not."
> — lead review, limes

```go
// REJECTED: "Sort" implies in-place mutation
func SortMapKeys[M map[K]V, K ~string, V any](mapToSort M) []K {

// CORRECT: "Sorted" communicates it returns a new collection
func SortedMapKeys[M map[K]V, K ~string, V any](mapToSort M) []K {
```

### 26.5 Avoid Stuttering in Nested Struct Fields

> "I would like to take the opportunity and make this data a bit more structured. All these attributes should be bundled into a substruct (with `FlavorName` also renamed to just `Name` to avoid stuttering)."
> — lead review, limes

```go
// REJECTED: flavor prefix repeated on every field
type SubresourceAttributes struct {
    FlavorName  string `json:"flavor_name"`
    FlavorVCPUs int    `json:"flavor_vcpus"`
}

// CORRECT: group into substruct, drop the prefix
type SubresourceAttributes struct {
    Flavor FlavorAttributes `json:"flavor"`
}
type FlavorAttributes struct {
    Name  string `json:"name"`
    VCPUs int    `json:"vcpus"`
}
```

### 26.6 Counter Metric Names Must Be Plural

> "Names for counter metric families should be plural."
> — lead review, limes

```go
// REJECTED
Name: "limes_mail_delivery",

// CORRECT
Name: "limes_mail_deliveries",
```

### 26.7 Metric Names Must Include Application Prefix

> "The name must mention that it's a Limes metric."
> — lead review, limes

```go
// REJECTED
Name: "mail_deliveries",

// CORRECT
Name: "limes_mail_deliveries",
```

### 26.8 Method Receiver = The Actor, Not the Data

> "I don't like that the method receiver is `MailInfo` here. The method receiver should usually be 'the thing that does the action'."
> — lead review, limes

```go
// REJECTED: MailInfo is data, not an actor
func (m MailInfo) Send(client MailClient) error {

// CORRECT: MailClient is the actor
func (c *MailClient) Send(info MailInfo) error {
```

### 26.9 Short-Lived Success Variables Use "ok" or "exists"

> "For shortlived success variables like this, it's idiomatic to use short, undistinct names (usually `ok` or `exists`)."
> — lead review, limes

```go
// REJECTED: verbose boolean name
fixedCapaConfig, fixedCapacityConfigurationExists := p.FixedCapacityConfiguration.Unpack()

// CORRECT: idiomatic short name
fixedCapaConfig, ok := p.FixedCapacityConfiguration.Unpack()
```

### 26.10 Field Names Must Use Domain Canonical Terminology

> "This field contains a share type name and should be named as such. `ShareTypeName`."
> — lead review, castellum

```go
// REJECTED: project-specific abbreviation
NFSType string

// CORRECT: Manila's canonical term
ShareTypeName string
```

### 26.11 No Contractions in Error Messages

> "Contractions are usually avoided in writing."
> — lead review, castellum

```go
// REJECTED
return fmt.Errorf("%s/%s quota for project %s isn't reported by Limes", svc, res, proj)

// CORRECT
return fmt.Errorf("%s/%s quota for project %s is not reported by Limes", svc, res, proj)
```

### 26.12 Error Messages Must Read as Complete Sentences

> "Phrasing: Error messages should be readable as sentences."
> — lead review, limes

```go
// REJECTED: not a sentence
errs.Addf("parse mail template: %w", err)

// CORRECT: reads as English
errs.Addf("could not parse mail template: %w", err)
```

### 26.13 Preposition Precision in Error Messages

> "It's not a query _for_ Prometheus (i.e. on behalf of Prometheus), it's a query _towards_ or _in_ Prometheus."
> — lead review, castellum

```go
// REJECTED: "for" implies on behalf of Prometheus
return fmt.Errorf("query failed for Prometheus: %s: %s", query, err)

// CORRECT: describes the target correctly
return fmt.Errorf("could not execute Prometheus query: %s: %s", query, err)
```

---

## 27. Database and SQL Patterns (Deep Dive)

Extends section 7 with rules from limes reviews and castellum reviews. These patterns are specific to PostgreSQL and the `easypg`/`sqlext` ecosystem.

### 27.1 Existing Migrations Are Immutable

> "Existing migrations may not be touched. You need to add your migration at the bottom as number 11, otherwise this will break on existing databases (i.e. in production)."
> — lead review, limes

**Rule**: Never edit an existing migration file. Always append a new migration with the next sequence number. Modifying a migration that has already run in production causes schema drift.

### 27.2 Database Constraints Over Application-Level Checks

> "Please remove this part and instead add a uniqueness constraint on the `project_commitments.transfer_token` column. I'd much rather have the DB enforce this."
> — lead review, limes

```go
// REJECTED: checking uniqueness in Go
if tokenAlreadyExists(token) {
    return errors.New("token already exists")
}

// CORRECT: let PostgreSQL enforce it
// Migration: ALTER TABLE project_commitments ADD CONSTRAINT ... UNIQUE (transfer_token);
```

### 27.3 Always Use TIMESTAMPTZ, Never TIMESTAMP

> "The type `TIMESTAMP` does not work correctly because it does not persist timezone information."
> — lead review, limes

```sql
-- REJECTED
ALTER TABLE commitments ADD COLUMN confirmed_at TIMESTAMP;

-- CORRECT
ALTER TABLE commitments ADD COLUMN confirmed_at TIMESTAMPTZ;
```

### 27.4 NOT NULL for Always-Populated Fields

> "This field must always be populated, so it should be NOT NULL."
> — lead review, limes

**Rule**: If a field should never be null in normal operation, declare it `NOT NULL` in the schema. Let the database enforce invariants.

### 27.5 Use ORM for Simple Single-Record Updates, Raw SQL for Complex Queries

> "For OLTP-type queries like this, I find it easier to work with the ORM directly, i.e. update the record object on the Go side and have the ORM write it back."
> — lead review, limes

```go
// REJECTED: raw SQL for a simple single-record update
tx.Exec("UPDATE project_commitments SET transfer_status = '', transfer_token = '' WHERE id = $1", id)

// CORRECT: use the ORM for simple updates
dbCommitment.TransferStatus = ""
dbCommitment.TransferToken = ""
err := p.DB.Update(&dbCommitment)

// ALSO CORRECT: raw SQL when the query is complex (JOINs, subqueries, CTEs)
var complexQuery = sqlext.SimplifyWhitespace(`
    SELECT DISTINCT ON (asset_id) o.* FROM finished_operations o
        JOIN assets a ON a.id = o.asset_id
        WHERE a.resource_id = $1
    ORDER BY o.asset_id, o.finished_at DESC
`)
```

### 27.6 Use ExpandEnumPlaceholders for Status Values in SQL

> "Please rewrite this condition into the ExpandEnumPlaceholders style."
> — lead review, limes

```go
// REJECTED: hardcoded status strings in SQL
var query = sqlext.SimplifyWhitespace(`
    SELECT * FROM commitments WHERE state = 'active' OR state = 'pending'
`)

// CORRECT: use ExpandEnumPlaceholders
var query = sqlext.SimplifyWhitespace(`
    SELECT * FROM commitments WHERE state IN ($ACTIVE_STATES)
`)
// Then expand at runtime with db.ExpandEnumPlaceholders
```

### 27.7 Return tx.Commit() Directly

> (Multiple PRs)

```go
// REJECTED: redundant nil-check
err = tx.Commit()
if err != nil {
    return err
}
return nil

// CORRECT: direct return
return tx.Commit()
```

### 27.8 Omit Unnecessary JOINs

> "`LEFT OUTER JOIN` can be replaced by `JOIN` since the condition makes it impossible to have partially-null result rows."
> — lead review, limes

**Rule**: Use the simplest JOIN type that satisfies the query. If an INNER JOIN is sufficient, do not use LEFT OUTER JOIN.

### 27.9 Omit Unnecessary GROUP BY

> "`GROUP BY` is not necessary since no aggregate functions are used."
> — lead review, limes

**Rule**: Only use GROUP BY when aggregate functions (COUNT, SUM, MAX, etc.) are present.

### 27.10 No Explicit Transactions for Single Statements

> "Since only one update statement is issued, the explicit transaction is superfluous and can be omitted."
> — lead review, castellum

**Rule**: A single SQL statement is already atomic. Do not wrap it in a transaction.

### 27.11 Use DISTINCT ON for Latest-Per-Group Queries

> "I was going to suggest you look at ... a feature in Postgres: DISTINCT ON."
> — lead review, castellum

```go
// REJECTED: fetch all rows, filter in Go
rows, _ := db.Select(&ops, "SELECT * FROM finished_operations WHERE resource_id = $1", resID)
latestByAsset := make(map[int64]Operation)
for _, op := range rows {
    if existing, ok := latestByAsset[op.AssetID]; !ok || op.FinishedAt.After(existing.FinishedAt) {
        latestByAsset[op.AssetID] = op
    }
}

// CORRECT: let PostgreSQL do it
var latestOpsQuery = sqlext.SimplifyWhitespace(`
    SELECT DISTINCT ON (asset_id) o.* FROM finished_operations o
        JOIN assets a ON a.id = o.asset_id
        WHERE a.resource_id = $1
    ORDER BY o.asset_id, o.finished_at DESC
`)
```

### 27.12 Construct url.URL Literals, Don't Sprintf Then Re-Parse

> "Since we have all the bits and pieces of the URL already, it's weird to merge it all together into a string, then parse it again."
> — lead review, castellum

```go
// REJECTED: string concatenation then re-parse
dbURL := fmt.Sprintf("postgres://%s@%s:%s/%s?%s", user, host, port, name, opts)
dbi, err := db.Init(dbURL)

// CORRECT: construct the URL as a literal
dbURL := &url.URL{
    Scheme:   "postgres",
    User:     url.UserPassword(user, pass),
    Host:     host + ":" + port,
    Path:     name,
    RawQuery: opts,
}
dbi, err := db.Init(dbURL)
```

---

## 28. CLI Tool Patterns

These patterns come from limesctl and castellum reviews. The existing keppel-focused sections had ZERO CLI patterns. This section fills that gap.

### 28.1 CLI Arguments Should Be Optional When Backend Has Defaults

> "The ID should be optional for `cluster show` and `cluster set`. The default value `current` will be understood by Limes."
> — lead review, limesctl

```go
// REJECTED: forcing the user to provide what the backend already knows
clusterShowID = clusterShowCmd.Arg("cluster-id", "Cluster ID.").Required().String()

// CORRECT: let the backend interpret the default
clusterShowID = clusterShowCmd.Arg("cluster-id", "Cluster ID (default: current).").String()
```

### 28.2 Use Regex for Input Parsing, Not Index/Substring Slicing

> "This parsing logic based on indexes and substring operations looks brittle and is hardly readable. Consider using a regex to parse this."
> — lead review, limesctl

```go
// REJECTED: brittle index arithmetic
unitStr := tmpVal[len(tmpVal)-3:]
valStr := tmpVal[:len(tmpVal)-3]

// CORRECT: regex with clear capture groups
var valueUnitRx = regexp.MustCompile(`^(\d+(?:\.\d+)?)\s*([a-zA-Z]*)$`)
matches := valueUnitRx.FindStringSubmatch(input)
```

### 28.3 Compile Regex Once as Package-Level var

> "1. `MustCompile` in a loop is not nice. The regex should be compiled once (e.g. in a global variable assignment) and then reused."
> — lead review, limesctl

```go
// REJECTED: compiling regex inside a loop
for _, input := range inputs {
    rx := regexp.MustCompile(`...`)
    if rx.MatchString(input) { ... }
}

// CORRECT: compile once at package level
var inputRx = regexp.MustCompile(`...`)
```

Additionally, for user-supplied patterns:

> "Since this regex is supplied by the user, we should not panic on parse error. Please use `regexp.Compile()` instead."
> — lead review, castellum

```go
// REJECTED: user input can panic
rgx := regexp.MustCompile("^" + userPattern + "$")

// CORRECT: handle the error
rgx, err := regexp.Compile("^" + userPattern + "$")
if err != nil {
    return fmt.Errorf("invalid pattern %q: %w", userPattern, err)
}
```

### 28.4 Use time.RFC3339 for All Date/Time Output

> "Please use the `time.RFC3339` format, which is also the format recommended by ISO. One of its significant advantages is that its lexical sorting matches the proper date sorting."
> — lead review, limesctl

```go
// REJECTED: ambiguous custom format
time.Unix(ts, 0).Format("15:04:05 02-Jan-2006")

// CORRECT: ISO standard, lexically sortable
time.Unix(ts, 0).Format(time.RFC3339)
```

### 28.5 Set Env Var Overrides at Entry Point, Not Throughout

> "Consider [setting env vars at the beginning of func main(), right after app.Parse()]. This would also simplify the diff on this branch dramatically since you won't have to carry those auth options down into all the subcommands."
> — lead review, limesctl

```go
// REJECTED: passing auth options through every function call
func showCluster(authOpts AuthOptions) {
    provider, _ := auth.NewClient(authOpts)
    ...
}

// CORRECT: set env vars once at main(), use env-based auth everywhere
func main() {
    // after flag parsing:
    if opts.AuthURL != "" {
        os.Setenv("OS_AUTH_URL", opts.AuthURL)
    }
    // ... all subcommands just use clientconfig.AuthenticatedClient(nil)
}
```

### 28.6 Use Library Auth Discovery, Not Explicit Env Var Enumeration

> "I would rather use `clientconfig.AuthOptions()` if at all possible... This isn't as explicit, but also means we don't have to care about which env vars exist."
> — lead review, limesctl

```go
// REJECTED: manually listing every OS_* env var
type AuthConfig struct {
    AuthURL     string `env:"OS_AUTH_URL"`
    Username    string `env:"OS_USERNAME"`
    Password    string `env:"OS_PASSWORD"`
    // ... missing: token auth, application credentials, etc.
}

// CORRECT: let the library discover all supported auth methods
provider, err := clientconfig.AuthenticatedClient(nil)
```

### 28.7 Accept Plain Names, Add Internal Prefixes

> "I would rather only take the plain service type without `liquid-` on the CLI, and then add `liquid-` on our side."
> — lead review, limesctl

```go
// REJECTED: user must know internal naming convention
// Usage: limesctl liquid-usage liquid-cinder ...

// CORRECT: user provides the simple name, CLI adds prefix
// Usage: limesctl liquid-usage cinder ...
serviceType := "liquid-" + userInput
```

### 28.8 Hyper-Specific Error Messages for Admin Tools

> "It's admin-only, so these people will probably know. Or at the very least, a hyper-specific error message is good for grepping."
> — lead review, limesctl

```go
// REJECTED: vague error
return errors.New("invalid input")

// CORRECT: admin-friendly, grep-friendly
return fmt.Errorf("could not find project with project_id = %q, project_domain_id = %q: %v", projID, domainID, err)
```

### 28.9 Suggest Correct Command on Entity-Type Mismatch

> `return nil, errors.New("the given ID belongs to a domain, usage instructions: limesctl domain --help")`
> — lead review, limesctl

**Rule**: When a user passes an ID of the wrong entity type (e.g., domain ID to a project command), the error message should tell them which command to use instead.

### 28.10 Try GET-by-ID First, Then Filtered List

> "Listing all projects can be expensive in large domains. Please prefer the approach used by the python-openstackclient for resolving a user input that can be either a name or an ID."
> — lead review, limesctl

```go
// REJECTED: list everything and filter client-side
allProjects, _ := projects.ListAll(client)
for _, p := range allProjects {
    if p.Name == userInput || p.ID == userInput { return p }
}

// CORRECT: try ID first (cheap), fall back to filtered list
project, err := projects.Get(client, userInput)
if err == nil {
    return project, nil
}
// userInput is probably a name; list with server-side filter
pager := projects.List(client, projects.ListOpts{Name: userInput})
```

### 28.11 Flag Help Text Must State Behavioral Constraints Precisely

> "Confusing wording. What you mean to say is: 'When this option is given, the domain must be identified by ID. Specifying a domain name will not work.'"
> — lead review, limesctl

```go
// REJECTED: ambiguous
cmd.Flag("cluster-id", "Cluster ID. This flag requires a domain ID, domain name will not work.")

// CORRECT: precise about what changes and what breaks
cmd.Flag("cluster-id", "Cluster ID. When this option is given, the domain must be identified by ID. Specifying a domain name will not work.")
```

### 28.12 Normalize Volatile Fields Before Diffing

> "I recommend overwriting the Version number with 0 before diffing."
> — lead review, limesctl

```go
// REJECTED: diff includes irrelevant version/timestamp differences
diff := cmp.Diff(oldResponse, newResponse)

// CORRECT: normalize volatile fields first
oldResponse.Version = 0
newResponse.Version = 0
diff := cmp.Diff(oldResponse, newResponse)
```

### 28.13 Validate Completeness of User-Provided Values

> "I would like to see a validation here that quotas were provided for all resources."
> — lead review, limesctl

**Rule**: When a CLI set/update command modifies resources, validate that the user provided values for ALL required fields. Do not silently leave some at zero.

---

## 29. Modern Go Standard Library Usage

The project actively corrects colleagues to use modern Go features. These patterns appear in 3+ repos and represent the current preferred Go style (Go 1.22+).

### 29.1 slices.Sorted(maps.Keys()) for Sorted Map Keys

> "This can be expressed much more compactly with recently added std functions."
> — lead review, limes

```go
// REJECTED: manual key extraction and sorting
serviceTypes := make([]db.ServiceType, 0, len(c.LiquidConnections))
for serviceType := range c.LiquidConnections {
    serviceTypes = append(serviceTypes, serviceType)
}
sort.Slice(serviceTypes, func(i, j int) bool { return serviceTypes[i] < serviceTypes[j] })

// CORRECT: one line
serviceTypes := slices.Sorted(maps.Keys(c.LiquidConnections))
```

### 29.2 slices.Collect(maps.Keys()) for Key Extraction

> (lead review, limes)

```go
// REJECTED: manual loop
var projectIDs []db.ProjectID
for id := range task.Notifications {
    projectIDs = append(projectIDs, id)
}

// CORRECT
projectIDs := slices.Collect(maps.Keys(task.Notifications))
```

### 29.3 slices.Clone() for Slice Copying

> "This used to be the idiomatic way to clone a slice, but a standard library function has been added recently."
> — lead review, limes

```go
// REJECTED: old idiom
resourceAZs = append([]AZ{}, allAZs...)

// CORRECT
resourceAZs = slices.Clone(allAZs)
```

### 29.4 slices.Clone Before Appending to Foreign Slices

> "The problem is that you're touching a slice that someone else provided to you, which modifies the memory contents of the underlying array."
> — lead review, limes

```go
// REJECTED: mutates the caller's underlying array
allAZsWithUnknown := append(allAZs, liquid.AvailabilityZoneUnknown)

// CORRECT: clone first to avoid aliasing
allAZsWithUnknown := append(slices.Clone(allAZs), liquid.AvailabilityZoneUnknown)
```

### 29.5 slices.ContainsFunc for Membership Checks

> (lead review, castellum — suggestion block)

```go
// REJECTED: manual for-loop-with-break
isAllowed := false
for _, access := range projectsWithAccess {
    if scopeUUID == access.ProjectID {
        isAllowed = true
        break
    }
}

// CORRECT
isAllowed := slices.ContainsFunc(projectsWithAccess, func(a ShareTypeAccess) bool {
    return a.ProjectID == scopeUUID
})
```

### 29.6 strings.CutPrefix() for Check-and-Remove

> "Look at `strings.CutPrefix()` for how to check a prefix and remove it at the same time."
> — lead review, limes

```go
// REJECTED: repeating the prefix string
if strings.HasPrefix(string(assetType), "nfs-shares-type:") {
    nfsType := strings.TrimPrefix(string(assetType), "nfs-shares-type:")

// CORRECT: single operation
if nfsType, ok := strings.CutPrefix(string(assetType), "nfs-shares-type:"); ok {
```

### 29.7 Built-in min()/max() Functions (Go 1.21+)

> (lead review, limes)

```go
// REJECTED: manual comparison
if amount > maxAmount {
    amount = maxAmount
}

// CORRECT
amount = min(amount, maxAmount)
```

### 29.8 for range N for Fixed Repetition (Go 1.22+)

> "The following probably better communicates intent: `for range 2 {`"
> — lead review, limes

```go
// REJECTED: classic C-style loop for fixed count
for i := 0; i < 2; i++ {
    doSomething()
}

// CORRECT: Go 1.22+ integer range
for range 2 {
    doSomething()
}
```

### 29.9 Go 1.22+ Loop Variable Semantics (No More Capture Workaround)

> "The thing where you need to pass a loop iteration variable as an explicit argument to a closure to avoid it from being overwritten in subsequent iterations is not necessary anymore since Go 1.22."
> — lead review, go-bits

```go
// REJECTED: pre-1.22 workaround (LLMs generate this from old training data!)
for i := 0; i < 10; i++ {
    i := i  // capture loop variable
    go func() { use(i) }()
}

// CORRECT: Go 1.22+ — loop variables are per-iteration
for i := range 10 {
    go func() { use(i) }()
}
```

### 29.10 t.Context() in Tests (Go 1.24+)

From portunus and go-bits: the project uses `t.Context()` instead of `context.Background()` or `context.TODO()` in tests:

```go
// REJECTED: manual context in tests
ctx := context.Background()

// CORRECT: Go 1.24+ test context tied to test lifecycle
ctx := t.Context()
```

---

## 30. go-bits Testing API Evolution (Current Preferred)

The go-bits testing API is actively being migrated. This section documents what NEW code must use versus what exists in the codebase. Source: go-bits PRs.

### 30.1 httptest.Handler Replaces assert.HTTPRequest

The old `assert.HTTPRequest` struct pattern is soft-deprecated. New tests MUST use the fluent `httptest.Handler.RespondTo()` API.

```go
// OLD (soft-deprecated) — do NOT use for new code:
assert.HTTPRequest{
    Method:       "GET",
    Path:         "/healthcheck",
    ExpectStatus: http.StatusOK,
    ExpectBody:   assert.StringData("ok\n"),
}.Check(t, h)

// NEW (current preferred):
h := httptest.NewHandler(myHandler)

// Simple status check:
h.RespondTo(ctx, "GET /healthcheck").
    ExpectStatus(t, http.StatusOK)

// JSON response check:
h.RespondTo(ctx, "GET /v1/accounts").
    ExpectJSON(t, http.StatusOK, jsonmatch.Object{
        "accounts": jsonmatch.Array{},
    })

// Text response check:
h.RespondTo(ctx, "GET /healthcheck").
    ExpectText(t, http.StatusOK, "ok\n")

// Status-only (e.g., 403 Forbidden):
h.RespondTo(ctx, "GET /admin/endpoint").
    ExpectStatus(t, http.StatusForbidden)
```

Rationale for `ExpectStatus()`:
> "It looks weird to write sometimes the chained method call style, but then other times the sequence-of-statements style."

The soft-deprecation comment format is deliberately NOT the Go convention `// Deprecated:`:

```go
// Warning: This function is considered deprecated.
// Please use httptest.Handler instead, which provides more flexible assertions.
```

This avoids triggering golangci-lint warnings, allowing gradual migration.

### 30.2 assert.Equal (Generic) Replaces assert.DeepEqual for Comparable Types

> "For comparable values like this one (i.e. values that Go allows to compare with `==`), `assert.Equal` is to be preferred because it does not require reflection."
> — lead review, go-bits

```go
// OLD: uses reflection, requires description string
assert.DeepEqual(t, "Clock.Now as Unix timestamp", c.Now().Unix(), int64(0))

// NEW: generic, no reflection, no description string
assert.Equal(t, c.Now().Unix(), int64(0))
```

`assert.DeepEqual` still exists and is correct for non-comparable types (slices, maps, structs with slice fields).

### 30.3 assert.ErrEqual — Flexible Error Matching

```go
// Match against nil (no error expected):
assert.ErrEqual(t, err, nil)

// Match against exact error string:
assert.ErrEqual(t, err, "wrong foo supplied")

// Match against error value (uses errors.Is for wrapped errors):
assert.ErrEqual(t, err, errFoo)

// Match against regex:
assert.ErrEqual(t, err, regexp.MustCompile(`wrong fo* supplied`))

// Match against wrapped error (errBar wraps errFoo):
errBar := fmt.Errorf("could not connect to bar: %w", errFoo)
assert.ErrEqual(t, errBar, errFoo)  // passes via errors.Is()
```

### 30.4 must.SucceedT and must.ReturnT — Test-Safe Fatal Helpers

```go
// OLD: verbose manual error checking
err := store.UpdateMetrics()
if err != nil {
    t.Fatalf("unexpected error: %v", err)
}

// NEW: one-liner
must.SucceedT(t, store.UpdateMetrics())

// For functions returning (value, error):
// OLD:
files, err := store.ListFiles()
if err != nil {
    t.Fatalf("unexpected error: %v", err)
}

// NEW: curried form (the only signature that works — see NOTE in go-bits)
files := must.ReturnT(store.ListFiles())(t)
```

The curried `ReturnT` signature is forced by Go generics limitations:
> "We cannot do `must.ReturnT(t, os.ReadFile(...))` because filling multiple arguments using a call expression with multiple return values is only allowed when there are no other arguments."
> — go-bits documentation

### 30.5 assert.TestingT Interface

```go
type TestingT interface {
    Helper()
    Errorf(msg string, args ...any)
}
```

Minimal interface — only `Helper()` and `Errorf()`. This enables mock-based testing of assertion functions themselves using `testutil.MockT`.

---

## 31. go-bits API Design Principles

How the project evolves APIs in its shared library. Source: go-bits PRs.

### 31.1 Soft-Deprecation via Docstring, Not `// Deprecated:` Annotation

> "I want to move all of that to jsonmatch eventually, but since that will take a while, assert.HTTPRequest is only to be considered 'soft-deprecated' via the docstring, instead of having an actual deprecation warning that would cause a warning in golangci-lint."
> — lead review, go-bits

```go
// REJECTED: triggers tooling warnings across all consumers
// Deprecated: Use httptest.Handler instead.
func (r HTTPRequest) Check(t *testing.T, h http.Handler) { ... }

// CORRECT: soft-deprecation that allows gradual migration
// Warning: This function is considered deprecated.
// Please use httptest.Handler instead, which provides more flexible assertions.
func (r HTTPRequest) Check(t *testing.T, h http.Handler) { ... }
```

### 31.2 Add Alongside, Never Replace

The established migration pattern for shared libraries:

1. Add the new API alongside the old one
2. Migrate all internal usage in the SAME PR
3. Leave the old API with soft-deprecation notice
4. Separate PRs for downstream consumer migration

```go
// OLD API still works:
assert.DeepEqual(t, label, actual, expected)

// NEW API added alongside:
assert.Equal(t, actual, expected)  // for comparable types

// The old delegates to the new or vice versa — never duplicate logic:
func (errs ErrorSet) Join(sep string) string {
    return errs.JoinedError(sep).Error()  // delegates to new JoinedError
}
```

### 31.3 Extract-to-Library Pattern (Three Steps)

The project follows a consistent extraction pattern:

```
Step 1: Code exists inline in a specific application
        (e.g., limitRequestsMiddleware in liquidapi)

Step 2: Extract to shared library with improved docs
        (e.g., httpext.LimitConcurrentRequestsMiddleware)

Step 3: Further extract the core primitive
        (e.g., syncext.Semaphore from the middleware)
```

The original code is then refactored to use the library version:

```go
// After extraction, the middleware uses the new primitive:
semaphore := syncext.NewSemaphore(maxRequests)
return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    semaphore.Run(func() { inner.ServeHTTP(w, r) })
})
```

### 31.4 Curried Signatures When Go Generics Force It

> "This is the only function signature that works."
> — go-bits documentation (on `must.ReturnT`)

```go
// CANNOT do this (Go limitation: multi-return can't mix with other args):
func ReturnT[V any](t *testing.T, val V, err error) V

// CANNOT do this (Go limitation: no new type params on methods):
func (m *Must) ReturnT[V any](val V, err error) V

// ONLY option that works — curried form:
func ReturnT[V any](val V, err error) func(*testing.T) V

// Usage:
files := must.ReturnT(store.ListFiles())(t)
```

### 31.5 errext.JoinedError — Unwrappable Error Joining

> "For users that want to be able to Unwrap() the joined error for inspection with errors.Is() and errors.As()."
> — go-bits documentation

```go
// OLD: Join() returns string — cannot unwrap
msg := errs.Join(", ")

// NEW: JoinedError() returns error — supports errors.Is() / errors.As()
err := errs.JoinedError(", ")

// The old delegates to the new (backward compatible):
func (errs ErrorSet) Join(sep string) string {
    return errs.JoinedError(sep).Error()
}
```

### 31.6 Verbose Parameter Names for IDE Discoverability

From `assert.ErrEqual`:

```go
// The parameter name IS the documentation for IDE autocomplete:
func ErrEqual(t TestingT, actual error, expectedErrorOrMessageOrRegexp any) bool
```

> "The verbose name of the last argument is intended to help users who see only the function signature in their IDE autocomplete."
> — go-bits documentation

### 31.7 syncext.Semaphore — Callback Pattern Over Acquire/Release

```go
// REJECTED: manual acquire/release (error-prone, can forget to release)
sem.Acquire()
defer sem.Release()
doWork()

// CORRECT: callback ensures release
sem.Run(func() {
    doWork()
})

// With error propagation:
err := sem.RunFallible(func() error {
    return doFallibleWork()
})
```

---

## 32. Option[T] Complete Usage Guide

Consolidates ALL Option patterns from all 5 research sources. This is the definitive guide to `github.com/majewsky/gg/option` in sapcc code.

### 32.1 Always Dot-Import the option Package

> "As per convention, please make `option` a dot-import."
> — lead review, limes

```go
import (
    . "github.com/majewsky/gg/option"
)

// Enables clean type usage:
var x Option[time.Time]
y := Some(time.Now())
z := None[int64]()
```

This is the ONLY package that gets dot-imported in the project.

### 32.2 Option[T] Replaces *T for Optionality

> "This has a pointer type only to express optionality, so type Option should be used instead."
> — lead review, limes

```go
// REJECTED
type Commitment struct {
    ConfirmBy *time.Time `json:"confirm_by,omitempty"`
}

// CORRECT
type Commitment struct {
    ConfirmBy Option[time.Time] `json:"confirm_by,omitzero"`
}
```

Note the JSON tag: `omitzero` for Option[T], `omitempty` for regular types.

### 32.3 When NOT to Use Option[T]

**Do not use Option for non-optional fields:**

> "This does not need to be an Option. LIQUID does not allow None here."
> — lead review, limes

```go
// REJECTED: field is always populated
Forbidden Option[bool] `db:"forbidden"`

// CORRECT
Forbidden bool `db:"forbidden"`
```

**Do not use Option in runtime struct fields when the None case is resolved at init time:**

> "Having `Option` here means that each method of FileBackingStore needs to handle the None case, even though you are removing the None case during Init."
> — lead review, go-bits

```go
// REJECTED: Option in runtime struct
type fileBackingStore struct {
    MaxFileSize  Option[int64]
}

// CORRECT: Option only at parse time, concrete value in struct
var cfg struct {
    MaxFileSize Option[int64] `json:"max_file_size"`
}
json.Unmarshal(params, &cfg)
store := fileBackingStore{
    MaxFileSize: cfg.MaxFileSize.UnwrapOr(10 << 20),
}
```

**Do not wrap already-nilable types unnecessarily:**

> "This does not need to be an Option."
> — lead review, limes

### 32.4 Unpack() — Combine Check and Extraction

> "The Unpack here can be combined with the IsNone check above."
> — lead review, limes

```go
// REJECTED: separate check and extract
if targetQuotaPtr.IsNone() {
    return errors.New("no quota set")
}
targetQuota := targetQuotaPtr.UnwrapOrPanic()

// CORRECT: one Unpack call
targetQuota, ok := targetQuotaPtr.Unpack()
if !ok {
    return errors.New("no quota set")
}
```

### 32.5 IsNoneOr() — Readable Conditional Checks

> "I would find the following more readable."
> — lead review, limes

```go
// REJECTED: verbose unpack-then-check
minConfirmDate, hasMinConfirmDate := b.MinConfirmDate.Unpack()
canConfirm := !hasMinConfirmDate || minConfirmDate.Before(t)

// CORRECT: expressive one-liner
canConfirm := b.MinConfirmDate.IsNoneOr(func(min time.Time) bool {
    return min.Before(t)
})
```

### 32.6 Map() for Transforming Option Values

> "I recently learned that you can refer to a method that way."
> — lead review, limes

```go
// Transform Option value with a method reference:
commitment.ConfirmBy = options.Map(commitment.ConfirmBy, time.Time.Local)
```

### 32.7 FromPointer() for Pointer-to-Option Conversion

> "As an FYI: this API exists: `options.FromPointer(quota).UnwrapOr(0)`"
> — lead review, limes

```go
// Converting from legacy *T to Option[T]:
optQuota := options.FromPointer(quota).UnwrapOr(0)
```

### 32.8 Option Types Can Be Compared by Value

> "Option types can be compared to each other by value (unlike pointer types)."
> — lead review, limes

```go
// CORRECT: direct comparison with ==
if currentQuotaPtr != Some(targetQuota) {
    // quota changed
}
```

### 32.9 TryInstantiate Returns Option[T]

From go-bits (`pluggable.Registry`):

> "If we had had Option[] back when this was built, I would have Instantiate() return it directly. As it stands, we will stick with the existing interface for backwards-compatibility, but I need an Option[] return now because generic code cannot do the `if result == nil` comparison."

```go
// NEW: Option-returning variant for generic code
result := registry.TryInstantiate(pluginTypeID)
if plugin, ok := result.Unpack(); ok {
    // use plugin
}
```

### 32.10 Option[*big.Int] for Nullable Big Numbers

> "If these fields may be nil, please declare them as `Option[*big.Int]` instead."
> — lead review, limes

**Rule**: Even pointer types get wrapped in Option when you need to distinguish "not provided" from "nil value."

---

## 33. Personal Go Architecture Patterns (from Portunus)

Patterns from `github.com/majewsky/portunus` — a personal project with zero corporate constraints. These reveal the IDEAL architecture versus the corporate compromises in keppel/limes.

### 33.1 State Reducer Pattern (Nexus)

The most distinctive pattern in portunus. ALL database mutations go through a reducer:

```go
type UpdateAction func(*Database) errext.ErrorSet

errs := nexus.Update(func(db *core.Database) errext.ErrorSet {
    db.Users[0].GivenName = "Changed"
    return nil
}, nil)
```

The Nexus `Update()` method:
1. Clones the current database
2. Applies the action to the clone
3. Validates the result
4. Enforces the seed (if any)
5. Only commits if valid AND actually changed
6. Notifies all listeners

This is a **functional reactive** pattern that is NOT used in keppel (where SQL transactions serve a similar role). It reveals an architectural preference for immutable state + reducers when free from database constraints.

### 33.2 Listener-Based Pub-Sub for Cross-Component Communication

```go
nexus.AddListener(ctx, func(db Database) {
    writeChan <- db
})
```

Both the LDAP adapter and the store adapter register as listeners on the Nexus. The comment addresses concurrency explicitly:

> "Note that the callback is invoked from whatever goroutine is causing the DB to be updated. If a specific goroutine shall process the event, the callback should send into a channel from which that goroutine is receiving."

Keppel uses direct function calls instead. This observer pattern is the preferred approach for decoupled components.

### 33.3 Handler Step Chains (Pipeline Pattern for HTTP)

Unlike keppel's middleware-wrapping approach, portunus uses sequential step execution:

```go
func postUserEditHandler(n core.Nexus) http.Handler {
    return Do(
        LoadSession,
        VerifyLogin(n),
        VerifyPermissions(adminPerms),
        loadTargetUser(n),
        useUserForm(n),
        ReadFormStateFromRequest,
        validateUserForm,
        TryUpdateNexus(n, executeEditUser),
        ShowFormIfErrors("Edit user"),
        RedirectWithFlashTo("/users", "Updated"),
    )
}
```

Steps share state through an `Interaction` struct. Any step can abort the chain by setting `i.writer = nil`.

### 33.4 Deep Clone Semantics on All Domain Types

```go
func (u User) Cloned() User {
    if u.POSIX != nil {
        val := *u.POSIX
        u.POSIX = &val
    }
    if u.SSHPublicKeys != nil {
        u.SSHPublicKeys = append([]string(nil), u.SSHPublicKeys...)
    }
    return u
}
```

Manual deep cloning for every domain type. Slices: `append([]T(nil), original...)`. Pointers: dereference and take address of the copy. This is required by the state reducer pattern — mutations must not affect the original.

### 33.5 Generic ObjectList with Clone-on-Read

```go
type Object[Self any] interface {
    Key() string
    Cloned() Self
}

type ObjectList[T Object[T]] []T

func (list ObjectList[T]) Cloned() ObjectList[T] { ... }
func (list ObjectList[T]) Find(predicate func(T) bool) (T, bool) { ... }
func (list *ObjectList[T]) Update(newObject T) error { ... }
func (list *ObjectList[T]) Delete(key string) error { ... }
```

A generic, type-safe collection with clone semantics. The `Object[Self]` constraint ensures that both `User` and `Group` implement `Key()` and `Cloned()`.

### 33.6 Validation Errors with ObjectRef/FieldRef Chain

```go
type FieldRef struct {
    Object ObjectRef
    Name   string // e.g. "surname"
}

type ValidationError struct {
    FieldRef   FieldRef
    FieldError error
}

// WrapFirst applies validators and returns the FIRST error:
errs.Add(ref.Field("login_name").WrapFirst(
    MustNotBeEmpty(u.LoginName),
    MustNotHaveSurroundingSpaces(u.LoginName),
    MustBeUserLoginName(u.LoginName, cfg),
    MustNotIncludeDNSyntaxElements(u.LoginName),
))
```

Each validation rule is a standalone function returning nil or error. `WrapFirst` short-circuits on the first failure. This composable validation pattern is richer than keppel's flat errors.

### 33.7 Atomic File Writes (Temp + Rename)

```go
func (a *Adapter) writeStoreFile(buf []byte) error {
    tmpPath := filepath.Join(
        filepath.Dir(a.storePath),
        fmt.Sprintf(".%s.%d", filepath.Base(a.storePath), os.Getpid()),
    )
    err := os.WriteFile(tmpPath, buf, 0666)
    if err != nil { return err }
    return os.Rename(tmpPath, a.storePath)
}
```

Write to temp file, then atomic rename. Prevents partial writes from corrupting the database file. Keppel uses PostgreSQL transactions instead.

### 33.8 Hand-Written String Parsers with Fuzz Testing

Hand-rolled parsers are used to avoid pulling regex into the root-privileged orchestrator binary:

```go
func IsLDAPSuffix(input string) bool {
    for field := range strings.SplitSeq(input, ",") {
        key, value, found := strings.Cut(field, "=")
        if !found || key != "dc" { return false }
        if !checkEachByte([]byte(value), checkByteInDomainComponent) { return false }
    }
    return true
}
```

Verified against the regex using fuzz testing:

```go
func FuzzIsLDAPSuffix(f *testing.F) {
    ldapSuffixRx := regexp.MustCompile(LDAPSuffixRegex)
    f.Add("dc=example,dc=com")
    f.Fuzz(func(t *testing.T, input string) {
        actual := IsLDAPSuffix(input)
        expected := ldapSuffixRx.MatchString(input)
        if actual != expected { t.Errorf(...) }
    })
}
```

### 33.9 Privilege Separation (Orchestrator/Server Split)

Environment variables are explicitly cleared after reading to prevent leakage:

```go
must.Succeed(os.Unsetenv(key)) // avoid unintentional leakage of env vars to child processes
```

The orchestrator binary keeps imports minimal:

> "Please keep the imports of this package as small as reasonably possible. All the code that is located or imported here ends up in the orchestrator binary that runs as root. Let's all do our part to keep the TCB small."

### 33.10 What This Reveals About the Ideal Architecture

When free from constraints, the project gravitates toward:

- **Central immutable state store** (Nexus) with reducers, not direct mutations
- **Observer notifications** for side effects (listeners), not direct function calls
- **Deep cloning** for isolation, not database-read-per-operation
- **Sequential pipeline processing** (Handler Steps), not middleware wrapping
- **Hand-built test doubles**, not generated mocks
- **Self-contained binaries** with embedded assets

This is the architecture of someone who thinks in terms of **data flow and state transitions**, not objects and methods.

---

## 34. Architectural Opinions (February 2026)

The most recent expressed opinions, from active PR reviews on limes and keppel.

### 34.1 Code as Documentation — Types on pkg.go.dev, Not Markdown

> "I don't want to have the v2 API specs as Markdown documents, because those tend to drift from reality faster than code comments. The v2 API should be documented in the same style as https://pkg.go.dev/github.com/sapcc/go-api-declarations/liquid."
> — lead review, limes

```go
// REJECTED: separate Markdown spec file
// docs/api/v2-spec.md with endpoint tables and JSON examples

// CORRECT: Go type declarations with doc comments
// The API spec IS the Go package rendered on pkg.go.dev
package v2api

// DomainReport contains all quota and usage data for a domain.
// The top-level object returned by GET /resources/v2/domains/:id.
type DomainReport struct {
    Areas map[string]AreaReport `json:"areas"`
}
```

### 34.2 Package Isolation for Clean Deletion

> "Please place this in a new package, e.g. `internal/api/v2`, that does not depend on the old stuff. I would like to be able to just delete the old package once we're done with the migration."
> — lead review, limes

```
// REJECTED: v2 types alongside or importing v1
internal/api/types.go        // shared by both versions
internal/api/v1_handlers.go
internal/api/v2_handlers.go

// CORRECT: zero-dependency v2 package
internal/api/v1/             // old, will be deleted
internal/api/v2/             // new, zero imports from v1
internal/api/v2/types/       // portable, can move to go-api-declarations later
```

The architecture is two-tier:
1. **Type declarations package** (portable, eventually promoted to `go-api-declarations`)
2. **Implementation package** (HTTP handlers, logic)

### 34.3 Consumer-Oriented API Design ("Think About the jq User")

> "Imagine writing out `.service_areas["compute"].services["nova"].categories["hv_version_2"].resources["ram_hv_version_2"]` in your jq script, and then a month later the liquid-nova maintainer decides to rename the category..."
> — lead review, limes

**Rule**: Design API response structures for the real consumers — people using `curl | jq`. Deep nesting with unstable intermediate keys creates fragile access paths. Prefer flatter structures when intermediate keys might change.

### 34.4 No JSON Fixture Files — Composable Test Data Instead

> "One of my big gripes with the v1 API test suite is having a billion `fixtures/*.json` files."
> — lead review, limes

```go
// REJECTED: file per scenario
// fixtures/info-cloud-admin.json
// fixtures/info-domain-admin.json
// fixtures/info-project-viewer.json

// CORRECT: composable baseline + modifier functions
var fullInfo = assert.JSONObject{
    "areas": assert.JSONObject{
        "compute": assert.JSONObject{...},
    },
}

func withoutCommitmentInfo(info assert.JSONObject) assert.JSONObject {
    // remove commitment-related fields
    ...
}

// cloud-admin sees everything:
resp.ExpectJSON(t, http.StatusOK, fullInfo)

// domain-admin without commitments:
resp.ExpectJSON(t, http.StatusOK, withoutCommitmentInfo(fullInfo))
```

### 34.5 Eliminate Legacy Global State in New Code

> "`AllServiceInfos` is a leftover from when we held all ServiceInfo in memory at all times. I would like to eventually get rid of it."
> — lead review, limes

```go
// REJECTED: using legacy global-state function in v2
allInfos := AllServiceInfos()

// CORRECT: targeted query for exactly what you need
var query = sqlext.SimplifyWhitespace(`
    SELECT s.type, r.name, r.category
    FROM services s JOIN resources r ON s.id = r.service_id
    WHERE s.type = $1
`)
```

### 34.6 Reflection for Exhaustive Coverage Over Switch Statements

> "We could use reflection on type MailTemplateConfiguration to find a field in where the `json:` tag matches the requested `templateType`."
> — lead review, limes

```go
// REJECTED: switch that drifts when new templates are added
switch templateType {
case "confirmed_commitments":
    template = cfg.Templates.ConfirmedCommitments
case "expiring_commitments":
    template = cfg.Templates.ExpiringCommitments
// ... easy to forget new ones
}

// CORRECT: reflection iterates all fields automatically
for fieldDecl, fieldValue := range reflect.ValueOf(mailConfig.Templates).Fields() {
    if fieldDecl.Tag.Get("json") == templateType {
        template, ok = fieldValue.Interface().(core.MailTemplate)
    }
}
```

### 34.7 Batch All Related Changes Atomically

> "If LIQUID (or the DB) rejects the commitment confirmation here, the consumption must be rolled back."
> — lead review, limes

> "The CommitmentChangeRequest that gets evaluated only has the commitment in project 1, not the commitments in projects 2 and 3. If this is so, then that ain't right."
> — lead review, limes

**Rule**: When operations have side effects, batch all related changes into a single request and commit atomically. Do not apply partial changes that become inconsistent if a later step fails.

### 34.8 Audit Events Must Cover All Affected Projects

> "If a CommitmentChangeRequest spans over multiple projects, we should post the audit event to all relevant projects."
> — lead review, limes

And on the deep copy requirement:

> "This need to operate on a sufficiently deep copy of `t.CommitmentChangeRequest`. After the first loop iteration, `redactLiquidProjectMetadataNames()` will have removed the names."
> — lead review, limes

**Rule**: When iterating over shared data while applying mutations (like redaction), each iteration needs its own deep copy. This is a classic Go gotcha with reference semantics.

### 34.9 Ignore AI Linter Noise

> "I'm going to ignore this based purely on the fact that Copilot complains about `os.Stdout.Write()`, but not about the much more numerous instances of `fmt.Println` that theoretically suffer the same problem."
> — lead review, keppel

**Rule**: If an AI code review tool flags one instance of a pattern but ignores hundreds of others, the suggestion lacks credibility. Evaluate for consistency and practical impact.

---

## 35. Cross-Repository Pattern Reinforcement Table

Patterns that appear in 3+ repos are the strongest-held preferences. Patterns in 2 repos are strong. Patterns in 1 repo may be context-specific. This tells the LLM which rules are MOST important to follow.

### Tier 1: Appears in 4+ Repos (keppel + limes + castellum/limesctl + portunus + go-bits)

These are non-negotiable. Violating any of these WILL get your PR rejected.

| Pattern | Repos | Section Reference |
|---------|-------|-------------------|
| `must.Return()` / `must.Succeed()` for startup errors | keppel, limes, portunus, castellum | 3, 15 |
| `logg` package for ALL logging (never `log.Printf`) | keppel, limes, portunus, castellum | 6 |
| `errext.ErrorSet` for multi-error collection | keppel, limes, portunus, castellum | 6, 33.6 |
| `osext.MustGetenv()` for required env vars | keppel, limes, portunus, castellum | 2 |
| `Option[T]` over `*T` for optionality | keppel, limes, castellum, go-bits | 7, 32 |
| Three-group import ordering | keppel, limes, portunus, castellum | 11 |
| `assert.DeepEqual` / `assert.Equal` from go-bits | keppel, limes, portunus, go-bits | 9, 30.2 |
| Vendored dependencies | keppel, limes, portunus, castellum | — |
| Environment variables for config (no config files) | keppel, limes, portunus, castellum | 2 |
| `internal/` for all application code | keppel, limes, portunus, castellum | 10 |
| Named return only when `defer` reads it | keppel, limes, castellum, portunus | 1 |
| `////////////////` section separators (80 slashes) | keppel, limes, portunus | 13 |
| No "failed to" in error messages — use "cannot" or "while" | keppel, limes, castellum, limesctl | 6, 22 |
| Trust stdlib error messages; don't re-wrap | keppel, limes, limesctl | 6, 28.3 |
| Code duplication is aggressively eliminated | keppel, limes, limesctl, castellum | 25.4, 28 |
| `append(nil, x)` is valid — never pre-initialize | keppel, limes, limesctl | 19, 29 |
| Contract cohesion — constants/sentinels/validation live with their interface | keppel, limes, castellum, limesctl | 36 |

### Tier 2: Appears in 2-3 Repos (Strong Signal)

| Pattern | Repos | Section Reference |
|---------|-------|-------------------|
| `slices.Sorted(maps.Keys())` for sorted map keys | limes, castellum | 29.1 |
| `strings.CutPrefix()` over `HasPrefix` + `TrimPrefix` | limes, castellum | 29.6 |
| `min()` / `max()` builtins (Go 1.21+) | limes, keppel | 29.7 |
| `for range N` for fixed repetition | limes, go-bits | 29.8 |
| Soft-deprecation via docstring, not `// Deprecated:` | go-bits, limes | 31.1 |
| Constructors infallible — no error return | keppel, portunus | 3 |
| Positional struct literals in constructors | keppel, portunus | 3, 22 |
| DB constraints over app-level checks | limes, castellum | 27.2 |
| `regexp.MustCompile` for static patterns, `Compile` for user input | limesctl, castellum | 28.3 |
| Custom error types over string matching | keppel, castellum | 6 |
| Mutable state in struct fields, not package vars | castellum, portunus | 28 |
| Clear error state on success | castellum, keppel | — |
| Deep copy awareness when iterating + mutating | limes, portunus | 34.8, 33.4 |

### Tier 3: Appears in 1 Repo (Context-Specific)

| Pattern | Repo | Section Reference |
|---------|------|-------------------|
| Handler Step chains (pipeline HTTP) | portunus | 33.3 |
| State Reducer / Nexus pattern | portunus | 33.1 |
| Fuzz testing for parser correctness | portunus | 33.8 |
| Atomic file writes (tmp + rename) | portunus | 33.7 |
| Hand-written string parsers (avoid regex in root binary) | portunus | 33.8 |
| `httptest.Handler.RespondTo()` fluent API | go-bits/limes | 30.1 |
| Composable JSON builders for test data | limes | 34.4 |
| Reflection for exhaustive field coverage | limes | 34.6 |
| `DISTINCT ON` in PostgreSQL | castellum | 27.11 |
| CLI arguments optional when backend has defaults | limesctl | 28.1 |
| Accept plain names, add prefixes internally | limesctl | 28.7 |

---

## 36. Contract Cohesion — Constants, Sentinels, and Validation Live with Their Interface

File organization follows a "contract cohesion" principle: the file that defines an interface or contract type also contains all artifacts that belong to that contract.

### What Lives Together

The file defining an interface or contract type MUST also contain:

1. **Constants** that are part of that contract (sentinel values, permission enums, error codes)
2. **Error sentinels** returned by that interface's methods
3. **Validation functions** for that interface's parameters

The file is named for the domain concept, not generically. `storage_driver.go` not `interface.go`. `auth_driver.go` not `types.go`.

### Evidence from Keppel (Reference Implementation)

| What | File | Pattern |
|------|------|---------|
| `StorageDriver` interface + `ErrAuthDriverMismatch` (returned by StorageDriver methods when auth driver is incompatible) + `ErrCannotGenerateURL` | `storage_driver.go` | Interface + its sentinels in same file |
| `AuthDriver` interface + `Permission` constants (`CanViewAccount`, etc.) | `auth_driver.go` | Interface + its enum constants in same file |
| `FederationDriver` interface + `ErrNoSuchPrimaryAccount` | `federation_driver.go` | Interface + its sentinel in same file |
| `RBACPolicy` type + `RBACPermission` constants + `ValidateAndNormalize()` | `rbac_policy.go` | Type + its constants + its validation in same file |
| `GCPolicy` type + `Validate()` | `gc_policy.go` | Type + its validation in same file |

### Anti-Pattern: Scattered Contract Artifacts

```go
// util.go -- REJECTED: this constant is part of the Storage contract
const AllTenants = "*"
var ErrEmptyTenantID = errors.New("tenant ID cannot be empty")
func validateTenantID(tenantID string) error { ... }

// interface.go -- the actual Storage interface is over here
type Storage interface { ... }
```

Convention: "Move `AllTenants`, `ErrEmptyTenantID`, and `validateTenantID` into the same file as `Storage`. They are part of the Storage contract."

### Correct: Contract Cohesion

```go
// storage.go (or storage_driver.go)
const AllTenants = "*"
var ErrEmptyTenantID = errors.New("tenant ID cannot be empty")

type Storage interface {
    ListTenants(ctx context.Context) ([]string, error)
    GetTenant(ctx context.Context, tenantID string) (Tenant, error)
}

func validateTenantID(tenantID string) error {
    if tenantID == "" {
        return ErrEmptyTenantID
    }
    return nil
}
```

### What IS Acceptable in util.go

Genuinely cross-cutting utilities that serve multiple unrelated types:

- Field mappings shared across backends
- Generic deduplication helpers
- String manipulation utilities
- HTTP/URL helpers

**The test**: if you can name which interface/type a function validates or which contract a constant belongs to, it doesn't belong in `util.go`.

### Review Severity

- **MEDIUM** when introducing new constants/sentinels in `util.go` or `constants.go` that belong to a specific interface. This is a "move it during this PR" finding, not a "rewrite the whole repo" finding.
- **LOW** for pre-existing violations in code not touched by the current PR.

### Cross-Repo Reinforcement

This pattern appears in 4+ sapcc repos (keppel, limes, castellum, limesctl), making it **NON-NEGOTIABLE** per the reinforcement table (§35 Tier 1).

---

## Master Summary: All New Rules (Sections 26-36)

| # | Section | Rule | One-Line Description |
|---|---------|------|----------------------|
| N1 | 26.1 | SQL vars end with "Query" | Distinguish data variables from function calls |
| N2 | 26.2 | Functions describe actual side effects | `buildSplit` not `split` if no DB mutation |
| N3 | 26.3 | `Is...` for queries, active verbs for mutations | `IsIgnoredFlavor` not `IgnoreFlavor` for a check |
| N4 | 26.4 | `Sorted` = new collection, `Sort` = in-place | Past tense for non-mutating operations |
| N5 | 26.5 | Group fields with shared prefix into substruct | `Flavor.Name` not `FlavorName` |
| N6 | 26.6 | Counter metrics are plural | `limes_mail_deliveries` not `delivery` |
| N7 | 26.7 | Metrics include app prefix | `limes_` prefix on all metrics |
| N8 | 26.8 | Method receiver = actor, not data | `MailClient.Send(info)` not `MailInfo.Send(client)` |
| N9 | 26.9 | Short-lived booleans use `ok`/`exists` | Not `fixedCapacityConfigurationExists` |
| N10 | 26.10 | Field names use domain terminology | `ShareTypeName` not `NFSType` |
| N11 | 26.11 | No contractions in error messages | "is not" not "isn't" |
| N12 | 26.12 | Error messages read as sentences | "could not parse" not "parse" |
| N13 | 26.13 | Preposition precision in errors | "Prometheus query" not "query for Prometheus" |
| N14 | 27.1 | Existing migrations are immutable | Never edit deployed migration files |
| N15 | 27.2 | DB constraints over app logic | UNIQUE constraint, not Go duplicate check |
| N16 | 27.3 | TIMESTAMPTZ, never TIMESTAMP | PostgreSQL timestamp must include timezone |
| N17 | 27.4 | NOT NULL for required fields | Let the DB enforce invariants |
| N18 | 27.5 | ORM for simple CRUD, raw SQL for complex | `db.Update(&obj)` for single records |
| N19 | 27.6 | ExpandEnumPlaceholders for status values | No hardcoded status strings in SQL |
| N20 | 27.7 | Return tx.Commit() directly | No redundant nil check after Commit |
| N21 | 27.8 | Simplest JOIN type that works | INNER JOIN over LEFT OUTER when possible |
| N22 | 27.9 | GROUP BY only with aggregate functions | Remove GROUP BY if no COUNT/SUM/MAX |
| N23 | 27.10 | No transactions for single statements | A single statement is already atomic |
| N24 | 27.11 | DISTINCT ON for latest-per-group | PostgreSQL feature, not client-side filtering |
| N25 | 27.12 | Construct url.URL literals | Don't Sprintf then re-parse |
| N26 | 28.1 | CLI args optional when backend has defaults | Let backend infer "current" |
| N27 | 28.2 | Regex for input parsing, not index slicing | Readable and robust |
| N28 | 28.3 | Compile regex once at package level | `MustCompile` for static, `Compile` for user input |
| N29 | 28.4 | time.RFC3339 for all date output | ISO standard, lexically sortable |
| N30 | 28.5 | Env var overrides at main() entry point | Set once, not throughout the call chain |
| N31 | 28.6 | Use library auth discovery | Don't enumerate OS_* env vars manually |
| N32 | 28.7 | Accept plain names, add prefixes internally | User says "cinder", CLI adds "liquid-" |
| N33 | 28.8 | Hyper-specific error messages for admin tools | Grep-friendly error strings |
| N34 | 28.9 | Suggest correct command on type mismatch | "this is a domain, try limesctl domain" |
| N35 | 28.10 | GET-by-ID first, then filtered list | Never list-all-then-filter for name resolution |
| N36 | 28.11 | Flag help text states precise constraints | "domain name will not work" not "requires ID" |
| N37 | 28.12 | Normalize volatile fields before diffing | Zero out Version/timestamps before compare |
| N38 | 28.13 | Validate completeness of set/update inputs | All required fields must be provided |
| N39 | 29.1 | `slices.Sorted(maps.Keys())` | One-liner sorted key extraction |
| N40 | 29.2 | `slices.Collect(maps.Keys())` | One-liner key extraction |
| N41 | 29.3 | `slices.Clone()` for copying | Not `append([]T{}, src...)` |
| N42 | 29.4 | Clone before appending to foreign slices | Avoid aliasing shared memory |
| N43 | 29.5 | `slices.ContainsFunc` for membership | Not manual for-loop-with-break |
| N44 | 29.6 | `strings.CutPrefix()` for check-and-remove | Single operation, no repeated prefix |
| N45 | 29.7 | Built-in `min()`/`max()` | Not manual comparison |
| N46 | 29.8 | `for range N` for fixed repetition | Not C-style `for i := 0; i < N; i++` |
| N47 | 29.9 | Go 1.22+ loop variables are per-iteration | No more `i := i` capture workaround |
| N48 | 29.10 | `t.Context()` in tests | Not `context.Background()` |
| N49 | 30.1 | `httptest.Handler.RespondTo()` for new tests | Not `assert.HTTPRequest{}` |
| N50 | 30.2 | `assert.Equal` for comparable types | Not `assert.DeepEqual` (avoids reflection) |
| N51 | 30.3 | `assert.ErrEqual` for flexible error matching | Supports nil, string, error, regexp |
| N52 | 30.4 | `must.SucceedT` / `must.ReturnT` in tests | Not manual `if err != nil { t.Fatal }` |
| N53 | 31.1 | Soft-deprecation via docstring | Not `// Deprecated:` annotation |
| N54 | 31.2 | Add alongside, never replace | Old API stays until migration is complete |
| N55 | 31.3 | Extract-to-library in three steps | Inline -> shared package -> core primitive |
| N56 | 31.4 | Curried signatures when generics force it | `must.ReturnT(val, err)(t)` |
| N57 | 31.5 | `errext.JoinedError` for unwrappable joins | Supports `errors.Is()` / `errors.As()` |
| N58 | 31.6 | Verbose parameter names for IDE discoverability | `expectedErrorOrMessageOrRegexp` |
| N59 | 31.7 | Callback pattern over acquire/release | `sem.Run(func() { ... })` |
| N60 | 32.1 | Dot-import the option package | Only package that gets dot-imported |
| N61 | 32.2 | `Option[T]` replaces `*T` for optionality | With `omitzero` JSON tag |
| N62 | 32.3 | Don't use Option for non-optional fields | `bool` not `Option[bool]` when always populated |
| N63 | 32.4 | `Unpack()` combines check and extraction | Not separate `IsNone()` + `UnwrapOrPanic()` |
| N64 | 32.5 | `IsNoneOr()` for conditional checks | One-liner optional value predicates |
| N65 | 32.6 | `options.Map()` for transforming Option values | Method references work: `time.Time.Local` |
| N66 | 32.7 | `options.FromPointer()` for legacy conversion | Bridges *T to Option[T] |
| N67 | 32.8 | Option types can be compared with `==` | Direct value comparison |
| N68 | 32.9 | `TryInstantiate` returns `Option[T]` | For generic code that can't do `== nil` |
| N69 | 33.1 | State Reducer / Nexus pattern | Functional reactive: reducers + immutable state |
| N70 | 33.2 | Listener-based pub-sub | Observer pattern for decoupled components |
| N71 | 33.3 | Handler Step chains | Pipeline pattern for HTTP request processing |
| N72 | 33.4 | Deep clone semantics on domain types | Manual clone for slices and pointers |
| N73 | 33.5 | Generic ObjectList with type constraints | `Object[Self]` interface + `ObjectList[T]` |
| N74 | 33.6 | Validation errors with ObjectRef/FieldRef | Composable validators with `WrapFirst` |
| N75 | 33.7 | Atomic file writes (tmp + rename) | Prevents partial write corruption |
| N76 | 33.8 | Fuzz testing for hand-optimized parsers | Verify against regex reference implementation |
| N77 | 34.1 | Code as documentation — types on pkg.go.dev | Not Markdown API specs |
| N78 | 34.2 | Package isolation for clean deletion | v2 package has zero v1 imports |
| N79 | 34.3 | Consumer-oriented API design | Think about the jq user's access paths |
| N80 | 34.4 | Composable JSON builders for test data | Not static fixture files |
| N81 | 34.5 | Eliminate legacy global state in new code | Targeted queries, not `AllXInfo()` |
| N82 | 34.6 | Reflection for exhaustive field coverage | Not switch statements that drift |
| N83 | 34.7 | Batch all related changes atomically | No partial commits that can become inconsistent |
| N84 | 34.8 | Deep copy when iterating + mutating shared data | Each iteration needs its own copy |
| N85 | 34.9 | Ignore inconsistent AI linter suggestions | Evaluate for consistency and practical impact |
| N86 | 36.1 | Contract cohesion — artifacts live with their interface | Constants, sentinels, validation in same file as interface |
| N87 | 36.2 | Files named for domain concept, not generically | `storage_driver.go` not `interface.go` or `types.go` |
| N88 | 36.3 | util.go only for genuinely cross-cutting utilities | If you can name the owning interface, it doesn't belong in util |
| N89 | 36.4 | Scattered contract artifacts are a review finding | MEDIUM for new violations, LOW for pre-existing |

---

*Sections 26-36 synthesized from 4,837 lines of research across limes (614 comments), castellum/limesctl (111 comments), go-bits (52 PRs), portunus (full codebase analysis), and 23 recent architectural opinions. Total file now covers patterns from 6 repositories.*
