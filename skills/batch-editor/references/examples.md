# Batch Editor Examples

Detailed usage examples with full input/output formatting.

---

## Example 1: Simple Find/Replace

**Request:**
```
/batch-edit find-replace "Hugo" "Hugo SSG"
```

**Preview Output:**
```
===============================================================
 BATCH EDIT: Find/Replace
===============================================================

 Pattern: "Hugo"
 Replace: "Hugo SSG"
 Mode: Literal
 Scope: content/posts/*.md

 PREVIEW (3 files, 7 matches):

 content/posts/2024-12-theme.md:
   Line 5:  "Using Hugo for static sites"
         -> "Using Hugo SSG for static sites"
   Line 23: "Hugo's template system"
         -> "Hugo SSG's template system"

 content/posts/first-post.md:
   Line 3:  "Built with Hugo"
         -> "Built with Hugo SSG"

 content/posts/2025-01-debugging.md:
   Line 12: "When Hugo fails to build"
         -> "When Hugo SSG fails to build"
   Line 34: "Hugo configuration"
         -> "Hugo SSG configuration"
   Line 56: "Hugo themes"
         -> "Hugo SSG themes"
   Line 78: "Hugo shortcodes"
         -> "Hugo SSG shortcodes"

===============================================================
 SUMMARY:
   Files to modify: 3
   Total replacements: 7

 SAFETY CHECK:
   Git status: Clean
   Ready to apply

 Apply changes? [--apply to proceed]
===============================================================
```

---

## Example 2: Add Author Field to All Posts

**Request:**
```
/batch-edit frontmatter add author "Jane" --filter missing
```

**Preview Output:**
```
===============================================================
 BATCH EDIT: Frontmatter Update
===============================================================

 Operation: Add
 Field: author
 Value: "Jane"
 Filter: Posts missing 'author' field

 PREVIEW (4 files):

 content/posts/first-post.md:
   ---
   title: "Hello World"
   date: 2024-12-24
   draft: false
 + author: "Jane"
   ---

 content/posts/2024-12-theme.md:
   ---
   title: "Theme Setup"
   date: 2024-12-20
   draft: false
   tags: ["hugo", "themes"]
 + author: "Jane"
   ---

===============================================================
 SUMMARY:
   Files to modify: 4
   Files skipped: 0

 SAFETY CHECK:
   Git status: Clean

 Apply changes? [--apply to proceed]
===============================================================
```

---

## Example 3: Regex Pattern Replace

**Request:**
```
/batch-edit find-replace --regex "(\d{4})-(\d{2})-(\d{2})" "$2/$3/$1"
```

**Preview Output:**
```
===============================================================
 BATCH EDIT: Find/Replace
===============================================================

 Pattern: (\d{4})-(\d{2})-(\d{2})
 Replace: $2/$3/$1
 Mode: Regex
 Scope: content/posts/*.md

 PREVIEW (2 files, 3 matches):

 content/posts/first-post.md:
   Line 3:  "date: 2024-12-24"
         -> "date: 12/24/2024"

 content/posts/2024-12-theme.md:
   Line 3:  "date: 2024-12-20"
         -> "date: 12/20/2024"
   Line 15: "Last updated: 2024-12-22"
         -> "Last updated: 12/22/2024"

===============================================================
 SUMMARY:
   Files to modify: 2
   Total replacements: 3

 SAFETY CHECK:
   Git status: Clean

 Apply changes? [--apply to proceed]
===============================================================
```

---

## Example 4: Remove Deprecated Field

**Request:**
```
/batch-edit frontmatter remove deprecated_field
```

**Preview Output:**
```
===============================================================
 BATCH EDIT: Frontmatter Update
===============================================================

 Operation: Remove
 Field: deprecated_field

 PREVIEW (2 files):

 content/posts/2024-12-old-post.md:
   ---
   title: "Old Post"
   date: 2024-12-01
 - deprecated_field: "old_value"
   ---

 content/posts/2024-12-another-old.md:
   ---
   title: "Another Old"
   date: 2024-12-05
 - deprecated_field: "another_value"
   ---

===============================================================
 SUMMARY:
   Files to modify: 2
   Files without field: 8 (no changes needed)

 SAFETY CHECK:
   Git status: Clean

 Apply changes? [--apply to proceed]
===============================================================
```

---

## Example 5: Batch Tag Update

**Request:**
```
/batch-edit frontmatter modify tags ["hugo", "static-site"] --filter has-tag "hugo"
```

**Preview Output:**
```
===============================================================
 BATCH EDIT: Frontmatter Update
===============================================================

 Operation: Modify
 Field: tags
 Value: ["hugo", "static-site"]
 Filter: Posts with tag "hugo"

 PREVIEW (3 files):

 content/posts/2024-12-theme.md:
   - tags: ["hugo", "themes"]
   + tags: ["hugo", "static-site"]

 content/posts/2025-01-debugging.md:
   - tags: ["hugo", "debugging"]
   + tags: ["hugo", "static-site"]

===============================================================
 SUMMARY:
   Files to modify: 3

 SAFETY CHECK:
   Git status: Clean

 Apply changes? [--apply to proceed]
===============================================================
```

---

## Example 6: Dry Run (Validation Only)

**Request:**
```
/batch-edit find-replace "test" "TEST" --dry-run
```

**Output:**
```
===============================================================
 BATCH EDIT: Find/Replace (DRY RUN)
===============================================================

 Pattern: "test"
 Replace: "TEST"
 Mode: Literal
 Scope: content/posts/*.md

 DRY RUN - No files will be modified

 MATCHES FOUND (1 file, 2 matches):

 content/posts/2025-01-debugging.md:
   Line 45: "This is a test case"
   Line 67: "Running the test suite"

===============================================================
 DRY RUN COMPLETE
   Pattern valid: Yes
   Matches found: 2

 To apply: Remove --dry-run and add --apply
===============================================================
```

---

## Output Format Templates

### Safety Check Banner

```
===============================================================
 GIT SAFETY CHECK
===============================================================

 Repository: $HOME/your-project
 Branch: main
 Status: [Clean | Uncommitted Changes | Not a Git Repo]

 [If uncommitted changes:]
 Modified files:
   - content/posts/2024-12-theme.md

 WARNING: Uncommitted changes detected!
 Recommended: git commit -m "backup before batch edit" or git stash

 Proceed anyway? [--force to override]
===============================================================
```

### Post-Apply Confirmation

```
===============================================================
 BATCH EDIT: Applied
===============================================================

 Changes Applied:

 content/posts/2024-12-theme.md:
   [DONE] 2 replacements

 content/posts/2025-01-debugging.md:
   [DONE] 1 replacement

===============================================================
 COMPLETE: 3 replacements in 2 files

 To undo: git checkout -- content/posts/
===============================================================
```
