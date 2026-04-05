# Testing Patterns Reference

<!-- Loaded by golang-general-engineer-compact when task involves: tests, table-driven, benchmarks, fuzz, subtests, t.Run, b.Loop, parallel tests, test helpers -->
<!-- scope: Go testing correctness and patterns | version-range: Go 1.18-1.26+ | date: 2026-04-05 -->

Complete testing patterns with detection commands for anti-patterns. The agent body has a minimal table-driven stub; this file has the full structures and everything needed to write, benchmark, and fuzz correctly.

---

## Pattern Table

| Pattern | Purpose | Go Version |
|---|---|---|
| Table-driven with `t.Run` | Multiple cases, individually runnable | 1.18+ |
| `t.Helper()` | Clean failure locations in helpers | 1.18+ |
| `t.Cleanup()` | Resource teardown after subtests | 1.18+ |
| `t.Parallel()` | Independent subtests run concurrently | 1.18+ |
| `t.Context()` | Test-scoped context, cancelled on test end | **1.24+** |
| `b.Loop()` | Benchmark loop without allocation skew | **1.24+** |
| Fuzz with `f.Fuzz` | Property-based random input discovery | 1.18+ |
| `httptest.NewRecorder` | Handler testing without a server | 1.18+ |
| `t.TempDir()` | Auto-cleaned temp directories | 1.15+ |

---

## Correct Patterns

### Table-Driven Test Structure

Standard shape: `[]struct` with `name`, `input`, `want`, and optional `wantErr`.

```go
func TestParseAmount(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int
        wantErr bool
    }{
        {name: "whole number", input: "42", want: 42},
        {name: "zero", input: "0", want: 0},
        {name: "empty", input: "", wantErr: true},
        {name: "negative", input: "-5", wantErr: true},
        {name: "non-numeric", input: "abc", wantErr: true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseAmount(tt.input)
            if tt.wantErr {
                if err == nil {
                    t.Fatalf("ParseAmount(%q) expected error, got %d", tt.input, got)
                }
                return
            }
            if err != nil {
                t.Fatalf("ParseAmount(%q) unexpected error: %v", tt.input, err)
            }
            if got != tt.want {
                t.Errorf("ParseAmount(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

Run single case: `go test -run TestParseAmount/zero`

### Parallel Subtests (independent cases)

```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel() // safe when tt is captured by value (Go 1.22+ loop semantics)
        got := compute(tt.input)
        if got != tt.want {
            t.Errorf("got %v, want %v", got, tt.want)
        }
    })
}
```

### t.Helper + t.Cleanup

```go
func setupDB(t *testing.T) *sql.DB {
    t.Helper() // failure lines point to caller, not here
    db, err := sql.Open("sqlite3", ":memory:")
    if err != nil {
        t.Fatalf("open db: %v", err)
    }
    t.Cleanup(func() { db.Close() }) // runs after test AND subtests
    return db
}
```

### t.Context() (Go 1.24+)

Instead of:
```go
ctx := context.Background()
```

Use in tests (context cancelled when test ends):
```go
func TestFetch(t *testing.T) {
    ctx := t.Context() // cancelled automatically on test end/failure
    result, err := client.Fetch(ctx, "https://example.com")
    ...
}
```

### Benchmark with b.Loop() (Go 1.24+)

Instead of:
```go
func BenchmarkOld(b *testing.B) {
    for i := 0; i < b.N; i++ {
        doWork()
    }
}
```

Use (avoids off-by-one allocation skew, cleaner semantics):
```go
func BenchmarkHash(b *testing.B) {
    data := make([]byte, 1024) // setup outside loop
    rand.Read(data)

    b.ResetTimer()
    for b.Loop() {
        _ = sha256.Sum256(data)
    }
}
// Run: go test -bench BenchmarkHash -benchmem ./...
```

Use `b.ReportAllocs()` to always print allocations regardless of flags.

### Fuzz Test Stub (Go 1.18+)

```go
func FuzzParseConfig(f *testing.F) {
    // Seed corpus: valid inputs the fuzzer starts from
    f.Add(`{"port": 8080}`)
    f.Add(`{}`)
    f.Add(`{"port": 0}`)

    f.Fuzz(func(t *testing.T, data string) {
        cfg, err := ParseConfig([]byte(data))
        if err != nil {
            return // invalid input is expected; must NOT panic
        }
        // Property assertions on valid output:
        if cfg.Port < 0 {
            t.Errorf("ParseConfig produced negative port: %d", cfg.Port)
        }
    })
}
```

Run with: `go test -fuzz FuzzParseConfig -fuzztime 30s ./...`

Corpus entries are saved to `testdata/fuzz/FuzzParseConfig/` when failures are found.

---

## Anti-Pattern Catalog

### Hardcoded Sleeps in Tests

**Impact:** HIGH — flaky tests that sometimes pass, sometimes fail based on machine load.

Instead of:
```go
go startServer()
time.Sleep(500 * time.Millisecond) // hope the server is up
resp, err := http.Get("http://localhost:8080/health")
```

Use:
```go
go startServer()
waitForReady(t, "http://localhost:8080/health", 2*time.Second)

func waitForReady(t *testing.T, url string, timeout time.Duration) {
    t.Helper()
    deadline := time.Now().Add(timeout)
    for time.Now().Before(deadline) {
        resp, err := http.Get(url)
        if err == nil && resp.StatusCode == 200 {
            return
        }
        time.Sleep(10 * time.Millisecond)
    }
    t.Fatalf("server at %s not ready after %v", url, timeout)
}
```

Detection:
```bash
rg 'time\.Sleep' --include='*_test.go' -n
```

### Global State Mutation in Tests

**Impact:** HIGH — tests interfere with each other, order-dependent failures.

Instead of:
```go
var defaultTimeout = 30 * time.Second // package-level var

func TestFoo(t *testing.T) {
    defaultTimeout = 1 * time.Second // mutates global state
    ...
}
```

Use:
```go
// Inject configuration via parameter or functional option
func TestFoo(t *testing.T) {
    svc := NewService(WithTimeout(1 * time.Second))
    ...
}
```

Detection:
```bash
# Find package-level var assignments inside test functions
rg '^\s+\w+ = ' --include='*_test.go' -n

# Find tests that modify os.Environ (another common global)
rg 'os\.Setenv|os\.Unsetenv' --include='*_test.go' -n
```

### Non-Parallel Independent Subtests

**Impact:** MEDIUM — unnecessarily slow test suite.

When subtests share no state, add `t.Parallel()`:

```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        t.Parallel() // add this when subtests are independent
        ...
    })
}
```

Detection:
```bash
# Find t.Run blocks without t.Parallel
rg 't\.Run\(' --include='*_test.go' -n -A 3 | rg -v 't\.Parallel'
# (Review results: some tests legitimately need serial execution)
```

### Old Benchmark Loop (pre-1.24)

Detection:
```bash
rg 'for i := 0; i < b\.N; i\+\+' --include='*_test.go' -n
```

Fix: replace with `for b.Loop() {` (Go 1.24+).

### context.Background() in Tests (pre-1.24 pattern)

Detection:
```bash
rg 'context\.Background\(\)' --include='*_test.go' -n
```

Fix: use `t.Context()` in Go 1.24+ — context is cancelled when the test ends, which prevents goroutine leaks from tests that fail early.

---

## Error-Fix Mappings

| Error / Symptom | Cause | Fix |
|---|---|---|
| `--- FAIL: TestX/case_name (0.00s)` line points to helper | Helper missing `t.Helper()` | Add `t.Helper()` at top of helper func |
| Test passes alone but fails in suite | Global state mutation | Isolate state per test; use `t.Setenv` instead of `os.Setenv` |
| Fuzz finds panic on empty input | Missing nil/empty guard | Add input validation before processing |
| Benchmark allocations fluctuate between runs | Setup code inside loop | Move setup before `b.ResetTimer()` or outside `b.Loop()` |
| `-race` fails only in CI | Missing `t.Parallel()` combining with shared global | Add mutex or remove global state |
| Subtest never runs | Typo in `-run` filter | Use `go test -v -run TestFoo` to list subtests |
| `context.DeadlineExceeded` in test | `t.Context()` cancelled because test timed out | Increase `-timeout` flag or fix slow operation |

---

## Detection Commands Reference

```bash
# Find all time.Sleep in test files (flakiness risk)
rg 'time\.Sleep' --include='*_test.go' -n

# Find old benchmark loop pattern
rg 'for i := 0; i < b\.N; i\+\+' --include='*_test.go' -n

# Find context.Background() in tests (upgrade to t.Context() in Go 1.24+)
rg 'context\.Background\(\)' --include='*_test.go' -n

# Find t.Run blocks missing t.Parallel
rg 't\.Run\(' --include='*_test.go' -l

# Find os.Setenv/os.Unsetenv in tests (should use t.Setenv)
rg 'os\.(Setenv|Unsetenv)' --include='*_test.go' -n

# Find tests missing t.Helper() in helper functions (heuristic)
rg 'func \w+\(t \*testing\.T' --include='*_test.go' -n

# Run tests with race detector
go test -race ./...

# Run fuzz for 30 seconds
go test -fuzz FuzzXxx -fuzztime 30s ./...

# Run benchmarks with memory stats
go test -bench=. -benchmem ./...

# Run single subtest by name
go test -run TestFoo/subtest_name -v ./...

# Check go.mod version before applying 1.24+ patterns
grep '^go ' go.mod
```
