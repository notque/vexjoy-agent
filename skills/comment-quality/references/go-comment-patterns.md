# Go Comment Anti-Patterns

> **Scope**: Temporal and activity-based comment anti-patterns specific to Go source files.
> **Version range**: Go 1.13+ (error wrapping), Go 1.18+ (generics)
> **Generated**: 2026-04-16

---

## Overview

Go has a strong convention of package-level doc comments and inline explanation comments.
These comments age poorly when they describe how code changed rather than what it does.
The most common failure modes: comments referencing past bugs, goroutine "fixes", migration
from one pattern to another, and package doc comments that describe the changelog instead
of the API contract.

---

## Anti-Pattern Catalog

### ❌ "Now uses context" — Concurrency migration residue

**Detection**:
```bash
grep -rn '//.*now.*context\|//.*context.*now\|//.*added.*context' --include="*.go" -i
rg '//.*now uses context|//.*added context|//.*context.*added' --type go -i
```

**What it looks like**:
```go
// Bad: Updated to use context for cancellation
func FetchUser(ctx context.Context, id int) (*User, error) { ... }

// Bad: Now propagates context to downstream calls
func processRequest(ctx context.Context, req *Request) error { ... }
```

**Why wrong**: Describes the migration decision, not the current contract. Future maintainers
need to know what the context controls, not that it was "added".

**Fix**:
```go
// Accepts context for cancellation; returns ctx.Err() if parent context expires.
func FetchUser(ctx context.Context, id int) (*User, error) { ... }

// Propagates context deadline and cancellation to all downstream service calls.
func processRequest(ctx context.Context, req *Request) error { ... }
```

---

### ❌ "Fixed panic" / "Fixed nil" — Bug fix residue

**Detection**:
```bash
grep -rn '//.*[Ff]ixed.*\(panic\|nil\|crash\|race\)' --include="*.go"
rg '//\s*(Fixed|Fixes|Fixing) (panic|nil|crash|race condition)' --type go
```

**What it looks like**:
```go
// Fixed panic when receiver is nil
if r == nil {
    return errors.New("nil receiver")
}

// Fixed race condition by adding mutex
mu.Lock()
defer mu.Unlock()
```

**Why wrong**: The bug is gone. "Fixed" describes historical surgery; the invariant being
maintained is what matters to future readers.

**Fix**:
```go
// Guards against nil receiver to prevent panic in field access below.
if r == nil {
    return errors.New("nil receiver")
}

// Mutex protects counter from concurrent modification across goroutines.
mu.Lock()
defer mu.Unlock()
```

---

### ❌ "Improved error handling" / "Better errors"

**Detection**:
```bash
grep -rn '//.*\(improved\|better\|enhanced\).*err\|//.*err.*\(improved\|better\|enhanced\)' --include="*.go" -i
rg '//\s*(improved|better|enhanced) error' --type go -i
```

**What it looks like**:
```go
// Improved error handling for database operations
func queryUser(id int) (*User, error) {
    if err != nil {
        return nil, fmt.Errorf("query user %d: %w", id, err)
    }
}
```

**Why wrong**: "Improved" is relative to a past state that no longer exists. The comment
should explain what context the wrapping provides, not that it improved.

**Fix**:
```go
// Wraps database errors with user ID so log entries can be correlated to a specific user.
func queryUser(id int) (*User, error) {
    if err != nil {
        return nil, fmt.Errorf("query user %d: %w", id, err)
    }
}
```

**Version note**: `%w` error wrapping available since Go 1.13. For Go 1.12-, use
`github.com/pkg/errors` `Wrap()`.

---

### ❌ "Updated to use goroutines" — Parallelism migration

**Detection**:
```bash
grep -rn '//.*\(updated\|changed\|switched\|migrated\).*goroutine\|//.*now.*concurrent' --include="*.go" -i
rg '//\s*(updated|changed|switched) to (use )?goroutine' --type go -i
```

**What it looks like**:
```go
// Updated to use goroutines for better performance
func processItems(items []Item) error {
    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(it Item) { defer wg.Done(); process(it) }(item)
    }
    wg.Wait()
    return nil
}
```

**Why wrong**: "Updated to use" is history. The reader needs the concurrency model and its limits.

**Fix**:
```go
// Processes each item in a separate goroutine; blocks until all complete.
// No concurrency limit — callers must bound the items slice for large inputs.
func processItems(items []Item) error {
    var wg sync.WaitGroup
    for _, item := range items {
        wg.Add(1)
        go func(it Item) { defer wg.Done(); process(it) }(item)
    }
    wg.Wait()
    return nil
}
```

---

### ❌ Package-level doc comments with activity language

**Detection**:
```bash
grep -rn '^// Package.*\b\(added\|updated\|improved\|fixed\|now\|new\|recently\|refactored\)\b' --include="*.go" -i
rg '^// Package \w+ (was|has been|now|recently|is new)' --type go
```

**What it looks like**:
```go
// Package auth provides authentication. Recently updated to support OAuth 2.0 and JWT.

// Package cache was refactored to use Redis instead of in-memory storage.
```

**Why wrong**: Package doc comments appear in `go doc` output and should describe the
package's permanent API contract, not its changelog. Use CHANGELOG.md for history.

**Fix**:
```go
// Package auth provides authentication via OAuth 2.0 and JWT token validation.
// Session tokens expire after 24 hours; use Refresh() to extend active sessions.

// Package cache provides read-through caching backed by Redis with LRU eviction.
```

---

## Error-Fix Mappings

| Pattern Found | Root Cause | Rewrite Strategy |
|---------------|------------|------------------|
| `// Fixed panic when X` | Bug narrative | `// Guards against X to prevent panic` |
| `// Updated to use context` | Migration narrative | `// Accepts context for cancellation/timeout` |
| `// Improved error handling` | Vague enhancement | `// Wraps errors with [specific context detail]` |
| `// Added nil check` | Development activity | `// Guards against nil [receiver/param] to prevent [consequence]` |
| `// Changed to goroutines` | Parallelism migration | `// Processes concurrently; [limit or no-limit note]` |
| `// Now uses sync.Mutex` | Concurrency fix narrative | `// Mutex protects [field] from concurrent access` |
| `// Removed deprecated X` | Removal narrative | Describe what replaced it and why |

---

## Detection Commands Reference

```bash
# All activity-based comment patterns in Go files
grep -rn '//.*\b(fixed|updated|added|changed|improved|enhanced|refactored|removed|migrated)\b' \
  --include="*.go" -i

# "now" temporal patterns (exclude time.Now())
grep -rn '//.*\bnow\b' --include="*.go" | grep -v 'time\.Now\|\.Now()'

# Comparative patterns
grep -rn '//.*\b(better|worse|faster|slower|more efficient|less efficient)\b' \
  --include="*.go" -i

# Package doc with temporal language
grep -rn '^// Package.*\b(new|old|recently|updated|improved|fixed)\b' --include="*.go" -i
```

---

## See Also

- `anti-patterns.md` — complete temporal anti-pattern catalog across all languages
- `examples.md` — before/after rewrite examples
