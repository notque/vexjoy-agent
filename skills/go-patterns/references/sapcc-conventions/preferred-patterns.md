# SAP CC Anti-Patterns

Code patterns that will FAIL review. Each includes BAD/GOOD examples.

---

## AP-1: Creating Types for One-Off JSON Marshaling

**What it looks like**:
```go
// BAD
type fsParams struct {
    Path string `json:"path"`
}
type fsConfig struct {
    Type   string   `json:"type"`
    Params fsParams `json:"params"`
}
config, _ := json.Marshal(fsConfig{Type: "filesystem", Params: fsParams{Path: path}})
```

**Why wrong**: Creating struct types with json tags that are used exactly once adds ceremony without benefit. This is overengineered.

**GOOD**:
```go
storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`,
  must.Return(json.Marshal(filesystemPath)))
```

---

## AP-2: Wrapping Errors That Already Have Context

**What it looks like**:
```go
// BAD
val, err := strconv.ParseUint(s, 10, 32)
if err != nil {
    return fmt.Errorf("failed to parse chunk number %q: %w", s, err)
}
```

**Why wrong**: `strconv.ParseUint` already says `"strconv.ParseUint: parsing \"hello\": invalid syntax"`. The wrapper adds noise, not clarity.

**GOOD**:
```go
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
```

Also applies to well-designed constructors like `NewAuthDriver`, `NewStorageDriver` that already include driver type in their error messages.

---

## AP-3: Manual Argument Dispatch Instead of Cobra

**What it looks like**:
```go
// BAD
switch args[0] {
case "read-manifest":
    handleReadManifest(args[1:])
case "write-blob":
    handleWriteBlob(args[1:])
default:
    fmt.Fprintf(os.Stderr, "unknown operation: %s\n", args[0])
}
```

**Why wrong**: Manually rolling structure that usually would be represented as Cobra subcommands instead.

**GOOD**:
```go
// Each operation is a Cobra subcommand
readManifestCmd := &cobra.Command{Use: "read-manifest", Run: handleReadManifest}
writeBlobCmd := &cobra.Command{Use: "write-blob", Run: handleWriteBlob}
parent.AddCommand(readManifestCmd, writeBlobCmd)
```

If argument ordering prevents Cobra subcommands, change the argument order.

---

## AP-4: Using must.Return in Request Handlers

**What it looks like**:
```go
// BAD: inside an HTTP handler
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    account := must.Return(a.db.FindAccount(name))
    // ...
}
```

**Why wrong**: `must.Return` calls `logg.Fatal` which calls `os.Exit(1)`. In a request handler, this crashes the entire server.

**GOOD**:
```go
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    account, err := a.db.FindAccount(name)
    if respondwith.ObfuscatedErrorText(w, err) {
        return
    }
    // ...
}
```

`must.*` is for startup code and tests only. Never in handlers or business logic.

---

## AP-5: Global Mutable Variables for Configuration

**What it looks like**:
```go
// BAD
var LiquidOptionTypes = []any{
    Option[int]{}, Option[string]{}, // ...
}
```

**Why wrong**: Having a global variable for this that callers can mess with is a design flaw.

**GOOD**:
```go
func ForeachOptionTypeInLIQUID[T any](action func(any) T) []T {
    types := []any{Option[int]{}, Option[string]{}}
    result := make([]T, len(types))
    for i, t := range types {
        result[i] = action(t)
    }
    return result
}
```

---

## AP-6: Handling Theoretical Errors

**What it looks like**:
```go
// BAD: handling os.Stdout.Write errors
n, err := os.Stdout.Write(data)
if err != nil {
    logg.Error("failed to write to stdout: %s", err.Error())
}
```

**Why wrong**: This is a theoretical concern: writes to stdout almost never fail in practice. If `fmt.Println` ignoring errors is OK everywhere else, so is `os.Stdout.Write`.

**GOOD**:
```go
os.Stdout.Write(data)
```

---

## AP-7: Adding Defer Close on io.NopCloser

**What it looks like**:
```go
// BAD
rc := io.NopCloser(bytes.NewReader(data))
defer rc.Close()  // "honor the ownership contract"
```

**Why wrong**: This is an irrelevant contrivance. NopCloser's Close is a no-op. If the operation succeeds, cleanup happened internally. If it fails, you fatal out.

**GOOD**: Don't add the defer. It communicates nothing.

---

## AP-8: Manual Error String Building

**What it looks like**:
```go
// BAD
result := ""
for _, e := range errs {
    result += e.Error() + "; "
}
// Produces trailing "; " at the end
```

**Why wrong**: Manual concatenation mishandles trailing separators. go-bits already has `errext.ErrorSet`.

**GOOD**:
```go
var errs errext.ErrorSet
for _, item := range items {
    errs.Add(validate(item))
}
if !errs.IsEmpty() {
    return errs.Join("; ")
}
```

---

## AP-9: Manual Field Formatting Instead of json.Marshal

**What it looks like**:
```go
// BAD
errMsg := fmt.Sprintf("validation failed: mediaType=%s, layers=%d", mt, len(layers))
// Must be updated whenever fields change
```

**Why wrong**: Doing manual footwork that will require updates whenever we add new expressions.

**GOOD**:
```go
payload, _ := json.Marshal(evalInput)
errMsg := fmt.Sprintf("validation failed for payload: %s", payload)
// Automatically includes all fields
```

---

## AP-10: Vague CLI Command Names

**What it looks like**:
```
# BAD
keppel test <driver> <method>
```

**Why wrong**: "keppel test" is really vague and blocks future sibling commands.

**GOOD**:
```
keppel test-driver storage <driver> <method>
# Later: keppel test-driver federation <driver> <method>
```

---

## AP-11: Smart Defaults That Won't Scale

**What it looks like**:
```go
// BAD: inferring params from driver name
switch driverName {
case "swift":
    params = `{"container": "default"}`
case "filesystem":
    params = `{"path": "/tmp/data"}`
}
```

**Why wrong**: Won't work when a `multi` driver wraps other drivers.

**GOOD**:
```go
// Explicit params via flag
cmd.Flags().String("params", "", "JSON driver parameters")
```

---

## AP-12: Using Forbidden Libraries

**What it looks like**:
```go
// BAD
import "github.com/stretchr/testify/assert"
import "go.uber.org/zap"
import "github.com/gin-gonic/gin"
import "gorm.io/gorm"
```

**Why wrong**: SAP CC has standardized on go-bits equivalents. Using these will fail review.

**GOOD**:
```go
import "github.com/sapcc/go-bits/assert"
import "github.com/sapcc/go-bits/logg"
import "github.com/sapcc/go-bits/httpapi"
import "github.com/go-gorp/gorp/v3"
```

---

## AP-13: Missing httpapi.IdentifyEndpoint

**What it looks like**:
```go
// BAD: jumping straight to business logic
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request) {
    accounts, err := a.db.GetAccounts()
    // ...
}
```

**Why wrong**: Every handler MUST call `httpapi.IdentifyEndpoint` first for Prometheus metrics.

**GOOD**:
```go
func (a *API) handleGetAccounts(w http.ResponseWriter, r *http.Request) {
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts")
    // ...
}
```

---

## AP-14: Data Access Before Authentication

**What it looks like**:
```go
// BAD: loading resource before auth check
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts/:account")
    account, err := a.findAccount(mux.Vars(r)["account"])
    authz := a.authenticateRequest(w, r, ...)
}
```

**Why wrong**: Loading resources before authentication leaks information about resource existence. Authenticate BEFORE any data access.

**GOOD**:
```go
func (a *API) handleGetAccount(w http.ResponseWriter, r *http.Request) {
    httpapi.IdentifyEndpoint(r, "/keppel/v1/accounts/:account")
    authz := a.authenticateRequest(w, r, scopes)
    if authz == nil { return }
    account := a.findAccountFromRequest(w, r, authz)
    if account == nil { return }
}
```

---

## AP-15: Returning null for Empty Collections

**What it looks like**:
```go
// BAD: nil slice marshals to null
var accounts []Account
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": accounts})
// Response: {"accounts": null}
```

**Why wrong**: JSON `null` breaks client code expecting an array.

**GOOD**:
```go
if len(accounts) == 0 {
    accounts = []Account{}
}
respondwith.JSON(w, http.StatusOK, map[string]any{"accounts": accounts})
// Response: {"accounts": []}
```

---

## AP-16: Using httptest.NewRecorder Directly

**What it looks like**:
```go
// BAD: manual test setup
w := httptest.NewRecorder()
r := httptest.NewRequest("GET", "/path", nil)
handler.ServeHTTP(w, r)
if w.Code != 200 { t.Errorf(...) }
body := w.Body.String()
// manual JSON parsing...
```

**Why wrong**: `assert.HTTPRequest` handles all this with better error messages.

**GOOD**:
```go
assert.HTTPRequest{
    Method:       "GET",
    Path:         "/path",
    ExpectStatus: http.StatusOK,
    ExpectBody:   assert.JSONObject{"key": "value"},
}.Check(t, handler)
```

---

## AP-17: Silently Removing Test Assertions During Refactoring

**What it looks like**:
```go
// BEFORE refactoring: tested vuln_status_changed_at
// AFTER refactoring: field assertion removed without comment
```

**Why wrong**: Test assertions that verify behavior must be preserved. Silently removing them hides regressions.

**GOOD**: Keep all behavior-verifying assertions. If a refactoring makes an assertion impossible, that's a signal the refactoring may be wrong.

---

## AP-18: Using time.Now() Directly in Testable Code

**What it looks like**:
```go
// BAD
type API struct { /* ... */ }
func (a *API) handleGet(w http.ResponseWriter, r *http.Request) {
    now := time.Now()
    // ...
}
```

**Why wrong**: Makes tests non-deterministic. Cannot control time in tests.

**GOOD**:
```go
type API struct {
    timeNow func() time.Time  // default: time.Now
}
func (a *API) OverrideTimeNow(f func() time.Time) *API {
    a.timeNow = f; return a
}
func (a *API) handleGet(w http.ResponseWriter, r *http.Request) {
    now := a.timeNow()
}
// In tests:
api.OverrideTimeNow(clock.Now)
```

---

## AP-19: Missing DisallowUnknownFields on JSON Config

**What it looks like**:
```go
// BAD: accepts any JSON fields silently
err := json.Unmarshal(data, &config)
```

**Why wrong**: Typos in config are silently ignored. Use `DisallowUnknownFields()` to catch them.

**GOOD**:
```go
decoder := json.NewDecoder(bytes.NewReader(data))
decoder.DisallowUnknownFields()
err := decoder.Decode(&config)
```

---

## AP-20: TODOs Without Context

**What it looks like**:
```go
// BAD
// TODO: fix this later
```

**Why wrong**: TODOs must include what, where to start, and why not done now.

**GOOD**:
```go
// TODO: Investigate how to declare the fields of `layers` correctly.
// See https://pkg.go.dev/github.com/google/cel-go@v0.26.1/common/types#NewObjectType
// Currently blocked because cel-go strongly prefers protobuf type declarations.
```

---

## AP-21: Using Standard Log Package

**What it looks like**:
```go
// BAD
import "log"
log.Printf("starting server on %s", addr)
log.Fatalf("failed to connect: %s", err)
```

**Why wrong**: SAP CC uses `go-bits/logg` for consistent log formatting with level prefixes.

**GOOD**:
```go
import "github.com/sapcc/go-bits/logg"
logg.Info("starting server on %s", addr)
logg.Fatal("failed to connect: %s", err.Error())
```

---

## AP-22: Wrong Import Grouping

**What it looks like**:
```go
// BAD: sapcc/go-bits in the local (third) group
import (
    "fmt"

    "github.com/gorilla/mux"

    "github.com/sapcc/go-bits/logg"  // WRONG: this is external, not local
    "github.com/sapcc/keppel/internal/models"
)
```

**Why wrong**: `sapcc/go-bits` and `sapcc/go-api-declarations` sort with external deps (Group 2), not local project (Group 3).

**GOOD**:
```go
import (
    "fmt"

    "github.com/gorilla/mux"
    "github.com/sapcc/go-bits/logg"  // Correct: Group 2 (external)

    "github.com/sapcc/keppel/internal/models"  // Group 3 (local)
)
```

---

## AP-23: Not Validating Migration Paths

**What it looks like**:
```go
// BAD: removing env var usage without checking for stale references
// Old: osext.MustGetenv("KEPPEL_OSLO_POLICY_PATH")
// New: config from JSON, but no check if old env var is still set
```

**Why wrong**: Silent misconfiguration during migration is dangerous. Always check if deprecated env vars are still set and abort with a clear message.

**GOOD**:
```go
// Check for deprecated env vars and abort with clear message
if os.Getenv("KEPPEL_OSLO_POLICY_PATH") != "" {
    logg.Fatal("KEPPEL_OSLO_POLICY_PATH is no longer used. " +
        "Configure via KEPPEL_DRIVER_AUTH JSON instead.")
}
```

---

## AP-24: Panicking on User Input or External Failures

**What it looks like**:
```go
// BAD
func handleRequest(w http.ResponseWriter, r *http.Request) {
    data := must.Return(io.ReadAll(r.Body))  // panics on read error
    config := must.Return(parseConfig(data))  // panics on invalid input
}
```

**Why wrong**: User input and network I/O can always fail. `must.*` calls `os.Exit(1)`.

**GOOD**:
```go
func handleRequest(w http.ResponseWriter, r *http.Request) {
    data, err := io.ReadAll(r.Body)
    if err != nil {
        http.Error(w, "failed to read request body", http.StatusBadRequest)
        return
    }
    config, err := parseConfig(data)
    if respondwith.ObfuscatedErrorText(w, err) {
        return
    }
}
```
