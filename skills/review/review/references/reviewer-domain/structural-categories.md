# The 9 Structural Categories

## Category 1: Type Export Decisions

Flag exported struct types that should be unexported because only their interface is public.

**Check**: "Is this type only used through an interface? If yes, unexport it."

```go
// FLAGGED: exported type only used through interface
type FileBackingStore struct { ... }
func NewFileBackingStore(...) BackingStore { return &FileBackingStore{...} }

// CORRECT: unexported concrete, exported interface
type fileBackingStore struct { ... }
func NewFileBackingStore(...) BackingStore { return &fileBackingStore{...} }
```

**Severity**: HIGH — leaks implementation details, expands public API unnecessarily.

## Category 2: Unnecessary Wrappers/Helpers

Flag functions wrapping a single stdlib/library call without adding value.

**Checks**:
- Custom `go func()` when `wg.Go()` exists
- Custom `mustXxx` when `must.ReturnT`/`must.SucceedT` exist
- Manual row iteration when `sqlext.ForeachRow` exists
- Getter methods returning a field
- Custom error collection when `errext.ErrorSet` exists

```go
// FLAGGED:
func mustGetUser(t *testing.T, db *DB, id string) User {
    u, err := db.GetUser(id)
    if err != nil { t.Fatal(err) }
    return u
}
// Convention: use must.ReturnT
user := must.ReturnT(db.GetUser(id))(t)
```

**must vs assert**:
- `must.SucceedT`/`must.ReturnT` — setup/preconditions (fatal)
- `assert.ErrEqual(t, err, nil)` — operation results (non-fatal)
- Flag `must` used for operation results, `assert` used for preconditions

**Severity**: MEDIUM

## Category 3: Option[T] Resolution Timing

Flag `Option[T]` persisting beyond parse/config into runtime structs.

```go
// FLAGGED: Option in runtime struct
type fileBackingStore struct {
    MaxFileSize Option[int64]  // checked on every write
}

// CORRECT: resolve at parse time
store := fileBackingStore{
    MaxFileSize: cfg.MaxFileSize.UnwrapOr(10 << 20),
}
```

**Severity**: HIGH — forces every method to handle None when decision was made at init.

## Category 4: Dependency/Resource Management

Flag separate pools when shared should be passed. Flag heavy imports when go-bits alternatives exist.

**Checks**:
- Per-request HTTP clients instead of sharing
- Separate DB pools instead of passing `*sql.DB`
- `gophercloud/utils` when `go-bits/gophercloudext` exists
- Utilities in exported packages that should be `internal`

**Severity**: HIGH for transitive dep pollution, MEDIUM for resource management.

## Category 5: Anti-Over-Engineering

Flag abstractions adding complexity without value.

**Checks**:
- Throwaway structs for simple JSON (use `fmt.Sprintf` + `json.Marshal`)
- Manual error concatenation (use `errext.ErrorSet`)
- Custom test helpers duplicating go-bits
- Inference that won't scale
- Repository patterns wrapping direct DB
- Option structs for constructors (use positional params)
- Config structs bundling unrelated params

**Severity**: MEDIUM general, HIGH when creating maintenance burden.

## Category 6: Forward Compatibility in Naming

Flag names blocking future siblings.

**Checks**:
- `keppel test` -> `keppel test-driver storage`
- Names claiming the only slot
- Types named after first implementation

**Severity**: MEDIUM — compounds as siblings added.

## Category 7: go-bits Library Usage

Flag manual implementations of patterns go-bits provides.

| Manual Pattern | go-bits Replacement | Package |
|----------------|---------------------|---------|
| `rows.Next()` + `rows.Scan()` | `sqlext.ForeachRow()` | sqlext |
| `if err != nil { t.Fatal(err) }` | `must.SucceedT(t, err)` | must |
| Manual DB test setup | `easypg.WithTestDB()` | easypg |
| Manual error collection | `errext.ErrorSet` | errext |
| `log.Printf` | `logg.Info()` | logg |
| `json.Marshal` + `w.Write` | `respondwith.JSON()` | respondwith |
| `os.Getenv` without validation | `osext.MustGetenv()` | osext |
| Manual factory maps | `pluggable.Registry[T]` | pluggable |
| Manual HTTP server lifecycle | `httpext.ListenAndServeContext()` | httpext |

```go
// FLAGGED: manual row iteration
rows, err := db.Query(query, args...)
defer rows.Close()
for rows.Next() { ... }

// Convention: use sqlext.ForeachRow
err := sqlext.ForeachRow(db, query, args, func(rows *sql.Rows) error {
    return rows.Scan(&item.ID, &item.Name)
})
```

**Severity**: MEDIUM, HIGH when manual version has bugs go-bits avoids.

## Category 8: Test Structure

**Checks**:
- Missing `testWithEachTypeOf` for multi-implementation interfaces
- Tests covering only one implementation when multiple exist
- `MockXxx` types in production (non-test) files
- `PedanticRegistry` in production (test-only)
- Integration tests in table-driven format instead of sequential narrative

```go
// Convention: testWithEachTypeOf
func testWithEachBackingStore(t *testing.T, action func(*testing.T, BackingStore)) {
    t.Run("with file store", func(t *testing.T) { action(t, newTestFileBackingStore(t)) })
    t.Run("with SQL store", func(t *testing.T) {
        easypg.WithTestDB(t, func(t *testing.T, db *sql.DB) { action(t, newTestSQLBackingStore(t, db)) })
    })
}
```

**Severity**: HIGH for missing multi-implementation coverage, MEDIUM for structural issues.

## Category 9: Contract Cohesion

Constants, error sentinels, validation functions must live with their owning interface.

**Checks**:
- `ErrFoo` in `util.go` when returned by a specific interface
- Constants in `constants.go` parameterizing a specific interface
- Validation in `util.go` for a specific type
- Generic filenames (`interface.go`) that should be domain-named

**Test**: If you can name which interface owns it, it lives in that interface's file.

**Acceptable in util.go**: Cross-cutting utilities serving multiple unrelated types.

**Severity**: MEDIUM for new violations (move during this PR). LOW for pre-existing in untouched code.

**Cross-repo**: Appears in 4+ sapcc repos — NON-NEGOTIABLE per Tier 1.
