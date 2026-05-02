# Go Patterns, Gates, and Rationalizations

Modern idiom replacements, hard gates, rationalizations, and death loop prevention.

## Modern Idiom Patterns

| Outdated Pattern | Modern Replacement | Since |
|-----------------|-------------------|-------|
| `interface{}` | `any` | Go 1.18 |
| `if a > b { return a }; return b` | `max(a, b)` | Go 1.21 |
| Manual loop for slice search | `slices.Contains(items, x)` | Go 1.21 |
| `sort.Slice(s, less)` | `slices.SortFunc(s, cmp)` | Go 1.21 |
| Manual map copy loop | `maps.Clone(m)` | Go 1.21 |
| `sync.Once` + wrapper func | `sync.OnceFunc(fn)` | Go 1.21 |
| `for i := 0; i < n; i++` | `for i := range n` | Go 1.22 |
| Chain of nil checks for defaults | `cmp.Or(a, b, c, "default")` | Go 1.22 |
| `for _, part := range strings.Split(s, ",")` | `for part := range strings.SplitSeq(s, ",")` | Go 1.24 |
| `for i := 0; i < b.N; i++` in benchmarks | `for b.Loop()` | Go 1.24 |
| `ctx, cancel := context.WithCancel(...)` in tests | `ctx := t.Context()` | Go 1.24 |
| `json:"field,omitempty"` for structs/Duration | `json:"field,omitzero"` | Go 1.24 |
| `wg.Add(1); go func() { defer wg.Done()... }()` | `wg.Go(func() { ... })` | Go 1.25 |
| `x := val; &x` for pointer | `new(val)` | Go 1.26 |
| `var t *T; errors.As(err, &t)` | `errors.AsType[*T](err)` | Go 1.26 |

### Protocol Reasoning Instead of Library Verification
**Signal**: "Kafka consumer groups will rebalance, so this is safe."
**Why wrong**: Protocol-level != library-level behavior.
**Do instead**: Read source in GOMODCACHE: `cat $(go env GOMODCACHE)/path/to/lib@version/file.go`

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

### Go-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Tests pass, code is correct" | Tests may not cover race conditions | Run `go test -race`, check coverage |
| "Go's type system catches it" | Types miss goroutine leaks and logic errors | Test concurrency, check goroutine lifecycle |
| "It compiles, it's correct" | Compilation ≠ Correctness | Run tests, vet, and race detector |
| "Defer will handle cleanup" | Defer only runs when function returns | Check early returns, panics, infinite loops |
| "Channels prevent race conditions" | Channels alone leave some races uncovered | Still need proper synchronization patterns |
| "Error handling can wait" | Errors compound in production | Handle errors at write time |
| "Small change, skip tests" | Small changes cause big bugs | Full test suite always |
| "This Go version doesn't matter" | Using wrong-version features breaks builds | Check `go.mod`, use version-appropriate features |
| "gopls isn't needed, I can grep" | gopls understands types and references; grep sees text | Use `go_symbol_references` before renaming |

## Hard Gate Patterns

Before writing Go code, check for these patterns. If found:
1. STOP - Pause implementation
2. REPORT - Flag to user
3. FIX - Remove before continuing

See [shared-patterns/forbidden-patterns-template.md](../../skills/shared-patterns/forbidden-patterns-template.md) for framework.

| Pattern | Why Blocked | Correct Alternative |
|---------|---------------|---------------------|
| `_ = err` (blank error) | Silent failures, violates Go conventions | `if err != nil { return fmt.Errorf("context: %w", err) }` |
| `interface{}` instead of `any` | Deprecated syntax (Go 1.18+) | Use `any` |
| `panic()` in library code | Crashes caller, no recovery | Return errors instead |
| Unbuffered channel in select | Potential deadlock | Use buffered channel or proper sync |
| `go func()` without WaitGroup/context | Goroutine leak, no way to wait/cancel | Use WaitGroup or context for lifecycle |
| `for i := 0; i < b.N; i++` | Outdated benchmark loop (Go 1.24+) | Use `b.Loop()` |
| `json:",omitempty"` on structs/Duration | Doesn't work correctly for these types | Use `json:",omitzero"` (Go 1.24+) |

### Detection
```bash
# Find blank error ignores
grep -rn "_ = .*err" --include="*.go"

# Find interface{} usage
grep -rn "interface{}" --include="*.go"

# Find panic in non-main packages
grep -rn "panic(" --include="*.go" --exclude="*_test.go" | grep -v "/main.go"

# Find outdated benchmark loops
grep -rn "for.*b\.N" --include="*_test.go"

# Find omitempty on struct/Duration fields
grep -rn 'omitempty.*Duration\|omitempty.*Time\|omitempty.*struct' --include="*.go"
```

### Exceptions
- `panic()` in `main()` or `init()` for configuration errors
- `interface{}` in generated code (protobuf, etc.)
- Blank identifier for intentionally ignored values (not errors)
- `omitempty` when targeting Go < 1.24

## Blocker Criteria

STOP and ask the user (get explicit confirmation) before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Concurrency model choice | Architecture decision | "Worker pool vs fan-out/fan-in? What's the concurrency pattern?" |
| Error handling strategy | Consistency needed | "Wrap all errors or sentinel errors? What's the existing pattern?" |
| Interface design | API contract | "What operations should this interface support?" |
| External dependency | Maintenance burden | "Add package X or implement? What's the maintenance posture?" |
| Breaking API change | Affects consumers | "This changes public API. How to handle migration?" |
| Database/storage choice | Long-term architecture | "SQL, NoSQL, or file-based? What are the requirements?" |

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for any operation (build, test, vet)
- Clear failure escalation: fix root cause, address a different aspect each attempt

### Compilation-First Rule
1. Verify `go build` succeeds before running tests
2. Fix compilation errors before linting
3. Run tests before benchmarking or profiling

### Recovery Protocol
**Detection**: If making repeated similar changes that fail
**Intervention**:
1. Run `go build ./...` to verify compilation
2. Run `go test -v ./...` to see actual failures
3. Read the ACTUAL error message carefully
4. Check if fix addresses root cause vs symptom
5. Use `go_diagnostics` if gopls MCP is available for richer error context
