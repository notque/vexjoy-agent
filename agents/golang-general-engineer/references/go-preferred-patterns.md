# Go General Engineer - Preferred Patterns

Action-first patterns for correct Go code. Each section leads with what to do and why, followed by detection commands for finding violations.

## Handle Every Error Return

Check every error return immediately after the call. Wrap errors with `fmt.Errorf("context: %w", err)` to build a traceable chain from the failure point to the caller. For write operations, also verify the byte count matches the expected length.

```go
result, err := database.Query("SELECT ...")
if err != nil {
    return fmt.Errorf("query failed: %w", err)
}

n, err := file.Write(data)
if err != nil {
    return fmt.Errorf("write failed: %w", err)
}
if n != len(data) {
    return fmt.Errorf("incomplete write: wrote %d of %d bytes", n, len(data))
}
```

**Why this matters**: Unchecked errors hide root causes. A nil-pointer panic three calls later is harder to debug than the original error. Silent failures compound in production and make debugging impossible.

**Detection**: `grep -rn '_ :=' --include="*.go"` and `grep -rn '_ =' --include="*.go"` find suppressed error returns.

---

## Give Every Goroutine an Exit Strategy

Pass a `context.Context` or a stop channel to every goroutine and `select` on it inside the loop. This ensures graceful shutdown and prevents goroutine leaks that grow memory unbounded.

```go
func StartWorker(ctx context.Context) {
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

// Alternative: channel-based stop signal
func StartWorker(stop <-chan struct{}) {
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
```

**Why this matters**: A goroutine without an exit path runs until the process dies. In long-running services, leaked goroutines accumulate resources (memory, file descriptors, network connections) with no way to reclaim them.

**Detection**: `grep -rn 'go func' --include="*.go" | grep -v 'ctx\|cancel\|stop\|done\|quit'` finds goroutines that may lack exit signals.

---

## Call WaitGroup.Add Before Spawning the Goroutine

Always call `wg.Add(1)` in the parent goroutine before the `go` statement, never inside the spawned goroutine. This eliminates the race between `Add()` and `Wait()`.

```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1) // Add BEFORE spawning goroutine
    go func(i Item) {
        defer wg.Done()
        process(i)
    }(item)
}
wg.Wait()
```

**Why this matters**: When `Add()` runs inside the goroutine, `Wait()` can return before all goroutines have registered. This creates a race condition that causes intermittent panics or incorrect synchronization -- the kind of bug that passes tests 99% of the time.

**Detection**: `grep -A3 'go func' --include="*.go" -rn | grep 'wg.Add'` finds `Add()` calls inside goroutines.

---

## Capture Loop Variables Before Passing to Goroutines

Pass loop variables as function parameters to goroutines, or shadow them with a local copy. In Go versions before 1.22, closures capture the variable reference, not the value -- all goroutines see the last iteration's value.

```go
// Option 1: Pass as parameter (works on all Go versions)
for _, item := range items {
    go func(i Item) {
        process(i)
    }(item)
}

// Option 2: Shadow the loop variable
for _, item := range items {
    item := item // Shadow loop variable -- creates a new copy per iteration
    go func() {
        process(item)
    }()
}
```

**Why this matters**: Without capturing, every goroutine processes the same (last) item. This produces correct-looking output that is silently wrong. Go 1.22+ changed loop variable semantics to create a new variable per iteration, but explicit capture remains the safe portable pattern.

**Detection**: `grep -B2 -A3 'go func()' --include="*.go" -rn | grep 'range'` finds closures in range loops that may capture the loop variable.

---

## Close Channels When the Producer Finishes

Use `defer close(ch)` at the top of the producer function. The receiver's `range` loop exits automatically when the channel closes. Only the sender should close a channel -- never the receiver.

```go
func produce(ch chan int) {
    defer close(ch) // Close when done producing
    for i := 0; i < 10; i++ {
        ch <- i
    }
}

// Receiver exits cleanly when channel closes
for val := range ch {
    fmt.Println(val)
}
```

**Why this matters**: An unclosed channel causes `range` loops to block forever. The receiving goroutine leaks, and the program hangs or accumulates zombie goroutines.

**Detection**: Look for `range ch` patterns where the producing function lacks a `close()` call. `grep -rn 'range.*chan\|for.*:=.*range' --include="*.go"` identifies range-over-channel consumers to audit.

---

## Copy Loop Variables Before Taking Their Address

When appending pointers from a loop, create an explicit copy of the loop variable before taking its address. Without the copy, all pointers reference the same memory location and resolve to the last iteration's value.

```go
func getUsers() []*User {
    var users []*User
    for _, data := range userData {
        user := parseUser(data)
        u := user // Create a new variable -- each pointer gets its own copy
        users = append(users, &u)
    }
    return users
}

// Alternative: construct the value directly
func getUsers() []*User {
    var users []*User
    for _, data := range userData {
        users = append(users, &User{
            Name: data.Name,
            Email: data.Email,
        })
    }
    return users
}
```

**Why this matters**: All pointers in the slice end up pointing to the same memory address, which holds only the last iteration's value. This is a silent data corruption bug -- the slice appears correctly sized but every element is identical.

**Detection**: `grep -B3 -A1 'append.*&' --include="*.go" -rn | grep 'range'` finds pointer-append patterns inside range loops.

---

## Extract defer Cleanup Into a Separate Function

`defer` runs at function exit, not at the end of a loop iteration. To release resources per iteration, extract the loop body into its own function so `defer` fires at each iteration's function return.

```go
// Correct: extract to function so defer runs per iteration
for _, file := range files {
    if err := processFile(file); err != nil {
        return err
    }
}

func processFile(filename string) error {
    f, err := os.Open(filename)
    if err != nil {
        return err
    }
    defer f.Close() // Runs when processFile returns -- once per file

    return process(f)
}

// Alternative: explicit close without defer
for _, file := range files {
    f, err := os.Open(file)
    if err != nil {
        return err
    }

    err = process(f)
    f.Close() // Close immediately, don't defer

    if err != nil {
        return err
    }
}
```

**Why this matters**: `defer` inside a loop accumulates all deferred calls until the enclosing function returns. For file handles, this means all files stay open simultaneously. With enough iterations, the process exhausts file descriptors and crashes.

**Detection**: `grep -B2 'defer.*Close\|defer.*Unlock\|defer.*Release' --include="*.go" -rn | grep 'for '` finds defer-in-loop patterns.

---

## Check Slice Length Directly With len()

Use `len(slice) > 0` to check for a non-empty slice. A nil slice returns `len() == 0`, so a separate nil check is redundant. This applies to maps too: `len(m) > 0` covers both nil and empty.

```go
if len(slice) > 0 {
    // Process slice
}

// len(nil) == 0, so this is safe and idiomatic
```

**Why this matters**: `if slice != nil && len(slice) > 0` is functionally identical but adds visual noise. Go's standard library treats nil slices and empty slices interchangeably, and idiomatic Go follows this convention.

**Detection**: `grep -rn '!= nil && len(' --include="*.go"` finds redundant nil-before-length checks.

---

## Return Errors Instead of Panicking

Use the `(value, error)` return pattern for expected failure cases. Reserve `panic` for truly unrecoverable situations: corrupted invariants, impossible states, and startup configuration failures in `main()` or `init()`.

```go
func getUser(id int) (*User, error) {
    user := db.Find(id)
    if user == nil {
        return nil, fmt.Errorf("user not found: %d", id)
    }
    return user, nil
}
```

**When panic IS appropriate**:
- In `main()` or `init()` for missing configuration
- Unrecoverable corruption (violated data invariants)
- Programming errors that indicate a logic bug (index out of range on a fixed-size array)

**Why this matters**: `panic` crashes the goroutine's stack. If the caller has no `recover()`, the entire program dies. Using panic for expected conditions (user not found, network timeout) forces every caller to add recovery boilerplate and makes error handling unpredictable.

**Detection**: `grep -rn 'panic(' --include="*.go" | grep -v '_test.go\|main.go\|init()'` finds panics outside test/init contexts.

---

## Buffer Channels When the Sender Must Not Block

Use `make(chan T, 1)` (buffer size 1) when a goroutine produces a single result and must not block if the receiver has not called receive yet. This prevents goroutine leaks when the receiver panics or returns early.

```go
// Buffer size 1: sender never blocks, even if receiver is delayed or absent
ch := make(chan Result, 1)
go func() {
    result := compute()
    ch <- result // Never blocks because buffer absorbs the value
}()

doSomethingThatMightPanic()
result := <-ch
```

**Why this matters**: With an unbuffered channel, the sender blocks until a receiver is ready. If the receiver panics, returns early, or simply never reads, the sending goroutine leaks permanently. A buffer of 1 lets the sender complete and exit regardless of receiver timing.

**Detection**: `grep -rn 'make(chan' --include="*.go" | grep -v ','` finds unbuffered channel allocations to audit.

---

## Use Field Comparison or Equal Methods for Structs With Non-Comparable Fields

Structs containing slices, maps, or functions cannot use `==`. Compare individual fields, implement a custom `Equal` method, or use `reflect.DeepEqual` (slower, for tests only).

```go
// Option 1: Compare individual fields explicitly
if user1.Name == user2.Name && slices.Equal(user1.Tags, user2.Tags) {
    fmt.Println("equal")
}

// Option 2: Implement a custom Equal method
func (u User) Equal(other User) bool {
    return u.Name == other.Name && slices.Equal(u.Tags, other.Tags)
}

// Option 3: reflect.DeepEqual -- acceptable in tests, avoid in production
if reflect.DeepEqual(user1, user2) {
    fmt.Println("equal")
}
```

**Why this matters**: Using `==` on a struct with slice or map fields produces a compile error. Using `reflect.DeepEqual` in production paths adds significant overhead. Explicit field comparison or custom `Equal` methods are both correct and performant.

**Detection**: `grep -rn 'DeepEqual' --include="*.go" | grep -v '_test.go'` finds production use of reflection-based comparison.

---

## Keep Mutexes Unexported and Wrap Access in Methods

Embed mutexes as unexported fields (`mu sync.Mutex`) and expose thread-safe methods instead of exposing the lock to callers. This prevents external code from acquiring the lock without releasing it.

```go
type Counter struct {
    mu    sync.Mutex // Unexported -- callers cannot misuse the lock
    count int        // Unexported -- access only through methods
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.count++
}

func (c *Counter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}
```

**Why this matters**: An exported `sync.Mutex` (or embedded `sync.Mutex` in an exported struct) lets any caller call `Lock()` directly. A caller who locks without unlocking deadlocks the entire struct. Unexported mutexes with method wrappers make correct locking the only option.

**Detection**: `grep -rn 'sync.Mutex' --include="*.go" | grep -v 'mu \|mu  '` finds mutexes that may be exported or improperly named.
