# Go Patterns Reference

<!-- Loaded by golang-general-engineer-compact when task involves: idiom detection, version upgrades, go vet errors, golangci-lint errors, modernizing code -->
<!-- scope: Go idioms, version upgrade detection, linter error-fix mappings | version-range: Go 1.18-1.26+ | date: 2026-04-05 -->

Modern Go idiom detection, version upgrade paths, and linter error fixes. The agent body covers what patterns look like; this file covers how to find them and fix what complains.

---

## Version Upgrade Table

What changed and how to detect old patterns in a codebase:

| Go Version | Feature Added | Old Pattern | Modern Pattern | Detect With |
|---|---|---|---|---|
| 1.18 | `any` alias | `interface{}` | `any` | `rg 'interface\{\}'` |
| 1.18 | Generics | Hand-rolled type-specific funcs | Generic func | manual review |
| 1.18 | Fuzz testing | No fuzz tests | `FuzzXxx(f *testing.F)` | `rg 'func Fuzz'` to confirm present |
| 1.19 | `atomic.Int64` etc. | `atomic.AddInt64(&x, 1)` | `x.Add(1)` | `rg 'atomic\.AddInt64\|atomic\.LoadInt64'` |
| 1.20 | `errors.Join` | Multi-error libs | `errors.Join(e1, e2)` | `rg 'multierr\|hashicorp/go-multierror'` |
| 1.20 | `context.WithCancelCause` | Raw context.WithCancel | `context.WithCancelCause` | — |
| 1.21 | `min`/`max` builtins | Ternary-style `if a > b` | `max(a, b)` | `rg 'if \w+ > \w+ \{' --multiline` |
| 1.21 | `slices` package | Manual loops for search/sort | `slices.Contains`, `slices.Sort` | `rg 'sort\.Slice\|sort\.Sort'` |
| 1.21 | `maps` package | Manual map iteration copy | `maps.Clone`, `maps.Keys` | manual review |
| 1.21 | `sync.OnceValue` | `sync.Once` + stored result | `sync.OnceValue(fn)` | `rg 'sync\.Once'` |
| 1.21 | `slog` package | Custom logger structs | `slog.Info`, `slog.Error` | `rg '"log"' go.mod` |
| 1.22 | `for i := range n` | `for i := 0; i < n; i++` | `for i := range n` | `rg 'for \w+ := 0; \w+ <'` |
| 1.22 | Loop var per-iteration | Loop capture bug pattern | No closure capture needed | `rg 'go func.*\btt\b\|go func.*\bv\b'` |
| 1.23 | Iterators (`iter.Seq`) | Slice-returning APIs | Push/pull iterator | manual review |
| 1.23 | `slices.Collect` | Manual collect loop | `slices.Collect(seq)` | — |
| 1.24 | `t.Context()` | `context.Background()` in tests | `t.Context()` | `rg 'context\.Background\(\)' --include='*_test.go'` |
| 1.24 | `b.Loop()` | `for i := 0; i < b.N; i++` | `for b.Loop() {` | `rg 'b\.N' --include='*_test.go'` |
| 1.24 | `omitzero` JSON tag | `omitempty` on zero-value structs | `json:"field,omitzero"` | `rg 'omitempty' --include='*.go'` (then audit) |
| 1.24 | `strings.SplitSeq` | `strings.Split` in range loop | `strings.SplitSeq` | `rg 'for.*strings\.Split\b'` |
| 1.25 | `wg.Go(fn)` | `wg.Add(1); go func(){defer wg.Done()` | `wg.Go(fn)` | `rg 'wg\.Add\(1\)'` |
| 1.26 | `new(val)` | `x := val; &x` | `new(val)` | `rg '(\w+) := \w+[^=\n]*\n.*&\1\b'` |
| 1.26 | `errors.AsType[T]` | `errors.As(err, &t)` | `errors.AsType[T](err)` | `rg 'errors\.As\('` |

**Workflow**: Check `go.mod` for the `go` directive first. Only flag patterns for versions the module has already adopted.

---

## Detection Commands Reference

```bash
# Find all interface{} usage (replace with any)
rg 'interface\{\}' --include='*.go' -n

# Find old-style numeric for loops (candidates for range n)
rg 'for \w+ := 0; \w+ < \w+; \w+\+\+' --include='*.go' -n

# Find old benchmark loop pattern
rg 'for i := 0; i < b\.N; i\+\+' --include='*_test.go' -n

# Find bare error returns (no %w wrapping)
rg 'return err$' --include='*.go' -n

# Find context.Background() in test files (use t.Context() in Go 1.24+)
rg 'context\.Background\(\)' --include='*_test.go' -n

# Find wg.Add(1) patterns (replace with wg.Go in Go 1.25+)
rg 'wg\.Add\(1\)' --include='*.go' -n

# Find sort.Slice / sort.Sort (replace with slices package)
rg 'sort\.Slice|sort\.Sort' --include='*.go' -n

# Find strings.Split used in range loop (replace with strings.SplitSeq in 1.24+)
rg 'for .+ := range strings\.Split' --include='*.go' -n

# Detect Go version in module
grep '^go ' go.mod

# Run go vet
go vet ./...

# Run golangci-lint (requires install)
golangci-lint run ./...
```

---

## Error-Fix Mappings

### `go vet` Errors

| Error | Cause | Fix |
|---|---|---|
| `printf: Errorf call has arguments but no formatting directives` | `fmt.Errorf("msg", err)` | `fmt.Errorf("msg: %w", err)` |
| `lostcancel: the cancel function returned by context.WithCancel should be called, not discarded` | `ctx, _ = context.WithCancel(...)` | `ctx, cancel = ...; defer cancel()` |
| `copylocks: ... contains sync.Mutex` | Mutex copied by value | Pass struct by pointer |
| `unreachable code` | Dead code after `return` | Remove dead branch |
| `assign: self-assignment` | `x = x` | Remove or fix assignment |
| `structtag: ... not compatible with reflect.StructTag.Lookup` | Malformed struct tag | Fix tag syntax (backticks, no spaces around `:`) |
| `tests: Fuzz... does not have the right signature` | Wrong fuzz func signature | Use `func FuzzX(f *testing.F)` |

### `golangci-lint` / `staticcheck` Errors

| Linter / Code | Error | Fix |
|---|---|---|
| `govet` | Same as `go vet` above | See above |
| `SA1006` | `Printf` with no args | Use `Print` or add format verb |
| `SA4006` | Value assigned to variable never used | Remove assignment or use value |
| `SA9003` | Empty branch | Remove empty `if` / `else` |
| `ST1003` | Poorly named identifier (e.g. `Url` should be `URL`) | Rename to Go initialisms (`URL`, `ID`, `HTTP`) |
| `errcheck` | Unchecked error return | Handle or explicitly ignore with `_ =` and comment |
| `gosimple S1039` | Unnecessary use of `fmt.Sprintf` | Use string literal directly |
| `ineffassign` | Ineffectual assignment | Remove unused intermediate variable |
| `noctx` | HTTP request without context | Use `http.NewRequestWithContext` |
| `bodyclose` | HTTP response body not closed | `defer resp.Body.Close()` after nil check |
| `unused` | Exported symbol never used outside package | Remove or unexport |
| `revive` / `exported` | Missing godoc on exported symbol | Add `// FuncName does ...` comment |

### Common `go build` Errors

| Error | Cause | Fix |
|---|---|---|
| `undefined: slices` | Go < 1.21 but using `slices` package | Bump `go` in `go.mod` or use `golang.org/x/exp/slices` |
| `undefined: any` | Go < 1.18 | Bump `go` directive or use `interface{}` |
| `cannot use ... (type X) as type Y` | Interface not satisfied | Check method set; pointer vs value receiver |
| `declared and not used` | Unused local variable | Remove or use `_` |
| `imported and not used` | Unused import | Remove import |

---

## Correct Patterns

### Error Wrapping (always add context)

Instead of:
```go
return err
```

Use:
```go
return fmt.Errorf("operation context: %w", err)
```

### Bare Return → Named + Wrapped

Instead of:
```go
func load(path string) (*Config, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err // loses call site
    }
    ...
}
```

Use:
```go
func load(path string) (*Config, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, fmt.Errorf("open config %s: %w", path, err)
    }
    ...
}
```

### `interface{}` → `any`

Instead of:
```go
func store(key string, val interface{}) { ... }
var cache map[string]interface{}
```

Use:
```go
func store(key string, val any) { ... }
var cache map[string]any
```

### Functional Options Pattern

Extensible constructors without breaking callers:

```go
type ServerOption func(*serverConfig)

func WithTimeout(d time.Duration) ServerOption {
    return func(c *serverConfig) { c.timeout = d }
}

func NewServer(addr string, opts ...ServerOption) *Server {
    cfg := &serverConfig{timeout: 30 * time.Second} // defaults
    for _, o := range opts {
        o(cfg)
    }
    return &Server{addr: addr, cfg: cfg}
}
```
