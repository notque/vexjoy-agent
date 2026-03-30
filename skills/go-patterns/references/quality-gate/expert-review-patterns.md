# Expert Review Patterns (Beyond Linting)

These patterns come from real code reviews and address issues that automated tools miss.

## General Go Patterns

### Type Export Design
- **Check**: Are implementation types unnecessarily exported?
- **Issue**: Exported types let users bypass constructors and create invalid instances
- **Fix**: Keep implementation types unexported, export only interfaces and constructors

### Batch+Callback Race Conditions
- **Check**: Does `ReadBatch()` + `commit()` pattern protect against concurrent writes?
- **Issue**: Clearing all items in commit() loses events added between ReadBatch and commit
- **Fix**: commit() should remove only the specific batch returned, not all items

### Function Extraction Justification
- **Check**: Is function extraction adding value or just satisfying metrics?
- **Issue**: Extracting 3-line code to a helper adds indirection without benefit
- **Fix**: Only extract if (a) reused elsewhere, or (b) hides complex details

### Defer Timing
- **Check**: Is `defer f.Close()` placed after the error check?
- **Issue**: Deferring before error check can panic on nil pointer
- **Fix**: Always check error first, then defer cleanup

### Go 1.22+ Loop Variables
- **Check 1**: Are loop variables being reassigned (`i := i`)?
- **Check 2**: Are loop variables passed as closure arguments (`go func(id int) { }(i)`)?
- **Issue**: Both patterns are unnecessary since Go 1.22 - each iteration has its own variable
- **Fix**: Remove reassignment AND closure parameters; use loop variable directly in closure
- **Detection**: Flag `go func(x TYPE) { ... }(loopVar)` where parameter matches argument

### Double File Traversal
- **Check**: Is the same directory being stat'd multiple times?
- **Issue**: listFiles() stats files, then calculateSize() stats them again
- **Fix**: Return all needed data from single traversal

### Database Connection Pooling
- **Check**: Is code creating duplicate connection pools?
- **Issue**: Each component opening its own connection wastes resources
- **Fix**: Use factory closures to share existing connections

### Prometheus Metrics Initialization
- **Check**: Are counter metrics pre-initialized with `.Add(0)`?
- **Issue**: Metrics don't exist until first increment, causing alerts issues
- **Fix**: Initialize all known label combinations to 0 on startup

### Test Deduplication
- **Check**: Are tests for multiple interface implementations copy-pasted?
- **Issue**: Duplicated test logic is hard to maintain
- **Fix**: Use `testWithEachBackingStore()` pattern to share test body

## Organization Library Ecosystem Checks

When a project uses shared organization libraries, apply these additional checks:

### Option Type Usage
- **Check**: Are optional config fields using the organization's preferred option type?
- **Issue**: Pointer fields or zero-value checks are verbose and error-prone
- **Fix**: Use the organization's standard option type for optional fields

### SQL Iteration Pattern
- **Check**: Is manual SQL row iteration used?
- **Issue**: `rows.Next()` + `rows.Scan()` + `rows.Err()` is verbose and error-prone
- **Fix**: Use the organization's SQL helper functions if available

### Test Helper Usage
- **Check**: Are tests using verbose `if err != nil { t.Fatalf(...) }` patterns?
- **Issue**: Repetitive error handling obscures test intent
- **Fix**: Use the organization's test assertion helpers

### Assertion Selection (Equal vs DeepEqual)
- **Check**: Is `reflect.DeepEqual` used for comparable types (int, string, bool)?
- **Issue**: `DeepEqual` uses reflection unnecessarily
- **Fix**: Use direct comparison for comparable types. Use deep comparison only for slices, maps, and structs with non-comparable fields.

### Test Database Setup
- **Check**: Is manual database connection setup used in tests?
- **Issue**: Won't work with CI test infrastructure; cleanup issues
- **Fix**: Use the organization's test database helpers

### Prometheus Test Registry
- **Check**: Are tests using `prometheus.NewRegistry()`?
- **Issue**: Misses metric definition issues
- **Fix**: Use `prometheus.NewPedanticRegistry()` for stricter validation

### Dead Code Detection
- **Check**: Are there unused helper functions or leftover files?
- **Issue**: Leftover migration files, redundant wrappers
- **Fix**: Remove dead code; flag for review

### Database Function Naming
- **Check**: Do SQL functions indicate the specific database?
- **Issue**: Generic `SQLStoreFactory` hides PostgreSQL dependency
- **Fix**: Name it `SQLStoreFactoryWithPostgresDB` if using PostgreSQL syntax
