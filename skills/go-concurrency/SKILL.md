---
name: go-concurrency
description: |
  Go concurrency patterns and primitives: goroutines, channels, sync
  primitives, worker pools, rate limiting, context propagation. Use when
  writing concurrent Go code, implementing worker pools, fan-out/fan-in
  pipelines, rate limiters, or debugging race conditions and goroutine
  leaks. Triggers: goroutine, channel, sync.Mutex, sync.WaitGroup,
  worker pool, fan-out, fan-in, rate limit, concurrent, parallel,
  context.Context, race condition, deadlock. Do NOT use for sequential
  Go code, general Go syntax, error handling patterns, or HTTP routing
  without concurrency concerns.
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
  force_routing: true
---

# Go Concurrency Skill

## Operator Context

This skill operates as an operator for Go concurrency workflows, configuring Claude's behavior for correct, leak-free concurrent code. It implements the **Domain Intelligence** architectural pattern -- encoding Go concurrency idioms, sync primitives, and channel patterns as non-negotiable constraints rather than suggestions.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before writing concurrent code
- **Over-Engineering Prevention**: Use concurrency only when justified by I/O, CPU parallelism, or measured bottleneck. Sequential code is correct by default
- **Context First Parameter**: All cancellable or I/O operations accept `context.Context` as first parameter
- **No Goroutine Leaks**: Every goroutine must have a guaranteed exit path via context, channel close, or explicit shutdown
- **Race Detector Required**: Run `go test -race` on all concurrent code during development
- **Channel Ownership**: Only the sender closes a channel. Never close from receiver side
- **Select With Context**: Every `select` statement in concurrent code must include a `<-ctx.Done()` case

### Default Behaviors (ON unless disabled)
- **errgroup Over WaitGroup**: Prefer `golang.org/x/sync/errgroup` for goroutine management with error collection
- **Buffered Channel Sizing**: Buffer size matches expected backpressure, not arbitrary large numbers
- **Directional Channel Returns**: Return `<-chan T` (receive-only) from producer functions to prevent caller misuse
- **Mutex Scope Minimization**: Lock only the critical section, use `defer Unlock()` immediately after `Lock()`
- **Loop Variable Safety**: Use Go 1.22+ loop variable semantics; remove legacy `item := item` shadows in new code
- **Graceful Shutdown**: Workers and servers implement clean shutdown with drain timeout
- **Atomic for Counters**: Use `atomic.Int64` / `atomic.Value` for simple shared counters instead of mutex

### Optional Behaviors (OFF unless enabled)
- **Gopls MCP Analysis**: Use gopls MCP tools to trace channel usage and context propagation — `go_symbol_references` for tracing channel flow, `go_file_context` for understanding goroutine spawn sites, `go_diagnostics` after concurrent code edits. Fallback: `gopls references` CLI or LSP tool
- **Container GOMAXPROCS Tuning**: Configure GODEBUG flags for container CPU limit overrides
- **Performance Profiling**: Profile goroutine counts and channel contention under load
- **Custom Rate Limiter**: Build token-bucket rate limiter instead of using `golang.org/x/time/rate`

## What This Skill CAN Do
- Guide implementation of worker pools, fan-out/fan-in, and pipeline patterns
- Apply correct context propagation through concurrent call chains
- Select appropriate sync primitives (Mutex, RWMutex, WaitGroup, Once, atomic)
- Implement rate limiting with context-aware waiting
- Diagnose and fix race conditions, deadlocks, and goroutine leaks
- Structure graceful shutdown for background workers and servers

## What This Skill CANNOT Do
- Fix general Go bugs unrelated to concurrency (use systematic-debugging instead)
- Optimize non-concurrent performance (use performance optimization workflows instead)
- Write tests for concurrent code (use go-testing skill instead)
- Handle Go error handling patterns (use go-error-handling skill instead)

---

## Instructions

### Step 1: Assess Concurrency Need

Before writing concurrent code, answer these questions:

1. **Is the work I/O-bound?** (network, database, filesystem) -- concurrency likely helps
2. **Is the work CPU-bound?** -- concurrency helps only if parallelizable
3. **Is there a measured bottleneck?** -- if not measured, don't assume

If none apply, write sequential code. Concurrency adds complexity; justify it.

### Step 2: Choose the Right Primitive

| Need | Primitive | When |
|------|-----------|------|
| Communicate between goroutines | Channel | Data flows from producer to consumer |
| Protect shared state | `sync.Mutex` | Multiple goroutines read/write same data |
| Read-heavy shared state | `sync.RWMutex` | Many readers, few writers |
| Wait for goroutines to finish | `errgroup.Group` | Need error collection + context cancel |
| Wait without error collection | `sync.WaitGroup` | Fire-and-forget goroutines |
| One-time initialization | `sync.Once` | Lazy singleton, config loading |
| Simple shared counter | `atomic.Int64` | Increment/read without mutex overhead |

### Step 3: Context Propagation

Always pass context as first parameter for I/O or cancellable operations.

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

When to use context vs not:

```go
// USE context: I/O, cancellable operations, request-scoped values
func FetchUserData(ctx context.Context, userID string) (*User, error) { ... }

// NO context needed: pure computation
func CalculateTotal(prices []float64) float64 { ... }
```

### Step 4: Implement the Pattern

**Sync Primitives**

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

**errgroup for concurrent work with error handling (preferred over WaitGroup)**

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

For worker pool, fan-out/fan-in, pipeline, rate limiter, and graceful shutdown patterns, see `references/concurrency-patterns.md`.

### Step 5: Run Race Detector

```bash
# ALWAYS run with race detector during development
go test -race -count=1 -v ./...

# Run specific test with race detection
go test -race -run TestConcurrentOperation ./...
```

### Step 6: Concurrency Checklist

Before declaring concurrent code complete, verify:

- [ ] **Context propagation** - All I/O operations accept context
- [ ] **Goroutine exit paths** - Every goroutine can terminate
- [ ] **Channel closure** - Channels closed by sender only
- [ ] **Select with context** - All selects include `<-ctx.Done()`
- [ ] **Proper synchronization** - Shared state protected
- [ ] **Race detector passes** - `go test -race` clean
- [ ] **Graceful shutdown** - Workers stop cleanly
- [ ] **No goroutine leaks** - All goroutines tracked

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

## Anti-Patterns

### Anti-Pattern 1: Goroutine Without Exit Path
**What it looks like**: `go func() { for { doWork() } }()` with no context check or stop channel
**Why wrong**: Goroutine runs forever, leaking memory. Cannot be cancelled or shut down gracefully.
**Do instead**: Always include `<-ctx.Done()` or a stop channel in goroutine loops.

### Anti-Pattern 2: Unnecessary Concurrency
**What it looks like**: Spawning goroutines for sequential work that does not benefit from parallelism
**Why wrong**: Adds complexity (error channels, WaitGroups, race risks) without performance gain. Sequential code is simpler and correct by default.
**Do instead**: Measure first. Use concurrency only for I/O-bound, CPU-parallel, or proven bottleneck scenarios.

### Anti-Pattern 3: Closing Channel From Receiver Side
**What it looks like**: Consumer goroutine calling `close(ch)` on a channel it reads from
**Why wrong**: Sender may still send, causing panic. Multiple receivers may double-close.
**Do instead**: Only the sender (producer) closes the channel. Use `defer close(ch)` in the goroutine that writes.

### Anti-Pattern 4: Mutex Lock Without Defer Unlock
**What it looks like**: `mu.Lock()` followed by complex logic before `mu.Unlock()`, with early returns in between
**Why wrong**: Early returns or panics skip the `Unlock()`, causing deadlocks.
**Do instead**: Always `defer mu.Unlock()` immediately after `mu.Lock()`.

### Anti-Pattern 5: Ignoring Context in Select
**What it looks like**: `select { case msg := <-ch: handle(msg) }` without a `<-ctx.Done()` case
**Why wrong**: Goroutine blocks forever if channel never receives and context is cancelled.
**Do instead**: Every `select` in concurrent code must include `case <-ctx.Done(): return`.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "No need for context, this is fast" | Fast today, slow tomorrow under load | Pass context to all I/O operations |
| "Race detector is slow, skip it" | Races are silent until production | Run `go test -race` every time |
| "One goroutine leak won't matter" | Leaks compound; OOM in production | Verify every goroutine has exit path |
| "Sequential is too slow" | Assumption without measurement | Profile first, then add concurrency |
| "Buffer of 1000 should be enough" | Arbitrary buffers hide backpressure bugs | Size buffers to actual throughput |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/concurrency-patterns.md`: Worker pool, fan-out/fan-in, pipeline, rate limiter, and graceful shutdown patterns with full code examples
