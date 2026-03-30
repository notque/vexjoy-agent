# Error Handling and Logging Conventions -- Detailed Reference

Comprehensive error handling, error propagation, and logging patterns from `sapcc/keppel`. All 27 rules with full code examples.

---

## 1. Error Wrapping Patterns

### 1.1 Standard `%w` Wrapping with Context

Keppel wraps errors with `fmt.Errorf` using the `%w` verb to preserve the error chain. Error messages follow a consistent action-prefix pattern:

```go
// "while" prefix -- operations in progress
return fmt.Errorf("while finding source repository: %w", err)
return fmt.Errorf("while parsing response for GET %s: %w", reqURL, err)
return fmt.Errorf("while deleting manifest %q in repository %q: %w", digestStr, repo.Name, err)

// "cannot" prefix -- failed actions
return fmt.Errorf("cannot parse digest %q: %w", blobDigestStr, err)
return fmt.Errorf("cannot find account for repo %s: %w", repo.FullName(), err)
return fmt.Errorf("cannot load GC policies for account %s: %w", account.Name, err)

// "during" prefix -- HTTP operations
return nil, fmt.Errorf("during %s %s: %w", r.Method, uri, err)
return nil, fmt.Errorf("during POST %s: expected 200, got %d with response: %s", reqURL, resp.StatusCode, string(body))

// "could not" prefix -- task/background jobs
return fmt.Errorf("could not get ManagedAccountNames() from account management driver: %w", err)
return fmt.Errorf("could not ConfigureAccount(%q) in account management driver: %w", accountName, err)
```

### 1.2 Error Message Format Conventions

| Convention | Example |
|-----------|---------|
| **Lowercase first character** | `"cannot parse digest..."` not `"Cannot parse..."` |
| **Include the failed input** | Digests, account names, repo names, URLs are quoted |
| **Use `%q` for string values** | `"cannot parse digest %q"`, `"while deleting manifest %q in repository %q"` |
| **Use `%s` for pre-formatted values** | digest objects, URLs |
| **No trailing punctuation** | Error messages never end with a period |
| **Descriptive action prefix** | "while", "cannot", "during", "could not" |

### 1.3 Multi-Error Aggregation

When an operation fails AND cleanup also fails, both errors are combined:

```go
// Primary error preserved with %w (for errors.Is/errors.As)
// Secondary error appended as string with %s in parentheses
err = fmt.Errorf("%w (additional error encountered while recording validation error: %s)", err, updateErr.Error())
return fmt.Errorf("%w (additional error when writing next_enforcement_at: %s)", err, err2.Error())
```

**Rule**: The primary error is preserved with `%w` for unwrapping. The secondary error is appended as a string with `%s` in parentheses. This allows callers to `errors.Is`/`errors.As` on the primary error while still seeing the secondary error in the message.

### 1.4 Error Sentinel Values

Package-level sentinel errors use `errors.New`:

```go
// internal/keppel/federation_driver.go
var ErrNoSuchPrimaryAccount = errors.New("no such primary account")

// internal/keppel/storage_driver.go
var ErrAuthDriverMismatch = errors.New("given AuthDriver is not supported by this driver")
var ErrCannotGenerateURL = errors.New("URLForBlob() is not supported")

// internal/processor/accounts.go
var ErrAccountNameEmpty = errors.New("account name cannot be empty string")
```

These are checked with `errors.Is()` at call sites.

### 1.5 `sql.ErrNoRows` Handling

The most commonly checked sentinel error. The pattern is always:

```go
if errors.Is(err, sql.ErrNoRows) {
    // handle "not found" case specifically
    return keppel.ErrNameUnknown.With("repository not found")
}
// handle other errors normally
if err != nil {
    return err
}
```

This appears in the processor, API handlers, and task layers. `sql.ErrNoRows` is never treated as a real error -- it signals "not found" and is converted to an appropriate response.

---

## 2. `must.Return` / `must.Succeed` Usage

### 2.1 Package Definition

From `github.com/sapcc/go-bits/must`:

| Function | Behavior |
|----------|----------|
| `must.Succeed(err)` | If `err != nil`, calls `logg.Fatal(err.Error())` which exits the process |
| `must.Return[V](val, err)` | If `err != nil`, calls `logg.Fatal`; otherwise returns `val` |
| `must.SucceedT(t, err)` | Test variant -- calls `t.Fatal()` instead of `os.Exit` |
| `must.ReturnT[V](val, err)` | Test variant returning a curried `func(*testing.T) V` |

### 2.2 Non-Test Usage (Production Code)

`must.Succeed` and `must.Return` are used ONLY for:

**1. Program entry point** (startup failures are fatal):
```go
// main.go
must.Succeed(rootCmd.Execute())
```

**2. Static initialization** (values that must work or the program is misconfigured):
```go
// internal/keppel/validation.go
var celASTCache = must.Return(lru.New[string, *cel.Ast](128))
var celEnv = must.Return(cel.NewEnv(...))
```

**3. Audit event construction** (infallible by construction):
```go
// internal/api/keppel/audit.go
must.Return(cadf.NewJSONAttachment("payload", a.Policy))
```

**RULE: `must.Return`/`must.Succeed` is NEVER used in request handlers or business logic.** It is reserved for startup code and values that are guaranteed to succeed under correct configuration.

### 2.3 Test Usage

In tests, the `T` variants are used pervasively:

```go
must.SucceedT(t, s.DB.Insert(&models.Repository{...}))
digest := must.ReturnT(rc.UploadMonolithicBlob(ctx, img.Layers[0].Contents))(t)
count := must.ReturnT(db.SelectInt(`SELECT COUNT(*) FROM blobs`))(t)
```

---

## 3. `logg` Package -- Complete Level Guide

### 3.1 Log Level Summary

| Level | Function | Output Prefix | When Used |
|-------|----------|---------------|-----------|
| Fatal | `logg.Fatal()` | `FATAL:` | Unrecoverable errors during startup; calls `os.Exit(1)` |
| Error | `logg.Error()` | `ERROR:` | Non-fatal errors in production code |
| Info | `logg.Info()` | `INFO:` | Informational messages, operational events |
| Debug | `logg.Debug()` | `DEBUG:` | Diagnostic messages (gated by `logg.ShowDebug` / `KEPPEL_DEBUG`) |
| Other | `logg.Other()` | `{LEVEL}:` | Custom level, used by httpapi middleware as `REQUEST:` |

### 3.2 `logg.Fatal` -- Startup/CLI Only

Used ONLY in:
- **CLI commands**: `cmd/test/storage.go`, `cmd/healthmonitor/main.go`, `cmd/validate/main.go`
- **Configuration parsing**: `internal/keppel/config.go`
- **NEVER in HTTP handlers or background tasks**

```go
// cmd/healthmonitor/main.go
logg.Fatal("while setting up auth driver: %s", err.Error())

// internal/keppel/config.go
logg.Fatal("failed to read %s_ISSUER_KEY: %s", prefix, err.Error())
logg.Fatal("malformed %s: %s", key, err.Error())
```

### 3.3 `logg.Error` -- Errors That Cannot Bubble Up

Used when the error cannot be returned because:
- We are already handling a different error
- We are in a deferred cleanup function
- The operation is advisory (caching, timestamp updates)
- We are in a goroutine/callback with no error return path

```go
// Additional cleanup errors during error recovery
logg.Error("additional error encountered while aborting upload %s into account %s: %s",
    upload.StorageID, account.Name, err.Error())

// Non-critical timestamp update failures
logg.Error("could not update last_pulled_at timestamp on manifest %s@%s: %s",
    repo.FullName(), dbManifest.Digest, err.Error())

// Transaction rollback failures
logg.Error("implicit rollback failed: " + err.Error())

// Errors in fire-and-forget operations
logg.Error("cannot cache token payload in Redis: %s", err.Error())
```

### 3.4 `logg.Info` -- Operational Events

```go
logg.Info("rejecting overlong repository name: %q", scope.ResourceName)
logg.Info("could not read manifest %s@%s from DB (falling back to read from storage): %s", ...)
logg.Info("last_pulled_at timestamp of manifest %s@%s got updated by more than 7 days by user %q, user agent %q", ...)
logg.Info("aborting upload because of error during parseContentRange()")
```

### 3.5 `logg.Debug` -- Diagnostic Detail

Gated behind `KEPPEL_DEBUG` environment variable:

```go
logg.Debug("parsing configuration...")
logg.Debug("initializing %s %q", driverType, configJSON)
logg.Debug("ValidateAndStoreManifest: in repository %d, manifest %s already exists = %t", ...)
logg.Debug("token has object attributes = %v", a.t.Context.Request)
logg.Debug("policy rule %q evaluates to %t", rule, result)
```

### 3.6 Log Message Format

- `%s` for `.Error()`, `%q` for quoted strings, `%d` for integers, `%v` for complex objects
- No trailing newlines (the `logg` package adds them)
- Multiline content automatically flattened (`\n` replaced with `\\n`)
- Messages are lowercase unless referencing a specific proper noun or type

---

## 4. HTTP Error Response System

### 4.1 Three Distinct API Surfaces

| API | Error Format | Response Helper |
|-----|-------------|-----------------|
| **Registry V2 API** (`/v2/...`) | JSON `{"errors": [...]}` | `respondWithError()` in `internal/api/registry/api.go` |
| **Keppel V1 API** (`/keppel/v1/...`) | Obfuscated plain text | `respondwith.ObfuscatedErrorText()` from `go-bits` |
| **Auth API** (`/keppel/v1/auth`) | JSON `{"details": "..."}` | `WriteAsAuthResponseTo(w)` |

### 4.2 Registry V2 Error System (`RegistryV2Error`)

#### Error Codes and HTTP Status Mapping

```go
type RegistryV2ErrorCode string

const (
    ErrBlobUnknown         = "BLOB_UNKNOWN"          // 404
    ErrBlobUploadInvalid   = "BLOB_UPLOAD_INVALID"   // 400
    ErrBlobUploadUnknown   = "BLOB_UPLOAD_UNKNOWN"   // 404
    ErrDigestInvalid       = "DIGEST_INVALID"        // 400
    ErrManifestBlobUnknown = "MANIFEST_BLOB_UNKNOWN" // 404
    ErrManifestInvalid     = "MANIFEST_INVALID"      // 400
    ErrManifestUnknown     = "MANIFEST_UNKNOWN"      // 404
    ErrNameInvalid         = "NAME_INVALID"           // 400
    ErrNameUnknown         = "NAME_UNKNOWN"           // 404
    ErrSizeInvalid         = "SIZE_INVALID"           // 400
    ErrUnauthorized        = "UNAUTHORIZED"           // 401
    ErrDenied              = "DENIED"                 // 401 (not 403, for Docker compat)
    ErrUnsupported         = "UNSUPPORTED"            // 405
    ErrUnknown             = "UNKNOWN"                // 500
    ErrUnavailable         = "UNAVAILABLE"            // 503
    ErrTooManyRequests     = "TOOMANYREQUESTS"        // 429
)
```

#### Builder Pattern

```go
// Basic: code + message
keppel.ErrBlobUnknown.With("blob does not exist in this repository")
keppel.ErrDigestInvalid.With(err.Error())
keppel.ErrSizeInvalid.With("Content-Length was %d, but %d bytes were sent", sizeBytes, dw.bytesWritten)
keppel.ErrDenied.With("cannot push tag %q as it is forbidden by a tag_policy", m.Reference.Tag)

// With status override
keppel.ErrDenied.With(msg).WithStatus(http.StatusConflict)
keppel.ErrUnsupported.With("account is being deleted").WithStatus(http.StatusMethodNotAllowed)
keppel.ErrSizeInvalid.With(err.Error()).WithStatus(http.StatusRequestedRangeNotSatisfiable)

// With extra headers
err.WithHeader("Www-Authenticate", "Bearer "+fields.String())

// With detail field
keppel.AsRegistryV2Error(err).WithStatus(http.StatusUnprocessableEntity).WithDetail(celErr.Error())

// From existing error
keppel.ErrUnknown.WithError(err)

// Fallback conversion (any error -> RegistryV2Error)
keppel.AsRegistryV2Error(err)  // preserves type if already RegistryV2Error, wraps in ErrUnknown otherwise
```

#### JSON Response Format

```json
{
  "errors": [
    {
      "code": "MANIFEST_UNKNOWN",
      "message": "manifest unknown",
      "detail": "optional detail string or object"
    }
  ]
}
```

The response always wraps the single error in an array (Docker spec requirement).

#### Three Write Methods

| Method | Used By | Format |
|--------|---------|--------|
| `WriteAsRegistryV2ResponseTo(w, r)` | Registry V2 API handlers | JSON `{"errors": [...]}` |
| `WriteAsAuthResponseTo(w)` | Auth API (`/keppel/v1/auth`) | JSON `{"details": "..."}` |
| `WriteAsTextTo(w)` | Keppel V1 API, peer API | Plain text error message |

### 4.3 Keppel V1 API Error Handling

Uses `respondwith.ObfuscatedErrorText(w, err)` from `go-bits`:

- Returns `true` if `err != nil` (error was handled)
- For 5xx errors: logs the real error with a UUID, returns `"Internal Server Error (ID = <uuid>)"` to client
- For 4xx errors: returns the error message directly (no obfuscation)
- Default status is 500; use `respondwith.CustomStatus()` to override

Client-facing validation errors use `http.Error()` directly:

```go
http.Error(w, "account not found", http.StatusNotFound)
http.Error(w, "unauthorized", http.StatusUnauthorized)
http.Error(w, `changing attribute "account.name" in request body is not allowed`, http.StatusUnprocessableEntity)
http.Error(w, "request body is not valid JSON: "+err.Error(), http.StatusBadRequest)
```

### 4.4 The `respondWithError` Guard Pattern

Both API surfaces use a guard-clause pattern that checks-and-returns in one step:

```go
// Registry V2 API
if respondWithError(w, r, err) {
    return
}

// Keppel V1 API
if respondwith.ObfuscatedErrorText(w, err) {
    return
}
```

The `respondWithError` function handles type switching:

```go
func respondWithError(w http.ResponseWriter, r *http.Request, err error) bool {
    if err == nil {
        return false
    } else if perr, ok := errext.As[processor.UpstreamManifestMissingError](err); ok {
        return respondWithError(w, r, perr.Inner)
    } else if rerr, ok := errext.As[*keppel.RegistryV2Error](err); ok {
        rerr.WriteAsRegistryV2ResponseTo(w, r)
        return true
    }
    keppel.ErrUnknown.With(err.Error()).WriteAsRegistryV2ResponseTo(w, r)
    return true
}
```

---

## 5. Panic Usage Rules

### 5.1 Acceptable Panic Contexts

Panic is used ONLY in non-test code for:

**Programming Errors (Unreachable Code)**:
```go
// internal/auth/token.go
panic(fmt.Sprintf("do not know which JWT method to use for issuerKey.type = %T", key))
panic("unreachable")

// internal/keppel/gc_policy.go
panic(fmt.Sprintf("unexpected GC policy time constraint target: %q (why was this not caught by Validate!?)", tc.FieldName))
panic("unexpected GC policy time constraint: no threshold configured (why was this not caught by Validate!?)")
```

Note the defensive comment pattern: `"(why was this not caught by Validate!?)"` documents the invariant.

**Infallible Operations**:
```go
// crypto/rand.Read should never fail
_, err := rand.Read(buf)
if err != nil {
    panic(err.Error())
}

// json.Marshal on known-good data
buf, err := json.Marshal(p)
if err != nil {
    panic(err.Error())
}
```

**Driver Initialization Guards**:
```go
panic("called before Connect()")  // invariant: method called before init
panic("attempted to register multiple auth drivers with name = " + name)
```

**Test Infrastructure**:
```go
panic("WithRoundTripper calls may not be nested")
panic(err.Error())  // test helpers that must succeed
```

### 5.2 Panic is NEVER Used For

- Request handling errors
- Recoverable errors
- User input validation
- External service failures
- Database errors

---

## 6. Error Flow Through Driver Interfaces

### 6.1 Driver Method Signatures

All driver interface methods return `error` as the last return value:

```go
// StorageDriver
AppendToBlob(ctx, account, storageID, chunkNumber, chunkLength, chunk) error
ReadBlob(ctx, account, storageID) (io.ReadCloser, uint64, error)
CanSetupAccount(ctx, account) error

// FederationDriver
ClaimAccountName(ctx, account, token) (ClaimResult, error)
FindPrimaryAccount(ctx, accountName) (string, error)

// AuthDriver -- returns *RegistryV2Error instead of error
AuthenticateUser(ctx, userName, password) (UserIdentity, *RegistryV2Error)
AuthenticateUserFromRequest(r) (UserIdentity, *RegistryV2Error)
```

Note: `AuthDriver` returns `*RegistryV2Error` directly because authentication failures need specific error codes for the Registry V2 protocol.

### 6.2 Error Propagation Flow

```
Driver method returns error
    |
    v
Processor layer adds context (fmt.Errorf "while/cannot X: %w")
    |
    v
API handler converts to response format:
    - Registry V2: respondWithError() -> RegistryV2Error JSON
    - Keppel V1: respondwith.ObfuscatedErrorText() -> obfuscated text
    - Peer API: respondwith.ObfuscatedErrorText() or WriteAsTextTo()
```

### 6.3 Special Error Types for Cross-Layer Communication

```go
// UpstreamManifestMissingError -- signals that a 404 from upstream should be
// passed through to the client, not treated as an internal error
type UpstreamManifestMissingError struct {
    Ref   models.ManifestReference
    Inner error
}

// Used by respondWithError to unwrap and pass through:
if perr, ok := errext.As[processor.UpstreamManifestMissingError](err); ok {
    return respondWithError(w, r, perr.Inner)
}
```

### 6.4 Background Task Error Handling

Tasks (in `internal/tasks/`) return errors to the `jobloop` framework from `go-bits`:

- `sql.ErrNoRows` signals "no work to do" (slows down the polling loop -- 3s sleep)
- Other errors are logged by `jobloop` at ERROR level (5s sleep for backpressure)
- Tasks add context to driver errors before returning:

```go
return fmt.Errorf("cannot find account for repo %s: %w", repo.FullName(), err)
return fmt.Errorf("could not ConfigureAccount(%q) in account management driver: %w", accountName, err)
```

---

## 7. The `errext` Package

### 7.1 `errext.As` (Generic Type Assertion)

Used instead of `errors.As` for cleaner syntax:

```go
// Instead of:
var rerr *keppel.RegistryV2Error
if errors.As(err, &rerr) { ... }

// Keppel uses:
if rerr, ok := errext.As[*keppel.RegistryV2Error](err); ok { ... }
```

### 7.2 `errext.ErrorSet` (Multiple Error Collection)

Used for validating accounts where multiple fields can fail:

```go
var errs errext.ErrorSet
errs.Add(validateField1())
errs.Add(validateField2())
if !errs.IsEmpty() {
    http.Error(w, errs.Join("\n"), http.StatusUnprocessableEntity)
    return
}
```

Convention: Use `errext.ErrorSet` instead of manual string building. Manual concatenation produces trailing separators. Use `errs.Join("; ")` instead.

---

## 8. Complete Rules Summary

### Error Construction Rules (1-6)

1. **Error messages are lowercase** and do not end with punctuation
2. **Wrap with `%w`** when the caller needs `errors.Is`/`errors.As`
3. **Use `%s` for secondary errors** in multi-error messages: `fmt.Errorf("%w (additional error: %s)", primary, secondary.Error())`
4. **Include identifying data** in error messages: account names, digests, URLs, repository names
5. **Use `%q` for string values**, `%s` for pre-formatted values (digests, URLs)
6. **Prefix error messages** with "while", "cannot", "during", "could not" to describe the failed operation

### Error Handling Rules (7-10)

7. **Never ignore errors** -- always check, wrap, or log
8. **Use `errors.Is` for sentinel errors**, especially `sql.ErrNoRows`
9. **Use `errext.As` for typed errors**, especially `*keppel.RegistryV2Error`
10. **Guard-clause pattern** for HTTP handlers: `if respondWithError(w, r, err) { return }`

### Logging Rules (11-15)

11. **`logg.Fatal`**: startup/CLI only, never in HTTP handlers or background tasks
12. **`logg.Error`**: for errors that cannot bubble up (cleanup failures, advisory operations, deferred functions)
13. **`logg.Info`**: operational events, graceful degradation, notable conditions
14. **`logg.Debug`**: diagnostic detail, gated behind `KEPPEL_DEBUG`
15. **Log format**: `%s` for `.Error()`, `%q` for quoted strings, `%d` for numbers

### Panic Rules (16-19)

16. **Panic only for programming errors**: unreachable code, violated invariants
17. **Panic for infallible operations**: `crypto/rand.Read`, `json.Marshal` on known-good data
18. **Panic for init-order violations**: "called before Connect()"
19. **Never panic for**: user input, external services, database errors, request handling

### HTTP Response Rules (20-24)

20. **Registry V2 API**: use `RegistryV2Error` with appropriate error code from the OCI distribution spec
21. **Keppel V1 API**: use `respondwith.ObfuscatedErrorText` (5xx errors are hidden behind UUIDs)
22. **AuthDriver**: return `*RegistryV2Error` directly (not `error`)
23. **Client-facing validation errors**: use `http.Error(w, message, status)` directly with descriptive messages
24. **Status code overrides**: use `.WithStatus()` on `RegistryV2Error` when the default mapping is wrong for the context

### `must.Return`/`must.Succeed` Rules (25-27)

25. **Production code**: only for program entry and static initialization
26. **Test code**: use `must.SucceedT`/`must.ReturnT` freely for test setup
27. **Never in request handlers or business logic**
