# Common Go Review Comments

Reusable code examples for frequent review findings. Reference these patterns when writing review reports.

---

## Error Handling

### Missing Error Context

```go
// Bad: Raw error propagation
return err

// Good: Wrapped with context
return fmt.Errorf("load config: %w", err)
```

### Ignored Errors

```go
// Bad: Error discarded
data, _ := fetchData()
save(data)

// Good: Error checked and propagated
data, err := fetchData()
if err != nil {
    return fmt.Errorf("fetch data: %w", err)
}
if err := save(data); err != nil {
    return fmt.Errorf("save data: %w", err)
}
```

---

## Concurrency

### Goroutine Leak

```go
// Bad: May block forever if nobody reads from ch
go func() {
    ch <- result
}()

// Good: Context-aware goroutine
go func() {
    select {
    case ch <- result:
    case <-ctx.Done():
    }
}()
```

### Concurrent Map Access

```go
// Bad: Panic on concurrent read/write
var cache = make(map[string]string)

func getValue(key string) string {
    if val, ok := cache[key]; ok {
        return val
    }
    val := fetchFromDB(key)
    cache[key] = val
    return val
}

// Good: Protected with mutex
var (
    cache = make(map[string]string)
    mu    sync.RWMutex
)

func getValue(key string) string {
    mu.RLock()
    if val, ok := cache[key]; ok {
        mu.RUnlock()
        return val
    }
    mu.RUnlock()

    val := fetchFromDB(key)

    mu.Lock()
    cache[key] = val
    mu.Unlock()

    return val
}
```

---

## Testing

### Table-Driven Tests

```go
// Bad: Separate test functions for each case
func TestFoo(t *testing.T) { ... }
func TestFooEmpty(t *testing.T) { ... }
func TestFooError(t *testing.T) { ... }

// Good: Single table-driven test
func TestFoo(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    string
        wantErr bool
    }{
        {name: "valid", input: "hello", want: "HELLO"},
        {name: "empty", input: "", want: ""},
        {name: "error", input: "invalid", wantErr: true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := Foo(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("Foo() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if got != tt.want {
                t.Errorf("Foo() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

### Missing t.Helper()

```go
// Bad: Test helper without t.Helper()
func assertNoError(t *testing.T, err error) {
    if err != nil {
        t.Fatalf("unexpected error: %v", err) // Reports this line, not caller
    }
}

// Good: Marked as helper
func assertNoError(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatalf("unexpected error: %v", err) // Reports caller's line
    }
}
```

---

## Modern Go Patterns

### any vs interface{}

```go
// Bad: Legacy empty interface
func Process(data interface{}) interface{} { ... }

// Good: Modern Go (1.18+)
func Process(data any) any { ... }
```

### Naked Returns

```go
// Bad: Naked return obscures what is returned
func parse(s string) (result int, err error) {
    result, err = strconv.Atoi(s)
    return // What is being returned?
}

// Good: Explicit return
func parse(s string) (int, error) {
    result, err := strconv.Atoi(s)
    if err != nil {
        return 0, fmt.Errorf("parse %q: %w", s, err)
    }
    return result, nil
}
```

---

## Performance

### String Concatenation in Loops

```go
// Bad: O(n^2) string building
var result string
for _, item := range items {
    result += item.String() + ","
}

// Good: O(n) with strings.Builder
var b strings.Builder
for _, item := range items {
    b.WriteString(item.String())
    b.WriteByte(',')
}
result := b.String()
```

### Defer in Loops

```go
// Bad: Deferred close accumulates until function exits
func processFiles(paths []string) error {
    for _, p := range paths {
        f, err := os.Open(p)
        if err != nil {
            return err
        }
        defer f.Close() // Not closed until function returns
        process(f)
    }
    return nil
}

// Good: Wrap in closure or extract function
func processFiles(paths []string) error {
    for _, p := range paths {
        if err := processOne(p); err != nil {
            return err
        }
    }
    return nil
}

func processOne(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close()
    return process(f)
}
```

---

## Security

### Crypto/rand for Secrets

```go
// Bad: math/rand for tokens
import "math/rand"
token := fmt.Sprintf("%d", rand.Int63())

// Good: crypto/rand for security-critical values
import "crypto/rand"
b := make([]byte, 32)
if _, err := rand.Read(b); err != nil {
    return "", err
}
token := base64.URLEncoding.EncodeToString(b)
```

### Time-Constant Comparison

```go
// Bad: Variable-time comparison leaks info via timing
if apiKey == storedKey { ... }

// Good: Constant-time comparison
import "crypto/subtle"
if subtle.ConstantTimeCompare([]byte(apiKey), []byte(storedKey)) == 1 { ... }
```
