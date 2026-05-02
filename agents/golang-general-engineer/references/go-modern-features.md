# Modern Go Features by Version

## Pre-Generics Era (Go 1.0 - 1.17)

| Feature | Idiom | Since |
|---------|-------|-------|
| `time.Since` | `time.Since(start)` not `time.Now().Sub(start)` | 1.0 |
| `time.Until` | `time.Until(deadline)` not `deadline.Sub(time.Now())` | 1.8 |
| `errors.Is` | `errors.Is(err, target)` not `err == target` (works with wrapped errors) | 1.13 |

## Go 1.18: Generics and Fuzzing

**Generics**:

```go
// OLD: separate per-type functions
// NEW: single generic function
func Contains[T comparable](s []T, v T) bool {
    for _, item := range s {
        if item == v {
            return true
        }
    }
    return false
}
```

**Fuzzing** — built-in fuzz testing support.

```go
func FuzzReverse(f *testing.F) {
    f.Add("hello")
    f.Fuzz(func(t *testing.T, s string) {
        rev := Reverse(s)
        doubleRev := Reverse(rev)
        if s != doubleRev {
            t.Errorf("double reverse: %q -> %q -> %q", s, rev, doubleRev)
        }
    })
}
```

**`any`** — builtin alias for `interface{}`. Prefer `any` everywhere.

## Go 1.19: Atomic Types

Type-safe wrappers in `sync/atomic`:

```go
// OLD: untyped atomic operations
var counter int64
atomic.AddInt64(&counter, 1)
val := atomic.LoadInt64(&counter)

// NEW: typed atomic values
var counter atomic.Int64
counter.Add(1)
val := counter.Load()

// Also: atomic.Bool, atomic.Pointer[T]
var ready atomic.Bool
ready.Store(true)
if ready.Load() {
    // ...
}
```

## Go 1.20: errors.Join and Context Enhancements

**errors.Join** — combine multiple errors:

```go
// NEW: collect and return all errors
func validate(cfg Config) error {
    var errs []error
    if cfg.Port == 0 {
        errs = append(errs, fmt.Errorf("port is required"))
    }
    if cfg.Host == "" {
        errs = append(errs, fmt.Errorf("host is required"))
    }
    if cfg.Port < 0 || cfg.Port > 65535 {
        errs = append(errs, fmt.Errorf("port %d out of range", cfg.Port))
    }
    return errors.Join(errs...) // returns nil if errs is empty
}

// Each sub-error is still matchable with errors.Is / errors.As
```

**context.WithCancelCause** — attach reason to cancellation:

```go
ctx, cancel := context.WithCancelCause(parentCtx)

// Cancel with a reason
cancel(fmt.Errorf("user %s requested shutdown", userID))

// Retrieve the cause
if err := ctx.Err(); err != nil {
    cause := context.Cause(ctx)
    slog.Info("context canceled", "cause", cause)
}
```

## Go 1.21: slices, maps, slog, and Builtins

**slices and maps** — generic stdlib helpers:

```go
// OLD: hand-written sort
sort.Slice(users, func(i, j int) bool {
    return users[i].Age < users[j].Age
})

// NEW: type-safe sort
slices.SortFunc(users, func(a, b User) int {
    return cmp.Compare(a.Age, b.Age)
})

// Other highlights:
slices.Contains(names, "alice")
slices.Index(names, "bob")
slices.Compact(sorted)         // remove consecutive duplicates
maps.Keys(m)                   // []K from map[K]V
maps.Values(m)                 // []V from map[K]V
maps.Clone(m)                  // shallow copy
```

**min/max builtins**:

```go
// OLD
func min(a, b int) int { if a < b { return a }; return b }

// NEW: built-in, works with any ordered type
x := min(a, b)
y := max(a, b, c) // variadic
```

**slog** — structured logging:

```go
// OLD: log.Printf with string formatting
log.Printf("processing order id=%s user=%s", orderID, userID)

// NEW: structured, leveled logging
slog.Info("processing order", "order_id", orderID, "user_id", userID)
slog.Error("payment failed", "err", err, "order_id", orderID)

// Configure handler
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))
slog.SetDefault(logger)
```

**clear()** — zero out maps and slices:

```go
m := map[string]int{"a": 1, "b": 2}
clear(m) // m is now empty (len 0), but allocated memory is retained

s := []int{1, 2, 3}
clear(s) // sets all elements to zero value: [0, 0, 0]
```

**sync.OnceValue / sync.OnceFunc**:

```go
var getConfig = sync.OnceValue(func() *Config {
    cfg, _ := loadConfigFromDisk()
    return cfg
})
// Usage: cfg := getConfig()
```

## Go 1.22: Range Over Integers and Enhanced ServeMux

**Range over integers**:

```go
// OLD
for i := 0; i < 10; i++ {
    fmt.Println(i)
}

// NEW: range over int
for i := range 10 {
    fmt.Println(i) // 0..9
}
```

**Enhanced ServeMux** — method prefix and path parameters:

```go
// NEW: method prefix and {param} wildcards
mux := http.NewServeMux()
mux.HandleFunc("GET /users/{id}", func(w http.ResponseWriter, r *http.Request) {
    id := r.PathValue("id")
    // ...
})
mux.HandleFunc("POST /users", createUser)
mux.HandleFunc("DELETE /users/{id}", deleteUser)
```

**Loop variable fix** — per-iteration variables (no more closure capture bugs). In Go 1.22+, each iteration gets its own `v`.

## Go 1.23: Range Over Functions and unique Package

**Range over function iterators**:

```go
// Define an iterator using the iter package types
func Fibonacci() iter.Seq[int] {
    return func(yield func(int) bool) {
        a, b := 0, 1
        for {
            if !yield(a) {
                return
            }
            a, b = b, a+b
        }
    }
}

// Use it with for-range
for n := range Fibonacci() {
    if n > 1000 {
        break
    }
    fmt.Println(n)
}

// Seq2 for key-value pairs
func Enumerate[T any](s []T) iter.Seq2[int, T] {
    return func(yield func(int, T) bool) {
        for i, v := range s {
            if !yield(i, v) {
                return
            }
        }
    }
}
```

**unique package** — interned comparable values for memory efficiency:

```go
// Intern strings to reduce memory for repeated values
handle := unique.Make("frequently-used-string")
val := handle.Value() // "frequently-used-string"

// Two handles with the same value compare as equal (pointer comparison internally)
h1 := unique.Make("hello")
h2 := unique.Make("hello")
fmt.Println(h1 == h2) // true — same underlying storage
```

## Go 1.24: Weak Pointers, os.Root, and testing/synctest

**weak package** — weak pointers (don't prevent GC):

```go
// Create a weak pointer — does not keep the object alive
type CacheEntry struct{ data []byte }

strong := &CacheEntry{data: loadData()}
w := weak.Make(strong)

// Later: check if the object is still alive
if val := w.Value(); val != nil {
    use(val)
} else {
    // Object was garbage collected; reload
}
```

**os.Root** — confined filesystem access:

```go
// Open a root directory — all operations are confined within it
root, err := os.OpenRoot("/var/data/uploads")
if err != nil {
    return err
}
defer root.Close()

// These operations cannot escape /var/data/uploads
f, err := root.Open("user/photo.jpg")    // OK
f, err = root.Open("../etc/passwd")       // error: path escapes root
```

**testing/synctest** — deterministic concurrent testing:

```go
func TestTimeout(t *testing.T) {
    synctest.Run(func() {
        ch := make(chan string)

        go func() {
            time.Sleep(10 * time.Second) // doesn't actually wait
            ch <- "done"
        }()

        // Advance fake time to trigger the sleep
        synctest.Wait()
        time.Sleep(10 * time.Second) // advances fake clock
        synctest.Wait()

        select {
        case msg := <-ch:
            if msg != "done" {
                t.Errorf("unexpected: %s", msg)
            }
        default:
            t.Fatal("expected message")
        }
    })
}
```

## Go 1.25: Swiss Table Maps and GOROOT Removal

**Swiss table maps** — automatic performance improvement, no code changes needed. **GOROOT removal** — `runtime.GOROOT()` deprecated; use `go env GOROOT`. **Improved build caching** — faster incremental builds.

```go
// No migration needed for Swiss tables — just upgrade Go.
// Benchmark your map-heavy code to see improvements:
func BenchmarkMapLookup(b *testing.B) {
    m := make(map[string]int, 1000)
    for i := range 1000 {
        m[fmt.Sprintf("key-%d", i)] = i
    }
    b.ResetTimer()
    for range b.N {
        _ = m["key-500"]
    }
}
```

## Go 1.26: Extended new() and errors.AsType

**Extended `new()`** — accepts expressions, returns pointer to copy:

```go
// NEW: new(val) returns pointer directly
cfg := Config{
    Timeout: new(30),   // *int
    Debug:   new(true), // *bool
}

// Type is inferred: new(0) -> *int, new("s") -> *string, new(T{}) -> *T
// Do NOT use redundant casts like new(int(0)) -- just write new(0)
```

**`errors.AsType[T]`** — generic error type assertion:

```go
// NEW: generic, returns value and bool
if pathErr, ok := errors.AsType[*os.PathError](err); ok {
    handle(pathErr)
}
```

## Migration Checklist

| Old Pattern | New Pattern | Since |
|---|---|---|
| `time.Now().Sub(start)` | `time.Since(start)` | 1.0 |
| `deadline.Sub(time.Now())` | `time.Until(deadline)` | 1.8 |
| `err == target` | `errors.Is(err, target)` | 1.13 |
| `interface{}` | `any` | 1.18 |
| `atomic.AddInt64(&x, 1)` | `x.Add(1)` with `atomic.Int64` | 1.19 |
| Custom multi-error | `errors.Join(errs...)` | 1.20 |
| `sort.Slice(s, less)` | `slices.SortFunc(s, cmp)` | 1.21 |
| `log.Printf(...)` | `slog.Info(msg, key, val)` | 1.21 |
| Hand-written `min`/`max` | Built-in `min(a, b)` | 1.21 |
| `for i := 0; i < n; i++` | `for i := range n` | 1.22 |
| Third-party HTTP router | `mux.HandleFunc("GET /path/{id}", h)` | 1.22 |
| Custom iterator types | `iter.Seq[T]` / `iter.Seq2[K,V]` | 1.23 |
| String dedup caches | `unique.Make(s)` | 1.23 |
| Manual path sanitization | `os.OpenRoot(dir)` | 1.24 |
| `time.Sleep` in tests | `testing/synctest` | 1.24 |
| `x := val; &x` for pointer | `new(val)` | 1.26 |
| `var t *T; errors.As(err, &t)` | `errors.AsType[*T](err)` | 1.26 |
