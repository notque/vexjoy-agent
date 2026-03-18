# Go General Engineer - Anti-Patterns

Common Go mistakes and corrections.

## ❌ Ignoring Errors

**What it looks like**:
```go
result, _ := database.Query("SELECT ...")
file.Write(data) // Ignores error return
```

**Why wrong**:
- Silent failures compound
- Bugs escape to production
- Violates Go conventions
- Makes debugging impossible

**✅ Correct approach**:
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

---

## ❌ Starting Goroutines Without Exit Strategy

**What it looks like**:
```go
func StartWorker() {
    go func() {
        for {
            work() // No way to stop!
        }
    }()
}
```

**Why wrong**:
- Goroutine leaks
- Resource exhaustion
- No graceful shutdown
- Memory grows unbounded

**✅ Correct approach**:
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

// Or with channel
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

---

## ❌ Using sync.WaitGroup Incorrectly

**What it looks like**:
```go
var wg sync.WaitGroup
for _, item := range items {
    go func() {
        wg.Add(1) // WRONG: Add inside goroutine causes race
        defer wg.Done()
        process(item)
    }()
}
wg.Wait()
```

**Why wrong**:
- Race condition between Add() and Wait()
- May wait before all Add() calls complete
- Can cause panic or incorrect sync

**✅ Correct approach**:
```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1) // CORRECT: Add before spawning goroutine
    go func(i Item) {
        defer wg.Done()
        process(i)
    }(item)
}
wg.Wait()
```

---

## ❌ Mutating Loop Variable in Goroutine

**What it looks like**:
```go
for _, item := range items {
    go func() {
        process(item) // BUG: All goroutines see last value!
    }()
}
```

**Why wrong**:
- Loop variable is reused
- Closure captures variable reference, not value
- All goroutines may process the last item

**✅ Correct approach**:
```go
// Option 1: Pass as parameter
for _, item := range items {
    go func(i Item) {
        process(i)
    }(item)
}

// Option 2: Create new variable (Go 1.22+ auto-fixes this)
for _, item := range items {
    item := item // Shadow loop variable
    go func() {
        process(item)
    }()
}
```

---

## ❌ Not Closing Channels

**What it looks like**:
```go
func produce(ch chan int) {
    for i := 0; i < 10; i++ {
        ch <- i
    }
    // Forgot to close!
}

for val := range ch { // Waits forever after 10 values
    fmt.Println(val)
}
```

**Why wrong**:
- Range loop waits forever
- Goroutine leak
- Receiver never knows producer finished

**✅ Correct approach**:
```go
func produce(ch chan int) {
    defer close(ch) // Close when done producing
    for i := 0; i < 10; i++ {
        ch <- i
    }
}

for val := range ch { // Exits when channel closed
    fmt.Println(val)
}
```

---

## ❌ Returning Pointer to Loop Variable

**What it looks like**:
```go
func getUsers() []*User {
    var users []*User
    for _, data := range userData {
        user := parseUser(data)
        users = append(users, &user) // BUG: All point to same variable!
    }
    return users
}
```

**Why wrong**:
- Loop variable is reused
- All pointers point to last value
- Subtle bug, hard to detect

**✅ Correct approach**:
```go
func getUsers() []*User {
    var users []*User
    for _, data := range userData {
        user := parseUser(data)
        // Option 1: Create new variable
        u := user
        users = append(users, &u)

        // Option 2: Return by value, take address later
        users = append(users, &User{...})
    }
    return users
}
```

---

## ❌ Using defer in Loop

**What it looks like**:
```go
for _, file := range files {
    f, _ := os.Open(file)
    defer f.Close() // BUG: All defers run after loop exits!
    process(f)
}
// All files still open until function returns
```

**Why wrong**:
- defer runs at function exit, not loop iteration end
- File descriptors accumulate
- Resource leak for many iterations

**✅ Correct approach**:
```go
// Option 1: Extract to function
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
    defer f.Close() // Runs at function exit

    return process(f)
}

// Option 2: Explicit close
for _, file := range files {
    f, err := os.Open(file)
    if err != nil {
        return err
    }

    err = process(f)
    f.Close() // Close immediately

    if err != nil {
        return err
    }
}
```

---

## ❌ Checking for Empty Slice with len() != nil

**What it looks like**:
```go
if slice != nil && len(slice) > 0 {
    // Process slice
}
```

**Why wrong**:
- Overly verbose
- nil slice and empty slice behave identically
- len(nil slice) is 0, safe to call

**✅ Correct approach**:
```go
if len(slice) > 0 {
    // Process slice
}

// len(nil) == 0, so this is safe
```

---

## ❌ Using Panic for Normal Errors

**What it looks like**:
```go
func getUser(id int) *User {
    user := db.Find(id)
    if user == nil {
        panic("user not found") // BAD: Panic for expected error
    }
    return user
}
```

**Why wrong**:
- Panics should be for truly exceptional situations
- Crashes caller's goroutine
- Forces caller to recover
- Makes error handling difficult

**✅ Correct approach**:
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
- In `main()` or `init()` for config errors
- Unrecoverable errors (corrupted state)
- Programming errors (violated invariants)

---

## ❌ Not Using Buffered Channels When Appropriate

**What it looks like**:
```go
ch := make(chan Result)
go func() {
    result := compute()
    ch <- result // May block forever if receiver doesn't exist
}()

// If this panics before receiving, sender blocks forever
doSomethingThatMightPanic()
result := <-ch
```

**Why wrong**:
- Unbuffered send blocks until receive
- Goroutine leak if receiver never reads
- Fragile error handling

**✅ Correct approach**:
```go
// Use buffer size 1 for send-and-forget
ch := make(chan Result, 1)
go func() {
    result := compute()
    ch <- result // Never blocks
}()

doSomethingThatMightPanic()
result := <-ch
```

---

## ❌ Comparing Structs with ==

**What it looks like**:
```go
type User struct {
    Name  string
    Tags  []string // Slice is not comparable!
}

user1 := User{Name: "Alice", Tags: []string{"admin"}}
user2 := User{Name: "Alice", Tags: []string{"admin"}}

if user1 == user2 { // Compilation error!
    fmt.Println("equal")
}
```

**Why wrong**:
- Structs containing slices, maps, or functions are not comparable
- Results in compilation error

**✅ Correct approach**:
```go
// Option 1: Compare individual fields
if user1.Name == user2.Name && slices.Equal(user1.Tags, user2.Tags) {
    fmt.Println("equal")
}

// Option 2: Implement custom Equal method
func (u User) Equal(other User) bool {
    return u.Name == other.Name && slices.Equal(u.Tags, other.Tags)
}

// Option 3: Use reflection (slower)
if reflect.DeepEqual(user1, user2) {
    fmt.Println("equal")
}
```

---

## ❌ Embedding Mutex in Exported Struct

**What it looks like**:
```go
type Counter struct {
    sync.Mutex // Embedded, exported!
    Count int
}

// Caller can misuse the lock
counter := &Counter{}
counter.Lock() // External lock!
counter.Count++
// Forgot to unlock!
```

**Why wrong**:
- Exposes internal locking mechanism
- Callers can misuse the lock
- Violates encapsulation
- Difficult to change locking strategy

**✅ Correct approach**:
```go
type Counter struct {
    mu    sync.Mutex // Unexported
    count int        // Unexported
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
