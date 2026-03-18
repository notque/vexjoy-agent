---
name: batch-editor
description: |
  Safe bulk editing across multiple Hugo markdown posts: find/replace, frontmatter
  updates, content transforms with mandatory preview before apply. Use when user
  needs batch text replacement, bulk frontmatter field changes, heading/link/whitespace
  normalization, or regex-based content transforms across posts. Use for "batch edit",
  "find and replace across files", "add field to all posts", "bulk update tags".
  Do NOT use for single-file edits, structural refactoring, or content generation.
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

# Batch Editor Skill

## Operator Context

This skill operates as an operator for bulk content editing, configuring Claude's behavior for safe, reversible batch modifications across Hugo blog posts. It implements a **Preview-Confirm-Apply** pattern with mandatory git safety checks before any destructive operation.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files
- **Preview First**: ALWAYS show complete preview before applying any changes
- **Git Safety**: Check for uncommitted changes before any modification
- **Never Auto-Apply**: Require explicit user confirmation for destructive operations
- **Complete Output**: Show all affected files and changes, never summarize matches
- **Atomic Operations**: All files succeed or none are modified

### Default Behaviors (ON unless disabled)
- **Preview Mode**: Show all matches without modifying files
- **Backup Reminder**: Suggest git commit/stash before applying changes
- **Case Sensitive**: Find/replace is case-sensitive by default
- **Content Scope**: Only process files in content/posts/
- **Preserve Formatting**: Keep original frontmatter indentation, quotes, field order

### Optional Behaviors (OFF unless enabled)
- **Case Insensitive**: Use --ignore-case for case-insensitive matching
- **Include Drafts**: Use --include-drafts to also process draft posts
- **Extended Scope**: Use --scope to process other content directories
- **Force Apply**: Use --force to skip git safety checks (dangerous)

## What This Skill CAN Do
- Find and replace text (literal or regex) across multiple markdown files
- Add, modify, or remove frontmatter fields in bulk
- Batch update tags, categories, or other taxonomy arrays
- Standardize heading levels, link formats, and whitespace
- Preview all changes with line-level context before applying
- Count total matches and affected files with dry-run validation

## What This Skill CANNOT Do
- Modify files outside content/ directory
- Skip the preview step (hardcoded safety)
- Undo changes without git (use git rollback)
- Modify files when git has uncommitted changes (unless --force)
- Process binary files or images
- Make external API calls

---

## Instructions

### Usage

```
/batch-edit [operation] [options]
```

**Operations:**
- `find-replace` - Text replacement with optional regex
- `frontmatter` - Add/modify/remove frontmatter fields
- `transform` - Content transformations (links, headings, whitespace, quotes)

**Common Options:**
- `--dry-run` - Validate pattern, show matches, don't apply
- `--apply` - Apply changes after preview confirmation
- `--ignore-case` - Case-insensitive matching
- `--include-drafts` - Also process draft posts
- `--scope <path>` - Process different content directory
- `--regex` - Enable regex mode for find-replace

### Phase 1: SAFETY CHECK

Before any batch operation, verify git status:

```bash
cd $HOME/your-project && git status --porcelain
```

**Analyze results:**

| Status | Action |
|--------|--------|
| Empty (clean) | Proceed with operation |
| Has changes | Warn user, suggest commit/stash first |
| Not a git repo | Warn about no rollback capability |

**Safety check output must include:**
- Repository path and current branch
- Clean/dirty status
- List of modified files (if any)
- Recommended action (commit, stash, or proceed)

**Gate**: Git status is clean OR user provides --force. Do not proceed without passing this gate.

### Phase 2: SCAN AND PREVIEW

**Step 1: Parse request**

Extract from user request:
- **Pattern**: Text or regex to find (for find-replace)
- **Replacement**: Text to replace with (for find-replace)
- **Field/Value**: Frontmatter field name and value (for frontmatter ops)
- **Action**: add | modify | remove (for frontmatter ops)
- **Scope**: File pattern (default: `content/posts/*.md`)
- **Options**: Case sensitivity, regex mode, draft inclusion

**Step 2: Find all matches**

Use Grep to locate all matches within scope:

```bash
# For literal text
grep -rn "search-pattern" $HOME/your-project/content/posts/*.md

# For regex
grep -rn -E "regex-pattern" $HOME/your-project/content/posts/*.md
```

For frontmatter operations, read each file and parse the YAML frontmatter block between `---` delimiters to check field presence and values.

**Step 3: Generate preview**

For each match, show:
- File path relative to repository root
- Line number and surrounding context
- Before/after comparison (for replacements)
- Diff-style additions (+) and removals (-) for frontmatter operations
- Total count of files affected and matches found

**Preview format for find-replace:**
```
content/posts/example.md:
  Line 5:  "original text here"
        -> "replacement text here"
```

**Preview format for frontmatter:**
```
content/posts/example.md:
  + author: "Author Name"           (add)
  - deprecated: "old"        (remove)
  ~ tags: ["a"] -> ["a","b"] (modify)
```

**Gate**: Preview displayed with all matches visible. User must see every individual change. Never summarize as "N matches in M files" without showing each one.

### Phase 3: APPLY (on explicit confirmation only)

Only proceed when user explicitly confirms with `--apply` or clear affirmative.

**For find-replace:**
1. Read each file with matches
2. Perform all replacements in the file
3. Write the modified content back
4. Report per-file completion

**For frontmatter add:**
1. Read file, parse frontmatter (YAML --- delimiters)
2. Insert new field before closing `---`
3. Preserve original formatting (indentation, quote style, field order)
4. Write modified content

**For frontmatter modify:**
1. Read file, locate the target field line
2. Replace only that line's value
3. Preserve formatting of all other fields
4. Write modified content

**For frontmatter remove:**
1. Read file, locate and remove the target field line
2. Write modified content

**Gate**: All files written successfully. Show post-apply summary with per-file counts and rollback command.

### Phase 4: VERIFY

After applying changes:

1. **Report totals**: Files changed, total replacements or field modifications
2. **Show per-file summary**: Each file with count of changes made
3. **Provide rollback command**: `git checkout -- content/posts/`
4. **Suggest next steps**:
   - `git diff content/posts/` to review all changes
   - `hugo --quiet` to verify site still builds
   - `git commit -am "batch edit: description"` to save changes

**Gate**: Post-apply summary displayed with rollback instructions.

### Content Transformation Reference

The `transform` operation supports these built-in transforms:

| Transform | Pattern | Replacement |
|-----------|---------|-------------|
| Demote headings | `^(#{1,5}) (.+)$` | `#$1 $2` |
| Promote headings | `^##(#{0,4}) (.+)$` | `#$1 $2` |
| Trailing whitespace | `[ \t]+$` | (empty) |
| Multiple blank lines | `\n{3,}` | `\n\n` |
| Smart quotes to straight | `[\u201C\u201D]` | `"` |
| HTTP to HTTPS links | `\[([^\]]+)\]\(http://` | `[$1](https://` |

For custom transforms, use `find-replace --regex` with user-provided patterns. See `references/regex-patterns.md` for tested patterns.

---

## Examples

### Example 1: Simple Find/Replace
User says: "Replace Hugo with Hugo SSG across all posts"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Grep for "Hugo" in content/posts/*.md, show all matches with line context (SCAN)
3. Display preview: 3 files, 7 matches with before/after for each line (PREVIEW gate)
4. User confirms with --apply
5. Apply replacements, show per-file summary with rollback command (APPLY + VERIFY)
Result: All occurrences replaced, rollback instructions provided

### Example 2: Add Frontmatter Field
User says: "Add author field to all posts that don't have one"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Scan all posts, parse frontmatter, identify those missing `author` field (SCAN)
3. Show preview with `+ author: "Author Name"` for each file, skip files that already have it (PREVIEW gate)
4. User confirms with --apply
5. Insert field before closing `---` in each file, preserving formatting (APPLY)
6. Report: 4 files modified, 2 skipped (already had author) (VERIFY)
Result: Field added to posts missing it, existing posts unchanged

### Example 3: Content Transform
User says: "Demote all H1 headings to H2"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Grep for `^# ` (H1 pattern), show before/after per line (SCAN)
3. Display preview: `# Introduction` -> `## Introduction` for each match (PREVIEW gate)
4. User confirms with --apply
5. Apply regex replacement `^# (.+)$` -> `## $1` across matched files (APPLY)
6. Suggest `hugo --quiet` to verify no build issues (VERIFY)
Result: All H1 headings demoted, H2+ unchanged

### Example 4: Regex with Dry Run
User says: "Show me all date formats in posts but don't change anything"
Actions:
1. Check git status (SAFETY CHECK)
2. Grep for `(\d{4})-(\d{2})-(\d{2})` across posts (SCAN)
3. Display all matches with file and line context (PREVIEW)
4. DRY RUN mode -- no apply option shown, pattern validation only
Result: User sees all date occurrences, can decide on follow-up action

See `references/examples.md` for full output format templates with banner formatting.

---

## Error Handling

### Error: "No Matches Found"
Cause: Pattern does not match any content in scope
Solution:
1. Check spelling of search pattern
2. Try case-insensitive with --ignore-case
3. Expand scope with --scope content/
4. Verify files exist in target directory

### Error: "Uncommitted Git Changes"
Cause: Working directory has modifications that could be lost
Solution:
1. Commit changes: `git commit -am "backup before batch edit"`
2. Stash changes: `git stash`
3. Override with --force (not recommended)

### Error: "Invalid Regex Pattern"
Cause: Malformed regular expression syntax
Solution:
1. Escape special characters: `\( \) \[ \]`
2. Test pattern first: `grep -E "pattern" content/posts/*.md`
3. Use literal mode (no --regex) for simple text replacement

### Error: "Partial Application Failure"
Cause: Some files could not be written (permissions, disk space)
Solution:
1. Check file permissions: `ls -la content/posts/`
2. Rollback applied changes: `git checkout -- content/posts/`
3. Fix permissions: `chmod 644 content/posts/*.md`
4. Retry operation

---

## Anti-Patterns

### Anti-Pattern 1: Applying Without Preview
**What it looks like**: Immediately modifying files without showing what will change
**Why wrong**: Batch operations can cause widespread damage. User loses ability to catch mistakes.
**Do instead**: ALWAYS show complete preview first. Never modify files until user explicitly confirms.

### Anti-Pattern 2: Summarizing Instead of Showing
**What it looks like**: "Found 47 matches across 12 files. Apply changes?"
**Why wrong**: User cannot verify each change is correct. Some matches may be false positives.
**Do instead**: Show every match with line-level before/after context.

### Anti-Pattern 3: Ignoring Git State
**What it looks like**: Proceeding with batch edit when git has uncommitted changes
**Why wrong**: User may lose work. Rollback becomes complicated with mixed changes.
**Do instead**: Always check git status first. Block if uncommitted changes exist (unless --force).

### Anti-Pattern 4: Destroying Frontmatter Format
**What it looks like**: Rewriting entire frontmatter block when modifying a single field
**Why wrong**: Creates noisy git diffs, may break parsers, loses author's preferred formatting.
**Do instead**: Modify only the target field. Preserve indentation, quote style, and field order.

### Anti-Pattern 5: Non-Atomic Application
**What it looks like**: Applying changes to some files, then failing on others mid-operation
**Why wrong**: Leaves repository in inconsistent state with partial edits.
**Do instead**: Validate all files are writable before applying any changes. All or nothing.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Only a few files, no need to preview" | Few files can still have false positives | Show complete preview |
| "Pattern is simple, regex won't over-match" | Simple patterns match unexpected content | Test with grep first |
| "Git is clean, no need to check" | Status could have changed since last check | Always verify |
| "User said apply, skip the preview" | User may not realize scope of changes | Preview is hardcoded, never skip |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/operation-types.md`: Detailed operation syntax and options
- `${CLAUDE_SKILL_DIR}/references/regex-patterns.md`: Common regex patterns for Hugo content
- `${CLAUDE_SKILL_DIR}/references/safety-checklist.md`: Pre-edit validation steps and rollback procedures
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Full output format templates and extended examples
