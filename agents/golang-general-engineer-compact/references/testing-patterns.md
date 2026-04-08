# Go Testing Patterns — Compact Reference

> **Scope**: Table-driven tests, subtests, benchmarks, fuzzing, goroutine leak detection. Does NOT cover integration test infrastructure.
> **Version range**: Go 1.21+ (t.Context requires 1.24+, b.Loop requires 1.24+)
> **Generated**: 2026-04-08

---

## Overview

Go testing has evolved substantially from 1.21 to 1.24+. The compact agent default is table-driven tests with `t.Run` subtests. The most common gap is test cleanup: forgetting `t.Cleanup`, not using `t.Context()` for goroutines, and missing `t.Parallel()` on independent subtests.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `t.Context()` | `1.24+` | Test goroutines need cancel signal | Go < 1.24 (use `context.Background()`) |
| `b.Loop()` | `1.24+` | All benchmarks | Go < 1.24 |
| `go test -fuzz=FuzzFoo` | `1.18+` | Input parsing, protocol handling | Pure computation with no external input |
| `t.Cleanup(fn)` | `1.14+` | Resource teardown in helpers | Functions where deferred cleanup works fine |
| `t.Setenv` | `1.17+` | Setting env vars in tests | Tests that must NOT run in parallel |
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

**Why**: `t.Parallel()` at both levels maximizes parallelism. `t.Fatalf` on error prevents confusing nil-deref panics on subsequent assertions.

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

**Why**: `t.Helper()` is essential — without it, failure line numbers point to the helper, not the caller. `t.Cleanup` is more reliable than defer in helpers because it runs even after `t.FailNow()`.

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

**Why**: Fuzz tests find edge cases like empty strings, null bytes, and extremely long inputs that table tests miss. The roundtrip property is a strong invariant to check.

---

## Anti-Pattern Catalog

### ❌ Missing t.Parallel() in Subtests

**Detection**:
```bash
grep -A5 't.Run(' --include="*_test.go" -rn . | grep -v 't.Parallel'
rg 't\.Run\(' --type go -A 3 | grep -v 't\.Parallel'
```

**What it looks like**:
```go
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        // No t.Parallel() — runs sequentially
        result := expensiveCompute(tt.input)
        ...
    })
}
```

**Why wrong**: Sequential subtests are 10-100x slower on multi-core machines. `go test -count=10` reveals this.

**Fix**: Add `t.Parallel()` as first line of each subtest. If subtests share mutable state, move that state inside the struct or use `t.Cleanup` for isolation.

---

### ❌ Using os.TempDir() Instead of t.TempDir()

**Detection**:
```bash
grep -rn 'os.TempDir()' --include="*_test.go"
rg 'os\.TempDir\(\)' --type go --glob '*_test.go'
```

**What it looks like**:
```go
func TestWriteFile(t *testing.T) {
    dir := os.TempDir() // Manual cleanup needed
    defer os.RemoveAll(dir)
    ...
}
```

**Why wrong**: `os.TempDir()` returns the system temp dir, not a test-scoped dir. Multiple test runs in the same process share it. If the test panics before defer, temp files leak.

**Fix**:
```go
func TestWriteFile(t *testing.T) {
    dir := t.TempDir() // Automatically cleaned up after test, even on failure
    ...
}
```

**Version note**: `t.TempDir()` available since Go 1.15.

---

### ❌ Context Not Canceled in Test Goroutines

**Detection**:
```bash
grep -rn 'context.Background()' --include="*_test.go"
rg 'context\.Background\(\)' --type go --glob '*_test.go'
```

**What it looks like**:
```go
func TestServer(t *testing.T) {
    ctx := context.Background() // Never canceled — goroutines may outlive test
    go startServer(ctx)
    ...
}
```

**Why wrong**: Goroutines started with `context.Background()` in tests run until process exit, causing goroutine leaks detected by `goleak`.

**Fix** (Go 1.24+):
```go
func TestServer(t *testing.T) {
    ctx := t.Context() // Canceled when test ends, cancels dependent goroutines
    go startServer(ctx)
    ...
}
```

**Fix** (Go < 1.24):
```go
func TestServer(t *testing.T) {
    ctx, cancel := context.WithCancel(context.Background())
    t.Cleanup(cancel)
    go startServer(ctx)
    ...
}
```

---

### ❌ Benchmark Without Reset or Skip Setup

**Detection**:
```bash
grep -B5 'for.*b\.N' --include="*_test.go" -rn . | grep -v 'b.ResetTimer'
rg 'for i := 0.*b\.N' --type go --glob '*_test.go'
```

**What it looks like**:
```go
func BenchmarkProcess(b *testing.B) {
    data := loadLargeDataset() // Counted in benchmark time!
    for i := 0; i < b.N; i++ {
        process(data)
    }
}
```

**Why wrong**: `loadLargeDataset()` runs once but the time is counted in benchmark initialization, skewing results.

**Fix** (Go 1.24+):
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
