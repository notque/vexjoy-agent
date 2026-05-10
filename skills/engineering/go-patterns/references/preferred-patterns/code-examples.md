# Go Failure Modes: Extended Code Examples

Detailed before/after examples for each failure mode. Referenced from `SKILL.md` for progressive disclosure.

---

## AP-1: Premature Interface Abstraction (Extended)

### Full Bad Example

```go
// Creating interfaces before you have multiple implementations
type UserRepository interface {
    GetUser(id string) (*User, error)
    SaveUser(user *User) error
}

type PostgresUserRepository struct {
    db *sql.DB
}

func (r *PostgresUserRepository) GetUser(id string) (*User, error) { ... }
func (r *PostgresUserRepository) SaveUser(user *User) error { ... }

// Only one implementation exists, interface adds no value
```

### Full Good Example

```go
// Start with concrete types
type UserRepository struct {
    db *sql.DB
}

func (r *UserRepository) GetUser(id string) (*User, error) { ... }
func (r *UserRepository) SaveUser(user *User) error { ... }

// Add interface ONLY when you need multiple implementations
// (e.g., adding CacheUserRepository or MockUserRepository for tests)
```

### Consumer-Side Interface Pattern

When you do need an interface for testing:

```go
// Define interface at the consumer, not the provider
// In the test file or the package that needs the abstraction:
type userGetter interface {
    GetUser(id string) (*User, error)
}

// The concrete UserRepository implicitly satisfies this
// No need for the provider to declare the interface
```

---

## AP-2: Goroutine Overkill (Extended)

### Full Bad Example

```go
func ProcessItems(items []Item) error {
    errCh := make(chan error, len(items))
    var wg sync.WaitGroup

    for _, item := range items {
        wg.Add(1)
        go func(item Item) {
            defer wg.Done()
            if err := process(item); err != nil {
                errCh <- err
            }
        }(item)
    }

    wg.Wait()
    close(errCh)

    for err := range errCh {
        if err != nil {
            return err
        }
    }
    return nil
}
```

### Full Good Example

```go
// Simple, clear, maintainable
func ProcessItems(items []Item) error {
    for _, item := range items {
        if err := process(item); err != nil {
            return fmt.Errorf("process item %s: %w", item.ID, err)
        }
    }
    return nil
}
```

### When Concurrency IS Justified

```go
// I/O bound operations with proven bottleneck
func FetchAllUsers(ids []string) ([]*User, error) {
    g, ctx := errgroup.WithContext(context.Background())
    users := make([]*User, len(ids))

    for i, id := range ids {
        i, id := i, id
        g.Go(func() error {
            user, err := fetchUserFromAPI(ctx, id)
            if err != nil {
                return fmt.Errorf("fetch user %s: %w", id, err)
            }
            users[i] = user
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return users, nil
}
```

---

## AP-3: Error Wrapping Without Context (Extended)

### Full Bad Example

```go
func LoadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("error: %w", err)  // No context
    }

    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, fmt.Errorf("failed: %w", err)  // Vague
    }

    return &cfg, nil
}
```

### Full Good Example

```go
func LoadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("load config from %s: %w", path, err)
    }

    var cfg Config
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, fmt.Errorf("parse config JSON from %s: %w", path, err)
    }

    return &cfg, nil
}
// Error output: "parse config JSON from /etc/app.json: invalid character..."
// Clear narrative of what failed and where
```

### Error Wrapping Decision Tree

1. **Is this the origination point?** Return the raw error or `errors.New()`
2. **Are you adding context?** Use `fmt.Errorf("operation on %s: %w", id, err)`
3. **Should callers match this error?** Use `%w` for wrapping
4. **Should callers NOT match?** Use `%v` to break the chain

---

## AP-4: Channel Misuse (Extended)

### Full Bad Example

```go
// Using channels when a simple return value works
func GetUserName(id string) <-chan string {
    ch := make(chan string, 1)
    go func() {
        user := fetchUser(id)
        ch <- user.Name
    }()
    return ch
}

// Caller must deal with channel
name := <-GetUserName("123")
```

### Full Good Example

```go
// Synchronous is clearer when there's no concurrent work
func GetUserName(id string) (string, error) {
    user, err := fetchUser(id)
    if err != nil {
        return "", err
    }
    return user.Name, nil
}
```

### When Channels ARE Appropriate

```go
// Worker pools receiving tasks
// Fan-out/fan-in patterns
// Event streams or pub/sub
// Pipeline stages with backpressure
```

---

## AP-5: Generic Abuse (Extended)

### Full Bad Example

```go
type Container[T any] struct {
    value T
}

func (c *Container[T]) Get() T {
    return c.value
}

func (c *Container[T]) Set(value T) {
    c.value = value
}

// Only ever used with one type:
container := &Container[string]{value: "hello"}
```

### Full Good Example

```go
type StringContainer struct {
    value string
}

func (c *StringContainer) Get() string {
    return c.value
}
```

### When Generics ARE Appropriate

```go
// Data structures used with multiple types
type Cache[K comparable, V any] struct { ... }

// Algorithms that genuinely operate on multiple types
func Map[T, U any](slice []T, fn func(T) U) []U { ... }

// When you have 2+ concrete implementations sharing behavior
```

---

## AP-6: Context Soup (Extended)

### Full Bad Example

```go
func CalculateTotal(ctx context.Context, prices []float64) float64 {
    var total float64
    for _, price := range prices {
        total += price
    }
    return total
}

func FormatPrice(ctx context.Context, price float64) string {
    return fmt.Sprintf("$%.2f", price)
}
```

### Full Good Example

```go
func CalculateTotal(prices []float64) float64 {
    var total float64
    for _, price := range prices {
        total += price
    }
    return total
}

func FormatPrice(price float64) string {
    return fmt.Sprintf("$%.2f", price)
}
```

### Context Decision Checklist

Use `context.Context` ONLY when the function:
- Does I/O (network, database, file system)
- Should be cancellable by the caller
- Performs long-running computation that respects deadlines
- Carries request-scoped values (trace IDs, auth tokens)

---

## AP-7: Unnecessary Function Extraction (Extended)

### Full Bad Example

```go
func (opts AuditorOpts) parsePort() (int, error) {
    if opts.Port == "" {
        return 5672, nil
    }
    return strconv.Atoi(opts.Port)
}

func (opts AuditorOpts) buildConnectionURL() (string, error) {
    port, err := opts.parsePort()  // Called exactly once
    if err != nil {
        return "", err
    }
    return fmt.Sprintf("amqp://%s:%d", opts.Host, port), nil
}
```

### Full Good Example

```go
func (opts AuditorOpts) buildConnectionURL() (string, error) {
    port := 5672
    if opts.Port != "" {
        var err error
        port, err = strconv.Atoi(opts.Port)
        if err != nil {
            return "", fmt.Errorf("parse port %q: %w", opts.Port, err)
        }
    }
    return fmt.Sprintf("amqp://%s:%d", opts.Host, port), nil
}
```

### Extraction Decision Matrix

| Factor | Extract | Keep Inline |
|--------|---------|-------------|
| Call sites | 2+ places | 1 place |
| Lines of code | 10+ lines | 1-5 lines |
| Logical complexity | Distinct operation | Obvious step |
| Testing need | Needs independent tests | Tested via caller |
| Name value | Name adds understanding | Name restates code |

---

## AP-8: Shotgun Surgery / Wrong Abstraction Boundary (Extended)

When a helper must be called at every call site of another function, the helper belongs inside the original function. An INVARIANT comment documenting this coupling is a code smell, not a safety measure.

### Full Bad Example

```go
func scopeToLabelConstraint(req *http.Request, ks keystone.Driver) (string, []string) {
    if projectID := req.Header.Get("X-Project-Id"); projectID != "" {
        children, err := ks.ChildProjects(ctx, projectID)
        if err != nil { panic(err) }
        return "project_id", append([]string{projectID}, children...)
    }
    return "domain_id", []string{req.Header.Get("X-Domain-Id")}
}

// INVARIANT: This function must be called after every scopeToLabelConstraint() call.
func appendSentinelValue(labelValues []string) []string {
    if sentinelValue != "" {
        result := make([]string, len(labelValues)+1)
        copy(result, labelValues)
        result[len(result)-1] = sentinelValue
        return result
    }
    return labelValues
}

// Every caller must remember the two-step dance:
func (p *v1Provider) Query(w http.ResponseWriter, req *http.Request) {
    labelKey, labelValue := scopeToLabelConstraint(req, ks)
    labelValue = appendSentinelValue(labelValue) // forget this = silent bug
    // ...
}
```

**Three compounding problems:**

| Problem | Detail |
|---------|--------|
| Shotgun surgery | A 5th caller that forgets `appendSentinelValue` silently breaks global metrics |
| Defensive copy on fresh slice | `make`+`copy` protects against mutation of a slice that was just allocated — no shared backing array exists |
| Over-testing trivial code | 74-line test for a 3-line `append` wrapper with cyclomatic complexity 2 |

### Full Good Example

```go
func scopeToLabelConstraint(req *http.Request, ks keystone.Driver) (string, []string) {
    if projectID := req.Header.Get("X-Project-Id"); projectID != "" {
        children, err := ks.ChildProjects(ctx, projectID)
        if err != nil { panic(err) }
        return "project_id", appendSentinelValue(append([]string{projectID}, children...))
    }
    return "domain_id", appendSentinelValue([]string{req.Header.Get("X-Domain-Id")})
}

func appendSentinelValue(labelValues []string) []string {
    if sentinelValue != "" {
        return append(labelValues, sentinelValue)
    }
    return labelValues
}

// Callers just use scopeToLabelConstraint — sentinel is always included:
func (p *v1Provider) Query(w http.ResponseWriter, req *http.Request) {
    labelKey, labelValue := scopeToLabelConstraint(req, ks)
    // no second step needed — impossible to forget
    // ...
}
```

### Detection Signals

| Signal | Detection | Fix |
|--------|-----------|-----|
| Coupling comment | `grep -rn "must be called after\|must always follow\|INVARIANT.*call" --include="*.go"` | Merge the "always follows" logic into the prerequisite function |
| Same-pair call pattern | `helperB(result)` after every `result := functionA()` | Move `helperB` inside `functionA` |
| Defensive copy on fresh slice | `make([]T, len(x)+N)` + `copy(result, x)` where x is freshly allocated | Replace with `append(x, elements...)` |
| Over-tested trivial code | Test LOC > 10x function LOC, cyclomatic complexity <= 2 | Integration tests likely cover it; delete or reduce |

### Triple-Validation

| Check | Evidence |
|-------|----------|
| Recurrence | Appears in SAP CC PRs (maia, limes, keppel) and general Go codebases — any function pair with always-follows coupling |
| Generative power | Predicts new bugs: any future caller of `functionA` that omits `helperB` |
| Exclusivity | Distinguishes from generic "extract function" advice — specifically targets the case where extraction creates mandatory call-site coupling |

**Origin**: [PR #220](https://github.com/SAP-cloud-infrastructure/maia/pull/220) — Stefan Majewsky. `appendSentinelValue` called at 4 sites after `scopeToLabelConstraint`; refactor moved sentinel inside `scopeToLabelConstraint`.
