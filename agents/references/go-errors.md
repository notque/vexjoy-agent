# Common Go Errors and Solutions

> Reference file for golang-general-engineer agent. Loaded as context during Go development tasks.

## cannot use X as type Y (interface satisfaction)

**Error**: `cannot use myStruct as type io.Reader in argument to foo: myStruct does not implement io.Reader (missing method Read)`

**Root cause**: The concrete type is missing a method required by the interface, or the method has a pointer receiver but a value is being passed.

**Solution**:
```go
// BAD: method on pointer receiver, but passing value
type MyReader struct{ data []byte }

func (r *MyReader) Read(p []byte) (int, error) {
    copy(p, r.data)
    return len(r.data), io.EOF
}

// This fails: cannot use MyReader{} as io.Reader
// var r io.Reader = MyReader{}

// GOOD: pass a pointer when methods have pointer receivers
var r io.Reader = &MyReader{data: []byte("hello")}
```

## multiple-value in single-value context

**Error**: `multiple-value os.Open() (value of type (*os.File, error)) used as single-value context`

**Root cause**: Calling a function that returns multiple values (typically value + error) but only capturing one.

**Solution**:
```go
// BAD: ignoring the error return
// f := os.Open("file.txt")

// GOOD: capture both returns
f, err := os.Open("file.txt")
if err != nil {
    return fmt.Errorf("open file: %w", err)
}
defer f.Close()
```

## undefined: X

**Error**: `undefined: myFunc` or `undefined: MyType`

**Root cause**: Usually one of three things:
1. The name is unexported (lowercase) and you're accessing it from another package.
2. Wrong package import or the symbol lives in a different file that isn't being compiled.
3. Typo in the name.

**Solution**:
```go
// BAD: trying to access unexported name from another package
// val := mypkg.internalHelper()

// GOOD: export the name if it needs cross-package access
// In mypkg:
func InternalHelper() string { return "exported now" }

// Or use the correct package — check your imports:
import "myproject/pkg/utils" // not "myproject/internal/utils" if outside internal
```

## import cycle not allowed

**Error**: `import cycle not allowed: package A imports package B imports package A`

**Root cause**: Circular dependency between packages.

**Solution**: Extract the shared types into a third package, or use interfaces to invert the dependency.
```go
// BAD: package user imports package order, and order imports user

// GOOD: extract shared interface into a third package
// package contracts
type UserFinder interface {
    FindUser(id string) (User, error)
}

// package order — depends on contracts, not user
type OrderService struct {
    users contracts.UserFinder
}

// package user — implements contracts.UserFinder
type Service struct{ db *sql.DB }

func (s *Service) FindUser(id string) (contracts.User, error) { ... }
```

## data race detected

**Error**: `WARNING: DATA RACE` with stack traces showing concurrent read/write to the same variable.

**Root cause**: Two or more goroutines access a shared variable without synchronization, and at least one access is a write.

**Solution**:
```go
// BAD: unsynchronized map access
var cache = make(map[string]string)

go func() { cache["key"] = "val" }()   // write
go func() { _ = cache["key"] }()        // read — RACE

// GOOD: use sync.RWMutex for shared state
type SafeCache struct {
    mu    sync.RWMutex
    items map[string]string
}

func (c *SafeCache) Set(k, v string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items[k] = v
}

func (c *SafeCache) Get(k string) (string, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    v, ok := c.items[k]
    return v, ok
}
```

Detect races early: always run `go test -race ./...` in CI.

## context deadline exceeded

**Error**: `context deadline exceeded` or `context canceled`

**Root cause**: An operation took longer than the context's deadline, or a parent context was canceled.

**Solution**:
```go
// BAD: no timeout awareness, blocks forever
func fetchData(ctx context.Context, url string) ([]byte, error) {
    resp, err := http.Get(url) // ignores context entirely
    ...
}

// GOOD: propagate context and handle timeout
func fetchData(ctx context.Context, url string) ([]byte, error) {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, fmt.Errorf("create request: %w", err)
    }
    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        if ctx.Err() == context.DeadlineExceeded {
            return nil, fmt.Errorf("request timed out for %s: %w", url, err)
        }
        return nil, fmt.Errorf("fetch %s: %w", url, err)
    }
    defer resp.Body.Close()
    return io.ReadAll(resp.Body)
}

// Set a reasonable timeout at the call site
ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
defer cancel()
data, err := fetchData(ctx, "https://api.example.com/data")
```

## connection refused

**Error**: `dial tcp 127.0.0.1:5432: connect: connection refused`

**Root cause**: The target service (database, API, etc.) is not running, not ready, or listening on a different address/port.

**Solution**:
```go
// In tests: wait for the dependency to be ready
func waitForReady(ctx context.Context, addr string) error {
    for {
        select {
        case <-ctx.Done():
            return fmt.Errorf("service at %s never became ready: %w", addr, ctx.Err())
        default:
            conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
            if err == nil {
                conn.Close()
                return nil
            }
            time.Sleep(250 * time.Millisecond)
        }
    }
}

// In production: use retry with backoff
func connectWithRetry(ctx context.Context, dsn string) (*sql.DB, error) {
    var db *sql.DB
    var err error
    for attempt := range 5 {
        db, err = sql.Open("postgres", dsn)
        if err == nil {
            if pingErr := db.PingContext(ctx); pingErr == nil {
                return db, nil
            }
        }
        wait := time.Duration(1<<attempt) * 100 * time.Millisecond
        select {
        case <-ctx.Done():
            return nil, ctx.Err()
        case <-time.After(wait):
        }
    }
    return nil, fmt.Errorf("connect after 5 attempts: %w", err)
}
```

## nil pointer dereference

**Error**: `runtime error: invalid memory address or nil pointer dereference`

**Root cause**: Dereferencing a pointer that was never initialized, or using a return value before checking the error.

**Solution**:
```go
// BAD: using result before checking error
resp, err := http.Get(url)
defer resp.Body.Close() // panics if resp is nil
if err != nil {
    return err
}

// GOOD: check error first, then use result
resp, err := http.Get(url)
if err != nil {
    return fmt.Errorf("fetch: %w", err)
}
defer resp.Body.Close()
```

## slice bounds out of range

**Error**: `runtime error: index out of range [5] with length 3`

**Root cause**: Accessing a slice index that doesn't exist, often from unchecked length assumptions.

**Solution**:
```go
// BAD: assuming slice has enough elements
first := items[0] // panics on empty slice

// GOOD: guard with length check
if len(items) == 0 {
    return fmt.Errorf("no items found")
}
first := items[0]
```
