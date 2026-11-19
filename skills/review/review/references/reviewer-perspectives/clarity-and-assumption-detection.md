# Clarity and Assumption Detection Patterns

> **Scope**: Detection commands for code clarity (Newcomer) and hidden assumptions (Contrarian). Load alongside respective reference.
> **Generated**: 2026-04-13

---

## Newcomer: Clarity Patterns

### Name All Constants

**Detection**:
```bash
rg -n '\b[2-9][0-9]+\b|\b1[0-9]{2,}\b' --type go --type py --type ts | rg -v 'port|timeout|size|limit|_test|//|#'
rg -n '"[a-z_]{4,}"' --type go | sort | uniq -d | head -20
```

**Signal**: `if response_code == 429: time.sleep(60)` — Why 60? Why 429?

**Preferred action**: Extract to named constants: `HTTP_TOO_MANY_REQUESTS = 429`, `RATE_LIMIT_BACKOFF_SECONDS = 60`.

---

### Document Public APIs

**Detection**:
```bash
# Go: exported functions without doc comments
rg -n '^func [A-Z]' --type go -B1 | rg -v '^//\|^---'
# Python: public functions without docstrings
rg -n '^def [a-z]' --type py -A1 | rg -v '"""|\047\047\047|#'
# TypeScript: exported without JSDoc
rg -n '^export (function|const|class)' --type ts -B2 | rg -v '/\*\*\|//'
# Go: packages without package docs
find . -name "*.go" -not -path "*/vendor/*" | xargs grep -L "^// Package" | grep -v "_test.go"
```

**Preferred action**: Add doc comment: purpose, key parameters, failure conditions in 2-4 lines.

---

### Use Descriptive Variable Names

**Detection**:
```bash
rg -n ':?=\s*[a-zA-Z][^a-zA-Z]' --type go | rg '^\s+[a-df-wyz]\s' | rg -v 'for\|range\|:=\s*range'
rg -n '\bpct\b|\bamt\b|\bcnt\b|\btmp\b|\bval\b|\bret\b|\bres\b' --type go --type py | rg -v '_test\|//\|#'
```

**Signal**: `func calc(d []float64, n int) float64` — `d`, `n`, `s`, `v` carry zero information.

**Preferred action**: Name variables after what they hold: `dataPoints`, `sum`, `sampleSize`.

---

### Document Preconditions

**Detection**:
```bash
rg -n 'panic\("' --type go | rg -v 'unreachable\|BUG\|test'
rg -n '\[0\]\|\.first()\b' --type py -B3 | rg -v 'if.*len\|if.*empty\|assert'
```

**Signal**: `customer := order.Customer` — panics if nil, no doc or guard.

**Preferred action**: Guard with nil check + error, or document precondition in doc comment.

---

## Contrarian: Hidden Assumption Detection

### Load Environment from Configuration

**Detection**:
```bash
rg -n 'localhost|127\.0\.0\.1' --type go --type py --type ts | rg -v '_test\|example\|//'
rg -n '"/home/\|"/Users/\|"C:\\' --type go --type py --type ts | rg -v '_test\|example'
rg -n ':8080|:3000|:5432|:6379' --type go --type py --type ts | rg -v 'test\|example\|default'
```

**Preferred action**: Load host, port, path from env vars with defaults. Makes assumption explicit and overridable.

---

### Validate Input Bounds

**Detection**:
```bash
rg -n '\[0\]\|\[1\]\|\[-1\]' --type go --type py | rg -v 'test\|len.*>\|if.*len'
rg -n 'args\[0\]\|parts\[1\]' --type go | rg -v '_test\|if.*len'
rg -n 'data\.\w+\.\w+' --type ts | rg -v '\?\.\|if.*data\.\w+\|&&'
```

**Preferred action**: Check bounds before indexing. Return descriptive error on violation.

---

### Scope Mutable State

**Detection**:
```bash
rg -n '^var [A-Za-z].*=\s' --type go | rg -v 'const\|//\|_test\|once\|sync\.'
rg -n '^[a-z_]+ = \[\|^[a-z_]+ = \{' --type py | rg -v 'test\|#\|TYPE_CHECKING'
```

**Preferred action**: Scope mutable state to request/transaction. Protect shared state with mutex, document guarded fields.

---

### Make Ordering Explicit

**Detection**:
```bash
rg -n 'for.*range.*map\[' --type go | rg -v 'sorted\|sort\.'
rg -n 'for.*in.*set(' --type py | rg -v 'sorted\|sort'
rg -n '\.sort()' --type ts --type js | rg -v '(a,\s*b)\|(a:\|b:'
```

**Preferred action**: Sort keys explicitly before iterating. Makes ordering visible in code.

---

## Error-Fix Mappings

| Symptom | Perspective | Fix |
|---------|-------------|-----|
| Can't understand function without reading callers | Newcomer | Add doc comment |
| Works in dev, fails in CI | Contrarian | Load from env var |
| Intermittent test with map data | Contrarian | Sort keys before iterating |
| `index out of range` in prod | Contrarian | Bounds check |
| "What does this number mean?" | Newcomer | Named constant |

---

## Detection Commands Reference

```bash
rg -n '\b[2-9][0-9]+\b' --type go --type py | rg -v '//\|#\|_test'   # Magic numbers
rg -n '^func [A-Z]' --type go -B1 | rg -v '^//'                       # Undocumented exports
rg -n 'localhost|127\.0\.0\.1' --type go --type py --type ts | rg -v '_test'  # Hardcoded localhost
rg -n 'for.*range.*map\[' --type go | rg -v 'sorted\|sort\.'          # Unordered map iteration
rg -n 'args\[0\]\|parts\[1\]' --type go | rg -v '_test\|if.*len'     # Unchecked slice index
rg -n '^var [A-Za-z].*=' --type go | rg -v 'const\|_test\|sync\.'    # Package-level mutable state
```

---

## See Also

- `newcomer.md` — full newcomer framework and severity
- `contrarian.md` — premise validation, assumption auditing, lock-in detection
- `code-review-detection.md` — production readiness and spec compliance detection
