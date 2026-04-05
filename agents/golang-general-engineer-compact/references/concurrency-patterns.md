# Concurrency Patterns Reference

<!-- Loaded by golang-general-engineer-compact when task involves: goroutines, channels, worker pool, fan-out, fan-in, errgroup, WaitGroup, mutex, race conditions, goroutine leaks -->
<!-- scope: Go concurrency correctness and patterns | version-range: Go 1.18-1.26+ | date: 2026-04-05 -->

Correct concurrency patterns and the anti-patterns that cause goroutine leaks, races, and panics. The agent body has a minimal worker pool; this file has full patterns with context cancellation and errgroup.

---

## Pattern Table

| Pattern | When to Use | Key Package | Go Version |
|---|---|---|---|
| Worker pool with errgroup | Bounded parallelism, stop-on-error | `golang.org/x/sync/errgroup` | 1.18+ |
| Fan-out / fan-in | Launch N concurrent ops, collect results | `errgroup` | 1.18+ |
| Pipeline (stage chain) | Stream processing, channel-per-stage | `context` | 1.18+ |
| `sync.Once` / `OnceValue` | Lazy init, run exactly once | `sync` | 1.18 / 1.21 |
| `wg.Go(fn)` | Fire goroutines without Add/Done | `sync` | **1.25+** |
| Semaphore channel | Cap goroutine count without errgroup | stdlib | 1.18+ |
| `context.WithCancelCause` | Cancel with a descriptive reason | `context` | 1.20+ |

---

## Correct Patterns

### Worker Pool with Context Cancellation

Bounded workers; first error cancels remaining work via errgroup context.

```go
import "golang.org/x/sync/errgroup"

func runPool(ctx context.Context, jobs []Job, concurrency int) error {
    g, gctx := errgroup.WithContext(ctx)
    g.SetLimit(concurrency) // cap active goroutines

    for _, job := range jobs {
        g.Go(func() error {
            // gctx is cancelled if any sibling errors or parent cancels
            return process(gctx, job)
        })
    }
    return g.Wait()
}
```

For channel-based dispatch (useful when jobs arrive dynamically):

```go
func workerPool(ctx context.Context, jobs <-chan Job, concurrency int) error {
    g, gctx := errgroup.WithContext(ctx)

    for range concurrency {
        g.Go(func() error {
            for {
                select {
                case <-gctx.Done():
                    return gctx.Err()
                case job, ok := <-jobs:
                    if !ok {
                        return nil // channel closed, done
                    }
                    if err := process(gctx, job); err != nil {
                        return fmt.Errorf("process job %s: %w", job.ID, err)
                    }
                }
            }
        })
    }
    return g.Wait()
}
```

### Fan-out / Fan-in with errgroup

Launch N concurrent fetches; collect into pre-allocated slice (index-safe, no mutex needed).

```go
func fetchAll(ctx context.Context, urls []string) ([]Result, error) {
    g, gctx := errgroup.WithContext(ctx)
    results := make([]Result, len(urls))

    for i, url := range urls {
        g.Go(func() error {
            r, err := fetch(gctx, url)
            if err != nil {
                return fmt.Errorf("fetch %s: %w", url, err)
            }
            results[i] = r // safe: each goroutine owns its index
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

### wg.Go() (Go 1.25+)

Replaces the Add(1)/go/Done dance entirely.

Instead of:
```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)
    go func(it Item) {
        defer wg.Done()
        process(it)
    }(item)
}
wg.Wait()
```

Use (Go 1.25+):
```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Go(func() {
        process(item) // item captured correctly; loop var is per-iteration since Go 1.22
    })
}
wg.Wait()
```

### Channel Ownership (producer closes)

```go
func produce(ctx context.Context, items []Item) <-chan Item {
    ch := make(chan Item)
    go func() {
        defer close(ch) // producer always closes
        for _, item := range items {
            select {
            case <-ctx.Done():
                return
            case ch <- item:
            }
        }
    }()
    return ch // return as receive-only
}
```

---

## Anti-Pattern Catalog

### Goroutine Leak: No ctx.Done

**Impact:** CRITICAL — goroutine runs forever, leaks memory/resources.

Instead of:
```go
go func() {
    for {
        doWork()
    }
}()
```

Use:
```go
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
```

Detection:
```bash
# Find goroutines without ctx.Done (heuristic: bare for loops in go func)
rg 'go func\(\)' --include='*.go' -n -A 5 | grep -v 'ctx\.Done\|select'

# Use golangci-lint contextcheck linter
golangci-lint run --enable contextcheck ./...
```

### wg.Add Inside Goroutine

**Impact:** HIGH — race condition: `Wait()` may return before goroutine runs.

Instead of:
```go
var wg sync.WaitGroup
go func() {
    wg.Add(1) // too late — Wait() may already be past this
    defer wg.Done()
    doWork()
}()
wg.Wait()
```

Use:
```go
var wg sync.WaitGroup
wg.Add(1) // Add before launching
go func() {
    defer wg.Done()
    doWork()
}()
wg.Wait()
```

Detection:
```bash
# Find wg.Add inside a goroutine body
rg 'go func' --include='*.go' -n -A 3 | rg 'wg\.Add'
```

### Sending on Closed Channel (panic)

**Impact:** CRITICAL — runtime panic.

Instead of:
```go
close(ch)
ch <- value // panic: send on closed channel
```

Use the ownership rule: only the producer closes, and only after all sends are done.

```go
// Safe: producer signals done via close, consumer drains
func producer(ctx context.Context) <-chan int {
    ch := make(chan int)
    go func() {
        defer close(ch)
        for i := range 10 {
            select {
            case <-ctx.Done():
                return
            case ch <- i:
            }
        }
    }()
    return ch
}
```

Detection:
```bash
# Find close() calls — review each to ensure no concurrent sends follow
rg '\bclose\(' --include='*.go' -n

# Run race detector on tests
go test -race ./...
```

### Lock Held During I/O

**Impact:** HIGH — degrades throughput, risks deadlock.

Instead of:
```go
func (s *Service) Refresh(id string) error {
    s.mu.Lock()
    defer s.mu.Unlock()
    data, err := s.client.Fetch(id) // network call under lock
    s.cache[id] = data
    return err
}
```

Use:
```go
func (s *Service) Refresh(id string) error {
    data, err := s.client.Fetch(id) // fetch without lock
    if err != nil {
        return fmt.Errorf("fetch %s: %w", id, err)
    }
    s.mu.Lock()
    s.cache[id] = data
    s.mu.Unlock()
    return nil
}
```

### Mutex Copied by Value

**Impact:** HIGH — invalidates mutex state, causes deadlock.

Detection:
```bash
go vet ./...
# Reports: "copylocks: ... passes lock by value"

rg 'sync\.Mutex|sync\.RWMutex' --include='*.go' -n
# Review each: must be in a struct accessed via pointer
```

---

## Error-Fix Mappings

| Error / Symptom | Cause | Fix |
|---|---|---|
| `go test -race` DATA RACE | Shared memory without synchronization | Add mutex or use channels |
| `panic: send on closed channel` | Multiple closers or send after close | Enforce single producer/closer |
| `fatal error: all goroutines are asleep` | Deadlock — all goroutines blocked | Audit channel/mutex pairing; check for WaitGroup misuse |
| `wg.Add called with negative delta` | `wg.Done()` called more times than `Add()` | Match each `Add(n)` with exactly n `Done()` calls |
| `context.DeadlineExceeded` unexpectedly fast | Timeout set on wrong context level | Check where `WithTimeout` is applied; parent may already be expired |
| `goroutine leak detected` (goleak) | Goroutine has no exit path | Add `ctx.Done()` select case; ensure channel is eventually closed |

---

## Detection Commands Reference

```bash
# Race detector (run in CI)
go test -race ./...

# Static goroutine leak detection (requires golangci-lint)
golangci-lint run --enable gocritic,contextcheck ./...

# Find all WaitGroup.Add calls for review
rg 'wg\.Add\(' --include='*.go' -n

# Find goroutine launches
rg '\bgo func\b|\bgo \w' --include='*.go' -n

# Find all channel close calls
rg '\bclose\(' --include='*.go' -n

# Check for missing defer cancel()
rg 'context\.With(Cancel|Timeout|Deadline)' --include='*.go' -n -A 2 | rg -v 'defer.*cancel'

# Detect old wg.Add(1)/Done pattern (replace with wg.Go in Go 1.25+)
rg 'wg\.Add\(1\)' --include='*.go' -n

# Check go.mod for Go version before applying 1.25+ patterns
grep '^go ' go.mod
```
