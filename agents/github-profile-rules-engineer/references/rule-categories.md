# GitHub Profile Rules — Category Taxonomy

> **Scope**: Taxonomy of extractable rule types, confidence scoring methodology, and output formats for CLAUDE.md compatibility.
> **Version range**: GitHub REST API v3 (all versions)
> **Generated**: 2026-04-08

---

## Overview

Rules extracted from a GitHub profile fall into six categories. Not all categories are always present — a data-focused developer may have no frontend style signals. The confidence scoring prevents over-fitting to a single repo's project-specific conventions. Low-confidence rules should be flagged to the user, not omitted — they may reflect intentional style.

---

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

## Anti-Pattern Catalog

### ❌ Extracting Universal Patterns

**Detection** (in your own rule output — review before emitting):
Look for rules that would appear in any developer's CLAUDE.md:
- "Use meaningful variable names"
- "Write tests for your code"
- "Handle errors appropriately"
- "Use consistent formatting"

**Why wrong**: Universal patterns add no value. The user already knows these. The value of extraction is finding *this developer's* specific choices that differ from the default.

**Fix**: Only emit rules where the developer made a non-obvious choice:
- "Uses `_` prefix for unexported package-level vars" (unusual)
- "Prefers `errors.New` over fmt.Errorf for leaf errors" (specific style)
- "Names test files `foo_integration_test.go` for integration vs `foo_test.go` for unit" (specific org)

---

### ❌ Rules Without Repo + File Evidence

**Detection** (in your rule generation):
```
Rule: "Always wrap errors with context"
Evidence: [none cited]
```

**Why wrong**: Without evidence, the rule is a guess. The user can't verify it, and it may conflict with their actual preference.

**Fix**: Every rule must cite at minimum:
- Which repo the pattern was observed in
- Which file (or file pattern) contains the example
- Optionally: the specific line or code snippet

---

### ❌ Confusing Project Convention with Personal Style

**Detection**: When a pattern appears in only one repo, check if that repo has a contributing guide, linter config, or external style guide that explains it.

**What it looks like**: Extracting "Always use 2-space indentation in Python" from one repo — but the repo is a web framework with enforced formatter config.

**Why wrong**: The developer may be following the project's style, not their own preference. They may write 4-space indentation in personal projects.

**Fix**: Cross-reference at least 2 repos before claiming it's a personal convention. When in doubt, label as `"project-specific"` in confidence metadata.

---

### ❌ Over-Weighting Authored Code vs Review Comments

**Detection**: If rule extraction only reads authored code files without checking PR reviews, it misses preference signals.

**Why wrong**: PR review comments reveal what the developer considers important enough to enforce on *others*. A developer who writes sloppy error handling in their own draft PRs but consistently requests proper error wrapping in reviews is showing you their real standard.

**Correct priority order**:
1. PR review comments (highest signal — explicit preference statements)
2. Cross-repo patterns (broad signal — consistent habits)
3. Single-repo patterns (narrow signal — may be project-specific)
4. README/CONTRIBUTING files (explicit rules, but project-scoped)

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
