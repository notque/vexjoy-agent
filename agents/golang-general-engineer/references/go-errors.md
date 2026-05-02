# Go Error Catalog

## Goroutine Leak

**Symptoms**: Increasing goroutine count, growing memory, slow application.
**Cause**: Goroutines never exit — missing context cancellation, unclosed channels, blocking with no timeout.

```go
// BAD - no exit path
go func() { for { work() } }()

// GOOD - context cancellation
func worker(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                work()
            }
        }
    }()
}
```

**Prevention**: Always provide exit mechanism. Use `context.WithCancel`/`WithTimeout`. Track with `sync.WaitGroup`. Close channels when done. Check: `runtime.NumGoroutine()`.

---

## Race Condition

**Symptoms**: Inconsistent results, panics, `go test -race` DATA RACE, flaky tests.
**Cause**: Concurrent access to shared memory without synchronization.

```go
// BAD
func (c *Counter) Increment() { c.count++ } // RACE

// GOOD - mutex
func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

// GOOD - atomic
func (c *Counter) Increment() { c.count.Add(1) }
```

**Detection**:
```bash
go test -race ./...
go build -race
```

**Prevention**: Run `go test -race` in CI. Use mutexes for shared state. Prefer channels over shared memory. Use atomics for simple counters.

---

## Panic on Nil Pointer

**Symptoms**: `panic: runtime error: invalid memory address or nil pointer dereference`
**Cause**: Method call on nil pointer, nil struct field access, write to nil map.

```go
// BAD
func process(user *User) { fmt.Println(user.Name) }

// GOOD
func process(user *User) error {
    if user == nil { return fmt.Errorf("user cannot be nil") }
    fmt.Println(user.Name)
    return nil
}

// BAD - nil map write
var m map[string]int
m["key"] = 1 // Panic!

// GOOD
m := make(map[string]int)
m["key"] = 1
```

**Prevention**: Initialize maps with `make()`. Validate pointer parameters. Add nil receiver checks. Return zero values instead of nil when possible.

---

## Interface Conversion Panic

**Symptoms**: `panic: interface conversion: interface is nil, not Type`
**Cause**: Type assertion on nil/wrong type without checking.

```go
// BAD
s := v.(string) // Panics if wrong type

// GOOD - two-value assertion
s, ok := v.(string)
if !ok { return fmt.Errorf("expected string, got %T", v) }

// GOOD - type switch
switch x := v.(type) {
case string: fmt.Println("String:", x)
case int:    fmt.Println("Int:", x)
case nil:    fmt.Println("Nil")
default:     fmt.Println("Unknown:", x)
}
```

**Prevention**: Always use two-value assertion `v, ok := x.(Type)`. Use type switch for multiple types.

---

## Context Deadline Exceeded

**Symptoms**: `context deadline exceeded`, request timeouts.
**Cause**: Operation exceeded deadline, context not propagated, tight deadline for slow operation.

```go
// Check ctx in loops
for _, item := range items {
    select {
    case <-ctx.Done():
        return ctx.Err()
    default:
    }
    if err := processItem(ctx, item); err != nil { return err }
}

// Propagate context to HTTP requests
req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
```

**Prevention**: Propagate context to all blocking ops. Check `ctx.Done()` in loops. Use `context.WithTimeout` for time-bound operations. Test timeout scenarios.

---

## Error Wrapping Without %w

**Symptoms**: `errors.Is()`/`errors.As()` don't work, lost error context.
**Cause**: Using `%v` instead of `%w`.

```go
// BAD - chain broken
return fmt.Errorf("failed: %v", err)

// GOOD - chain preserved
return fmt.Errorf("failed: %w", err)
```

**Prevention**: Always use `%w` when wrapping. Use `errors.Is()` and `errors.As()` for checking.

---

## Mutex Deadlock

**Symptoms**: Hangs, goroutines stuck in Lock(), `fatal error: all goroutines are asleep`
**Cause**: Lock not released, recursive lock, inconsistent ordering.

```go
// BAD - lock not released on early return
s.mu.Lock()
if condition { return } // BUG!
s.mu.Unlock()

// GOOD - defer
s.mu.Lock()
defer s.mu.Unlock()
if condition { return } // Lock released by defer

// BAD - recursive lock
func (s *Service) outer() {
    s.mu.Lock(); defer s.mu.Unlock()
    s.inner() // Deadlock!
}
func (s *Service) inner() { s.mu.Lock() ... }

// GOOD - separate locked helpers
func (s *Service) Outer() {
    s.mu.Lock(); defer s.mu.Unlock()
    s.innerLocked() // Assumes lock held
}
```

**Prevention**: Always `defer` unlock. No recursive locking. Consistent lock ordering. Use `RWMutex` for read-heavy workloads. Test with `-race`.

---

## Channel Deadlock

**Symptoms**: `fatal error: all goroutines are asleep - deadlock!`
**Cause**: Send on unbuffered channel with no receiver, unclosed channel in range loop.

```go
// BAD - deadlock
ch := make(chan int)
ch <- 1 // Blocks forever

// GOOD - send in goroutine
ch := make(chan int)
go func() { ch <- 1 }()
result := <-ch

// GOOD - close channel for range exit
go func() { ch <- 1; close(ch) }()
for val := range ch { fmt.Println(val) }

// GOOD - buffered for fire-and-forget
ch := make(chan int, 1)
ch <- 1
```

**Prevention**: Close channels when done producing. Use buffered channels when appropriate. Use select with timeout/default.

---

## Import Cycle

**Symptoms**: `import cycle not allowed`
**Cause**: Circular package dependency.

```go
// BAD - A imports B, B imports A

// GOOD - extract shared types
// package types: type User struct { ... }
// package models: import "types"
// package services: import "types"; import "models"

// GOOD - use interfaces to break dependency
```

**Prevention**: Design one-directional dependencies. Extract shared types. Use interfaces to decouple.
