# Go Concurrency Patterns — Compact Reference

> **Scope**: Goroutine lifecycle, channel patterns, sync primitives, context propagation. Does NOT cover networking or I/O.
> **Version range**: Go 1.21+ (compact idioms require 1.21+, modern WaitGroup requires 1.25+)
> **Generated**: 2026-04-08 — verify version-specific content against current release notes

---

## Overview

Go concurrency bugs fall into three classes: goroutine leaks (no exit strategy), data races (shared state without sync), and deadlocks (circular channel waits). The compact agent's job is to catch these before they reach production. Go 1.25+ `wg.Go()` eliminates the Add/Done race that was the #1 WaitGroup mistake.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `wg.Go(fn)` | `1.25+` | Spawning goroutines with WaitGroup | Target version < 1.25 (use Add/Done) |
| `for range n` | `1.22+` | Simple N-iteration goroutine dispatch | Needing loop index type other than int |
| `iter.Seq[T]` | `1.23+` | Custom iterators over goroutine results | Simple in-memory slices |
| `t.Context()` in tests | `1.24+` | Test goroutines need a cancel signal | Go < 1.24 (use `context.Background()`) |
| `b.Loop()` | `1.24+` | Benchmarks — replaces `for i := 0; i < b.N; i++` | Go < 1.24 |

---

## Correct Patterns

### Worker Pool with Context (Go 1.25+ compact form)

Use `wg.Go()` to avoid the manual Add/Done pattern. Never spawn goroutines without a context stop signal.

```go
func runPool(ctx context.Context, jobs <-chan Job) error {
    var wg sync.WaitGroup
    for range 4 { // Go 1.22+: for range n
        wg.Go(func() { // Go 1.25+: wg.Go eliminates Add/Done race
            for {
                select {
                case j, ok := <-jobs:
                    if !ok {
                        return
                    }
                    process(ctx, j)
                case <-ctx.Done():
                    return
                }
            }
        })
    }
    wg.Wait()
    return ctx.Err()
}
```

**Why**: `wg.Go()` ensures Add happens before goroutine launch — the classic race with `go func(){ wg.Add(1) ...}()` is impossible. Context cancel provides clean shutdown.

---

### Fan-out / Fan-in Pipeline

```go
func fanOut[T any](ctx context.Context, in <-chan T, n int, fn func(T) T) <-chan T {
    out := make(chan T, n)
    var wg sync.WaitGroup
    for range n {
        wg.Go(func() {
            defer func() {
                // Only close when all workers done (fan-in handles this)
            }()
            for v := range in {
                select {
                case out <- fn(v):
                case <-ctx.Done():
                    return
                }
            }
        })
    }
    go func() {
        wg.Wait()
        close(out) // Close after all writers done
    }()
    return out
}
```

**Why**: Only the goroutine that owns channel creation closes it. Multiple writers need a final goroutine to close after all writers exit.

---

## Anti-Pattern Catalog

### ❌ Goroutine Without Exit Strategy

**Detection**:
```bash
grep -rn 'go func()' --include="*.go" | grep -v "_test.go"
rg 'go func\(\)' --type go -l
```

**What it looks like**:
```go
func startBackgroundJob() {
    go func() {
        for {
            doWork() // No ctx.Done(), no stop channel
        }
    }()
}
```

**Why wrong**: The goroutine runs until process exit. If called repeatedly (e.g., in tests), goroutines accumulate. `goleak` in tests will catch this; production just slowly runs out of memory.

**Fix**:
```go
func startBackgroundJob(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                doWork()
            }
        }
    }()
}
```

**Version note**: For Go 1.24+ tests, use `t.Context()` instead of `context.Background()` so goroutines are canceled when the test ends.

---

### ❌ WaitGroup Add Inside Goroutine (Pre-1.25)

**Detection**:
```bash
grep -A2 'go func' --include="*.go" -rn . | grep 'wg.Add'
rg 'go func.*\{' --type go -A 3 | grep 'wg\.Add'
```

**What it looks like**:
```go
for _, item := range items {
    go func(i Item) {
        wg.Add(1) // Race: Wait() can return before Add() runs
        defer wg.Done()
        process(i)
    }(item)
}
wg.Wait()
```

**Why wrong**: `wg.Wait()` may return before some goroutines call `wg.Add(1)`. This is a race condition — Go's race detector catches it, but only if the timing is unlucky.

**Fix** (Go < 1.25):
```go
for _, item := range items {
    wg.Add(1) // Add BEFORE spawning goroutine
    go func(i Item) {
        defer wg.Done()
        process(i)
    }(item)
}
wg.Wait()
```

**Fix** (Go 1.25+):
```go
for _, item := range items {
    item := item
    wg.Go(func() { process(item) }) // wg.Go handles Add+Done
}
wg.Wait()
```

---

### ❌ Closing Channel from Multiple Writers

**Detection**:
```bash
grep -rn 'close(' --include="*.go" | grep -v "_test.go"
rg 'close\(ch\)' --type go
```

**What it looks like**:
```go
for _, worker := range workers {
    go func(w Worker) {
        result := w.Compute()
        results <- result
        close(results) // Panic: multiple goroutines close same channel
    }(worker)
}
```

**Why wrong**: Only one goroutine should close a channel. Multiple goroutines closing the same channel causes a runtime panic.

**Fix**:
```go
var wg sync.WaitGroup
for _, worker := range workers {
    wg.Go(func() {
        results <- worker.Compute()
    })
}
go func() {
    wg.Wait()
    close(results) // Single owner closes after all writers done
}()
```

---

### ❌ Benchmark Using b.N Loop (Pre-1.24)

**Detection**:
```bash
grep -rn 'for i := 0; i < b.N' --include="*_test.go"
rg 'i < b\.N' --type go
```

**What it looks like**:
```go
func BenchmarkOp(b *testing.B) {
    for i := 0; i < b.N; i++ { // Old idiom, still works but verbose
        op()
    }
}
```

**Fix** (Go 1.24+):
```go
func BenchmarkOp(b *testing.B) {
    for b.Loop() { // b.Loop() is idiomatic Go 1.24+
        op()
    }
}
```

**Version note**: `b.Loop()` was added in Go 1.24. It also avoids benchmark-startup overhead by not counting setup iterations. For Go < 1.24, the `for i := 0; i < b.N; i++` idiom is correct.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `panic: send on closed channel` | Sender doesn't know channel is closed | Use select with ok check: `v, ok := <-ch; if !ok { return }` |
| `panic: close of closed channel` | Multiple goroutines closing same channel | Designate single owner; use sync.Once for safety |
| `fatal error: all goroutines are asleep - deadlock!` | Goroutine waiting on channel with no sender | Check that producer goroutine is running and channel has buffer or receiver |
| `DATA RACE` from `-race` detector on WaitGroup | `wg.Add()` inside goroutine | Move `wg.Add()` before `go` statement, or use `wg.Go()` (1.25+) |
| `panic: sync: WaitGroup is reused before previous Wait has returned` | Reusing WaitGroup before Wait returns | Use a new WaitGroup per batch, or wait fully before reuse |

---

## Detection Commands Reference

```bash
# Goroutines without exit strategy
grep -rn 'go func()' --include="*.go" | grep -v '_test.go'

# WaitGroup Add inside goroutine
grep -B1 'wg.Add' --include="*.go" -rn . | grep 'go func'

# Benchmark old-style loop (upgrade to b.Loop())
grep -rn 'for i := 0; i < b.N' --include="*_test.go"

# Close calls (verify single owner)
grep -rn 'close(' --include="*.go" | grep -v '_test.go'

# Run race detector
go test -race ./...
```

---

## See Also

- `testing-patterns.md` — `t.Context()`, parallel tests, goroutine leak detection with goleak
- `go-patterns.md` — modern Go idioms table (wg.Go, b.Loop, for range n)
