---
name: go-error-handling
description: "Go error handling: wrapping, sentinel, and custom types."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
agent: golang-general-engineer
command: /go-error-handling
routing:
  force_route: true
  triggers:
    - error handling
    - fmt.Errorf
    - errors.Is
    - errors.As
    - error wrapping
    - "%w"
    - sentinel error
    - custom error
    - error context
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
---

# Go Error Handling Skill

Idiomatic Go error handling through context-rich wrapping, sentinel errors, custom error types, and proper error chain inspection. Every error return tells a story -- when read top-to-bottom, wrapped errors form a narrative of what happened and where.

## Available Scripts

- **`scripts/check-errors.sh`** -- Detect bare `return err` and log-and-return anti-patterns. Run `bash scripts/check-errors.sh --help` for options.

## Instructions

### Phase 1: Understand the Context

Read the repository CLAUDE.md before implementing any error handling, because project-specific conventions (error prefixes, logging patterns, custom base types) override generic Go idioms.

Scan existing error patterns in the package to understand what is already in use. When gopls MCP is available, use `go_symbol_references` to find all usages of sentinel errors across the codebase, and `go_diagnostics` to verify error handling correctness after edits. Fallback: `gopls references` CLI or LSP tool.

### Phase 2: Select the Right Error Pattern

Choose the simplest pattern that fits the situation, because over-engineering error types creates unnecessary abstraction that callers must learn and maintain. A simple wrap handles most cases; do not create custom types when a sentinel suffices, or sentinels when a simple wrap is enough.

| Situation | Pattern | Example |
|-----------|---------|---------|
| Operation failed, caller does not check type | **Wrap with context** | `fmt.Errorf("load config: %w", err)` |
| Caller needs to check for specific condition | **Sentinel error** | `var ErrNotFound = errors.New("not found")` |
| Caller needs structured error data | **Custom error type** | `type ValidationError struct{...}` |
| Error at HTTP boundary | **Status mapping** | `errors.Is(err, ErrNotFound) -> 404` |

Even when an error seems simple and unlikely to be inspected, always define a sentinel if the error crosses a package boundary, because you cannot predict what callers will need and adding sentinels later is a breaking change.

**Gate**: Before writing code, name the pattern you are using and why it fits. If the answer is "custom type" but no caller needs structured data, downgrade to sentinel or wrap.

### Phase 3: Wrap Errors with Context

Every error return adds context describing the operation that failed. Never use naked `return err`, because unwrapped errors lose context about where in the call chain the failure occurred -- by the time the error reaches the top, no one knows what operation triggered it.

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
// Output: "parse config JSON from /etc/app.json: invalid character..."
```

Rules for wrap messages:
- Describe the **operation**, not the error (`"load config"` not `"error loading config"`), because prefixes like "error" or "failed" add zero information -- the caller already knows it is an error
- Include **identifying data** (filename, ID, key), because without it the error message cannot distinguish between instances of the same operation
- Use `%w` to preserve the error chain, because `%v` severs the chain and makes `errors.Is`/`errors.As` return false for all wrapped errors
- Start lower-case, no trailing punctuation, because this is Go convention and errors are often concatenated with colons where capitals and periods look wrong

Wrap once per call boundary. Do not double-wrap at the same level (`fmt.Errorf("process: error processing: %w", fmt.Errorf("processing failed: %w", err))`), because redundant wrapping creates unreadable error chains where the same context appears multiple times.

Each level should add only its own context, not repeat caller context, because duplicate context in logs makes errors harder to parse and debug.

Every function that returns an error must have its error checked. Never silently discard errors (`file.Close()` without checking), because silent failures cause data corruption, resource leaks, or hard-to-debug issues downstream. If you intentionally ignore an error, make it explicit with `_ = fn()` so readers know the discard was deliberate, not accidental.

When auditing existing code, scan for naked `return err` statements and missing `%w` verbs to find places where context is being lost.

### Phase 4: Define Sentinel Errors When Callers Need to Check

Sentinel errors are package-level variables for conditions callers must handle specifically. Define them at API boundaries where callers need to branch on error identity.

```go
package mypackage

import "errors"

var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
    ErrInvalidInput = errors.New("invalid input")
)

func GetUser(ctx context.Context, id string) (*User, error) {
    user, err := db.QueryUser(ctx, id)
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return nil, ErrNotFound
        }
        return nil, fmt.Errorf("query user %s: %w", id, err)
    }
    return user, nil
}

// Caller:
user, err := GetUser(ctx, id)
if errors.Is(err, ErrNotFound) {
    // handle not found
}
```

### Phase 5: Create Custom Error Types for Rich Context

Use custom types only when callers need to extract structured data from errors, because a custom type forces callers to import your package and use `errors.As` -- unnecessary coupling if all they need is identity checking via `errors.Is`.

```go
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation failed on field %q: %s", e.Field, e.Message)
}

func ValidateUser(u *User) error {
    if u.Email == "" {
        return &ValidationError{Field: "email", Message: "required"}
    }
    return nil
}

// Caller uses errors.As:
var valErr *ValidationError
if errors.As(err, &valErr) {
    fmt.Printf("Field %s failed: %s\n", valErr.Field, valErr.Message)
}
```

### Phase 6: Inspect Errors with errors.Is and errors.As

Use `errors.Is` for value comparison and `errors.As` for type extraction. Never use string matching (`strings.Contains(err.Error(), "not found")`) or direct type assertions (`err.(*MyError)`), because string matching is fragile -- error messages change across versions and wrapping -- and type assertions skip the unwrap chain so they miss wrapped errors entirely.

**errors.Is** checks if any error in the chain matches a specific value:
```go
if errors.Is(err, ErrNotFound) { /* handle */ }
if errors.Is(err, context.Canceled) { /* cancelled */ }
if errors.Is(err, os.ErrNotExist) { /* file missing */ }
```

**errors.As** extracts a specific error type from the chain:
```go
var pathErr *os.PathError
if errors.As(err, &pathErr) {
    fmt.Printf("Path: %s, Op: %s\n", pathErr.Path, pathErr.Op)
}

var netErr net.Error
if errors.As(err, &netErr) {
    if netErr.Timeout() { /* handle timeout */ }
}
```

### Phase 7: Map Errors to HTTP Status at Boundaries

Error-to-status mapping belongs at the HTTP handler level, not in domain logic, because embedding HTTP semantics in domain code couples your business logic to the transport layer.

```go
func errorToStatus(err error) int {
    switch {
    case errors.Is(err, ErrNotFound):
        return http.StatusNotFound
    case errors.Is(err, ErrUnauthorized):
        return http.StatusUnauthorized
    case errors.Is(err, ErrInvalidInput):
        return http.StatusBadRequest
    default:
        return http.StatusInternalServerError
    }
}
```

### Phase 8: Test Error Paths

Use table-driven tests to verify error handling, because error paths are the most common source of untested behavior and table-driven structure makes it easy to add cases:

```go
func TestProcessUser(t *testing.T) {
    tests := []struct {
        name    string
        input   *User
        wantErr error
    }{
        {
            name:    "nil user",
            input:   nil,
            wantErr: ErrInvalidInput,
        },
        {
            name:    "missing email",
            input:   &User{Name: "test"},
            wantErr: ErrInvalidInput,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := ProcessUser(tt.input)
            if tt.wantErr != nil {
                if !errors.Is(err, tt.wantErr) {
                    t.Errorf("got error %v, want %v", err, tt.wantErr)
                }
            } else if err != nil {
                t.Errorf("unexpected error: %v", err)
            }
        })
    }
}
```

### Phase 9: Verify Error Handling Completeness

Before completing, check:
- [ ] All errors checked -- no unchecked returns, because silent failures cause data corruption and resource leaks
- [ ] Context added -- each wrap describes the operation, because without context the final error message is meaningless
- [ ] `%w` verb used -- error chain preserved, because `%v` severs the chain and breaks `errors.Is`/`errors.As`
- [ ] Narrative formed -- error messages readable top-to-bottom, because debugging relies on the error chain telling a coherent story
- [ ] Sentinel errors defined -- for conditions callers must check, because adding sentinels later is a breaking change
- [ ] `errors.Is`/`errors.As` used -- no string comparison or type assertion, because string matching breaks when messages change
- [ ] HTTP status mapped -- at handler boundaries only, because domain code should not know about HTTP
- [ ] Simplest pattern used -- no over-engineered custom types where a wrap or sentinel suffices

## Error Handling

### Error: "error chain broken -- errors.Is returns false"
Cause: Used `%v` instead of `%w` in `fmt.Errorf`, or created a new error instead of wrapping.
Solution:
1. Check all `fmt.Errorf` calls use `%w` for the error argument
2. Ensure sentinel errors are not re-created (use the same `var`)
3. Verify custom types implement `Unwrap()` if they wrap inner errors

### Error: "redundant error context in logs"
Cause: Same context added at multiple call levels, or wrapping errors that already contain the info.
Solution:
1. Each level should add only its own context, not repeat caller context
2. One wrap per call boundary -- do not double-wrap at the same level

### Error: "sentinel error comparison fails across packages"
Cause: Error was recreated with `errors.New` instead of using the exported variable.
Solution:
1. Import and reference the package-level `var ErrX` directly
2. Never shadow sentinel errors with local `errors.New` calls

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/patterns.md`: Extended patterns -- gopls tracing, HTTP handler patterns, error wrapping in middleware
