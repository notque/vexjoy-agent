# Comment Quality

Review code comments for temporal references, development-activity language, and relative comparisons. Produce structured reports with actionable rewrites that explain WHAT the code does and WHY. Supports `.go`, `.py`, `.js`, `.ts`, `.md`, and `.txt` files.

## Instructions

### Phase 1: SCAN

**Goal**: Identify all comments containing temporal, activity, or relative language.

**Step 1: Determine scope**

Read the repository `CLAUDE.md` first to pick up project-specific comment conventions.

Scan only what was requested. If the user specifies files, scan those files. If the user specifies a directory, scan that directory. Honor explicit scope and suggest expansion separately at the end.

If the user explicitly requests auto-fix, enable it; otherwise present findings for review. For large codebases, group findings by directory when reporting.

**Step 2: Search for temporal patterns**

Flag every instance of these categories (all temporal language ages poorly and needs a timeless rewrite):

- **Temporal words**: "new", "old", "previous", "current", "now", "recently", "latest", "modern"
- **Development activity**: "added", "removed", "deleted", "updated", "changed", "modified", "fixed", "improved", "enhanced", "refactored", "optimized"
- **State transitions**: "replaced", "migrated", "upgraded", "deprecated", "became", "turned into", "evolved"
- **Date references**: "as of", "since", "from", "after", "before"
- **Relative comparisons**: "better than", "faster than", "instead of", "unlike the previous"

**Step 3: Filter false positives**

Leave these untouched — they are legal or tooling markers, not developer prose comments:
- Copyright and license headers
- `@generated` markers
- `@deprecated` annotations (keep the tag; flag only temporal explanation text after it)
- Variable names or string literals containing temporal words
- TODO/FIXME items describing future work without temporal references

When a finding appears, inspect nearby comments in the same function or block because temporal language tends to cluster.

**Gate**: All files in scope scanned. Findings list populated with file path, line number, and matched text for every finding.

### Phase 2: ANALYZE

**Goal**: Understand context for each finding to produce meaningful rewrites.

**Step 1: Read surrounding code**

Read the function, block, or section each comment describes so the rewrite reflects actual behavior rather than merely deleting temporal words.

**Step 2: Classify the comment**

| Finding | Type | Severity |
|---|---|---|
| "now uses JWT" | Temporal + Activity | High |
| "improved perf" | Activity | Medium |
| "Copyright 2024" | Legal (skip) | N/A |

**Step 3: Determine replacement content**

For each comment, identify:
1. What does the code do right now?
2. Why does it do it this way?
3. What value does the comment add for a future reader?

**Gate**: Every finding classified with surrounding code context understood.

### Phase 3: REWRITE

**Goal**: Generate specific, valuable replacement comments.

**Step 1: Draft rewrites**

For each finding, produce file path, line number, current text, suggested replacement, and reasoning:

```markdown
**File: `path/to/file.ext`**

Line X - [Comment type]:
  Current:   // Authentication now uses JWT tokens
  Suggested: // Authenticates requests using signed JWT tokens
  Reason:    "now uses" is temporal - describe current behavior only
```

**Step 2: Validate rewrite quality**

Each rewrite must pass these checks:
- [ ] Makes sense 10 years from now
- [ ] Explains WHAT or WHY rather than WHEN
- [ ] More specific than what it replaces (adds substance rather than deleting a word)
- [ ] Adds value for a future maintainer

If a rewrite strips the temporal word without adding substance (`// Updated error handling` -> `// Error handling`), rewrite with specific behavior (`// Handles database connection errors with exponential backoff retry`).

**Gate**: All rewrites pass quality checks with specific, descriptive replacements.

### Phase 4: REPORT

**Goal**: Deliver a structured, actionable report.

**Step 1: Generate report**

Report facts concisely with file paths and line numbers. Include current text, suggested replacement, and reasoning for every finding:

```markdown
## Comment Quality Review

### Summary
- Files scanned: N
- Issues found: M
- Most common pattern: [temporal word]

### Findings
[All findings with file, line, current text, suggested text, reason]

### Recommendations
1. Apply suggested changes
2. Consider adding linter rules for temporal language prevention
```

**Step 2: Apply fixes (if auto-fix enabled)**

If the user requested auto-fix, apply all rewrites using Edit and verify each edit succeeded. Wait for explicit user authorization before auto-fixing.

**Step 3: Cleanup**

Remove any intermediate scan results, temporary reports, or helper files created during execution.

**Gate**: Report delivered and all findings accounted for.

## Error Handling

### Error: "No Temporal Language Found"
Cause: Files are clean or scope was too narrow.
Solution:
1. Verify common files were scanned (README, main source files).
2. Report clean results — this is a valid positive outcome.
3. Suggest expanding scope if the user suspects issues elsewhere.

### Error: "Too Many Results to Display"
Cause: Large codebase with widespread temporal language.
Solution:
1. Prioritize by file importance (README first, then core modules).
2. Group findings by pattern type.
3. Process files by directory with grouped reports.

### Error: "Comment Meaning Unclear Without History"
Cause: Comment relies on lost development context.
Solution:
1. Read surrounding code to infer current purpose.
2. If purpose is clear from code alone, suggest removing the comment.
3. If purpose remains unclear, ask the user before rewriting.

## Deep References

Load on demand when the current task matches the signal.

| Signal | Reference | Content |
|---|---|---|
| Go files in scope | `references/comment-quality/go-comment-patterns.md` | Go-specific temporal patterns with detection commands |
| Error handling code | `references/comment-quality/error-handling-patterns.md` | Temporal patterns in try/catch, `if err !=`, raise |
| Performance code | `references/comment-quality/performance-patterns.md` | Temporal patterns in cache, pool, concurrency comments |
| Rewrite examples needed | `references/comment-quality/examples.md` | Before/after examples of comment rewrites |
| Full failure mode reference | `references/comment-quality/preferred-patterns.md` | Core temporal failure mode catalog (language-agnostic) |
| Language-specific or doc comments | `references/comment-quality/preferred-patterns-language-specific.md` | Go, Python, JS/TS, README, API failure modes |
