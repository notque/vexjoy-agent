---
name: go-concurrency
description: "Go concurrency patterns: goroutines, channels, sync."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
command: /go-concurrency
routing:
  force_route: true
  triggers:
    - goroutine
    - channel
    - chan
    - sync.Mutex
    - sync.WaitGroup
    - worker pool
    - fan-in
    - rate limit
    - concurrent
    - context.Context
    - race condition
    - deadlock
    - "goroutine parallel"
    - "Go parallel"
    - "goroutine fan-out"
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
---

# Go Concurrency Skill

Guide implementation of correct, leak-free concurrent Go code using goroutines, channels, sync primitives, and context propagation. Works by assessing whether concurrency is justified, selecting the right primitive, enforcing context propagation, implementing the pattern, and verifying with the race detector.

## Instructions

### Phase 1: Assess Concurrency Need

**Goal**: Determine whether concurrency is justified before adding complexity.

Read and follow the repository's CLAUDE.md before writing any concurrent code, because project-specific conventions (naming, package structure, error handling) override general patterns.

Before writing concurrent code, answer these questions:

1. **Is the work I/O-bound?** (network, database, filesystem) -- concurrency likely helps
2. **Is the work CPU-bound?** -- concurrency helps only if parallelizable
3. **Is there a measured bottleneck?** -- if not measured, don't assume

If none apply, write sequential code. Sequential code is correct by default -- concurrency adds goroutine lifecycle management, synchronization, and race risk. Only introduce it when I/O, CPU parallelism, or a measured bottleneck justifies the complexity. Assuming "sequential is too slow" without profiling is a common mistake; profile first, then add concurrency.

**Gate**: At least one of the three conditions (I/O-bound, CPU-bound, measured bottleneck) is met. Proceed only when gate passes.

### Phase 2: Choose the Right Primitive

**Goal**: Select the minimal primitive that solves the concurrency need.

| Need | Primitive | When |
|------|-----------|------|
| Communicate between goroutines | Channel | Data flows from producer to consumer |
| Protect shared state | `sync.Mutex` | Multiple goroutines read/write same data |
| Read-heavy shared state | `sync.RWMutex` | Many readers, few writers |
| Wait for goroutines to finish | `errgroup.Group` | Need error collection + context cancel |
| Wait without error collection | `sync.WaitGroup` | Fire-and-forget goroutines |
| One-time initialization | `sync.Once` | Lazy singleton, config loading |
| Simple shared counter | `atomic.Int64` | Increment/read without mutex overhead |

Selection guidance:

- Prefer `errgroup.Group` over `sync.WaitGroup` because errgroup collects errors and cancels remaining goroutines on first failure, which is what you want in most production scenarios.
- Use `atomic.Int64` or `atomic.Value` for simple shared counters instead of mutex because atomic operations avoid lock contention and are sufficient when the shared state is a single value.
- Return `<-chan T` (receive-only) from producer functions because it prevents callers from accidentally closing or sending on a channel they don't own.
- Size buffered channels to match expected backpressure, not arbitrary large numbers, because oversized buffers hide flow-control bugs that surface under production load.
- When you need a custom rate limiter instead of `golang.org/x/time/rate`, build a token-bucket implementation -- but only when the standard library doesn't meet your needs.

**Gate**: Primitive selected with clear justification. Proceed only when gate passes.

### Phase 3: Context Propagation

**Goal**: Wire context through all cancellable operations so goroutines respond to cancellation.

Accept `context.Context` as the first parameter for all I/O or cancellable operations because a function that's fast today may become slow under load tomorrow, and retrofitting context is harder than passing it from the start.

```go
func FetchData(ctx context.Context, id string) (*Data, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    resultCh := make(chan *Data, 1)
    errCh := make(chan error, 1)

    go func() {
        data, err := slowOperation(id)
        if err != nil {
            errCh <- err
            return
        }
        resultCh <- data
    }()

    select {
    case data := <-resultCh:
        return data, nil
    case err := <-errCh:
        return nil, fmt.Errorf("fetch failed: %w", err)
    case <-ctx.Done():
        return nil, fmt.Errorf("fetch cancelled: %w", ctx.Err())
    }
}
```

Every `select` statement in concurrent code must include a `case <-ctx.Done()` because without it, a goroutine blocks forever if the channel never receives and the upstream context is cancelled -- this is the most common source of goroutine leaks.

When to use context vs not:

```go
// USE context: I/O, cancellable operations, request-scoped values
func FetchUserData(ctx context.Context, userID string) (*User, error) { ... }

// NO context needed: pure computation
func CalculateTotal(prices []float64) float64 { ... }
```

When gopls MCP tools are available, use `go_symbol_references` to trace channel flow and `go_file_context` to understand goroutine spawn sites -- this helps verify context propagation through concurrent call chains.

**Gate**: All I/O operations accept context, all `select` statements include `<-ctx.Done()`. Proceed only when gate passes.

### Phase 4: Implement the Pattern

**Goal**: Write the concurrent code using the selected primitive with correct lifecycle management.

**Sync Primitives**

Lock only the critical section and use `defer mu.Unlock()` immediately after `mu.Lock()` because early returns or panics between Lock and Unlock cause deadlocks that are extremely difficult to diagnose in production.

```go
// Mutex for state protection
type SafeCounter struct {
    mu    sync.Mutex
    count int
}

func (c *SafeCounter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

// RWMutex for read-heavy workloads
type Cache struct {
    mu    sync.RWMutex
    items map[string]any
}

func (c *Cache) Get(key string) (any, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    item, ok := c.items[key]
    return item, ok
}

func (c *Cache) Set(key string, value any) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items[key] = value
}
```

**errgroup for concurrent work with error handling**

Prefer `errgroup` over `sync.WaitGroup` because it collects errors and cancels remaining goroutines on first failure:

```go
import "golang.org/x/sync/errgroup"

func ProcessAll(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)

    for _, item := range items {
        g.Go(func() error {
            return process(ctx, item)  // Go 1.22+: item captured correctly
        })
    }

    return g.Wait()
}
```

Use Go 1.22+ loop variable semantics -- the `item` variable is per-iteration, so legacy `item := item` shadows are unnecessary in new code.

**sync.Once for one-time initialization**

```go
type Config struct {
    once   sync.Once
    config *AppConfig
    err    error
}

func (c *Config) Load() (*AppConfig, error) {
    c.once.Do(func() {
        c.config, c.err = loadConfigFromFile()
    })
    return c.config, c.err
}
```

**Channel patterns: buffered vs unbuffered**

Only the sender closes a channel because closing from the receiver side causes panics if the sender is still sending, and multiple receivers may double-close. Use `defer close(ch)` in the goroutine that writes.

```go
// Unbuffered: synchronous, sender blocks until receiver ready
ch := make(chan int)

// Buffered: async up to buffer size
ch := make(chan int, 100)

// Guidelines:
// - Use unbuffered when you need synchronization
// - Use buffered to decouple sender/receiver timing
// - Buffer size should match expected backpressure
```

**Graceful Shutdown**

Workers and servers must implement clean shutdown with a drain timeout because abrupt termination can lose in-flight work and corrupt state. See `references/concurrency-patterns.md` for the full graceful shutdown pattern.

For worker pool, fan-out/fan-in, pipeline, and rate limiter patterns, see `references/concurrency-patterns.md`.

When profiling goroutine counts and channel contention under load, use `runtime.NumGoroutine()` and pprof to identify bottlenecks. For container deployments, configure `GOMAXPROCS` to match container CPU limits when needed.

**Gate**: Code compiles, follows the selected pattern, channels closed by sender only, mutexes use defer Unlock. Proceed only when gate passes.

### Phase 5: Run Race Detector

**Goal**: Verify no data races exist in the concurrent code.

Run `go test -race` on all concurrent code because race conditions are silent until production -- they don't cause compile errors, often don't cause test failures, and manifest as rare, non-reproducible bugs under load.

```bash
# Run with race detector during development
go test -race -count=1 -v ./...

# Run specific test with race detection
go test -race -run TestConcurrentOperation ./...
```

After editing concurrent code, use `go_diagnostics` (when gopls MCP tools are available) to catch errors before running tests.

**Gate**: `go test -race` passes clean with no race conditions detected. Proceed only when gate passes.

### Phase 6: Verify Completeness

**Goal**: Confirm all concurrent code is correct and leak-free.

Every goroutine must have a guaranteed exit path via context cancellation, channel close, or explicit shutdown signal because goroutine leaks compound over time and lead to OOM in production -- a single leaked goroutine in a request handler means unbounded memory growth.

Before declaring concurrent code complete, verify:

- [ ] **Context propagation** -- All I/O operations accept context as first parameter
- [ ] **Goroutine exit paths** -- Every goroutine can terminate (via ctx.Done, channel close, or stop signal)
- [ ] **Channel closure** -- Channels closed by sender only, using `defer close(ch)`
- [ ] **Select with context** -- All `select` statements include `case <-ctx.Done()`
- [ ] **Proper synchronization** -- Shared state protected by mutex or atomic
- [ ] **Mutex discipline** -- `defer mu.Unlock()` immediately after `mu.Lock()`
- [ ] **Race detector passes** -- `go test -race` clean
- [ ] **Graceful shutdown** -- Workers and servers stop cleanly with drain timeout
- [ ] **No goroutine leaks** -- All goroutines tracked and have exit paths

**Gate**: All checklist items verified. Concurrent code is complete.

---

## Error Handling

### Error: "DATA RACE detected by race detector"
Cause: Multiple goroutines access shared variable without synchronization
Solution:
1. Identify the variable from the race detector output (it shows goroutine stacks)
2. Protect with `sync.Mutex` for complex state, or `atomic` for simple counters
3. If using channels, ensure the variable is only accessed by one goroutine at a time
4. Re-run `go test -race` to confirm fix

### Error: "all goroutines are asleep - deadlock!"
Cause: Circular wait on channels or mutexes; no goroutine can make progress
Solution:
1. Check for unbuffered channel sends with no receiver ready
2. Check for mutex lock ordering inconsistencies
3. Ensure channels are closed when done to unblock `range` loops
4. Add buffering to channels where appropriate

### Error: "context deadline exceeded" in concurrent operations
Cause: Operations not completing within timeout, or context cancelled upstream
Solution:
1. Check if timeout is realistic for the operation
2. Verify context is propagated correctly (not using `context.Background()` when a parent context exists)
3. Ensure goroutines check `ctx.Done()` in their select loops
4. Consider increasing timeout or adding per-operation timeouts with `context.WithTimeout`

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/concurrency-patterns.md`: Worker pool, fan-out/fan-in, pipeline, rate limiter, and graceful shutdown patterns with full code examples
