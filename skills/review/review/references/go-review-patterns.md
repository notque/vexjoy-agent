# Go-Specific Review Patterns

When reviewing Go code, watch for these patterns that linters miss:

## Type Export Design
- [ ] Are implementation types unnecessarily exported?
- [ ] Should types be unexported with only constructors exported?
- **Red flag**: `type FooStore struct{}` exported but only implements an interface

## Concurrency Patterns
- [ ] Does batch+callback pattern protect against concurrent writes?
- [ ] Does `commit()` only remove specific items, not clear all?
- [ ] Are loop variables using outdated patterns? (Go 1.22+ doesn't need cloning)
  - [ ] No `i := i` reassignment inside loops
  - [ ] No closure arguments for loop variables: `go func(id int) { }(i)`
- **Red flag**: `s.events = nil` in commit callback
- **Red flag**: `go func(x int) { ... }(loopVar)` - closure argument unnecessary since Go 1.22

## Modern Idioms (check go.mod first)
- [ ] 1.25+: `wg.Go(f)`, not `wg.Add(1)` + `go` + `defer wg.Done()`; timing tests use `synctest.Test`, not `time.Sleep`
- [ ] 1.24+: tests use `t.Context()`, not `context.Background()`; `slog.DiscardHandler`, not a handler on `io.Discard`
- [ ] 1.26+: `errors.AsType[*T](err)`, not `errors.As`; `go fix -diff ./...` prints nothing
- [ ] 1.27+: standard `uuid` package, not hand-rolled UUIDs; `strings.CutLast`, not `LastIndex` slicing
- [ ] Sentinels compared with `errors.Is`, never `==` or error-string matching
- [ ] Every exported name has a doc comment starting with the name
- **Red flag**: a hand-written 405 without an `Allow` header; a Go 1.22+ `ServeMux` already sends 405 with `Allow`
- Full rules with before/after code: `agents/golang-general-engineer/references/go-modern-code.md`

## Resource Management
- [ ] Is `defer f.Close()` placed AFTER error check?
- [ ] Are database connection pools shared, not duplicated?
- [ ] Is file traversal done once, not repeated for size calculation?
- **Red flag**: `defer f.Close()` immediately after `os.OpenFile()`

## Metrics & Observability
- [ ] Are Prometheus counter metrics pre-initialized with `.Add(0)`?
- [ ] Are all known label combinations initialized at startup?
- **Red flag**: CounterVec registered but not initialized

## Testing Patterns
- [ ] Are interface implementation tests deduplicated?
- [ ] Do tests use `assert.Equal` (no reflection) for comparable types?
- [ ] Does test setup use `prometheus.NewPedanticRegistry()`?
- **Red flag**: Copy-pasted tests for FileStore, MemoryStore, SQLStore

## Code Organization
- [ ] Is function extraction justified (reuse or complexity hiding)?
- [ ] Are unnecessary helper functions wrapping stdlib calls?
- **Red flag**: Helper that just calls through to another function

---

# Organization Library Ecosystem Patterns

When reviewing projects that use shared organization libraries, apply these additional checks:

## Library Usage
- [ ] Are optional fields using the organization's preferred option type?
- [ ] Is SQL iteration using helper functions instead of manual `rows.Next()` loops?
- [ ] Are tests using the organization's assertion helpers?
- **Red flag**: Manual SQL row iteration with defer/Next/Scan/Err pattern when helpers exist

## Test Assertions
- [ ] Is the correct assertion function used for the type being compared?
- [ ] Is deep comparison only used for non-comparable types (slices, maps, structs)?
- **Red flag**: Deep comparison used for simple types like int, string, bool

## Test Infrastructure
- [ ] Are DB tests using the organization's test database helpers?
- [ ] Are Prometheus tests using `NewPedanticRegistry()`?
- **Red flag**: Raw `sql.Open()` in test setup instead of test helpers

## Dead Code
- [ ] Are there leftover `*_migration.sql` files without usage?
- [ ] Are there helper functions that just wrap single stdlib calls?
- [ ] Are there redundant checks (e.g., empty string check before regex)?
- **Red flag**: Wrapper functions that add no value over the underlying call

## Database Naming
- [ ] Do functions using database-specific syntax indicate this in names?
- **Red flag**: Generic `SQLStoreFactory` that uses database-specific syntax
