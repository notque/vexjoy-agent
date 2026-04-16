# Error Handling Comment Anti-Patterns

> **Scope**: Temporal and activity-based comment anti-patterns in error handling code, across
> Go, Python, JavaScript, and TypeScript.
> **Version range**: Go 1.13+ (error wrapping), Python 3.11+ (exception groups)
> **Generated**: 2026-04-16

---

## Overview

Error handling code attracts temporal comments more than almost any other area. Bug fixes,
"improved" messages, and "added" retry logic leave comment residue that describes the
repair rather than the current behavior. The skill must recognize these patterns and rewrite
them to explain what the error handling actually does today.

---

## Anti-Pattern Catalog

### ❌ "Fixed bug where X caused error Y" — Bug archaeology

**Detection**:
```bash
grep -rn '//.*[Ff]ixed.*\(bug\|issue\|error\|problem\|crash\)\|//.*[Bb]ug.*fix' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js"
rg '//\s*(Fixed|Fixes|Patched|Resolved) (bug|issue|error|crash|problem)' -i
```

**What it looks like**:
```go
// Fixed bug where nil map access caused panic during error aggregation
if errs == nil {
    errs = make(map[string]error)
}

// Fixed error swallowing issue where database errors were silently ignored
if err != nil {
    return fmt.Errorf("db: %w", err)
}
```

**Why wrong**: The bug is gone. "Fixed bug" tells future readers nothing useful about what
the code does or why the guard exists.

**Fix**:
```go
// Initializes error map on first use; callers may pass nil to request a fresh map.
if errs == nil {
    errs = make(map[string]error)
}

// Wraps database errors with operation context for upstream callers to inspect.
if err != nil {
    return fmt.Errorf("db: %w", err)
}
```

---

### ❌ "Better/improved/enhanced error messages" — Enhancement residue

**Detection**:
```bash
grep -rn '//.*\(better\|improved\|enhanced\|richer\|more descriptive\).*\(error\|message\|msg\)' \
  --include="*.go" --include="*.py" --include="*.ts" -i
rg '//\s*(better|improved|enhanced) (error|err|message)' -i
```

**What it looks like**:
```go
// Provides better error messages with more context
return fmt.Errorf("validate user %d: field %q: %w", id, field, err)

// Improved error reporting to include request ID
log.WithField("request_id", reqID).Error("request failed")
```

**Why wrong**: "Better" is relative. The comment should describe what context is included
and why it helps, not that it is better than before.

**Fix**:
```go
// Error includes user ID and field name so callers can surface field-level validation failures.
return fmt.Errorf("validate user %d: field %q: %w", id, field, err)

// Logs request ID to correlate this failure with distributed trace spans.
log.WithField("request_id", reqID).Error("request failed")
```

---

### ❌ "Added retry logic" / "Now retries on failure" — Capability addition

**Detection**:
```bash
grep -rn '//.*added.*retr\|//.*now.*retr\|//.*retr.*added\|//.*retr.*now' \
  --include="*.go" --include="*.py" --include="*.ts" -i
rg '//\s*(added|now (has|includes|uses)) retry' -i
```

**What it looks like**:
```go
// Added retry logic to handle transient failures
func callWithRetry(ctx context.Context, fn func() error) error {
    for i := 0; i < 3; i++ {
        if err := fn(); err == nil {
            return nil
        }
        time.Sleep(time.Second << i) // exponential backoff
    }
    return fn()
}

// Now retries up to 3 times on network errors
resp, err := client.Do(req)
```

**Why wrong**: "Added retry logic" describes when the retry was introduced. The reader needs
to know the retry policy, which errors trigger it, and what happens on exhaustion.

**Fix**:
```go
// Retries fn up to 3 times with exponential backoff (1s, 2s, 4s).
// Does not retry if ctx is canceled. Returns the last error on exhaustion.
func callWithRetry(ctx context.Context, fn func() error) error {
    for i := 0; i < 3; i++ {
        if err := fn(); err == nil {
            return nil
        }
        time.Sleep(time.Second << i)
    }
    return fn()
}

// Retries up to 3 times on 5xx responses; returns error after final attempt fails.
resp, err := client.Do(req)
```

---

### ❌ "Changed error type from X to Y" — Migration narrative

**Detection**:
```bash
grep -rn '//.*changed.*error\|//.*error.*changed\|//.*switched.*error\|//.*error.*switched' \
  --include="*.go" --include="*.py" --include="*.ts" -i
rg '//\s*(changed|switched|migrated) (error|exception) (type|from|to)' -i
```

**What it looks like**:
```go
// Changed from returning bool to returning error for better composability
func Validate(input string) error { ... }

// Switched to custom error types instead of raw strings
type ValidationError struct {
    Field   string
    Message string
}
```

**Why wrong**: The caller needs to know the current contract, not the migration history.

**Fix**:
```go
// Returns nil if valid; returns ValidationError describing the first failed constraint.
func Validate(input string) error { ... }

// ValidationError carries the field name and human-readable message for structured responses.
type ValidationError struct {
    Field   string
    Message string
}
```

---

### ❌ Python: "Added exception handling for X"

**Detection**:
```bash
grep -rn '#.*added.*except\|#.*now.*except\|#.*handles.*exception.*added' \
  --include="*.py" -i
rg '#\s*(added|now handles|catches) (exception|error)' --type py -i
```

**What it looks like**:
```python
# Added exception handling for connection failures
try:
    conn = db.connect()
except ConnectionError as e:
    logger.error("connection failed: %s", e)
    raise

# Now catches ValueError to avoid crashing on bad input
try:
    value = int(raw)
except ValueError:
    return default
```

**Why wrong**: Describes the history of adding the handler, not what it handles or why.

**Fix**:
```python
# Propagates ConnectionError after logging; callers decide whether to retry.
try:
    conn = db.connect()
except ConnectionError as e:
    logger.error("connection failed: %s", e)
    raise

# Returns default when raw is not a valid integer (e.g., empty string, non-numeric).
try:
    value = int(raw)
except ValueError:
    return default
```

---

### ❌ TypeScript/JavaScript: "Now handles promise rejection"

**Detection**:
```bash
grep -rn '//.*now.*reject\|//.*added.*catch\|//.*handles.*rejection.*now' \
  --include="*.ts" --include="*.js" -i
rg '//\s*(now handles|added) (promise rejection|catch|error handling)' -i
```

**What it looks like**:
```typescript
// Now handles promise rejection to prevent unhandled promise errors
async function fetchData(url: string): Promise<Data> {
    try {
        const res = await fetch(url);
        return res.json();
    } catch (err) {
        logger.error('fetch failed', { url, err });
        throw err;
    }
}
```

**Fix**:
```typescript
// Logs fetch failures with URL context before re-throwing; callers handle retry/fallback.
async function fetchData(url: string): Promise<Data> {
    try {
        const res = await fetch(url);
        return res.json();
    } catch (err) {
        logger.error('fetch failed', { url, err });
        throw err;
    }
}
```

---

## Error-Fix Mappings

| Pattern Found | Root Cause | Rewrite Strategy |
|---------------|------------|------------------|
| `// Fixed bug where X caused Y` | Bug narrative | Describe the guard and what it prevents |
| `// Improved/better error messages` | Enhancement residue | List what context the error includes |
| `// Added retry logic` | Capability addition | State retry count, backoff, and exhaustion behavior |
| `// Changed error type from X to Y` | Migration narrative | Describe the current error type's contract |
| `// Now catches/handles X` | Addition narrative | Explain what the handler does and what callers receive |
| `// Fixed error swallowing` | Bug fix residue | Describe how errors are propagated or logged |

---

## Version-Specific Notes

| Language | Version | Change | Impact |
|----------|---------|--------|--------|
| Go | 1.13 | `%w` wrapping verb in `fmt.Errorf` | `errors.Is`/`errors.As` work on wrapped chains |
| Go | 1.20 | `errors.Join()` for multi-error | Use instead of custom multi-error types |
| Python | 3.11 | `ExceptionGroup` and `except*` | New patterns for concurrent error aggregation |
| TypeScript | 4.0 | Catch clause variables typed as `unknown` | Must narrow type before accessing properties |

---

## Detection Commands Reference

```bash
# All error-handling temporal patterns across languages
grep -rn '//.*\b(fixed|added|improved|enhanced|better)\b.*\b(error|err|exception|catch|retry)\b' \
  --include="*.go" --include="*.py" --include="*.ts" --include="*.js" -i

# Python-specific
grep -rn '#.*\b(added|improved|fixed|now)\b.*\b(exception|error|catch)\b' --include="*.py" -i

# Go error wrapping temporal patterns
grep -rn '//.*\b(better|improved)\b.*\bfmt\.Errorf\|//.*fmt\.Errorf.*\b(better|improved)\b' \
  --include="*.go" -i
```

---

## See Also

- `go-comment-patterns.md` — Go-specific temporal patterns with goroutine and context focus
- `anti-patterns.md` — complete temporal anti-pattern catalog across all languages
