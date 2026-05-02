# Go Preferred Patterns

Action-first patterns for correct Go code. Each section: what to do, why, and detection commands.

## Handle Every Error Return

Check every error return. Wrap with `fmt.Errorf("context: %w", err)`. For writes, verify byte count.

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

**Why**: Unchecked errors hide root causes. Silent failures compound in production.

**Detection**: `grep -rn '_ :=' --include="*.go"` and `grep -rn '_ =' --include="*.go"`

---

## Give Every Goroutine an Exit Strategy

Pass `context.Context` or stop channel. `select` on it inside the loop.

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

**Why**: Leaked goroutines accumulate resources (memory, FDs, connections) with no reclaim path.

**Detection**: `grep -rn 'go func' --include="*.go" | grep -v 'ctx\|cancel\|stop\|done\|quit'`

---

## Call WaitGroup.Add Before Spawning the Goroutine

Call `wg.Add(1)` in the parent before the `go` statement, never inside the spawned goroutine.

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

**Why**: `Add()` inside the goroutine races with `Wait()` — passes tests 99% of the time, panics in production.

**Detection**: `grep -A3 'go func' --include="*.go" -rn | grep 'wg.Add'`

---

## Capture Loop Variables Before Passing to Goroutines

Pass loop variables as parameters or shadow with a local copy. Pre-1.22, closures capture the reference, not the value.

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

**Why**: Without capture, every goroutine processes the last item. Go 1.22+ fixed this, but explicit capture is portable.

**Detection**: `grep -B2 -A3 'go func()' --include="*.go" -rn | grep 'range'`

---

## Close Channels When the Producer Finishes

Use `defer close(ch)` in the producer. Only the sender closes — never the receiver.

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

**Why**: Unclosed channels cause `range` loops to block forever, leaking goroutines.

**Detection**: `grep -rn 'range.*chan\|for.*:=.*range' --include="*.go"` finds range-over-channel consumers to audit.

---

## Copy Loop Variables Before Taking Their Address

Create an explicit copy before taking address in a loop. Without it, all pointers reference the last iteration's value.

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

**Why**: Silent data corruption — slice appears correct but every element is identical.

**Detection**: `grep -B3 -A1 'append.*&' --include="*.go" -rn | grep 'range'`

---

## Extract defer Cleanup Into a Separate Function

`defer` runs at function exit, not loop iteration end. Extract loop body into its own function for per-iteration cleanup.

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

**Why**: `defer` in a loop accumulates all deferred calls until function returns — exhausts file descriptors.

**Detection**: `grep -B2 'defer.*Close\|defer.*Unlock\|defer.*Release' --include="*.go" -rn | grep 'for '`

---

## Check Slice Length Directly With len()

Use `len(slice) > 0` — nil slices return 0, so separate nil check is redundant. Same for maps.

```go
if len(slice) > 0 {
    // Process slice
}

// len(nil) == 0, so this is safe and idiomatic
```

**Detection**: `grep -rn '!= nil && len(' --include="*.go"`

---

## Return Errors Instead of Panicking

Use `(value, error)` for expected failures. Reserve `panic` for corrupted invariants and `main()`/`init()` config failures.

```go
func getUser(id int) (*User, error) {
    user := db.Find(id)
    if user == nil {
        return nil, fmt.Errorf("user not found: %d", id)
    }
    return user, nil
}
```

**When panic IS appropriate**: `main()`/`init()` config, corrupted invariants, logic bugs (fixed-size array OOB).

**Detection**: `grep -rn 'panic(' --include="*.go" | grep -v '_test.go\|main.go\|init()'`

---

## Buffer Channels When the Sender Must Not Block

Use `make(chan T, 1)` when a goroutine produces one result and must not block if receiver is absent.

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

**Why**: Unbuffered sender blocks until receiver is ready. If receiver panics, goroutine leaks permanently.

**Detection**: `grep -rn 'make(chan' --include="*.go" | grep -v ','`

---

## Use Field Comparison or Equal Methods for Non-Comparable Structs

Structs with slices/maps/functions cannot use `==`. Compare fields, implement `Equal`, or use `reflect.DeepEqual` (tests only).

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

**Detection**: `grep -rn 'DeepEqual' --include="*.go" | grep -v '_test.go'`

---

## Keep Mutexes Unexported and Wrap Access in Methods

Embed as unexported `mu sync.Mutex`. Expose thread-safe methods only.

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

**Why**: Exported mutex lets callers lock without unlocking, deadlocking the struct.

**Detection**: `grep -rn 'sync.Mutex' --include="*.go" | grep -v 'mu \|mu  '`
