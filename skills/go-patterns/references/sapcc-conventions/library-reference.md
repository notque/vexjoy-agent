# SAP CC Library Reference

Complete dependency map for SAP Converged Cloud Go projects. Extracted from `sapcc/keppel` go.mod, `.golangci.yaml`, and usage analysis.

---

## APPROVED Direct Dependencies (30 total)

### SAP CC Internal (3)

| Library | Version | Files | Purpose | Key Functions/Types |
|---------|---------|-------|---------|---------------------|
| `github.com/sapcc/go-bits` | latest | ~170+ | Core framework | See go-bits subpackage table below |
| `github.com/sapcc/go-api-declarations` | v1.20.0 | ~20 | Shared API types | `bininfo`, `cadf.Event`, `liquid` |
| `github.com/databus23/goslo.policy` | latest | 1 | OpenStack policy.json enforcement | Policy rule evaluation |

### Related Libraries (2)

| Library | Version | Files | Purpose | Key Pattern |
|---------|---------|-------|---------|-------------|
| `github.com/majewsky/gg/option` | latest | ~45 | `Option[T]` type | Dot-import: `. "github.com/majewsky/gg/option"` |
| `github.com/majewsky/schwift/v2` | v2.0.0 | ~5 | OpenStack Swift client | Storage driver only |

**gg/option usage patterns**:
```go
// Model fields
NextBlobSweepedAt Option[time.Time] `db:"next_blob_sweep_at"`
ExternalPeerURL   Option[string]    `json:"external_peer_url,omitzero"`

// Constructing
val := Some("hello")
empty := None[string]()

// Unpacking
if v, ok := opt.Unpack(); ok {
    use(v)
}
v := opt.UnwrapOr("default")
```

### Infrastructure / Cloud (3)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/gophercloud/gophercloud/v2` | v2.10.0 | ~15 | OpenStack SDK (Keystone, Swift) |
| `github.com/prometheus/client_golang` | v1.23.2 | ~20 | Prometheus metrics |
| `github.com/redis/go-redis/v9` | v9.18.0 | ~10 | Redis client |

### OCI / Container (4)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/containers/image/v5` | latest | ~10 | OCI/Docker manifest parsing |
| `github.com/opencontainers/go-digest` | latest | ~15 | Content-addressable digests |
| `github.com/opencontainers/image-spec` | v1.1.1 | ~10 | OCI image spec types |
| `github.com/opencontainers/distribution-spec` | latest | ~4 | Distribution error codes |

### Web / HTTP (3)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/gorilla/mux` | v1.8.1 | ~20 | HTTP routing |
| `github.com/rs/cors` | v1.11.1 | 1 | CORS middleware |
| `github.com/timewasted/go-accept-headers` | latest | 1 | Accept header parsing |

### Database (3)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/go-gorp/gorp/v3` | v3.1.0 | ~15 | SQL ORM (PostgreSQL) |
| `github.com/dlmiddlecote/sqlstats` | latest | 2 | SQL pool metrics for Prometheus |
| `github.com/go-redis/redis_rate/v10` | v10.0.1 | 4 | Redis-based rate limiting |

### Security / Crypto (1)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/golang-jwt/jwt/v5` | v5.3.1 | 2 | JWT token handling |

### CLI (1)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/spf13/cobra` | v1.10.2 | ~10 | CLI framework |

### Utility (3)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/gofrs/uuid/v5` | latest | 4 | UUID generation |
| `github.com/hashicorp/golang-lru/v2` | latest | 1 | LRU cache (validation cache) |
| `github.com/google/cel-go` | latest | 2 | CEL for validation rules |

### Testing (1)

| Library | Version | Files | Purpose |
|---------|---------|-------|---------|
| `github.com/alicebob/miniredis/v2` | latest | 1 | In-memory Redis for tests |

---

## go-bits Subpackage Usage

| Subpackage | Source Files | Purpose | Key Functions/Types |
|------------|-------------|---------|---------------------|
| `logg` | 48 | Logging | `Info()`, `Error()`, `Fatal()`, `Debug()`, `ShowDebug` |
| `assert` | 27 (tests) | Test assertions | `Equal[T]()`, `ErrEqual()`, `HTTPRequest{}`, `JSONObject` |
| `must` | 30 | Fatal error shorthand | `Succeed(err)`, `Return(val, err)`, `SucceedT(t, err)`, `ReturnT(val, err)(t)` |
| `sqlext` | 18 | SQL helpers | `ForeachRow()`, `WithPreparedStatement()`, `RollbackUnlessCommitted()`, `SimplifyWhitespace()` |
| `respondwith` | 17 | HTTP responses | `JSON()`, `ErrorText()`, `ObfuscatedErrorText()`, `CustomStatus()` |
| `httpapi` | 20 | HTTP API framework | `Compose()`, `IdentifyEndpoint()`, `SkipRequestLog()` |
| `errext` | 15 | Error handling | `ErrorSet`, `As[T]()`, `IsOfType[T]()`, `JoinedError` |
| `osext` | 11 | Environment access | `MustGetenv()`, `GetenvBool()`, `GetenvOrDefault()` |
| `jobloop` | 10 | Background workers | `CronJob`, `ProducerConsumerJob[T]`, `TxGuardedJob` |
| `httpext` | 9 | HTTP server | `ListenAndServeContext()`, `ContextWithSIGINT()` |
| `easypg` | 7 | PostgreSQL setup | `Configuration{}`, `Init()`, `WithTestDB()`, `ConnectForTest()`, `AssertDBContent()` |
| `audittools` | 13 | CADF audit events | `Auditor`, `Event`, `MockAuditor` |
| `pluggable` | 8 | Driver plugins | `Registry[T]`, `Plugin` interface |
| `regexpext` | 5 | Regex config types | `PlainRegexp`, `BoundedRegexp`, `ConfigSet[K,V]` |
| `gophercloudext` | 3 | OpenStack auth | `NewProviderClient()` |
| `gopherpolicy` | 1 | Keystone authZ | `TokenValidator`, `Validator` |
| `mock` | 1 | Test doubles | `Clock`, `NewClock()`, `StepBy()` |
| `syncext` | 1 | Concurrency | `Semaphore`, `Run()`, `RunFallible()` |

---

## FORBIDDEN Libraries

### By golangci-lint forbidigo

| Pattern | Reason | Use Instead |
|---------|--------|-------------|
| `ioutil.*` | Deprecated since Go 1.16 | `os` and `io` packages |
| `http.DefaultServeMux` | Global mutable state; packages silently add handlers | `http.NewServeMux()` |
| `http.Handle()` / `http.HandleFunc()` | Registers on DefaultServeMux | Use router directly |
| `gopkg.in/square/go-jose.v2` (entire pkg) | Archived, has CVEs | `gopkg.in/go-jose/go-jose.v2` |
| `github.com/coreos/go-oidc` (entire pkg) | Depends on archived go-jose | `github.com/coreos/go-oidc/v3` |
| `github.com/howeyc/gopass` (entire pkg) | Archived | `golang.org/x/term` |

### By Convention (not in linter, but will fail review)

| Library | Reason | Use Instead |
|---------|--------|-------------|
| `testify` (assert/require/mock) | SAP CC has own testing framework | `go-bits/assert` + `go-bits/must` |
| `zap` / `zerolog` / `slog` | SAP CC standardized on simple logging | `go-bits/logg` |
| `logrus` | Only present as transitive dep | `go-bits/logg` |
| `gin` / `echo` / `fiber` | SAP CC uses stdlib + gorilla/mux | `go-bits/httpapi` + `gorilla/mux` |
| `gorm` / `sqlx` / `ent` | Lightweight ORM preference | `go-gorp/gorp/v3` + `go-bits/sqlext` |
| `google/uuid` / `satori/uuid` | Different UUID library chosen | `gofrs/uuid/v5` |
| `viper` | No config files; env-var-only | `go-bits/osext` + `os.Getenv` |
| `chi` / `httprouter` / stdlib `mux` | gorilla/mux established | `gorilla/mux` |
| `gophercloud/utils` | Too many dependencies | `go-bits/gophercloudext` |
| `testcontainers` | Different test approach | `go-bits/easypg` + `miniredis` |
| `gomock` / `mockery` | Manual mocks preferred | Hand-written test doubles |

---

## PREFERRED Patterns (Use This, Not That)

| Category | Use This | Not This | Reason |
|----------|----------|----------|--------|
| Logging | `go-bits/logg` | `zap`, `zerolog`, `logrus`, `slog` | SAP CC standard |
| Test assertions | `go-bits/assert` | `testify/assert`, `testify/require` | Generics-based, SAP CC standard |
| HTTP responses | `go-bits/respondwith` | manual `json.Marshal` + `w.Write` | `respondwith.JSON()`, `ObfuscatedErrorText()` |
| HTTP lifecycle | `go-bits/httpext` | manual signal handling | `ListenAndServeContext()` with graceful shutdown |
| HTTP framework | `go-bits/httpapi` | gin, echo, fiber | Middleware with logging, metrics |
| Fatal errors | `go-bits/must` | manual `if err != nil { log.Fatal }` | `must.Succeed(err)`, `must.Return(val, err)` |
| Env vars | `go-bits/osext` | manual `os.Getenv` | `MustGetenv()`, `GetenvBool()` |
| SQL helpers | `go-bits/sqlext` | manual row iteration | `ForeachRow()`, `SimplifyWhitespace()` |
| DB setup | `go-bits/easypg` | manual migration setup | PostgreSQL init + test DB |
| Background jobs | `go-bits/jobloop` | manual goroutine loops | `CronJob`, `ProducerConsumerJob` |
| Error collections | `go-bits/errext` | manual error slices | `ErrorSet` with `Add()`, `Join()` |
| Plugin registry | `go-bits/pluggable` | manual factory maps | `Registry[T]` for driver patterns |
| OpenStack auth | `go-bits/gophercloudext` | `gophercloud/utils` | Lightweight `NewProviderClient()` |
| Optional values | `gg/option` (`Option[T]`) | `*T` pointers | `Some(v)` / `None[T]()` |
| UUID | `gofrs/uuid/v5` | `google/uuid` | SAP CC standard |
| HTTP router | `gorilla/mux` | `chi`, `httprouter` | Established choice |
| CLI | `spf13/cobra` | `urfave/cli` | `AddCommandTo()` pattern |
| ORM | `go-gorp/gorp/v3` | `gorm`, `sqlx`, `ent` | Lightweight mapping |

---

## Import Grouping Rules

Enforced by `goimports -local github.com/sapcc/keppel`:

```go
import (
    // Group 1: Standard library
    "context"
    "database/sql"
    "encoding/json"
    "fmt"
    "net/http"

    // Group 2: External (includes sapcc/go-bits, NOT local project)
    imageManifest "github.com/containers/image/v5/manifest"
    "github.com/go-gorp/gorp/v3"
    . "github.com/majewsky/gg/option"              // dot-import (ONLY gg/option)
    "github.com/opencontainers/go-digest"
    "github.com/sapcc/go-bits/errext"               // sapcc/* sorts with external
    "github.com/sapcc/go-bits/logg"

    // Group 3: Local project imports
    "github.com/sapcc/keppel/internal/keppel"
    "github.com/sapcc/keppel/internal/models"
)
```

Key rules:
- `sapcc/go-bits` and `sapcc/go-api-declarations` sort in Group 2 (external), NOT Group 3 (local)
- Only `gg/option` uses dot-import
- Side-effect imports use blank identifier: `_ "github.com/sapcc/keppel/internal/drivers/openstack"`
- Package aliases for clarity: `imageManifest`, `keppelv1`, `registryv2`

---

## Dot-Import Whitelist (staticcheck)

Only these packages may be dot-imported:
- `github.com/majewsky/gg/option`
- `github.com/onsi/ginkgo/v2`
- `github.com/onsi/gomega`

---

## errcheck Excluded Functions

These return values may be safely ignored:
- `encoding/json.Marshal` -- only fails on unmarshalable types (programmer error)
- `(net/http.ResponseWriter).Write` -- errors handled by HTTP server
- `(*github.com/spf13/cobra.Command).Help` -- writes to stdout

---

## Dependency License Allowlist

From `.license-scan-rules.json`:

```
Apache-2.0, BSD-2-Clause, BSD-2-Clause-FreeBSD, BSD-3-Clause,
EPL-2.0, ISC, MIT, MPL-2.0, Unlicense, Zlib
```

Any new dependency must have one of these licenses or be added to `.license-scan-overrides.jsonl`.
