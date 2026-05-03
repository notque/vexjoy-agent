# Go General Engineer - Error Catalog

Common Go errors and their solutions.

## Goroutine Leak

**Symptoms**:
- Increasing goroutine count in production
- Memory usage grows over time
- Application becomes slow

**Cause**:
- Goroutines never exit
- Context not canceled
- Channels not closed
- Blocking operations with no timeout

**Solution**:
```go
// BAD - Goroutine leaks
func leakyWorker() {
    go func() {
        for {
            work() // No way to exit!
        }
    }()
}

// GOOD - Use context for cancellation
func worker(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return // Exit when context canceled
            default:
                work()
            }
        }
    }()
}

// GOOD - Use channel for signaling
func worker(stop <-chan struct{}) {
    go func() {
        for {
            select {
            case <-stop:
                return
            default:
                work()
            }
        }
    }()
}

// GOOD - Use sync.WaitGroup to track completion
func processItems(items []Item) {
    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(i Item) {
            defer wg.Done()
            process(i)
        }(item)
    }
    wg.Wait() // Wait for all to complete
}
```

**Prevention**:
- Always provide exit mechanism for goroutines
- Use context.WithCancel/WithTimeout
- Track goroutines with sync.WaitGroup
- Close channels when done producing
- Check goroutine count: `runtime.NumGoroutine()`

---

## Race Condition

**Symptoms**:
- Inconsistent results
- Panics in production
- `go test -race` reports DATA RACE
- Flaky tests

**Cause**:
- Concurrent access to shared memory without synchronization
- Multiple goroutines writing to same variable
- Reading while another goroutine writes

**Solution**:
```go
// BAD - Race condition
type Counter struct {
    count int
}

func (c *Counter) Increment() {
    c.count++ // RACE!
}

// GOOD - Use mutex
type Counter struct {
    mu    sync.Mutex
    count int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

// OR use atomic operations
type Counter struct {
    count atomic.Int64
}

func (c *Counter) Increment() {
    c.count.Add(1)
}

// OR use channels (message passing)
type Counter struct {
    ops chan func(*int)
}

func NewCounter() *Counter {
    c := &Counter{ops: make(chan func(*int))}
    go func() {
        var count int
        for op := range c.ops {
            op(&count)
        }
    }()
    return c
}

func (c *Counter) Increment() {
    c.ops <- func(count *int) { *count++ }
}
```

**Detection**:
```bash
# Always run tests with race detector
go test -race ./...

# Run specific test
go test -race -run TestConcurrent

# Build with race detector for manual testing
go build -race
```

**Prevention**:
- Run `go test -race` in CI
- Use mutexes for shared state
- Prefer message passing (channels) over shared memory
- Use atomic operations for simple counters
- Design for concurrency from the start

---

## Panic on Nil Pointer

**Symptoms**:
- `panic: runtime error: invalid memory address or nil pointer dereference`
- Crash in production

**Cause**:
- Calling method on nil pointer
- Accessing field of nil struct pointer
- Writing to nil map

**Solution**:
```go
// BAD - No nil check
func process(user *User) {
    fmt.Println(user.Name) // Panics if user is nil
}

// GOOD - Check for nil
func process(user *User) error {
    if user == nil {
        return fmt.Errorf("user cannot be nil")
    }
    fmt.Println(user.Name)
    return nil
}

// BAD - Nil map write
var m map[string]int
m["key"] = 1 // Panic!

// GOOD - Initialize map
m := make(map[string]int)
m["key"] = 1

// GOOD - Nil-safe map access (read)
value, ok := m["key"] // ok == false if m is nil

// BAD - Nil pointer method call
var user *User
user.Save() // Panics

// GOOD - Nil receiver check in method
func (u *User) Save() error {
    if u == nil {
        return fmt.Errorf("cannot save nil user")
    }
    // ... save logic
    return nil
}
```

**Prevention**:
- Always initialize maps with `make()`
- Validate pointer parameters in functions
- Add nil checks in constructors
- Use pointer receivers only when necessary
- Return zero values instead of nil when possible

---

## Interface Conversion Panic

**Symptoms**:
- `panic: interface conversion: interface is nil, not Type`
- `panic: interface conversion: interface is Type1, not Type2`

**Cause**:
- Type assertion on nil interface
- Type assertion to wrong type
- Not checking assertion success

**Solution**:
```go
// BAD - Panic if wrong type
func process(v any) {
    s := v.(string) // Panics if v is not string or is nil
    fmt.Println(s)
}

// GOOD - Two-value assertion
func process(v any) error {
    s, ok := v.(string)
    if !ok {
        return fmt.Errorf("expected string, got %T", v)
    }
    fmt.Println(s)
    return nil
}

// GOOD - Type switch for multiple types
func process(v any) {
    switch x := v.(type) {
    case string:
        fmt.Println("String:", x)
    case int:
        fmt.Println("Int:", x)
    case nil:
        fmt.Println("Nil value")
    default:
        fmt.Println("Unknown type:", x)
    }
}
```

**Prevention**:
- Always use two-value type assertion: `v, ok := x.(Type)`
- Use type switch for multiple possibilities
- Check for nil before type assertion
- Consider using concrete types instead of any/interface{}

---

## Context Deadline Exceeded

**Symptoms**:
- `context deadline exceeded` error
- Requests timing out
- Operations cancelled

**Cause**:
- Operation took longer than context deadline/timeout
- Context not propagated to blocking calls
- Tight deadline for slow operation

**Solution**:
```go
// Check if context is done in loops
func process(ctx context.Context, items []Item) error {
    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err() // Return immediately
        default:
        }

        if err := processItem(ctx, item); err != nil {
            return err
        }
    }
    return nil
}

// Increase timeout if operation is legitimately slow
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

// For long-running operations, use context.WithCancel
ctx, cancel := context.WithCancel(context.Background())
defer cancel()

// Propagate context to all blocking calls
func fetchData(ctx context.Context) (Data, error) {
    req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
    if err != nil {
        return Data{}, err
    }

    resp, err := client.Do(req)
    if err != nil {
        return Data{}, err
    }
    defer resp.Body.Close()

    // ... parse response
}
```

**Prevention**:
- Always propagate context to blocking operations
- Check `ctx.Done()` in long-running loops
- Use `context.WithTimeout` for time-bound operations
- Set realistic timeout values
- Test timeout scenarios

---

## Error Wrapping Without %w

**Symptoms**:
- `errors.Is()` and `errors.As()` don't work
- Cannot unwrap error chain
- Lost error context

**Cause**:
- Using `%v` or string concatenation instead of `%w`
- Not wrapping errors properly

**Solution**:
```go
// BAD - Error not wrapped
if err != nil {
    return fmt.Errorf("failed to save: %v", err) // Error chain broken!
}

// GOOD - Wrap with %w
if err != nil {
    return fmt.Errorf("failed to save: %w", err)
}

// Now errors.Is works
if errors.Is(err, ErrNotFound) {
    // Handle not found
}

// And errors.As works
var validationErr *ValidationError
if errors.As(err, &validationErr) {
    // Handle validation error
}
```

**Prevention**:
- Always use `%w` when wrapping errors
- Add context to wrapped errors
- Use `errors.Is()` to check for specific errors
- Use `errors.As()` to extract error details
- Don't wrap errors you want to hide

---

## Mutex Deadlock

**Symptoms**:
- Application hangs
- Goroutines stuck in Lock()
- `fatal error: all goroutines are asleep - deadlock!`

**Cause**:
- Lock not released
- Recursive lock attempt on non-recursive mutex
- Lock ordering inconsistency

**Solution**:
```go
// BAD - Lock not released
func (s *Service) update() {
    s.mu.Lock()
    if condition {
        return // BUG: Lock not released!
    }
    s.mu.Unlock()
}

// GOOD - Use defer
func (s *Service) update() {
    s.mu.Lock()
    defer s.mu.Unlock()

    if condition {
        return // Lock released by defer
    }
    // More code...
}

// BAD - Recursive lock
func (s *Service) outer() {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.inner() // Deadlock!
}

func (s *Service) inner() {
    s.mu.Lock() // Tries to lock again
    defer s.mu.Unlock()
    // ...
}

// GOOD - Separate public and internal methods
func (s *Service) Outer() {
    s.mu.Lock()
    defer s.mu.Unlock()
    s.innerLocked()
}

func (s *Service) innerLocked() {
    // Assumes lock is held
}

// BAD - Inconsistent lock ordering
func transfer(from, to *Account, amount int) {
    from.mu.Lock() // Thread A locks account 1
    to.mu.Lock()   // Thread B locks account 2
    // If Thread A wants account 2 and Thread B wants account 1: DEADLOCK
}

// GOOD - Consistent lock ordering
func transfer(from, to *Account, amount int) {
    // Always lock in consistent order (e.g., by ID)
    if from.ID < to.ID {
        from.mu.Lock()
        defer from.mu.Unlock()
        to.mu.Lock()
        defer to.mu.Unlock()
    } else {
        to.mu.Lock()
        defer to.mu.Unlock()
        from.mu.Lock()
        defer from.mu.Unlock()
    }

    from.Balance -= amount
    to.Balance += amount
}
```

**Prevention**:
- Always use `defer` to unlock
- Keep lock acquisition non-recursive; recursive locking creates deadlock risk
- Establish consistent lock ordering
- Use RWMutex for read-heavy workloads
- Consider channels instead of mutexes
- Test with `-race` flag

---

## Channel Deadlock

**Symptoms**:
- `fatal error: all goroutines are asleep - deadlock!`
- Send/receive operations block forever

**Cause**:
- Sending on unbuffered channel with no receiver
- Receiving on empty channel with no sender
- Channel not closed, range waits forever

**Solution**:
```go
// BAD - Deadlock on send
ch := make(chan int)
ch <- 1 // Blocks forever, no receiver!

// GOOD - Send in goroutine
ch := make(chan int)
go func() {
    ch <- 1
}()
result := <-ch

// BAD - Range never exits
ch := make(chan int)
go func() {
    ch <- 1
    // Forgot to close!
}()

for val := range ch { // Waits forever
    fmt.Println(val)
}

// GOOD - Close channel when done
ch := make(chan int)
go func() {
    ch <- 1
    close(ch) // Signal no more values
}()

for val := range ch {
    fmt.Println(val)
}

// GOOD - Use buffered channel for send-and-forget
ch := make(chan int, 1) // Buffer size 1
ch <- 1 // Doesn't block
```

**Prevention**:
- Close channels when done producing
- Use buffered channels when appropriate
- Ensure sender and receiver are coordinated
- Use select with timeout/default for non-blocking ops
- Test channel code carefully

---

## Import Cycle

**Symptoms**:
- `import cycle not allowed`
- Compilation fails

**Cause**:
- Package A imports package B
- Package B imports package A
- Circular dependency in package structure

**Solution**:
```go
// BAD - Circular dependency
// package models
import "services"

// package services
import "models" // Import cycle!

// GOOD - Extract shared types
// package types
type User struct { ... }

// package models
import "types"

// package services
import "types"
import "models" // No cycle

// OR - Use interfaces to break dependency
// package services
type UserRepository interface {
    Get(id int) (*User, error)
}

// package models
// Implements services.UserRepository but doesn't import services
```

**Prevention**:
- Design package structure carefully
- Extract shared types to common package
- Use interfaces to decouple packages
- Keep package dependencies one-directional; bidirectional dependencies create import cycles
- Draw package dependency graph
