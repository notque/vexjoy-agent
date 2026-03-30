# API Design Conventions -- Detailed Reference

Comprehensive HTTP/API patterns from `sapcc/keppel`. Full handler patterns, routing, middleware, OpenStack integration, rate limiting, and all response conventions.

---

## 1. Router Setup

### Framework

- **Router**: `gorilla/mux v1.8.1` via `httpapi.Compose()` from `sapcc/go-bits/httpapi`
- **Server**: Standard `net/http` with `httpext.ListenAndServeContext()` for graceful shutdown on SIGINT

### Composition Pattern

All API sub-modules implement the `httpapi.API` interface:

```go
func (a *API) AddTo(r *mux.Router)
```

APIs are composed into a single handler:

```go
handler := httpapi.Compose(
    keppelv1.NewAPI(...),
    auth.NewAPI(...),
    registryv2.NewAPI(...),
    peerv1.NewAPI(...),
    &headerReflector{...},
    httpapi.HealthCheckAPI{...},
    httpapi.WithGlobalMiddleware(reportClientIP),
    httpapi.WithGlobalMiddleware(corsMiddleware.Handler),
    pprofapi.API{...},
    &guiRedirecter{...},  // fallback match for undefined paths
)
```

`httpapi.Compose()`:
1. Creates a `mux.Router`
2. Calls `AddTo(r)` on each API
3. Wraps with middleware: request logging (nginx-style combined format), Prometheus metrics collection, out-of-band endpoint identification

### Route Groups by API Prefix

| Prefix | Package | Purpose |
|--------|---------|---------|
| `/keppel/v1/` | `internal/api/keppel` | Keppel-native management API |
| `/keppel/v1/auth` | `internal/api/auth` | Token issuance (Docker auth spec) |
| `/v2/` | `internal/api/registry` | OCI Distribution Spec (Registry V2) |
| `/peer/v1/` | `internal/api/peer` | Internal peer-to-peer replication API |
| `/liquid/v1/` | `internal/api/keppel` | LIQUID resource quota reporting |
| `/healthcheck` | `httpapi.HealthCheckAPI` | Health probe (DB ping) |
| `/metrics` | `promhttp.Handler()` | Prometheus metrics (on `http.ServeMux`, not mux.Router) |
| `/debug/pprof` | `pprofapi.API` | Go pprof (localhost only) |
| `/debug/reflect-headers` | `headerReflector` | Debug endpoint (dev/QA only) |

---

## 2. Routing Patterns

### URL Registration

All routes use explicit HTTP methods and exact paths:

```go
r.Methods("GET").Path("/keppel/v1/accounts").HandlerFunc(a.handleGetAccounts)
r.Methods("PUT").Path("/keppel/v1/accounts/{account:[a-z0-9][a-z0-9-]{0,47}}").HandlerFunc(a.handlePutAccount)
```

### URL Path Variable Conventions

```
{account:[a-z0-9][a-z0-9-]{0,47}}  -- Keppel account names (restricted char set, max 48 chars)
{repo_name:.+}                      -- Repository names (can contain slashes)
{repository:.+}                     -- Combined account/repo in Registry V2 (split later)
{digest}                            -- Content digest (sha256:...)
{reference}                         -- Tag name or digest
{auth_tenant_id}                    -- OpenStack project ID
{uuid}                              -- Upload session UUID
{hostname}                          -- Peer hostname for delegated pull
{tag_name}                          -- Tag name
```

### Resource Naming in URLs

- **Keppel API**: Account and repo are separate path segments: `/keppel/v1/accounts/{account}/repositories/{repo_name:.+}`
- **Registry V2 API**: Combined into single `{repository:.+}`, split later via `scope.ParseRepositoryScope()`
- **Domain-remapped APIs**: Account name is in the hostname, not the URL path

### Path Parameter Extraction

Always via `mux.Vars(r)`:
```go
accountName := models.AccountName(mux.Vars(r)["account"])
repoName := mux.Vars(r)["repo_name"]
digest := mux.Vars(r)["digest"]
```

### Query Parameter Extraction

Via `r.URL.Query()`:
```go
query := r.URL.Query()
marker := query.Get("marker")
limit := query.Get("limit")
format := r.URL.Query().Get("format")
```

---

## 3. Handler Patterns

### Handler Function Signature

All handlers use standard `http.HandlerFunc`:

```go
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request)
```

No custom return values. Errors are written directly to `w`.

### Endpoint Identification (MANDATORY)

Every handler MUST call `httpapi.IdentifyEndpoint()` as its first action:

```go
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request) {
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts")
    // ...
}
```

The format uses `:param` syntax (not `{param}`):
```
"/keppel/v1/accounts/:account"
"/v2/:account/:repo/blobs/:digest"
"/peer/v1/sync-replica/:account/:repo"
```

### Standard Handler Flow (Keppel API)

Every handler follows this exact sequence:

1. `httpapi.IdentifyEndpoint(r, "...")` -- identify for metrics
2. `a.authenticateRequest(w, r, scopes)` -- authenticate and authorize
3. `a.findAccountFromRequest(w, r, authz)` -- load account (if applicable)
4. `a.findRepositoryFromRequest(w, r, accountName)` -- load repo (if applicable)
5. Business logic
6. `respondwith.JSON(w, statusCode, data)` -- write response

Each step returns nil/false on failure (having already written the error to `w`):

```go
authz := a.authenticateRequest(w, r, scopes)
if authz == nil {
    return
}
account := a.findAccountFromRequest(w, r, authz)
if account == nil {
    return
}
```

### Standard Handler Flow (Registry V2 API)

Registry V2 handlers use a combined auth+lookup method:

```go
account, repo, authz, challenge := a.checkAccountAccess(w, r, strategy, anycastHandler)
if account == nil {
    return
}
```

`checkAccountAccess`:
1. Sets `Docker-Distribution-Api-Version: registry/2.0` header
2. Validates repository name format
3. Determines required actions from HTTP method (GET/HEAD -> pull, DELETE -> delete, others -> pull+push)
4. Authorizes via `auth.IncomingRequest{}.Authorize()`
5. Looks up account and repository
6. Handles anycast forwarding if account not found locally

### Request Body Parsing

JSON body decoding uses `DisallowUnknownFields()`:

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

Usage:
```go
var req struct {
    Account keppel.Account `json:"account"`
}
ok := decodeJSONRequestBody(w, r.Body, &req)
if !ok {
    return
}
```

---

## 4. Authentication and Authorization

### Authentication Flow

```go
authz, challenge, rerr := auth.IncomingRequest{
    HTTPRequest:          r,
    Scopes:               ss,
    CorrectlyReturn403:   true,
    PartialAccessAllowed: false,
}.Authorize(r.Context(), a.cfg, a.authDriver, a.db)
```

### Auth Methods (checked in order)

1. **Basic auth** (`Authorization: Basic ...`) -- only on token issuance endpoint
2. **Bearer token** (`Authorization: Bearer ...`) -- JWT tokens from the auth endpoint
3. **Driver auth** (`X-Auth-Token` for Keystone, or empty header) -- falls back to anonymous

### Scope-Based Authorization

```go
auth.Scope{
    ResourceType: "keppel_account",   // or "repository", "keppel_auth_tenant", "registry", "keppel_api"
    ResourceName: "myaccount",
    Actions:      []string{"view"},
}
```

### Permission Constants

| Permission | String | Used for |
|------------|--------|----------|
| `CanViewAccount` | `"view"` | Viewing account metadata |
| `CanPullFromAccount` | `"pull"` | Pulling images |
| `CanPushToAccount` | `"push"` | Pushing images |
| `CanDeleteFromAccount` | `"delete"` | Deleting manifests/tags |
| `CanChangeAccount` | `"change"` | Creating/updating accounts |
| `CanViewQuotas` | `"viewquota"` | Viewing quotas |
| `CanChangeQuotas` | `"changequota"` | Changing quotas |

### Registry V2 Method-to-Scope Mapping

```go
switch r.Method {
case http.MethodDelete:
    scope.Actions = []string{"delete"}
case http.MethodGet, http.MethodHead:
    scope.Actions = []string{"pull"}
default:
    scope.Actions = []string{"pull", "push"}
}
```

### Authorization Error Convention

- **Keppel API** (`CorrectlyReturn403: true`): Returns 403 for insufficient permissions
- **Registry V2 API** (`CorrectlyReturn403: false`): Returns 401 for Docker compatibility
- `ErrDenied` maps to 401 (not 403): _"403 would make more sense, but we need to show 401 for bug-for-bug compatibility with docker-registry"_

### Auth-Before-Data-Access Rationale

Authentication ALWAYS happens before any data access. This prevents information leakage about resource existence. An unauthenticated user should get 401, not 404, even if the resource doesn't exist.

### Auth Challenge Header

```
Www-Authenticate: Bearer realm="https://host/keppel/v1/auth",service="hostname",scope="repository:account/repo:pull"
```

### Keppel API authenticateRequest Pattern

```go
func (a *API) authenticateRequest(w http.ResponseWriter, r *http.Request, ss auth.ScopeSet) *auth.Authorization {
    authz, _, rerr := auth.IncomingRequest{
        HTTPRequest:          r,
        Scopes:               ss,
        CorrectlyReturn403:   true,
        PartialAccessAllowed: r.URL.Path == "/keppel/v1/accounts",
    }.Authorize(r.Context(), a.cfg, a.authDriver, a.db)
    if rerr != nil {
        rerr.WriteAsTextTo(w)
        return nil
    }
    return authz
}
```

`PartialAccessAllowed` is true only for the accounts list endpoint (filtering to visible accounts).

---

## 5. Middleware Stack

### Middleware Order (outermost to innermost)

1. **`httpapi.middleware`** (from `Compose()`) -- request logging, Prometheus metrics
2. **`reportClientIP`** -- adds `X-Keppel-Your-Ip` header
3. **`cors.Handler`** -- CORS middleware from `rs/cors`
4. **`mux.Router`** -- gorilla/mux routing

### CORS Configuration

```go
corsMiddleware := cors.New(cors.Options{
    AllowedOrigins: []string{"*"},
    AllowedMethods: []string{"HEAD", "GET", "POST", "PUT", "DELETE"},
    AllowedHeaders: []string{"Content-Type", "User-Agent", "Authorization", "X-Auth-Token", "X-Keppel-Sublease-Token"},
})
```

### Request Logging

nginx combined format:
```
<ip> - - "GET /path HTTP/1.1" 200 1234 "-" "user-agent" 0.123s
```

5xx response bodies are captured and logged as errors. Logging can be skipped per-endpoint via `httpapi.SkipRequestLog(r)` (health checks).

### Prometheus Metrics

Built-in from `httpapi.middleware`:
- `http_request_duration_seconds` (histogram) -- labeled by method, endpoint, status, app
- `http_first_byte_duration_seconds` (histogram)
- `http_request_body_size_bytes` (histogram)
- `http_response_body_size_bytes` (histogram)

Application-specific:
- `keppel_pulled_blob_bytes` / `keppel_pushed_blob_bytes` (counter)
- `keppel_pulled_blobs` / `keppel_pushed_blobs` (counter)
- `keppel_pulled_manifests` / `keppel_pushed_manifests` (counter)
- `keppel_aborted_uploads` (counter)

All labeled by: `account`, `auth_tenant_id`, `method` (values: `"registry-api"`, `"replication"`, `"registry-api+anycast"`).

### Custom Response Headers

| Header | When Set |
|--------|----------|
| `X-Keppel-Your-Ip` | Every response (middleware) |
| `Docker-Distribution-Api-Version: registry/2.0` | All Registry V2 responses (even errors) |
| `Docker-Content-Digest` | Blob/manifest responses |
| `X-Keppel-Vulnerability-Status` | Manifest GET |
| `X-Keppel-Min-Layer-Created-At` / `X-Keppel-Max-Layer-Created-At` | Manifest GET |
| `X-RateLimit-Action`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` | Rate-limited endpoints |
| `Retry-After` | 429 responses |
| `Blob-Upload-Session-Id` | Upload session UUID |
| `OCI-Filters-Applied` | Set to `"artifactType"` when referrers are filtered |
| `Oci-Subject` | Subject digest when pushing manifest with subject reference |

---

## 6. Response Patterns

### Success Responses

**JSON responses** use `respondwith.JSON()`:
```go
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": accountsRendered})
```

**Envelope convention** for Keppel API:
- Single resource: `{"account": {...}}`
- List of resources: `{"accounts": [...]}`
- Always serialize empty lists as `[]`, never `null`:

```go
if len(accountsFiltered) == 0 {
    accountsFiltered = []models.Account{}
}
```

**No-content responses**:
```go
w.WriteHeader(http.StatusNoContent)  // DELETE operations
```

**Binary responses** (blobs, manifests):
```go
w.Header().Set("Content-Length", strconv.FormatUint(lengthBytes, 10))
w.Header().Set("Content-Type", blob.SafeMediaType())
w.Header().Set("Docker-Content-Digest", blob.Digest.String())
w.WriteHeader(http.StatusOK)
```

### HTTP Status Code Usage

| Status | When Used |
|--------|-----------|
| 200 OK | GET success, PUT success (account create/update), token issuance |
| 201 Created | PUT manifest, POST blob upload (complete), blob cross-mount |
| 202 Accepted | DELETE blob (Registry V2), DELETE manifest (Registry V2), PATCH blob upload |
| 204 No Content | DELETE account, DELETE repo, DELETE tag, DELETE manifest (Keppel API) |
| 302 Found | GUI redirect |
| 307 Temporary Redirect | Blob storage URL redirect, manifest alternate redirect |
| 400 Bad Request | Malformed request body, invalid query params |
| 401 Unauthorized | Missing/invalid credentials, insufficient permissions (Registry V2) |
| 403 Forbidden | Insufficient permissions (Keppel API only) |
| 404 Not Found | Account/repo/manifest/blob not found |
| 405 Method Not Allowed | No vulnerability report, push to replica |
| 406 Not Acceptable | Manifest media type not in Accept header |
| 409 Conflict | Account being deleted, cannot delete repo with active uploads |
| 416 Range Not Satisfiable | Content-Range errors during blob upload |
| 422 Unprocessable Entity | Invalid repo name, conflicting account name, impossible quota |
| 429 Too Many Requests | Rate limit exceeded, concurrent replication |
| 500 Internal Server Error | Unexpected errors (obfuscated) |
| 503 Service Unavailable | Registry unavailable |

### Error Response Formats

**1. Keppel API -- Plain text errors:**
```go
http.Error(w, "account not found", http.StatusNotFound)
```

**2. Keppel API -- RegistryV2Error as text:**
```go
rerr.WriteAsTextTo(w)
```

**3. Registry V2 API -- JSON error envelope:**
```go
rerr.WriteAsRegistryV2ResponseTo(w, r)
```
```json
{
  "errors": [
    {
      "code": "NAME_UNKNOWN",
      "message": "repository name not known to registry",
      "detail": "optional detail"
    }
  ]
}
```

**4. Auth API -- JSON error:**
```go
rerr.WriteAsAuthResponseTo(w)
```
```json
{
  "details": "error message"
}
```

### Error Obfuscation

For 500-level errors, `respondwith.ObfuscatedErrorText()` replaces the actual message with a UUID:
```go
if respondwith.ObfuscatedErrorText(w, err) {
    return
}
```
Response: `Internal Server Error (ID = <uuid>)`

The real error is logged server-side with the same UUID. 4xx errors pass through without obfuscation.

### Pagination

**Keppel API** -- marker-based:
```go
type paginatedQuery struct {
    SQL         string      // with $LIMIT and $CONDITION placeholders
    MarkerField string      // e.g., "r.name"
    Options     url.Values  // from r.URL.Query()
    BindValues  []any
}
```
Query params: `?marker=<last-value>&limit=<n>` (default 1000, max 1000).
Response includes `"truncated": true` when results are truncated.

**Registry V2 API** -- OCI spec pagination:
```go
w.Header().Set("Link", fmt.Sprintf(`<%s>; rel="next"`, linkURL.String()))
```
Query params: `?n=<limit>&last=<marker>` (default 100).

---

## 7. Rate Limiting

### Architecture

- **Optional**: Only active when Redis is enabled (`KEPPEL_REDIS_ENABLE=true`)
- **Driver-based**: `RateLimitDriver` interface with pluggable implementations
- **Token bucket**: Uses `go-redis/redis_rate` over Redis

### Rate-Limited Actions

```go
BlobPullAction            = "pullblob"
BlobPushAction            = "pushblob"
ManifestPullAction        = "pullmanifest"
ManifestPushAction        = "pushmanifest"
AnycastBlobBytePullAction = "pullblobbytesanycast"  // amount = blob size in bytes
TrivyReportRetrieveAction = "retrievetrivyreport"
```

### Exemptions

Cluster-internal traffic is exempt:
```go
if userType == keppel.PeerUser || userType == keppel.TrivyUser {
    return nil
}
```

### Usage Pattern

```go
err := api.CheckRateLimit(r, w, a.rle, *account, authz, keppel.BlobPullAction, 1)
if respondWithError(w, r, err) {
    return
}
```

On limit exceeded: `ErrTooManyRequests` with `Retry-After` and `X-RateLimit-*` headers.

---

## 8. OpenStack Integration

### Authentication (Keystone)

**Driver**: `keystoneDriver` implementing `keppel.AuthDriver`

- Authenticates service user via `gophercloudext.NewProviderClient()` (reads `OS_*` env vars)
- Creates Identity V3 client for token validation
- Loads oslo.policy file for RBAC rule evaluation
- Caches validated tokens in Redis (or in-memory fallback)

**User authentication methods**:
1. **Keystone token**: `X-Auth-Token` header, validated via `gopherpolicy.TokenValidator.CheckToken()`
2. **Basic auth username formats**:
   - `user@domain/project@domain` -- standard Keystone credentials
   - `user@domain/project` -- domain defaults to user's domain
   - `applicationcredential-<id>` -- application credential
3. **Peer credentials**: `replication@<hostname>` -- for inter-Keppel replication

**Authorization**: Oslo policy rules evaluate against token context:
```go
ruleForPerm = map[keppel.Permission]string{
    CanViewAccount:       "account:show",
    CanPullFromAccount:   "account:pull",
    CanPushToAccount:     "account:push",
    CanDeleteFromAccount: "account:delete",
    CanChangeAccount:     "account:edit",
    CanViewQuotas:        "quota:show",
    CanChangeQuotas:      "quota:edit",
}
```

### Storage (Swift)

**Driver**: `swiftDriver` implementing `keppel.StorageDriver`

- Container naming: `keppel-<accountname>`
- Uses `schwift` library (wrapper around gophercloud Object Storage)
- Blobs stored as Swift Large Objects (Static Large Object manifests)
- Manifests stored as regular objects
- TempURL for blob redirect (20-minute expiry)
- Container metadata: `Write-Restricted: true`

**Object naming** (via `stringy` package):
- Blobs: `_blobs/<storageID>`
- Chunks: `_chunks/<storageID>/<chunkNumber>`
- Manifests: `_manifests/<repoName>/<digest>`
- Trivy reports: `_trivy/<repoName>/<digest>/<format>`

### Federation

- `FederationDriver` manages cross-region peering
- Anycast requests reverse-proxied to the peer that owns the account
- Loop protection via `X-Keppel-Forwarded-By` header/query parameter

---

## 9. API Struct Pattern

```go
type API struct {
    cfg        keppel.Configuration
    authDriver keppel.AuthDriver
    fd         keppel.FederationDriver
    sd         keppel.StorageDriver
    db         *keppel.DB
    auditor    audittools.Auditor
    rle        *keppel.RateLimitEngine
    timeNow    func() time.Time  // injectable for testing
}

func NewAPI(cfg keppel.Configuration, ...) *API {
    return &API{cfg, ...}
}

func (a *API) AddTo(r *mux.Router) {
    r.Methods("GET").Path("/...").HandlerFunc(a.handleXxx)
}
```

Key design decisions:
- `timeNow func() time.Time` is injected for deterministic testing
- `generateStorageID func() string` is also injectable in the Registry V2 API
- Rate limit engine `rle` may be nil (rate limiting is optional)
- A `processor()` factory method creates a fresh `Processor` for each request

---

## 10. Audit Trail

CADF events for state-changing operations:

```go
a.auditor.Record(audittools.Event{
    Time:       time.Now(),
    Request:    r,
    User:       userInfo,
    ReasonCode: http.StatusOK,
    Action:     "create/security-scan-policy",
    Target:     AuditSecurityScanPolicy{Account: *account, Policy: policy},
})
```

Events include: the original HTTP request, user info, CADF action string, target resource rendered as `cadf.Resource` with `TypeURI`, `ID`, `ProjectID`.

---

## 11. API Versioning

- Keppel native API: `/keppel/v1/` -- version in URL path
- Registry API: `/v2/` -- follows OCI Distribution Spec
- Peer API: `/peer/v1/` -- internal, version in path
- LIQUID API: `/liquid/v1/` -- follows LIQUID spec

No content negotiation or API version headers. Version is purely structural in the URL path.

---

## 12. Concrete Rules for New Endpoints

1. **Always call `httpapi.IdentifyEndpoint(r, ...)` first** in every handler
2. **Authenticate before any data access** to prevent information leakage about resource existence
3. **Use `respondwith.ObfuscatedErrorText(w, err)`** for internal errors (500s get UUID-masked)
4. **Use `http.Error(w, msg, status)`** for user-facing errors in the Keppel API
5. **Use `RegistryV2Error.WriteAsRegistryV2ResponseTo(w, r)`** for errors in the Registry V2 API
6. **Set `Docker-Distribution-Api-Version: registry/2.0`** on all Registry V2 responses including errors
7. **Decode JSON bodies with `DisallowUnknownFields()`** to reject unexpected fields
8. **Serialize empty slices as `[]` not `null`** in JSON responses
9. **Wrap single resources** in `{"resource_name": ...}` envelopes
10. **Use `http.StatusNoContent` (204)** for successful DELETE in Keppel API
11. **Use `http.StatusAccepted` (202)** for successful DELETE in Registry V2 API
12. **Check rate limits after auth but before business logic** via `api.CheckRateLimit()`
13. **Exempt peer and trivy users from rate limits**
14. **Use marker-based pagination** with default limit 1000 (Keppel API) or 100 (Registry V2)
15. **Log 5xx response bodies** via the middleware's error capture mechanism
16. **Use transactions with `defer sqlext.RollbackUnlessCommitted(tx)`** for multi-step DB operations
17. **Generate audit events** for all state-changing operations that have user identity

---

## 13. Key Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `gorilla/mux` | v1.8.1 | HTTP routing |
| `sapcc/go-bits/httpapi` | latest | HTTP composition, middleware, metrics |
| `sapcc/go-bits/respondwith` | latest | Response helpers (JSON, ErrorText, ObfuscatedErrorText) |
| `sapcc/go-bits/gopherpolicy` | latest | Oslo policy evaluation |
| `gophercloud/gophercloud/v2` | v2.10.0 | OpenStack SDK (Keystone, Swift) |
| `majewsky/schwift/v2` | v2.0.0 | Swift object storage client |
| `rs/cors` | v1.11.1 | CORS middleware |
| `redis/go-redis/v9` | v9.18.0 | Redis client |
| `go-redis/redis_rate/v10` | v10.0.1 | Token bucket rate limiting |
| `prometheus/client_golang` | v1.23.2 | Prometheus metrics |
| `spf13/cobra` | v1.10.2 | CLI framework |
| `databus23/goslo.policy` | latest | Oslo policy parser |
| `opencontainers/distribution-spec` | latest | OCI Distribution Spec types |
| `opencontainers/image-spec` | v1.1.1 | OCI Image Spec types |
| `golang-jwt/jwt/v5` | v5.3.1 | JWT token handling |
| `sapcc/go-api-declarations` | v1.20.0 | CADF, LIQUID type declarations |
| `go-gorp/gorp/v3` | v3.1.0 | ORM for PostgreSQL |
