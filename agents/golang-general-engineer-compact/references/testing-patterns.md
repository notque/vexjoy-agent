# Go Testing Patterns — Compact Reference

> **Scope**: Table-driven tests, subtests, benchmarks, fuzzing, goroutine leak detection. Not integration infra.
> **Version range**: Go 1.21+ (t.Context/b.Loop require 1.24+)

Default: table-driven tests with `t.Run`. Common gaps: missing `t.Cleanup`, no `t.Context()` for goroutines, no `t.Parallel()` on independent subtests.

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `t.Context()` | `1.24+` | Test goroutines need cancel signal | Go < 1.24 (use `context.Background()`) |
| `b.Loop()` | `1.24+` | All benchmarks | Go < 1.24 |
| `go test -fuzz=FuzzFoo` | `1.18+` | Input parsing, protocol handling | Pure computation with no external input |
| `t.Cleanup(fn)` | `1.14+` | Resource teardown in helpers | Functions where deferred cleanup works fine |
| `t.Setenv` | `1.17+` | Setting env vars in tests | Tests that share process-global state and need serialization |
| `t.TempDir()` | `1.15+` | Temp files in tests | Never — always prefer over os.TempDir() |

---

## Correct Patterns

### Table-Driven Test (Canonical Form)

```go
func TestParse(t *testing.T) {
    t.Parallel() // Top-level: run parallel with other test functions

    tests := []struct {
        name    string
        input   string
        want    string
        wantErr bool
    }{
        {"valid input",   "hello",  "HELLO",  false},
        {"empty string",  "",       "",       true},
        {"special chars", "a b\tc", "A B\tC", false},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            t.Parallel() // Subtests: run parallel with each other

            got, err := Parse(tt.input)
            if (err != nil) != tt.wantErr {
                t.Fatalf("Parse(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("Parse(%q) = %q, want %q", tt.input, got, tt.want)
            }
        })
    }
}
```

`t.Parallel()` at both levels maximizes parallelism. `t.Fatalf` on error prevents nil-deref panics.

---

### Test Helper with t.Helper()

```go
func requireNoError(t *testing.T, err error, msg string) {
    t.Helper() // Makes failure point to caller, not this function
    if err != nil {
        t.Fatalf("%s: %v", msg, err)
    }
}

func createTempDB(t *testing.T) *sql.DB {
    t.Helper()
    db, err := sql.Open("sqlite3", t.TempDir()+"/test.db")
    requireNoError(t, err, "open db")
    t.Cleanup(func() { db.Close() }) // Cleanup registered here, runs at test end
    return db
}
```

`t.Helper()` makes failures point to caller. `t.Cleanup` runs even after `t.FailNow()`.

---

### Fuzz Test (Go 1.18+)

```go
func FuzzParseURL(f *testing.F) {
    // Seed corpus
    f.Add("https://example.com/path?q=1")
    f.Add("http://localhost:8080")
    f.Add("") // Edge case

    f.Fuzz(func(t *testing.T, input string) {
        // Should never panic — fuzzer checks for panics
        u, err := ParseURL(input)
        if err != nil {
            return // Invalid input is fine
        }
        // Roundtrip property: parse → serialize → parse should be stable
        u2, err := ParseURL(u.String())
        if err != nil {
            t.Errorf("roundtrip failed: original %q, serialized %q: %v", input, u.String(), err)
        }
        _ = u2
    })
}
```

Fuzz tests find edge cases table tests miss. Roundtrip property is a strong invariant.

---

## Pattern Catalog

### Add t.Parallel() to Independent Subtests
**Detection**:
```bash
grep -A5 't.Run(' --include="*_test.go" -rn . | grep -v 't.Parallel'
rg 't\.Run\(' --type go -A 3 | grep -v 't\.Parallel'
```

**Signal**:
```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // No t.Parallel() — runs sequentially
        result := expensiveCompute(tt.input)
        ...
    })
}
```

**Why**: Sequential subtests 10-100x slower on multi-core.

**Fix**: `t.Parallel()` as first line. Shared state: move inside struct or `t.Cleanup`.

---

### Use t.TempDir() for Test Temporary Files
**Detection**:
```bash
grep -rn 'os.TempDir()' --include="*_test.go"
rg 'os\.TempDir\(\)' --type go --glob '*_test.go'
```

**Signal**:
```go
func TestWriteFile(t *testing.T) {
    dir := os.TempDir() // Manual cleanup needed
    defer os.RemoveAll(dir)
    ...
}
```

**Why**: `os.TempDir()` = system dir, shared across runs. Panic before defer = leaked files.

**Preferred action**:
```go
func TestWriteFile(t *testing.T) {
    dir := t.TempDir() // Automatically cleaned up after test, even on failure
    ...
}
```

**Version note**: `t.TempDir()` available since Go 1.15.

---

### Use t.Context() for Test Goroutines (Go 1.24+)
**Detection**:
```bash
grep -rn 'context.Background()' --include="*_test.go"
rg 'context\.Background\(\)' --type go --glob '*_test.go'
```

**Signal**:
```go
func TestServer(t *testing.T) {
    ctx := context.Background() // Never canceled — goroutines may outlive test
    go startServer(ctx)
    ...
}
```

**Why**: `context.Background()` goroutines run until process exit. `goleak` detects them.

**Preferred action** (Go 1.24+):
```go
func TestServer(t *testing.T) {
    ctx := t.Context() // Canceled when test ends, cancels dependent goroutines
    go startServer(ctx)
    ...
}
```

**Preferred action** (Go < 1.24):
```go
func TestServer(t *testing.T) {
    ctx, cancel := context.WithCancel(context.Background())
    t.Cleanup(cancel)
    go startServer(ctx)
    ...
}
```

---

### Reset Timer Before Benchmark Loop
**Detection**:
```bash
grep -B5 'for.*b\.N' --include="*_test.go" -rn . | grep -v 'b.ResetTimer'
rg 'for i := 0.*b\.N' --type go --glob '*_test.go'
```

**Signal**:
```go
func BenchmarkProcess(b *testing.B) {
    data := loadLargeDataset() // Counted in benchmark time!
    for i := 0; i < b.N; i++ {
        process(data)
    }
}
```

**Why**: Setup time counted in benchmark, skewing results.

**Preferred action** (Go 1.24+):
```go
func BenchmarkProcess(b *testing.B) {
    data := loadLargeDataset()
    b.ResetTimer() // Start counting after setup (still useful with b.Loop)
    for b.Loop() { // b.Loop() is idiomatic Go 1.24+
        process(data)
    }
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `panic: t.Parallel called after t.Cleanup` | `t.Parallel()` must be first line of subtest | Move `t.Parallel()` to line 1 of the `t.Run` func |
| `panic: testing: t.Fatal called after test finished` | Goroutine calls t.Fatal after test ended | Use `t.Context()` so goroutine is canceled before test ends |
| `goleak: found unexpected goroutines` | Test started goroutines that outlived the test | Pass `t.Context()` to all goroutines; add `goleak.VerifyNone(t)` |
| `flag provided but not defined: -test.fuzz` | Running fuzz on Go < 1.18 | Upgrade Go; fuzz requires 1.18+ |
| `testing: test ended with leaked goroutines` | Same as goleak above | Add `t.Cleanup(cancel)` pattern |

---

## Detection Commands Reference

```bash
# Missing t.Parallel() in subtests
grep -A5 't.Run(' --include="*_test.go" -rn . | grep -B5 'func(t' | grep -v 'Parallel'

# Using os.TempDir in tests (upgrade to t.TempDir)
grep -rn 'os.TempDir()' --include="*_test.go"

# context.Background() in tests (upgrade to t.Context())
grep -rn 'context.Background()' --include="*_test.go"

# Old benchmark loop (upgrade to b.Loop())
grep -rn 'for i := 0; i < b.N' --include="*_test.go"

# Run tests with race detector
go test -race ./...

# Run with goleak integration (if installed)
go test -v ./... -run TestFoo
```

---

## See Also

- `concurrency-patterns.md` — goroutine lifecycle, wg.Go, context cancellation
- `go-patterns.md` — modern Go idioms table with version annotations
