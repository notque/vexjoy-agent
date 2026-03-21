---
name: go-error-handling
description: |
  Go error handling patterns: wrapping with context, sentinel errors, custom
  error types, errors.Is/As chains, and HTTP error mapping. Use when
  implementing error returns, defining package-level errors, creating custom
  error types, wrapping errors with fmt.Errorf, or checking errors with
  errors.Is/As. Use for "error handling", "fmt.Errorf", "errors.Is",
  "errors.As", "sentinel error", "custom error", or "%w". Do NOT use for
  general Go development, debugging runtime panics, or logging strategy.
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
  force_routing: true
---

# Go Error Handling Skill

## Operator Context

This skill operates as an operator for Go error handling implementation, configuring Claude's behavior for idiomatic, context-rich error propagation. It implements the **Pattern Application** architectural approach -- select the right error pattern (wrap, sentinel, custom type), apply it consistently, verify the error chain is preserved.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before implementing error handling
- **Over-Engineering Prevention**: Use the simplest error pattern that fits. Do not create custom types when a sentinel suffices, or sentinels when a simple wrap is enough
- **Always Check Errors**: Every function that returns an error must have its error checked or explicitly ignored with `_ = fn()`
- **Always Wrap with Context**: Never use naked `return err`. Every wrap adds meaningful context describing the operation that failed
- **Preserve Error Chains**: Use `%w` verb in `fmt.Errorf` so callers can use `errors.Is` and `errors.As`
- **Error Messages Form a Narrative**: When read top-to-bottom, wrapped errors tell the story of what happened

### Default Behaviors (ON unless disabled)
- **Lower-case Error Messages**: Error strings start lower-case, no trailing punctuation (Go convention)
- **Contextual Identifiers**: Include relevant IDs, keys, or filenames in wrap messages
- **Sentinel Errors for API Boundaries**: Define sentinel errors for conditions callers need to check
- **Custom Types for Rich Context**: Use custom error types only when callers need structured data
- **errors.Is for Values, errors.As for Types**: Never use string matching or type assertions for error checks
- **HTTP Status Mapping**: Map domain errors to HTTP status codes at the handler boundary

### Optional Behaviors (OFF unless enabled)
- **gopls MCP Error Tracing**: Use `go_symbol_references` to find all usages of sentinel errors across the codebase, `go_diagnostics` to verify error handling correctness after edits. Fallback: `gopls references` CLI or LSP tool
- **Error Wrapping Audit**: Scan for naked `return err` statements and missing `%w` verbs
- **Table-Driven Error Tests**: Generate table-driven tests for error paths

## Available Scripts

- **`scripts/check-errors.sh`** — Detect bare `return err` and log-and-return anti-patterns. Run `bash scripts/check-errors.sh --help` for options.

## What This Skill CAN Do
- Guide idiomatic error wrapping with `fmt.Errorf` and `%w`
- Define and use sentinel errors (`errors.New` package-level vars)
- Create custom error types that implement the `error` interface
- Implement `errors.Is` and `errors.As` checks throughout error chains
- Map domain errors to HTTP status codes at handler boundaries
- Verify error propagation in table-driven tests

## What This Skill CANNOT Do
- Debug runtime panics or stack traces (use systematic-debugging instead)
- Implement structured logging (use logging-specific guidance instead)
- Handle Go concurrency error patterns (use go-concurrency instead)
- Design error monitoring or alerting systems (out of scope)

---

## Instructions

### Step 1: Identify the Error Pattern Needed

Before writing any error handling code, determine which pattern fits:

| Situation | Pattern | Example |
|-----------|---------|---------|
| Operation failed, caller does not check type | **Wrap with context** | `fmt.Errorf("load config: %w", err)` |
| Caller needs to check for specific condition | **Sentinel error** | `var ErrNotFound = errors.New("not found")` |
| Caller needs structured error data | **Custom error type** | `type ValidationError struct{...}` |
| Error at HTTP boundary | **Status mapping** | `errors.Is(err, ErrNotFound) -> 404` |

### Step 2: Wrap Errors with Context

Every error return should add context describing the operation that failed. Error messages form a readable narrative when chained.

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
- Describe the **operation**, not the error (`"load config"` not `"error loading config"`)
- Include **identifying data** (filename, ID, key)
- Use `%w` to preserve the error chain
- Start lower-case, no trailing punctuation

### Step 3: Define Sentinel Errors When Callers Need to Check

Sentinel errors are package-level variables for conditions callers must handle specifically.

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

### Step 4: Create Custom Error Types for Rich Context

Use custom types when callers need to extract structured data from errors.

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

### Step 5: Use errors.Is and errors.As Correctly

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

### Step 6: Map Errors to HTTP Status at Boundaries

Error-to-status mapping belongs at the HTTP handler level, not in domain logic.

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

### Step 7: Test Error Paths

Use table-driven tests to verify error handling:

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

### Step 8: Verify Error Handling Completeness

Before completing, check:
- [ ] All errors checked -- no unchecked returns
- [ ] Context added -- each wrap describes the operation
- [ ] `%w` verb used -- error chain preserved
- [ ] Narrative formed -- error messages readable top-to-bottom
- [ ] Sentinel errors defined -- for conditions callers must check
- [ ] `errors.Is`/`errors.As` used -- no string comparison or type assertion
- [ ] HTTP status mapped -- at handler boundaries only

---

## Error Handling

### Error: "error chain broken -- errors.Is returns false"
Cause: Used `%v` instead of `%w` in `fmt.Errorf`, or created a new error instead of wrapping
Solution:
1. Check all `fmt.Errorf` calls use `%w` for the error argument
2. Ensure sentinel errors are not re-created (use the same `var`)
3. Verify custom types implement `Unwrap()` if they wrap inner errors

### Error: "redundant error context in logs"
Cause: Same context added at multiple call levels, or wrapping errors that already contain the info
Solution:
1. Each level should add only its own context, not repeat caller context
2. One wrap per call boundary -- do not double-wrap at the same level

### Error: "sentinel error comparison fails across packages"
Cause: Error was recreated with `errors.New` instead of using the exported variable
Solution:
1. Import and reference the package-level `var ErrX` directly
2. Never shadow sentinel errors with local `errors.New` calls

---

## Anti-Patterns

### Anti-Pattern 1: Wrapping Without Meaningful Context
**What it looks like**: `return fmt.Errorf("error: %w", err)` or `return fmt.Errorf("failed: %w", err)`
**Why wrong**: "error" and "failed" add zero information. The chain becomes noise.
**Do instead**: Describe the operation: `return fmt.Errorf("load user %s from database: %w", userID, err)`

### Anti-Pattern 2: Naked Error Returns
**What it looks like**: `return err` without wrapping
**Why wrong**: Loses context at every call boundary. Final error message lacks the narrative chain.
**Do instead**: Always wrap: `return fmt.Errorf("outer operation: %w", err)`

### Anti-Pattern 3: Silently Ignoring Errors
**What it looks like**: `file.Close()` without checking the return, or `data, _ := fetchData()` without comment
**Why wrong**: Silent failures cause data corruption, resource leaks, or hard-to-debug issues downstream.
**Do instead**: Check and log: `if err := file.Close(); err != nil { log.Printf("close file: %v", err) }` or explicitly ignore: `_ = file.Close()`

### Anti-Pattern 4: String Matching for Error Checks
**What it looks like**: `if strings.Contains(err.Error(), "not found")`
**Why wrong**: Fragile. Error messages change. Breaks across wrapped errors.
**Do instead**: Use `errors.Is(err, ErrNotFound)` or `errors.As(err, &target)`

### Anti-Pattern 5: Over-Wrapping at the Same Level
**What it looks like**: `return fmt.Errorf("process: error processing: %w", fmt.Errorf("processing failed: %w", err))`
**Why wrong**: Redundant wrapping creates unreadable error chains.
**Do instead**: One clear wrap per call level: `return fmt.Errorf("process user request: %w", err)`

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Simple error, no need to wrap" | Unwrapped errors lose context at every level | Always wrap with `fmt.Errorf` and `%w` |
| "String check is fine for now" | String matching breaks when messages change | Use `errors.Is` or `errors.As` |
| "No one will check this error" | You cannot predict caller needs | Define sentinel if it crosses a package boundary |
| "Custom type is overkill" | Evaluate the actual need, but do not skip if callers need structured data | Match pattern to situation (Step 1 table) |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/patterns.md`: Extended patterns -- gopls tracing, HTTP handler patterns, error wrapping in middleware
