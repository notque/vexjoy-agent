---
name: batch-editor
description: "Bulk find/replace and frontmatter updates across Hugo posts."
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
routing:
  triggers:
    - "batch edit posts"
    - "bulk frontmatter update"
    - "find replace across files"
  category: content-publishing
---

# Batch Editor Skill

Safe, reversible bulk modifications across Hugo blog posts using a **Preview-Confirm-Apply** pattern. Supports find/replace (literal or regex), frontmatter field operations (add/modify/remove), and content transforms (headings, links, whitespace, quotes). All operations are scoped to `content/posts/*.md` by default and limited to markdown files -- binary files, images, and files outside `content/` are never touched.

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
- `--ignore-case` - Case-insensitive matching (default is case-sensitive)
- `--include-drafts` - Also process draft posts (excluded by default)
- `--scope <path>` - Process different content directory (default: `content/posts/`)
- `--regex` - Enable regex mode for find-replace
- `--force` - Skip git safety checks (dangerous -- no rollback safety net)

### Phase 1: SAFETY CHECK

Before any batch operation, verify git status. Batch edits are irreversible without git, so this check exists to guarantee a rollback path.

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

**Gate**: Git status is clean OR user provides --force. Do not proceed without passing this gate. Even when a few files are involved, uncommitted changes make rollback unreliable -- always verify.

### Phase 2: SCAN AND PREVIEW

The preview is mandatory and cannot be skipped. Users must see every individual change before any file is modified, because batch patterns frequently produce false positives that only a human can catch.

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

Show every match individually with context. Never summarize as "N matches in M files" without showing each one -- users cannot verify correctness from a count alone.

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

**Gate**: Preview displayed with all matches visible. User must see every individual change.

### Phase 3: APPLY (on explicit confirmation only)

Only proceed when user explicitly confirms with `--apply` or clear affirmative. Never auto-apply -- the user must opt in to every destructive operation.

All changes are atomic: validate that every target file is writable before modifying any of them. If any file would fail (permissions, disk space), abort the entire operation rather than leaving the repository in a partially edited state.

**For find-replace:**
1. Read each file with matches
2. Perform all replacements in the file
3. Write the modified content back
4. Report per-file completion

**For frontmatter add:**
1. Read file, parse frontmatter (YAML --- delimiters)
2. Insert new field before closing `---`
3. Preserve original formatting -- keep indentation, quote style, and field order intact. Modifying only the target field produces clean git diffs and avoids breaking parsers.
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

### Examples

**Example 1: Simple Find/Replace**
User says: "Replace Hugo with Hugo SSG across all posts"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Grep for "Hugo" in content/posts/*.md, show all matches with line context (SCAN)
3. Display preview: 3 files, 7 matches with before/after for each line (PREVIEW gate)
4. User confirms with --apply
5. Apply replacements, show per-file summary with rollback command (APPLY + VERIFY)
Result: All occurrences replaced, rollback instructions provided

**Example 2: Add Frontmatter Field**
User says: "Add author field to all posts that don't have one"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Scan all posts, parse frontmatter, identify those missing `author` field (SCAN)
3. Show preview with `+ author: "Author Name"` for each file, skip files that already have it (PREVIEW gate)
4. User confirms with --apply
5. Insert field before closing `---` in each file, preserving formatting (APPLY)
6. Report: 4 files modified, 2 skipped (already had author) (VERIFY)
Result: Field added to posts missing it, existing posts unchanged

**Example 3: Content Transform**
User says: "Demote all H1 headings to H2"
Actions:
1. Check git status -- clean, proceed (SAFETY CHECK)
2. Grep for `^# ` (H1 pattern), show before/after per line (SCAN)
3. Display preview: `# Introduction` -> `## Introduction` for each match (PREVIEW gate)
4. User confirms with --apply
5. Apply regex replacement `^# (.+)$` -> `## $1` across matched files (APPLY)
6. Suggest `hugo --quiet` to verify no build issues (VERIFY)
Result: All H1 headings demoted, H2+ unchanged

**Example 4: Regex with Dry Run**
User says: "Show me all date formats in posts but don't change anything"
Actions:
1. Check git status (SAFETY CHECK)
2. Grep for `(\d{4})-(\d{2})-(\d{2})` across posts (SCAN)
3. Display all matches with file and line context (PREVIEW)
4. DRY RUN mode -- no apply option shown, pattern validation only
Result: User sees all date occurrences, can decide on follow-up action

See `references/examples.md` for full output format templates with banner formatting.

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

## References

- `${CLAUDE_SKILL_DIR}/references/operation-types.md`: Detailed operation syntax and options
- `${CLAUDE_SKILL_DIR}/references/regex-patterns.md`: Common regex patterns for Hugo content
- `${CLAUDE_SKILL_DIR}/references/safety-checklist.md`: Pre-edit validation steps and rollback procedures
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Full output format templates and extended examples
