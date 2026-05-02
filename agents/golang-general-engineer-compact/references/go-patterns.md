# Go Modern Patterns — Compact Reference

> **Scope**: Version-specific idiom upgrades, core patterns. Go 1.18–1.26.

Targets Go 1.26+ but must check go.mod before using version-specific features.

## Version Upgrade Table

| Old Idiom | Modern Idiom | Since | Detection |
|-----------|-------------|-------|-----------|
| `interface{}` | `any` | 1.18 | `rg 'interface\{\}' --type go` |
| Manual generics via `interface{}` | `func[T any](v T) T` | 1.18 | N/A — look for repetitive typed functions |
| `sort.Slice(s, func(i,j int) bool{...})` | `slices.SortFunc(s, cmp.Compare)` | 1.21 | `rg 'sort\.Slice\(' --type go` |
| `len(m) == 0` check | `maps.Clone`, `maps.Keys`, `maps.Values` | 1.21 | `rg 'len\(.*\) == 0' --type go` |
| `if a > b { return a }` | `max(a, b)` / `min(a, b)` | 1.21 | `rg '\? .* : ' --type go` |
| `for i := 0; i < n; i++` | `for i := range n` | 1.22 | `rg 'for i := 0; i < ' --type go` |
| `for _, v := range s` loop variable capture | No capture needed | 1.22 | `rg 'item := item' --type go` |
| `strings.Split` in `range` | `strings.SplitSeq` | 1.24 | `rg 'strings\.Split\(' --type go` |
| `context.WithCancel` in test | `t.Context()` | 1.24 | `rg 'context\.Background.*test' --type go` |
| `omitempty` on zero-value structs | `omitzero` | 1.24 | N/A — check JSON tags |
| `wg.Add(1); go func(){defer wg.Done()...}` | `wg.Go(fn)` | 1.25 | `rg 'wg\.Add\(1\)' --type go` |
| `x := val; &x` | `new(val)` | 1.26 | `rg 'x := .*; &x' --type go` |
| `errors.As(err, &t)` | `errors.AsType[T](err)` | 1.26 | `rg 'errors\.As\(' --type go` |

---

## Correct Patterns

### Go Version Detection from go.mod

Always check go.mod before using version-specific features.

```bash
# Check target Go version
grep '^go ' go.mod
# Output: "go 1.23" means you can use 1.23 features, not 1.24+
```

```go
// gopls MCP workflow: run go_workspace first
// go_workspace → detect go.mod version → apply appropriate patterns
```

---

### Error Wrapping with %w (Go 1.13+)

```go
// Wrap to preserve error chain
if err := db.QueryRow(q).Scan(&id); err != nil {
    return fmt.Errorf("fetchUser %d: %w", userID, err)
}

// Unwrap for type checking
var notFound *NotFoundError
if errors.As(err, &notFound) { // Still works in all versions
    // handle
}

// Go 1.26+: generic AsType
if nf, ok := errors.AsType[*NotFoundError](err); ok {
    log.Printf("not found: %d", nf.ID)
}
```

`%w` preserves the error chain for `errors.Is`/`errors.As`. Without it, `errors.Is(err, sql.ErrNoRows)` returns false.

---

### Functional Options (Interface Design)

```go
type Server struct {
    timeout  time.Duration
    maxConns int
}

type Option func(*Server)

func WithTimeout(d time.Duration) Option {
    return func(s *Server) { s.timeout = d }
}

func NewServer(opts ...Option) *Server {
    s := &Server{timeout: 30 * time.Second, maxConns: 100} // defaults
    for _, o := range opts {
        o(s)
    }
    return s
}
```

Avoids zero-value ambiguity. Extends without breaking callers.

---

### Small Focused Interfaces

```go
// Good: 1-2 method interface is easy to satisfy, easy to mock
type Reader interface {
    Read(ctx context.Context, id string) (*Entity, error)
}

// Bad: fat interface forces callers to implement methods they don't need
type EntityManager interface {
    Read(ctx context.Context, id string) (*Entity, error)
    Write(ctx context.Context, e *Entity) error
    Delete(ctx context.Context, id string) error
    List(ctx context.Context, filter Filter) ([]*Entity, error)
    // ... 10 more methods
}
```

Fat interfaces = painful mocking + tight coupling. Consumer-side interfaces.

---

## Pattern Catalog

### Use any Instead of interface{} (Go 1.18+)
**Detection**:
```bash
grep -rn 'interface{}' --include="*.go"
rg 'interface\{\}' --type go
```

**Signal**:
```go
func process(v interface{}) interface{} { // Pre-1.18 style
    return v
}
```

**Preferred action**:
```go
func process(v any) any { // Go 1.18+: any is an alias for interface{}
    return v
}
```

**Version note**: `any` is a type alias since Go 1.18. Functionally identical — purely stylistic. The compact agent enforces `any` as a hard requirement.

---

### Wrap Errors with Call-Site Context
**Detection**:
```bash
grep -rn 'return err$' --include="*.go" | grep -v "_test.go"
rg 'return nil, err$' --type go | grep -v '_test.go'
```

**Signal**:
```go
func getConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err // Loses call context
    }
    ...
}
```

**Why**: Caller gets raw error with no call-site context.

**Preferred action**:
```go
func getConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("getConfig %s: %w", path, err)
    }
    ...
}
```

---

### Use Modern Range and WaitGroup Patterns
**Detection**:
```bash
# Old range pattern (loop variable capture)
grep -rn 'item := item' --include="*.go"
# Old WaitGroup pattern
grep -rn 'wg.Add(1)' --include="*.go"
# Old numeric loop
grep -rn 'for i := 0; i < [0-9]' --include="*.go"
```

**Signal**:
```go
for i := 0; i < 5; i++ { // Pre-1.22 numeric loop
    wg.Add(1)             // Pre-1.25 WaitGroup
    go func(n int) {
        defer wg.Done()
        process(n)
    }(i)
}
```

**Preferred action** (Go 1.25+):
```go
for i := range 5 { // Go 1.22+
    wg.Go(func() { process(i) }) // Go 1.25+: i captured by value in wg.Go
}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `cannot use X (type interface{}) as type any` | Old IDE generated code with `interface{}` | Replace with `any` throughout |
| `undefined: slices.Contains` | Go version < 1.21 | Upgrade go.mod or implement manually |
| `cannot range over N (variable of type int)` | Go version < 1.22 | Use `for i := 0; i < N; i++` |
| `undefined: (*sync.WaitGroup).Go` | Go version < 1.25 | Use Add/Done pattern |
| `undefined: errors.AsType` | Go version < 1.26 | Use `errors.As(err, &target)` |
| `t.Context undefined` | Go version < 1.24 | Use `context.WithCancel(context.Background())` + `t.Cleanup(cancel)` |

---

## Detection Commands Reference

```bash
# Find all interface{} usage (upgrade to any)
rg 'interface\{\}' --type go

# Find pre-1.22 numeric loops (upgrade to for range n)
rg 'for i := 0; i < ' --type go

# Find pre-1.25 WaitGroup patterns (upgrade to wg.Go)
rg 'wg\.Add\(1\)' --type go

# Find bare error returns (add context wrapping)
rg 'return nil, err$' --type go | grep -v '_test.go'

# Check current go.mod version
grep '^go ' go.mod
```

---

## See Also

- `concurrency-patterns.md` — goroutine lifecycle, channel patterns, wg.Go usage
- `testing-patterns.md` — t.Context(), b.Loop(), table-driven tests
