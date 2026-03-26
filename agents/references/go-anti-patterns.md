# Go Anti-Patterns

> Reference file for golang-general-engineer agent. Loaded as context during Go development tasks.

## panic in library code

Library code should never panic. Panics crash the entire program and prevent callers from handling failures gracefully.

```go
// BAD: library function panics
func ParseConfig(data []byte) Config {
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        panic("invalid config: " + err.Error())
    }
    return cfg
}

// GOOD: return an error and let the caller decide
func ParseConfig(data []byte) (Config, error) {
    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return Config{}, fmt.Errorf("parse config: %w", err)
    }
    return cfg, nil
}
```

Reserve `panic` for truly unrecoverable programmer errors (e.g., a `switch` case that should be unreachable in your own `main`).

## init() with side effects

`init()` functions run implicitly at import time, making behavior hard to trace, test, and control.

```go
// BAD: init makes network calls, sets global state
var db *sql.DB

func init() {
    var err error
    db, err = sql.Open("postgres", os.Getenv("DATABASE_URL"))
    if err != nil {
        log.Fatal(err)
    }
}

// GOOD: explicit initialization called from main
func NewDB(dsn string) (*sql.DB, error) {
    db, err := sql.Open("postgres", dsn)
    if err != nil {
        return nil, fmt.Errorf("open database: %w", err)
    }
    return db, nil
}
```

Acceptable `init()` use: registering a database driver or codec (pure registration, no I/O).

## Naked returns in long functions

Naked returns are fine in trivial functions (2-3 lines). In anything longer, they make it unclear what is being returned.

```go
// BAD: naked return in a 15-line function — what does it return on success?
func process(input string) (result string, err error) {
    data, err := fetch(input)
    if err != nil {
        return
    }
    result, err = transform(data)
    if err != nil {
        return
    }
    // ... more logic ...
    return // reader must trace back to figure out the values
}

// GOOD: explicit returns
func process(input string) (string, error) {
    data, err := fetch(input)
    if err != nil {
        return "", fmt.Errorf("fetch: %w", err)
    }
    result, err := transform(data)
    if err != nil {
        return "", fmt.Errorf("transform: %w", err)
    }
    return result, nil
}
```

## interface{} instead of any

Since Go 1.18, `any` is a built-in alias for `interface{}`. Use it.

```go
// BAD: pre-1.18 style
func toJSON(v interface{}) ([]byte, error) {
    return json.Marshal(v)
}

// GOOD: modern Go
func toJSON(v any) ([]byte, error) {
    return json.Marshal(v)
}
```

## sort.Slice instead of slices.SortFunc

Since Go 1.21, the `slices` package provides type-safe, generics-based sort functions.

```go
// BAD: sort.Slice uses interface{} and is not type-safe
sort.Slice(users, func(i, j int) bool {
    return users[i].Name < users[j].Name
})

// GOOD: slices.SortFunc is generic and clearer
slices.SortFunc(users, func(a, b User) int {
    return cmp.Compare(a.Name, b.Name)
})
```

## Goroutine leaks

Every goroutine you launch must have a clear shutdown path. Forgetting to cancel contexts or close channels leaves goroutines running forever.

```go
// BAD: goroutine runs until the process dies
func startWorker() {
    go func() {
        for {
            doWork()
            time.Sleep(time.Second)
        }
    }()
}

// GOOD: goroutine respects context cancellation
func startWorker(ctx context.Context) {
    go func() {
        ticker := time.NewTicker(time.Second)
        defer ticker.Stop()
        for {
            select {
            case <-ctx.Done():
                return
            case <-ticker.C:
                doWork()
            }
        }
    }()
}
```

## Mutable package-level state

Global mutable state makes code hard to test, prone to races, and impossible to reason about in concurrent programs.

```go
// BAD: mutable global
var DefaultTimeout = 30 * time.Second

func init() {
    if v := os.Getenv("TIMEOUT"); v != "" {
        d, _ := time.ParseDuration(v)
        DefaultTimeout = d
    }
}

// GOOD: pass configuration explicitly
type ClientConfig struct {
    Timeout time.Duration
}

func NewClient(cfg ClientConfig) *Client {
    if cfg.Timeout == 0 {
        cfg.Timeout = 30 * time.Second
    }
    return &Client{timeout: cfg.Timeout}
}
```

## Checking error after using the result

The `err` must be checked BEFORE the result is used. This is the single most common Go bug.

```go
// BAD: using resp before checking err — resp may be nil
resp, err := http.Get(url)
defer resp.Body.Close()
if err != nil {
    return err
}

// GOOD: check error first
resp, err := http.Get(url)
if err != nil {
    return fmt.Errorf("get %s: %w", url, err)
}
defer resp.Body.Close()
```

## Channel misuse: unbuffered when buffered needed

Unbuffered channels block the sender until a receiver is ready. If no receiver is waiting, the goroutine blocks forever.

```go
// BAD: unbuffered channel in fire-and-forget pattern
func notify(ch chan string, msg string) {
    ch <- msg // blocks if nobody is reading
}

// GOOD: buffered channel for async notification
func notify(ch chan string, msg string) {
    select {
    case ch <- msg:
    default:
        // drop the message rather than block
        slog.Warn("notification dropped", "msg", msg)
    }
}

// Or use a buffered channel at creation
ch := make(chan string, 100)
```

## sync.Mutex when sync.RWMutex allows concurrent reads

If your shared resource is read-heavy, a plain `Mutex` serializes all access unnecessarily.

```go
// BAD: all access is serialized, even concurrent reads
type Cache struct {
    mu    sync.Mutex
    items map[string]string
}

func (c *Cache) Get(key string) string {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.items[key]
}

// GOOD: allow concurrent reads
type Cache struct {
    mu    sync.RWMutex
    items map[string]string
}

func (c *Cache) Get(key string) string {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.items[key]
}

func (c *Cache) Set(key, value string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items[key] = value
}
```

## Error wrapping without context

Returning raw errors loses the call chain. Always wrap with `fmt.Errorf` and `%w`.

```go
// BAD: raw error propagation
func loadUser(id string) (*User, error) {
    row := db.QueryRow("SELECT ...", id)
    var u User
    if err := row.Scan(&u.Name); err != nil {
        return nil, err // caller sees "sql: no rows" with no context
    }
    return &u, nil
}

// GOOD: wrap with context
func loadUser(id string) (*User, error) {
    row := db.QueryRow("SELECT ...", id)
    var u User
    if err := row.Scan(&u.Name); err != nil {
        return nil, fmt.Errorf("load user %s: %w", id, err)
    }
    return &u, nil
}
```

## String concatenation in loops

Building strings with `+=` in a loop creates a new string each iteration (O(n^2)).

```go
// BAD: quadratic string building
var result string
for _, item := range items {
    result += item.String() + "\n"
}

// GOOD: use strings.Builder
var b strings.Builder
for _, item := range items {
    b.WriteString(item.String())
    b.WriteByte('\n')
}
result := b.String()
```
