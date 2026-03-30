# The 9 Structural Categories

## Category 1: Type Export Decisions

Flag exported struct types that should be unexported because only their interface is used externally.

**Check**: "Is this type only used through an interface? If yes, unexport it."

Project convention: unexport `InMemoryBackingStore` to `inMemoryBackingStore` when only `BackingStore` interface is public.

```go
// FLAGGED: exported type only used through interface
type FileBackingStore struct { ... }
func NewFileBackingStore(...) BackingStore { return &FileBackingStore{...} }

// CORRECT: unexported concrete, exported interface
type fileBackingStore struct { ... }
func NewFileBackingStore(...) BackingStore { return &fileBackingStore{...} }
```

**Severity**: HIGH — exported types that should be unexported leak implementation details and expand the public API surface unnecessarily.

## Category 2: Unnecessary Wrappers/Helpers

Flag functions that wrap a single stdlib/library call without adding value.

**Checks**:
- Custom `go func()` wrappers when `wg.Go()` exists
- Custom `mustXxx` helpers when `must.ReturnT` / `must.SucceedT` exist
- Manual row iteration loops when `sqlext.ForeachRow` exists
- Getter methods that just return a field (`func (s *Service) GetDB() *DB`)
- Custom error collection when `errext.ErrorSet` exists

```go
// FLAGGED: wrapper adds nothing
func mustGetUser(t *testing.T, db *DB, id string) User {
    u, err := db.GetUser(id)
    if err != nil { t.Fatal(err) }
    return u
}

// Convention: "Delete this, use must.ReturnT"
user := must.ReturnT(db.GetUser(id))(t)
```

**Severity**: MEDIUM — unnecessary wrappers add maintenance burden and hide the actual operation.

**must vs assert — When flagging test wrappers, also check for wrong package choice:**
- `must.SucceedT` / `must.ReturnT` → for `mustXxx` helpers and setup/preconditions (fatal, next lines depend on it)
- `assert.ErrEqual(t, err, nil)` → for checking the expected outcome of the tested operation (non-fatal, reports all failures)
- Flag `must.SucceedT(t, err)` used where `assert.ErrEqual(t, err, nil)` belongs (testing the operation's result, not a precondition)
- Flag `assert.ErrEqual(t, err, nil)` used where `must.SucceedT` belongs (setup that subsequent assertions depend on)

## Category 3: Option[T] Resolution Timing

Flag `Option[T]` fields that persist beyond the parse/config phase into runtime structs.

Project convention: resolve Options at parse time and pass concrete values to core logic. Resolve `Option[T]` once at parse time rather than propagating it through the call stack.

```go
// FLAGGED: Option persists in runtime struct
type fileBackingStore struct {
    MaxFileSize Option[int64]  // <-- this gets checked on every write
}

// Convention: "Having Option here means that each method needs to handle the
// None case, even though you are removing the None case during Init."

// CORRECT: resolve at parse time
var cfg struct {
    MaxFileSize Option[int64] `json:"max_file_size"`
}
json.Unmarshal(params, &cfg)
store := fileBackingStore{
    MaxFileSize: cfg.MaxFileSize.UnwrapOr(10 << 20),
}
```

**Severity**: HIGH — Option[T] in runtime structs forces every method to handle None when the decision was already made at init.

## Category 4: Dependency/Resource Management

Flag creation of separate connection pools or clients when a shared one should be passed in. Flag importing heavy packages when utilities exist in go-bits.

**Checks**:
- Creating per-request HTTP clients instead of sharing one
- Creating separate DB connection pools instead of passing `*sql.DB`
- Importing `gophercloud/utils` when `go-bits/gophercloudext` exists
- Importing heavy packages when go-bits has lightweight alternatives
- Utilities in exported packages that should be in `internal` to avoid transitive dep pollution

Project convention: "move utilities to internal to avoid transitive dep pollution."

```go
// FLAGGED: heavy import when go-bits alternative exists
import "github.com/gophercloud/utils"

// Review standard: "This would mean that a lot of applications will pull in
// dependencies into their vendor directories. Move to package internal."
```

**Severity**: HIGH for transitive dep pollution, MEDIUM for resource management.

## Category 5: Anti-Over-Engineering

Flag abstractions and structures that add complexity without adding value.

**Checks**:
- Throwaway struct types for simple JSON (use `fmt.Sprintf` + `json.Marshal`)
- Manual error string concatenation (use `errext.ErrorSet` and `Join()`)
- Custom test helpers that duplicate `must.SucceedT` / `must.ReturnT`
- Inference logic that won't scale to known upcoming use cases
- Repository patterns wrapping direct DB access
- Option structs or functional options for constructors (use positional params)
- Config structs bundling unrelated params
- Custom error types for one-off errors (use `fmt.Errorf` or sentinels)

```go
// FLAGGED: throwaway struct for JSON
type fsConfig struct {
    Type   string   `json:"type"`
    Params fsParams `json:"params"`
}
type fsParams struct {
    Path string `json:"path"`
}
buf, _ := json.Marshal(fsConfig{...})

// Convention: "This is overengineered."
storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`,
    must.Return(json.Marshal(filesystemPath)))
```

**Severity**: MEDIUM for general over-engineering, HIGH when it creates maintenance burden.

## Category 6: Forward Compatibility in Naming

Flag type names, function names, and CLI commands that are too generic or too specific for their actual scope.

Project convention: names should allow siblings without renaming.

**Checks**:
- CLI commands too vague: `keppel test` → `keppel test-driver storage`
- Names that claim the only slot: `ProcessData` when there will be `ProcessMetrics` too
- Types named after the first implementation: `BackendStore` when it's really `FileStore`
- Generic names that obscure the specialization

```go
// FLAGGED: name too vague, blocks siblings
cmd.AddCommand(&cobra.Command{Use: "test", ...})

// Convention: "This sets up the command to only ever test one thing.
// Use 'test-driver storage' so we could have 'test-driver federation' later."
cmd.AddCommand(&cobra.Command{Use: "test-driver", ...})
```

**Severity**: MEDIUM — naming issues compound over time as siblings are added.

## Category 7: go-bits Library Usage

Flag manual implementations of patterns that go-bits already provides. Cross-reference against library-reference.md.

**Key checks**:

| Manual Pattern | go-bits Replacement | Package |
|----------------|---------------------|---------|
| `rows.Next()` + `rows.Scan()` loops | `sqlext.ForeachRow()` | sqlext |
| Custom `if err != nil { t.Fatal(err) }` | `must.SucceedT(t, err)` | must |
| Custom `val, err := ...; if err { t.Fatal }; return val` | `must.ReturnT(f())(t)` | must |
| Manual DB test setup with DSN | `easypg.WithTestDB()` / `ConnectForTest()` | easypg |
| Manual error collection in loops | `errext.ErrorSet` with `Add()`, `Join()` | errext |
| `log.Printf` / `log.Fatal` | `logg.Info()` / `logg.Fatal()` | logg |
| Manual `json.Marshal` + `w.Write` | `respondwith.JSON()` | respondwith |
| `http.Error(w, msg, code)` for API errors | `respondwith.ErrorText()` | respondwith |
| `prometheus.NewRegistry()` in tests | `prometheus.NewPedanticRegistry()` | (prometheus) |
| `os.Getenv` without validation | `osext.MustGetenv()` | osext |
| Manual factory maps for drivers | `pluggable.Registry[T]` | pluggable |
| Manual HTTP server lifecycle | `httpext.ListenAndServeContext()` | httpext |

```go
// FLAGGED: manual row iteration
rows, err := db.Query(query, args...)
if err != nil { return err }
defer rows.Close()
for rows.Next() {
    var item Item
    if err := rows.Scan(&item.ID, &item.Name); err != nil { return err }
    items = append(items, item)
}

// Convention: "Use sqlext.ForeachRow"
err := sqlext.ForeachRow(db, query, args, func(rows *sql.Rows) error {
    var item Item
    return rows.Scan(&item.ID, &item.Name)
})
```

**Severity**: MEDIUM for missing go-bits usage, HIGH when the manual implementation has bugs that go-bits avoids.

## Category 8: Test Structure

Flag missing test patterns for multi-implementation interfaces.

**Checks**:
- Missing `testWithEachTypeOf` pattern when multiple implementations of the same interface exist
- Test files that only test one implementation when multiple exist
- Production code containing test utilities (`MockXxx` types in non-test files)
- `PedanticRegistry` used in production code (test-only)
- Integration tests using table-driven format instead of sequential narrative

```go
// FLAGGED: only testing one implementation
func TestFileBackingStore(t *testing.T) {
    store := NewFileBackingStore(t.TempDir())
    // tests...
}
// Missing: TestSQLBackingStore with same test cases

// Convention: use testWithEachTypeOf
func testWithEachBackingStore(t *testing.T, action func(*testing.T, BackingStore)) {
    t.Run("with file store", func(t *testing.T) {
        action(t, newTestFileBackingStore(t))
    })
    t.Run("with SQL store", func(t *testing.T) {
        easypg.WithTestDB(t, func(t *testing.T, db *sql.DB) {
            action(t, newTestSQLBackingStore(t, db))
        })
    })
}
```

**Severity**: HIGH for missing multi-implementation test coverage, MEDIUM for structural test issues.

## Category 9: Contract Cohesion (§36)

Flag constants, error sentinels, and validation functions that live in a different file from the interface or contract type they belong to.

**Checks**:
- Error sentinels (`ErrFoo`) in `util.go` or `errors.go` when they are returned by a specific interface's methods
- Constants (permission enums, sentinel values) in `constants.go` when they parameterize a specific interface
- Validation functions in `util.go` when they validate a specific type's fields
- Files named generically (`interface.go`, `types.go`) when they should be named for the domain concept (`storage_driver.go`, `rbac_policy.go`)

**The test**: if you can name which interface/type owns an artifact, that artifact must live in the interface's file.

```go
// FLAGGED: sentinel belongs to StorageDriver contract
// util.go
var ErrAuthDriverMismatch = errors.New("authn driver does not match")

// storage_driver.go -- the actual StorageDriver interface is here
type StorageDriver interface { ... }

// Convention: "Move ErrAuthDriverMismatch into storage_driver.go.
// It is part of the StorageDriver contract."
```

**What IS acceptable in util.go**: genuinely cross-cutting utilities serving multiple unrelated types — field mappings shared across backends, generic deduplication helpers, string manipulation, HTTP/URL helpers.

**Severity**: MEDIUM for new constants/sentinels introduced in `util.go` that belong to a specific interface (move it during this PR). LOW for pre-existing violations in code not touched by the current PR.

**Cross-repo reinforcement**: This pattern appears in 4+ sapcc repos (keppel, limes, castellum, limesctl) — NON-NEGOTIABLE per §35 Tier 1.
