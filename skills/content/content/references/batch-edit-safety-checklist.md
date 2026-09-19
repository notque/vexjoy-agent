# Batch Editor Safety Checklist

Pre-edit validation steps to ensure safe batch operations.

---

## Pre-Operation Checklist

### 1. Git Status Verification

**Check Command:**
```bash
cd $HOME/your-project && git status --porcelain
```

| Status | Action |
|--------|--------|
| Empty output | Safe to proceed |
| `M content/...` | Modified files - commit or stash first |
| `?? content/...` | Untracked files - add or ignore |
| `D content/...` | Deleted files - commit or restore |

**Decision Matrix:**

```
Uncommitted changes?
  |
  +-- No --> Proceed with batch edit
  |
  +-- Yes --> Are changes related to batch edit?
               |
               +-- Yes --> Commit first: git commit -am "pre-batch backup"
               |
               +-- No --> Stash first: git stash
```

---

### 2. Scope Verification

**Before running any batch operation:**

1. Confirm target directory exists:
   ```bash
   ls -la $HOME/your-project/content/posts/
   ```

2. Count target files:
   ```bash
   find $HOME/your-project/content/posts -name "*.md" | wc -l
   ```

3. Verify scope is not too broad:
   ```
   Scope: content/posts/*.md    - OK (specific)
   Scope: content/**/*.md       - Caution (recursive)
   Scope: **/*.md               - Dangerous (entire repo)
   ```

---

### 3. Pattern Validation

**Test pattern before applying:**

```bash
# Verify pattern matches expected content
grep -rn -E "pattern" content/posts/

# Count total matches
grep -rc -E "pattern" content/posts/ | awk -F: '{sum += $2} END {print sum}'

# Preview first few matches with context
grep -rn -E -B1 -A1 "pattern" content/posts/ | head -30
```

**Pattern Validation Checklist:**

- [ ] Pattern matches intended content
- [ ] Pattern does NOT match unintended content
- [ ] Replacement produces valid output
- [ ] No false positives in preview

---

### 4. Backup Verification

**Ensure rollback is possible:**

```bash
# Verify git is available
git --version

# Verify in git repo
git rev-parse --git-dir

# Check current branch
git branch --show-current

# Verify clean state (after stash/commit)
git status --porcelain
```

**Rollback Commands (if needed):**

```bash
# Undo all uncommitted changes
git checkout -- content/posts/

# Undo specific file
git checkout -- content/posts/specific-post.md

# Restore from stash
git stash pop
```

---

## During-Operation Checklist

### 5. Preview Review

**Before applying, verify in preview:**

- [ ] Correct number of files affected
- [ ] Correct number of replacements per file
- [ ] Before/after content looks correct
- [ ] No unintended side effects visible

**Red Flags in Preview:**

| Issue | Action |
|-------|--------|
| Too many files | Narrow scope |
| Unexpected matches | Refine pattern |
| Partial matches | Use word boundaries |
| Format changes | Preserve original formatting |

---

### 6. Confirmation Gate

**Never auto-apply. Always require explicit confirmation:**

```
Apply changes? [--apply to proceed]
```

**Valid Confirmation:**
- User explicitly provides --apply flag
- User explicitly says "apply" or "yes, apply"

**Invalid (do not apply):**
- User says "ok" (ambiguous)
- User asks questions
- User is silent
- User says "looks good" (not explicit)

---

## Post-Operation Checklist

### 7. Verification Steps

**After applying changes:**

1. Count modified files:
   ```bash
   git status --short | grep "^ M" | wc -l
   ```

2. Review changes:
   ```bash
   git diff content/posts/
   ```

3. Spot-check a few files:
   ```bash
   head -30 content/posts/first-post.md
   ```

4. Test Hugo build:
   ```bash
   cd $HOME/your-project && hugo --quiet
   ```

---

### 8. Commit or Rollback Decision

**After verification:**

| Result | Action |
|--------|--------|
| Changes correct | `git commit -am "batch edit: description"` |
| Some issues | Fix manually, then commit |
| Major issues | `git checkout -- content/posts/` |

**Commit Message Format:**

```
batch edit: [operation] [scope]

Examples:
- batch edit: replace "Hugo" with "Hugo SSG"
- batch edit: add author field to all posts
- batch edit: demote all H1 headings
```

---

## Emergency Procedures

### Full Rollback

If batch edit went wrong and changes were NOT committed:

```bash
# Discard all changes in content/
git checkout -- content/

# Verify clean state
git status
```

### Partial Rollback

If only some files need rollback:

```bash
# Rollback specific file
git checkout -- content/posts/specific-post.md

# Rollback files matching pattern
git checkout -- content/posts/2024-*.md
```

### Recovery After Commit

If changes were committed but need to be undone:

```bash
# Revert the commit (creates new commit)
git revert HEAD

# Or reset to previous commit (destructive)
git reset --hard HEAD~1
```

---

## Dangerous Operations

### Operations Requiring Extra Caution

| Operation | Risk | Mitigation |
|-----------|------|------------|
| Scope: `**/*.md` | Affects entire repo | Narrow scope |
| Regex with `.*` | Greedy matching | Use `.*?` |
| Remove frontmatter field | Data loss | Backup first |
| Modify date fields | SEO impact | Review carefully |
| Change URL slugs | Breaks links | Update links too |

### Blocked Operations

These operations are blocked by default:

- [ ] Modifying files outside `content/`
- [ ] Operations on binary files
- [ ] Batch edit with uncommitted changes (without --force)
- [ ] Applying without preview

---

## Quick Reference Card

```
===============================================================
 BATCH EDIT SAFETY - QUICK REFERENCE
===============================================================

 BEFORE:
   git status                    # Must be clean
   grep -c "pattern" files       # Count matches

 PREVIEW:
   /batch-edit ... (default)     # Always preview first
   /batch-edit ... --dry-run     # Validate pattern

 APPLY:
   /batch-edit ... --apply       # Only after preview

 VERIFY:
   git diff                      # Review changes
   hugo --quiet                  # Test build

 ROLLBACK:
   git checkout -- content/      # Undo all
   git checkout -- file.md       # Undo one

===============================================================
```
