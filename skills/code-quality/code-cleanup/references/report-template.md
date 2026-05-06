# Code Cleanup Report Template

Use this template to structure cleanup scan output. Replace placeholders with actual data.

---

```markdown
# Code Cleanup Report

**Generated**: {timestamp}
**Repository**: {repo_path}
**Languages**: {Python, Go, etc.}
**Scope**: {directories scanned}
**Total Issues**: {N}

---

## Executive Summary

| Tier | Count | Est. Effort |
|------|-------|-------------|
| Quick Wins (High Impact, Low Effort) | {N} | {time} |
| Important (High Impact, Medium+ Effort) | {N} | {time} |
| Polish (Medium/Low Impact) | {N} | {time} |

**Top Recommendations**:
1. {Highest priority type} - {N} instances
2. {Second priority type} - {N} instances
3. {Third priority type} - {N} instances

---

## Quick Wins

### Unused Imports ({N} files)
**Impact**: Medium | **Effort**: Trivial | **Auto-fixable**: Yes

- `{file}:{line}` - `{import}` imported but unused
- `{file}:{line}` - `{import}` imported but unused

**Fix**: `ruff check . --select F401 --fix` (Python) or `goimports -w .` (Go)

### Stale TODOs ({N} instances, >90 days old)
**Impact**: High | **Effort**: Low

- `{file}:{line}` - TODO from {date} ({N} days old)
  ```
  {context: 3 lines around the TODO}
  ```
  **Suggestion**: {specific action}

### Dead Code ({N} instances)
**Impact**: Medium | **Effort**: Low

- `{file}:{line}` - unused function `{name}` ({confidence}% confidence)

---

## Important

### High Complexity Functions ({N} functions)
**Impact**: High | **Effort**: High

**Critical (Complexity > 20)**:
- `{file}:{line}` - `{function}()` - Complexity: {N}, Lines: {N}
  **Suggestion**: Split into `{func1}()`, `{func2}()`, `{func3}()`

**Moderate (Complexity 11-20)**:
- `{file}:{line}` - `{function}()` - Complexity: {N}, Lines: {N}

### Deprecated Functions ({N} instances)
**Impact**: High | **Effort**: Medium

- `{file}:{line}` - `{old_func}()` deprecated since {version}
  **Fix**: Use `{new_func}()` instead

### Duplicate Code ({N} instances)
**Impact**: High | **Effort**: High

- `{file1}:{func1}()` ({N} lines) vs `{file2}:{func2}()` ({N} lines)
  **Similarity**: {N}%
  **Suggestion**: Extract common logic into `{shared_func}()`

---

## Polish

### Missing Type Hints ({N} functions)
**Impact**: Medium | **Effort**: Medium

- `{file}:{line}` - `{function}({params})` - Missing {param/return} types

### Missing Docstrings ({N} functions/classes)
**Impact**: Medium | **Effort**: Medium

- `{file}:{line}` - `{function}()` public function
- `{file}:{line}` - `{class}` public class

### Naming Inconsistencies ({N} violations)
**Impact**: Low | **Effort**: Medium

- `{file}:{line}` - `{current_name}` should be `{correct_name}`

### Magic Numbers ({N} instances)
**Impact**: Low | **Effort**: Low

- `{file}:{line}` - `{value}` should be `{CONSTANT_NAME} = {value}`

---

## Files by Issue Count

| File | Issues | Types |
|------|--------|-------|
| `{file}` | {N} | {types} |

---

## Auto-Fix Commands

**Safe to run** (no logic changes):

```bash
# Python
ruff check . --select F401,F811,I001 --fix
ruff format .

# Go
goimports -w .
gofmt -w .
go mod tidy
```

---

**Next action**: Run auto-fix commands, then re-scan to verify improvements.
```
