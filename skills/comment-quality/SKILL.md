---
name: comment-quality
description: |
  Review and fix comments containing temporal references, development-activity
  language, or relative comparisons. Use when reviewing code comments, preparing
  documentation for release, or auditing inline comments for timelessness. Use
  for "check comments", "temporal language", "comment review", or "fix docs".
  Do NOT use for writing new documentation, API reference generation, or
  code style linting unrelated to comment content.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
---

# Comment Quality Skill

## Operator Context

This skill operates as an operator for documentation quality assurance, configuring Claude's behavior for timeless, meaningful code comments and documentation. It implements a **Scan, Analyze, Rewrite, Verify** workflow with deterministic pattern matching against known temporal and activity language.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before scanning
- **Over-Engineering Prevention**: Scan only files explicitly requested or in the current working scope. Do NOT scan entire codebases unless user asks for full audit
- **Remove ALL Temporal Language**: Words like "new", "old", "now", "recently", "updated", "fixed" are NEVER acceptable in comments
- **Focus on WHAT and WHY**: Comments MUST explain current functionality and purpose, never history or development activity
- **No Exceptions for Temporal Language**: Every instance is flagged regardless of perceived harmlessness
- **Preserve Legal and Generated Markers**: Copyright headers, license text, @generated tags, and @deprecated annotations are left unchanged

### Default Behaviors (ON unless disabled)
- **Concise Reporting**: Report facts with file paths and line numbers. No excessive commentary
- **Suggest Rewrites**: Provide corrected versions of every problematic comment
- **Explain Reasoning**: Clarify why temporal language fails for long-term maintainability
- **Check Surrounding Context**: Inspect nearby comments for temporal patterns when one is found
- **Report All Findings**: List every instance, not just the first few
- **Temporary File Cleanup**: Remove scan results, intermediate reports, or helper files at task completion

### Optional Behaviors (OFF unless enabled)
- **Auto-Fix Mode**: Automatically apply corrections without user review (enable with explicit request)
- **Aggressive Scanning**: Check git commit messages and PR descriptions (enable with explicit request)
- **Batch Processing**: Process files by directory with grouped reports (enable for large codebases)

## What This Skill CAN Do
- Identify temporal language, development-activity words, and relative comparisons in comments
- Provide specific, actionable rewrites that explain WHAT and WHY
- Scan multiple file types: `.go`, `.py`, `.js`, `.ts`, `.md`, `.txt`
- Distinguish between developer comments and legal/generated markers
- Generate structured reports with file path, line number, current text, and suggested fix

## What This Skill CANNOT Do
- Write new documentation from scratch (use documentation skills instead)
- Enforce code style rules beyond comment content (use code-linting instead)
- Fix comments without reading surrounding code context
- Auto-fix without explicit user authorization
- Modify copyright headers, license text, or generated code markers

---

## Instructions

### Phase 1: SCAN

**Goal**: Identify all comments containing temporal, activity, or relative language.

**Step 1: Determine scope**

Scan only what was requested. If user specifies files, scan those files. If user specifies a directory, scan that directory. NEVER default to full codebase.

**Step 2: Search for temporal patterns**

Target these categories:
- **Temporal words**: "new", "old", "previous", "current", "now", "recently", "latest", "modern"
- **Development activity**: "added", "removed", "deleted", "updated", "changed", "modified", "fixed", "improved", "enhanced", "refactored", "optimized"
- **State transitions**: "replaced", "migrated", "upgraded", "deprecated", "became", "turned into", "evolved"
- **Date references**: "as of", "since", "from", "after", "before"
- **Relative comparisons**: "better than", "faster than", "instead of", "unlike the previous"

**Step 3: Filter false positives**

Exclude from findings:
- Copyright and license headers
- `@generated` markers
- `@deprecated` annotations (keep the tag, flag only temporal explanation text)
- Variable names or string literals that happen to contain temporal words
- TODO/FIXME items that describe future work without temporal references

**Gate**: All files in scope scanned. Findings list populated with file path, line number, and matched text. Proceed only when gate passes.

### Phase 2: ANALYZE

**Goal**: Understand context for each finding to produce meaningful rewrites.

**Step 1: Read surrounding code**

For each finding, read the function, block, or section the comment describes. Understand what the code actually does.

**Step 2: Classify the comment**

```markdown
| Finding | Type | Severity |
|---------|------|----------|
| "now uses JWT" | Temporal + Activity | High |
| "improved perf" | Activity | Medium |
| "Copyright 2024" | Legal (skip) | N/A |
```

**Step 3: Determine replacement content**

For each comment, identify:
1. What does the code do right now?
2. Why does it do it this way?
3. What value does the comment add for a future reader?

**Gate**: Every finding classified with context understood. Proceed only when gate passes.

### Phase 3: REWRITE

**Goal**: Generate specific, valuable replacement comments.

**Step 1: Draft rewrites**

For each finding, produce:

```markdown
**File: `path/to/file.ext`**

Line X - [Comment type]:
  Current:   // Authentication now uses JWT tokens
  Suggested: // Authenticates requests using signed JWT tokens
  Reason:    "now uses" is temporal - describe current behavior only
```

**Step 2: Validate rewrite quality**

Each rewrite MUST pass these checks:
- [ ] Would this comment make sense in 10 years?
- [ ] Does it explain WHAT or WHY, not WHEN?
- [ ] Is it more specific than what it replaces (not just temporal word removed)?
- [ ] Does it add value for a future maintainer?

If a rewrite just removes the temporal word without adding substance, it fails validation. Rewrite again with specific, descriptive content.

**Gate**: All rewrites pass quality checks. No vague or empty replacements. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Deliver structured, actionable report.

**Step 1: Generate report**

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

If user requested auto-fix, apply all rewrites using Edit tool. Verify each edit succeeded.

**Gate**: Report delivered. All findings accounted for. Task complete.

---

## Examples

### Example 1: Single File Review
User says: "Check the comments in auth.go"
Actions:
1. Scan only auth.go for temporal patterns (SCAN)
2. Read surrounding code for each finding, classify severity (ANALYZE)
3. Draft specific rewrites with WHAT/WHY focus (REWRITE)
4. Deliver report with file path, line, current, suggested, reason (REPORT)
Result: Targeted report for one file with actionable rewrites

### Example 2: Pre-Release Documentation Audit
User says: "Audit all markdown files in docs/ before release"
Actions:
1. Scan all .md files in docs/ directory (SCAN)
2. Classify findings, skip license headers and generated markers (ANALYZE)
3. Generate rewrites, validate each passes the 10-year test (REWRITE)
4. Deliver grouped report sorted by file, with summary statistics (REPORT)
Result: Comprehensive audit with every finding addressed

### Example 3: Auto-Fix Mode
User says: "Fix all temporal comments in pkg/api/ automatically"
Actions:
1. Scan all code files in pkg/api/ (SCAN)
2. Analyze context for each finding (ANALYZE)
3. Generate and validate rewrites (REWRITE)
4. Apply fixes using Edit tool, verify each succeeded, deliver report (REPORT)
Result: All temporal comments replaced in-place with verification

---

## Error Handling

### Error: "No Temporal Language Found"
Cause: Files are clean or scope was too narrow
Solution:
1. Verify common files were scanned (README, main source files)
2. Report clean results -- this is a valid positive outcome
3. Suggest expanding scope if user suspects issues exist elsewhere

### Error: "Too Many Results to Display"
Cause: Large codebase with widespread temporal language
Solution:
1. Prioritize by file importance (README first, then core modules)
2. Group findings by pattern type
3. Enable batch processing optional behavior

### Error: "Comment Meaning Unclear Without History"
Cause: Comment only makes sense with development context that no longer exists
Solution:
1. Read surrounding code to infer current purpose
2. If purpose is clear from code, suggest removing the comment entirely
3. If purpose is unclear, ask user for clarification before rewriting

---

## Anti-Patterns

### Anti-Pattern 1: Scanning Entire Codebase Without Scope
**What it looks like**: User asks "check comments in auth.go" and agent scans all 500 files
**Why wrong**: Wastes tokens, produces overwhelming reports, ignores user's explicit request
**Do instead**: Scan only what was requested. Ask before expanding scope.

### Anti-Pattern 2: Vague Rewrites That Remove Without Adding
**What it looks like**: `// Updated error handling` becomes `// Error handling`
**Why wrong**: Removing temporal word without adding substance produces a useless comment
**Do instead**: `// Handles database connection errors with exponential backoff retry`

### Anti-Pattern 3: Flagging Legal Text and Generated Markers
**What it looks like**: Flagging `Copyright 2023-2024` as temporal language
**Why wrong**: Copyright years are legal requirements; generated markers serve tooling
**Do instead**: Skip license headers, @generated markers, and @deprecated tags

### Anti-Pattern 4: Reporting Without Actionable Fixes
**What it looks like**: "Found 47 instances of temporal language" with no suggested rewrites
**Why wrong**: Diagnostic-only reports create work without providing solutions
**Do instead**: Every finding includes file path, line number, current text, suggested fix, and reason

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "That temporal word is harmless here" | All temporal language ages poorly | Flag and rewrite it |
| "Removing the word is enough" | Removing without adding produces empty comments | Write specific replacement |
| "Legal text has dates too" | Legal text is not a code comment | Skip legal headers, flag code comments |
| "User only asked about one file" | Nearby files may share patterns | Report scope, suggest expansion if warranted |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/temporal-keywords.txt`: Complete list of temporal words to flag
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Before/after examples of comment rewrites
- `${CLAUDE_SKILL_DIR}/references/anti-patterns.md`: Common problematic patterns with explanations
