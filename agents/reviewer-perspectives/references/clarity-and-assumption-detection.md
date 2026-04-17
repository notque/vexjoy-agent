# Clarity and Assumption Detection Patterns

> **Scope**: Detection commands for code clarity failures (Newcomer perspective) and hidden assumption violations (Contrarian perspective). Load alongside the Newcomer or Contrarian reference when reviewing a real codebase.
> **Version range**: All versions; language-specific commands noted inline
> **Generated**: 2026-04-13

---

## Overview

The Newcomer perspective needs evidence of where code confuses first-time readers. The Contrarian perspective needs to surface hidden assumptions baked into code. Both perspectives produce vague findings without concrete file/line citations — these detection commands provide that evidence.

---

## Newcomer: Clarity Anti-Patterns

### ❌ Magic Numbers and Unexplained Constants

**Detection**:
```bash
# Bare numbers in logic (not 0, 1, -1, or obvious array indices)
rg -n '\b[2-9][0-9]+\b|\b1[0-9]{2,}\b' --type go --type py --type ts | rg -v 'port|timeout|size|limit|_test|//|#'

# Repeated literal that should be a constant
rg -n '"[a-z_]{4,}"' --type go | sort | uniq -d | head -20

# Python: magic numbers in conditionals
rg -n 'if.*[^=!<>]=\s*[2-9][0-9]+' --type py
```

**What it looks like**:
```python
if response_code == 429:
    time.sleep(60)  # Why 60? Why 429 specifically?
```

**Why wrong**: A newcomer cannot distinguish `60` (seconds) from `60` (max retries) or `60` (a business rule). When the value changes, they don't know all the places to update.

**Do instead:**
```python
HTTP_TOO_MANY_REQUESTS = 429
RATE_LIMIT_BACKOFF_SECONDS = 60

if response_code == HTTP_TOO_MANY_REQUESTS:
    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
```

---

### ❌ Missing Documentation on Public APIs

**Detection**:
```bash
# Go: exported functions without doc comments
rg -n '^func [A-Z]' --type go -B1 | rg -v '^//\|^---'

# Python: public functions without docstrings
rg -n '^def [a-z]' --type py -A1 | rg -v '"""|\047\047\047|#'

# TypeScript: exported functions without JSDoc
rg -n '^export (function|const|class)' --type ts -B2 | rg -v '/\*\*\|//'

# Go: entire packages without package docs
find . -name "*.go" -not -path "*/vendor/*" | xargs grep -L "^// Package" | grep -v "_test.go"
```

**What it looks like**:
```go
func ProcessEvent(e Event, cfg *Config, dry bool) (Result, error) {
    // 200 lines of business logic with no explanation
}
```

**Why wrong**: The newcomer cannot call this function without reading all 200 lines to understand what `dry bool` does or what errors to expect.

**Do instead:** Add a doc comment explaining the function's purpose, key parameters, and failure conditions in 2-4 lines.

---

### ❌ Non-Obvious Variable Names

**Detection**:
```bash
# Single-letter variables outside of loops (except i, j, k, n, x, y)
rg -n ':?=\s*[a-zA-Z][^a-zA-Z]' --type go | rg '^\s+[a-df-wyz]\s' | rg -v 'for\|range\|:=\s*range'

# Common abbreviations that hide meaning
rg -n '\bpct\b|\bamt\b|\bcnt\b|\btmp\b|\bval\b|\bret\b|\bres\b' --type go --type py | rg -v '_test\|//\|#'

# Type-only names (just the type repeated as variable name)
rg -n 'var user User\|var config Config\|var err error\b' --type go | rg -v ':=\|_test'
```

**What it looks like**:
```go
func calc(d []float64, n int) float64 {
    var s float64
    for _, v := range d {
        s += v
    }
    return s / float64(n)
}
```

**Why wrong**: `d`, `n`, `s`, `v` carry zero information. Is this averaging? Summing? What is `d`? Why is `n` separate from `len(d)`?

**Do instead:** Name variables after what they hold, not their type or role in the computation. Replace `d` with `dataPoints`, `s` with `sum`, and `n` with `sampleSize`. A reader should be able to understand the intent without running the code.

---

### ❌ Implicit Preconditions Not Documented

**Detection**:
```bash
# Functions calling methods on potentially nil receivers without nil check
rg -n '\w+\.\w+(' --type go | rg -v 'if\s.*==\s*nil\|!= nil' | head -20

# Go: panic on unexpected nil (not-nil assumed but not documented)
rg -n 'panic\("' --type go | rg -v 'unreachable\|BUG\|test'

# Python: Assumes non-empty list without guard
rg -n '\[0\]\|\.first()\b' --type py -B3 | rg -v 'if.*len\|if.*empty\|assert'
```

**What it looks like**:
```go
func ProcessOrder(order *Order) {
    customer := order.Customer // panics if Customer is nil
    send(customer.Email)
}
```

**Why wrong**: A newcomer calling `ProcessOrder` does not know they must pre-populate `Customer`. The panic surfaces far from the actual mistake.

**Do instead:** Either guard with a nil check and return an error, or document the precondition in the function's doc comment: `// ProcessOrder requires order.Customer to be non-nil`.

---

## Contrarian: Hidden Assumption Detection

### ❌ Hardcoded Environment Assumptions

**Detection**:
```bash
# Hardcoded localhost/127.0.0.1
rg -n 'localhost|127\.0\.0\.1' --type go --type py --type ts | rg -v '_test\|example\|comment\|//'

# Absolute paths that only work on one machine
rg -n '"/home/\|"/Users/\|"C:\\' --type go --type py --type ts | rg -v '_test\|example'

# Port numbers hardcoded in business logic (not config)
rg -n ':8080|:3000|:5432|:6379' --type go --type py --type ts | rg -v 'test\|example\|default'
```

**Why wrong**: The Contrarian perspective asks "what happens in CI, staging, or prod?" Code assuming `localhost:5432` silently breaks in containerized environments.

**Do instead:** Load host, port, and path values from environment variables with sensible defaults. `os.Getenv("DB_HOST", "localhost")` documents the assumption explicitly and makes it overridable without a code change.

---

### ❌ Unvalidated Assumption About Input Size

**Detection**:
```bash
# Direct array index without bounds validation
rg -n '\[0\]\|\[1\]\|\[-1\]' --type go --type py | rg -v 'test\|len.*>\|if.*len'

# Go: slice with fixed index in non-test code
rg -n 'args\[0\]\|args\[1\]\|parts\[0\]\|parts\[1\]' --type go | rg -v '_test\|if.*len'

# JSON unmarshaling field access without existence check (JS/TS)
rg -n 'data\.\w+\.\w+' --type ts | rg -v '\?\.\|if.*data\.\w+\|&&'
```

**What it looks like**:
```go
func parseFlags(args []string) string {
    return args[1] // assumes at least 2 args — no validation
}
```

**Why wrong**: The Contrarian asks: "what if the caller passes zero args?" The assumption is invisible and produces a panic, not a clear error message.

**Do instead:** Check bounds before indexing and return a descriptive error on violation. `if len(args) < 2 { return "", fmt.Errorf("expected at least 2 args, got %d", len(args)) }` converts a runtime panic into an actionable message.

---

### ❌ Sync-Only Code Assuming Sequential Execution

**Detection**:
```bash
# Global/package-level mutable state (Go)
rg -n '^var [A-Za-z].*=\s' --type go | rg -v 'const\|//\|_test\|once\|sync\.'

# Python: module-level mutable state used in functions
rg -n '^[a-z_]+ = \[\|^[a-z_]+ = \{' --type py | rg -v 'test\|#\|TYPE_CHECKING'

# Node.js: singleton state assumed safe under concurrent requests
rg -n 'module\.exports\.\w+ = \[\|module\.exports\.\w+ = \{' --type js
```

**Why wrong**: The Contrarian asks: "this code runs fine with one request — what about 100 simultaneous requests?" Module-level mutable state is shared across all requests in most web frameworks.

**Do instead:** Scope mutable state to the request or transaction, not the module. Where shared state is unavoidable, protect it with a `sync.Mutex` or `sync.RWMutex` and document which fields it guards.

---

### ❌ Implicit Ordering Assumption

**Detection**:
```bash
# Map iteration assumed ordered (Go maps are explicitly unordered)
rg -n 'for.*range.*map\[' --type go | rg -v 'sorted\|sort\.'

# Set operations assumed ordered (Python sets are unordered)
rg -n 'for.*in.*set(' --type py | rg -v 'sorted\|sort'

# Array.sort() without comparator (JS default is lexicographic, not numeric)
rg -n '\.sort()' --type ts --type js | rg -v '(a,\s*b)\|(a:\|b:'
```

**What it looks like**:
```go
for key, val := range configMap {
    applyInOrder(key, val) // map iteration order is random in Go
}
```

**Why wrong**: The Contrarian asks: "what assumption is the author making here?" Map iteration being ordered is a frequent hidden assumption that causes intermittent bugs.

**Do instead:** Extract the keys, sort them explicitly with `sort.Strings(keys)`, then iterate the sorted slice. This makes the ordering contract visible in the code rather than hidden in an assumption about language behavior.

---

## Error-Fix Mappings

| Symptom | Perspective | Root Cause | Detection | Fix |
|---------|-------------|------------|-----------|-----|
| Newcomer can't understand a function without reading its callers | Newcomer | Missing doc comment or implicit precondition | `rg '^func [A-Z]' --type go -B1` | Add doc comment explaining inputs and error conditions |
| Code works in dev, fails in CI | Contrarian | Hardcoded localhost or absolute path | `rg 'localhost\|127\.0\.0\.1'` | Load from env var with documented default |
| Intermittent test failure with map data | Contrarian | Assumed map iteration order | `rg 'for.*range.*map\['` | Sort keys before iterating |
| `index out of range` in production | Contrarian | Unvalidated slice access | `rg 'args\[0\]\|parts\[1\]'` | Add bounds check with clear error message |
| New contributor asks "what does this number mean?" | Newcomer | Magic constant | `rg '\b[2-9][0-9]+\b' --type go` | Extract to named constant |

---

## Detection Commands Reference

```bash
# Magic numbers in conditionals
rg -n '\b[2-9][0-9]+\b' --type go --type py | rg -v '//\|#\|_test'

# Exported functions without doc comments (Go)
rg -n '^func [A-Z]' --type go -B1 | rg -v '^//'

# Hardcoded localhost (assumption about environment)
rg -n 'localhost|127\.0\.0\.1' --type go --type py --type ts | rg -v '_test'

# Unordered map iteration (Go)
rg -n 'for.*range.*map\[' --type go | rg -v 'sorted\|sort\.'

# Direct slice index without bounds (Go)
rg -n 'args\[0\]\|parts\[1\]' --type go | rg -v '_test\|if.*len'

# Package-level mutable state (Go)
rg -n '^var [A-Za-z].*=' --type go | rg -v 'const\|_test\|sync\.'
```

---

## See Also

- `newcomer.md` — full newcomer perspective framework and severity classification
- `contrarian.md` — full contrarian framework: premise validation, assumption auditing, lock-in detection
- `code-review-detection.md` — detection commands for production readiness and spec compliance issues
