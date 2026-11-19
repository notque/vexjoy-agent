# GitHub Profile Rules — Category Taxonomy

> **Scope**: Rule taxonomy, confidence scoring, CLAUDE.md output formats

Six categories (not all always present). Confidence scoring prevents over-fitting to single-repo conventions. Low-confidence rules: flag, don't omit.

## Rule Category Taxonomy

| Category | What to Look For | Signal Source | Confidence Threshold |
|----------|-----------------|---------------|---------------------|
| **Naming** | Variable, function, type naming conventions | Code files, PR reviews rejecting bad names | 3+ repos for high |
| **Error Handling** | Return patterns, error wrapping, panic usage | Go/Python/JS error handling in code | 2+ repos |
| **Testing** | Test file organization, assertion style, coverage habits | `*_test.go`, `test_*.py`, `*.spec.ts` | 2+ repos |
| **Architecture** | Package structure, separation of concerns, layering | Directory layout, import patterns | 2+ repos |
| **Style** | Formatting preferences beyond auto-formatters | PR review comments, linter config | 3+ repos |
| **Documentation** | Comment style, README format, docstring habit | Comment density, PR review comments on docs | 2+ repos |

---

## Confidence Scoring Model

```
Confidence = HIGH   if pattern appears in 3+ repos independently
Confidence = MEDIUM if pattern appears in 2 repos OR 1 repo with 5+ instances
Confidence = LOW    if pattern appears in 1 repo with < 5 instances

EXCEPTION: If repos < 3 total, downgrade all scores by one level.
```

### Evidence Requirements by Confidence Level

| Level | Minimum Evidence | CLAUDE.md Output |
|-------|-----------------|-----------------|
| HIGH | 3+ repos, independent occurrence | Full rule with examples |
| MEDIUM | 2 repos or 1 repo, multiple instances | Rule with confidence note |
| LOW | Single instance | Note with "unverified" tag |
| SKIP | Generic/universal pattern | Do not emit — adds no value |

---

## Correct Rule Output Format

### CLAUDE.md-Compatible Rule (High Confidence)

```markdown
## Error Handling

- Wrap errors with context: `return fmt.Errorf("fetchUser %d: %w", id, err)`
  _Observed in: github.com/user/service-a (7 instances), github.com/user/cli-tool (4 instances), github.com/user/api-gateway (3 instances)_

- Never ignore error returns: always `if err != nil { return ... }`
  _Observed in: all 5 analyzed repos — consistent pattern_
```

### JSON Output Format (for tooling)

```json
{
  "rule": "Wrap errors with context using %w",
  "category": "error-handling",
  "confidence": "high",
  "language": "go",
  "evidence": [
    {"repo": "user/service-a", "file": "internal/user/repo.go", "line": 42, "snippet": "fmt.Errorf(\"fetchUser %d: %w\", id, err)"},
    {"repo": "user/cli-tool", "file": "cmd/root.go", "line": 18, "snippet": "fmt.Errorf(\"init: %w\", err)"}
  ],
  "counter_examples": 0
}
```

---

## Pattern Catalog

### Extract Only Developer-Specific Patterns
Universal patterns ("use meaningful names", "write tests") add no value. Only emit non-obvious choices:
- "Uses `_` prefix for unexported package-level vars"
- "Prefers `errors.New` over fmt.Errorf for leaf errors"
- "Names test files `foo_integration_test.go` for integration vs `foo_test.go` for unit"

---

### Cite Evidence for Every Rule
Without evidence, the rule is a guess. Every rule must cite: repo, file (or pattern), optionally line/snippet.

---

### Cross-Reference Before Claiming Personal Style
Single-repo patterns may be project-enforced (framework formatter, contributing guide). Cross-reference 2+ repos. When in doubt: `"project-specific"` label.

---

### PR Review Comments = Strongest Signal
Reviews reveal what the developer enforces on others. Priority order:
1. PR review comments (explicit preferences)
2. Cross-repo patterns (consistent habits)
3. Single-repo patterns (may be project-specific)
4. README/CONTRIBUTING files (project-scoped)

---

## Rule Category Examples

### Naming Rules

```
HIGH: Uses snake_case for all Python variables (5 repos)
HIGH: Uses kebab-case for CLI flags, camelCase for config keys (4 repos)
MEDIUM: Prefixes interfaces with 'I' in TypeScript (2 repos)
LOW: Uses 'mgr' abbreviation for manager variables (1 repo)
```

### Architecture Rules

```
HIGH: Separates HTTP handler layer from business logic (services/ + handlers/) (4 repos)
HIGH: Places all external integrations in adapters/ directory (3 repos)
MEDIUM: Uses repository pattern for data access with interface-based mocking (2 repos)
```

### Testing Rules

```
HIGH: Uses table-driven tests in Go with struct{name string; input X; want Y} pattern (5 repos)
HIGH: Names test files foo_test.go (not test_foo.go) even in Python projects (3 repos)
MEDIUM: Uses testify/assert in preference to standard testing package (2 repos)
```

---

## See Also

- `github-api-patterns.md` — rate limiting, pagination, efficient endpoints for code sampling
- `confidence-scoring.md` — detailed scoring algorithm with edge cases
