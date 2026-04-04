# Reference File Quality Rubric

Classification criteria for Level 0-3. Used by Phase 4 Tier 2 self-assessment and by
`scripts/audit-reference-depth.py` for deterministic scoring.

---

## Level 0 — No References

**Criteria**: No `references/` directory exists for the component.

**What this means**: The agent or skill carries only what the base model already knows.
Generic domain knowledge is available but nothing project-specific, version-specific, or
pattern-specific has been codified.

**Example state**: A new agent created from template with only the body prompt. No references/
directory at all.

**Upgrade path**: Run Phase 1 DISCOVER to identify gaps, then proceed through the full pipeline.

---

## Level 1 — Thin References

**Criteria**: Reference files exist but average fewer than 50 lines, or content is dominated
by generic phrases with no version specificity, no code blocks, and no detection commands.

**What thin looks like**:
```
## Error Handling
Follow best practices for error handling in Go. Ensure errors are handled appropriately
and comprehensively. Consider edge cases and handle them thoroughly.
```

**Why it fails**: Adds no information the model doesn't already have. "Follow best practices"
is not a practice. "Handle appropriately" gives no guidance on what appropriate means here.

**Scoring signals that indicate Level 1**:
- Generic phrases: "best practices", "common issues", "review carefully", "ensure quality"
- No version ranges (`1.22+`, `Python 3.11+`)
- No fenced code blocks (` ``` `)
- No grep/rg/find detection commands
- No function names, package names, or import paths
- Fewer than 5 concrete pattern hits across all reference files

**Upgrade path**: Phase 2 RESEARCH — rewrite thin sections with version-specific content.
Each claim needs either a code example, a version qualifier, or a grep command.

---

## Level 2 — Domain-Specific References

**Criteria**: Reference files contain domain-specific patterns: version numbers, function names,
import paths, fenced code blocks, or enough concrete pattern hits to be useful.

**What Level 2 looks like**:
```
## Error Wrapping (Go 1.13+)

Use `fmt.Errorf("context: %w", err)` to wrap errors. Unwrap with `errors.Is()` and
`errors.As()`. Do NOT use `errors.New()` when you need to preserve the original error.

```go
// Good
if err := db.QueryRow(query).Scan(&id); err != nil {
    return fmt.Errorf("fetch user %d: %w", userID, err)
}
// Bad — loses original error
return errors.New("database error")
```
```

**Why it passes Level 2**: Version qualifier (1.13+), function names (`fmt.Errorf`, `errors.Is`),
code block showing correct and incorrect patterns.

**What's still missing for Level 3**: No detection command to find `errors.New()` misuse in
the codebase. No error-fix mapping for common error messages.

**Scoring signals that indicate Level 2**:
- At least one fenced code block
- OR at least 5 concrete pattern hits with specificity score >= 0.4
- Average line count >= 30 lines per file

---

## Level 3 — Deep References

**Criteria**: Detection commands present AND substantial concrete content (10+ concrete pattern
hits, average 80+ lines per file).

**What Level 3 looks like**:

```markdown
## Anti-Pattern: Using errors.New() When Wrapping

**Detection**:
```bash
grep -rn 'errors\.New(' --include="*.go" | grep -v "_test.go"
rg 'return errors\.New\(' --type go
```

**What it looks like**:
```go
func fetchUser(id int) (*User, error) {
    u, err := db.QueryRow(...).Scan(&u)
    if err != nil {
        return nil, errors.New("database error")  // loses context
    }
}
```

**Why wrong**: `errors.New()` creates a fresh error with no link to the original. Callers
using `errors.Is(err, sql.ErrNoRows)` will get false even when the root cause is ErrNoRows.
Breaks error chain inspection in production debugging.

**Fix**: `return nil, fmt.Errorf("fetchUser %d: %w", id, err)`

**Version note**: `%w` verb available since Go 1.13. For Go 1.12 and earlier, use
`github.com/pkg/errors` Wrap().
```

**Why it's Level 3**: Detection command with two alternatives (grep + rg), code example showing
the exact bad pattern, explanation of *why* it breaks (not just that it's wrong), fix with
version qualifier.

**Scoring signals that indicate Level 3**:
- At least one grep/rg/find detection command
- AND 10+ total concrete pattern hits across all reference files
- AND average 80+ lines per file

---

## Level 3 Checklist (Per Anti-Pattern Entry)

Use this checklist in Phase 4 Tier 2 self-assessment. Each anti-pattern entry should pass
at least 3 of 5:

- [ ] Detection command that finds the pattern in a real codebase (`grep`, `rg`, `find`)
- [ ] Code block showing the bad pattern (copy-pasteable, not pseudocode)
- [ ] Code block showing the correct fix
- [ ] Explanation of *why* the pattern is wrong (behavioral consequence, not style opinion)
- [ ] Version qualifier (when did this change? what version introduced the fix?)

---

## Common Failure Modes

| Failure | Symptom | Fix |
|---------|---------|-----|
| Generic advice | No code blocks, phrases like "handle errors properly" | Replace with specific pattern + code example |
| No detection | Anti-patterns listed but no grep commands | Add `grep -rn` or `rg` command for each anti-pattern |
| Version-free | Patterns stated without version context | Add version ranges where behavior changed |
| No error-fix mapping | Common errors listed without root cause | Add "Error: X → Root cause: Y → Fix: Z" rows |
| Too short | < 50 lines average across files | Each sub-domain warrants at least 80 lines of concrete content |
| Too long | > 500 lines in one file | Split into focused sub-topic files |

---

## Quick Test

To check if a reference file is Level 3, answer these three questions:

1. **Can you detect it?** Pick the most important anti-pattern in the file. Is there a grep
   command that would find it in a real codebase? If no: Level 1.

2. **Is it version-aware?** Does the file mention at least one specific version number where
   behavior changed? If no: likely Level 1-2.

3. **Does it fix, not just flag?** For each anti-pattern, is the correct replacement shown
   in a code block? If no: Level 2 at best.

All three "yes": Level 3. Two "yes": Level 2. Fewer: Level 1.
