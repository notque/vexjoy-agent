# Scan Commands Reference

Language-specific commands for each scan type. All commands assume you have already scoped to source directories and excluded vendor/generated code.

## Universal Scans (All Languages)

### Stale TODO/FIXME Detection

```bash
# Find all TODO-style comments with file, line, and content
grep -rn -E "(TODO|FIXME|HACK|XXX):" . \
  --include="*.py" --include="*.go" --include="*.js" --include="*.ts" \
  --exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir="venv" \
  --exclude-dir=".venv" --exclude-dir="build" --exclude-dir="dist"

# Age a specific TODO using git blame
git blame -L 45,45 src/api/handler.py --date=short
```

**Age Categories**:
- Critical: > 90 days old
- High: 30-90 days old
- Medium: 7-30 days old
- Low: < 7 days old (normal development)

### Magic Number Detection

```bash
# Python - numeric literals in conditions/assignments
grep -rn -E "[^a-zA-Z0-9](if|while|for|return).*[^.0-9]([2-9]|[1-9][0-9]+)[^.0-9]" . --include="*.py" | head -20

# Go - similar pattern
grep -rn -E "(if|for|return).*[[:space:]]([2-9]|[1-9][0-9]+)[[:space:]]" . --include="*.go" | head -20
```

---

## Python Scans

### Unused Imports

```bash
# Detect unused imports with ruff
ruff check . --select F401,F811 --output-format=grouped
```

Expected output:
```
src/module.py:
  5:1  F401  'os' imported but unused
  8:1  F401  'sys' imported but unused
```

### Dead Code

```bash
# Detect dead code with vulture
vulture . --min-confidence 80 --exclude=venv,build,dist
```

Expected output:
```
src/utils.py:34: unused function 'old_helper' (80% confidence)
src/models.py:56: unused class 'DeprecatedModel' (90% confidence)
```

### Cyclomatic Complexity

```bash
# Show functions with complexity >= C (11+)
radon cc . -s -n C
```

Expected output:
```
src/processor.py
    M 45:0 process_request - C (15)
    M 123:0 validate_data - D (22)
```

Complexity grades:
- A-B (1-10): Good
- C (11-20): Moderate, consider splitting
- D (21-30): High, should split
- E-F (31+): Very high, must refactor

### Missing Type Hints

```bash
# Detect missing type annotations
ruff check . --select ANN --output-format=grouped
```

### Deprecated Functions

```bash
# Search for common deprecation patterns
grep -rn "DeprecationWarning\|FutureWarning" . --include="*.py"

# Known deprecated functions (Python 3.10+)
grep -rn -E "(imp\.find_module|inspect\.getargspec|platform\.dist)" . --include="*.py"
```

### Missing Docstrings

```bash
# Detect missing docstrings
ruff check . --select D --output-format=grouped
```

### Naming Conventions

```bash
# Detect snake_case violations in functions
grep -rn -E "^[[:space:]]*(def|class) [A-Z]" . --include="*.py" | head -20
```

### Duplicate Code

```bash
# Use pylint duplicate detection
pylint --disable=all --enable=duplicate-code . 2>&1 | grep "Similar lines"
```

### Auto-Fix Commands (Safe)

```bash
# Fix unused imports and import sorting
ruff check . --select F401,I001 --fix

# Format code
ruff format .

# Safe auto-fixes only (no unsafe)
ruff check . --fix --unsafe-fixes=false
```

---

## Go Scans

### Unused Imports

```bash
# Detect files with import issues
goimports -l .
```

### Dead Code / Static Analysis

```bash
# Comprehensive static analysis
golangci-lint run --disable-all --enable=unused,deadcode,staticcheck

# Deprecated API detection
staticcheck ./... 2>&1 | grep "deprecated"
```

### Cyclomatic Complexity

```bash
# Show functions with complexity > 10
gocyclo -over 10 .
```

Expected output:
```
15 pkg/service/processor.go:45:1 ProcessRequest
23 pkg/api/handler.go:89:1 ValidateData
```

### Naming Conventions

```bash
# Detect non-idiomatic naming
grep -rn -E "^func [a-z].*\(" . --include="*.go" | grep -v "^func (.*)" | head -20
```

### Auto-Fix Commands (Safe)

```bash
# Fix imports and formatting
goimports -w .
gofmt -w .

# Tidy dependencies
go mod tidy
```

---

## Validation After Fixes

### Python

```bash
pytest              # Run tests
mypy .              # Check types
ruff check .        # Verify linting
```

### Go

```bash
go test ./...       # Run tests
go build ./...      # Verify build
golangci-lint run   # Check linting
```
