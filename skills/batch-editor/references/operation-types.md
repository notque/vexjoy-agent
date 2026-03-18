# Batch Editor Operation Types

Reference documentation for all batch editor operations.

---

## Find/Replace Operations

### Simple Text Replacement

Replace exact text matches across files.

**Syntax:**
```
/batch-edit find-replace "search" "replace"
```

**Options:**
- `--ignore-case` - Case-insensitive matching
- `--scope <path>` - Target different directory
- `--include-drafts` - Also process draft posts

**Examples:**

```
# Replace company name
/batch-edit find-replace "Acme Corp" "Acme Corporation"

# Case-insensitive
/batch-edit find-replace "javascript" "JavaScript" --ignore-case

# Specific directory
/batch-edit find-replace "old-link" "new-link" --scope content/pages/
```

---

### Regex Replacement

Use regular expressions for complex pattern matching.

**Syntax:**
```
/batch-edit find-replace --regex "pattern" "replacement"
```

**Capture Groups:**
- `$1`, `$2`, etc. - Reference captured groups in replacement
- `$0` - Entire match

**Examples:**

```
# Convert date formats: YYYY-MM-DD to MM/DD/YYYY
/batch-edit find-replace --regex "(\d{4})-(\d{2})-(\d{2})" "$2/$3/$1"

# Add protocol to bare URLs
/batch-edit find-replace --regex "www\.([a-z]+\.com)" "https://www.$1"

# Wrap code terms in backticks
/batch-edit find-replace --regex "\b(kubectl|docker|git)\b" "`$1`"

# Remove trailing whitespace
/batch-edit find-replace --regex "[ \t]+$" ""

# Normalize multiple blank lines
/batch-edit find-replace --regex "\n{3,}" "\n\n"
```

---

## Frontmatter Operations

### Add Field

Add a new field to posts that don't have it.

**Syntax:**
```
/batch-edit frontmatter add <field> <value>
/batch-edit frontmatter add <field> <value> --filter missing
```

**Value Types:**
- String: `"value"` or `'value'`
- Number: `123`
- Boolean: `true` or `false`
- Array: `["item1", "item2"]`

**Examples:**

```
# Add author to all posts
/batch-edit frontmatter add author "Jane"

# Add only to posts missing the field
/batch-edit frontmatter add author "Jane" --filter missing

# Add default tags
/batch-edit frontmatter add tags ["technical"]

# Add reading time placeholder
/batch-edit frontmatter add readingTime 5
```

---

### Modify Field

Change existing field values.

**Syntax:**
```
/batch-edit frontmatter modify <field> <value>
/batch-edit frontmatter modify <field> <value> --filter has-value "old"
```

**Filter Options:**
- `--filter has-value "X"` - Only modify where current value is X
- `--filter has-tag "X"` - Only modify where tags include X
- `--filter before-date "YYYY-MM-DD"` - Only modify posts before date

**Examples:**

```
# Change author name everywhere
/batch-edit frontmatter modify author "Jane Doe" --filter has-value "Jane"

# Update category name
/batch-edit frontmatter modify categories ["guides"] --filter has-value ["tutorials"]

# Mark old posts as archived
/batch-edit frontmatter modify archived true --filter before-date "2024-01-01"

# Change draft status
/batch-edit frontmatter modify draft false --filter has-value true
```

---

### Remove Field

Remove a field from all posts.

**Syntax:**
```
/batch-edit frontmatter remove <field>
```

**Examples:**

```
# Remove deprecated field
/batch-edit frontmatter remove deprecated_field

# Remove temporary metadata
/batch-edit frontmatter remove review_status

# Clean up test fields
/batch-edit frontmatter remove test_mode
```

---

### Append to Array Field

Add items to existing array fields (tags, categories).

**Syntax:**
```
/batch-edit frontmatter append <field> <value>
```

**Examples:**

```
# Add tag to all posts
/batch-edit frontmatter append tags "your-blog"

# Add category
/batch-edit frontmatter append categories "archive"

# Add multiple tags
/batch-edit frontmatter append tags ["updated", "reviewed"]
```

---

### Remove from Array Field

Remove specific items from array fields.

**Syntax:**
```
/batch-edit frontmatter remove-from <field> <value>
```

**Examples:**

```
# Remove deprecated tag
/batch-edit frontmatter remove-from tags "deprecated-tag"

# Remove old category
/batch-edit frontmatter remove-from categories "old-category"
```

---

## Content Transformations

### Heading Level Adjustment

Demote or promote all headings by one level.

**Syntax:**
```
/batch-edit transform demote-headings
/batch-edit transform promote-headings
```

**Examples:**

```
# Convert H1 to H2, H2 to H3, etc.
/batch-edit transform demote-headings

# Convert H2 to H1, H3 to H2, etc.
/batch-edit transform promote-headings
```

**Pattern Details:**
```
Demote: # Title -> ## Title
        ## Subtitle -> ### Subtitle

Promote: ### Subtitle -> ## Subtitle
         ## Subtitle -> # Subtitle
```

---

### Link Format Conversion

Convert between link formats.

**Syntax:**
```
/batch-edit transform links-to-inline
/batch-edit transform links-to-reference
```

**Examples:**

```
# Convert reference links to inline
# [text][1] ... [1]: url  ->  [text](url)
/batch-edit transform links-to-inline

# Convert inline links to reference
# [text](url)  ->  [text][1] ... [1]: url
/batch-edit transform links-to-reference
```

---

### Whitespace Cleanup

Normalize whitespace in content.

**Syntax:**
```
/batch-edit transform cleanup-whitespace
```

**Actions:**
- Remove trailing whitespace from lines
- Normalize multiple blank lines to two
- Ensure single newline at end of file
- Convert tabs to spaces (optional)

---

### Smart Quote Conversion

Convert between smart and straight quotes.

**Syntax:**
```
/batch-edit transform straight-quotes
/batch-edit transform smart-quotes
```

**Examples:**

```
# Smart to straight: "text" -> "text"
/batch-edit transform straight-quotes

# Straight to smart: "text" -> "text"
/batch-edit transform smart-quotes
```

---

## Scope Options

### Default Scope

By default, batch-edit processes:
- Path: `content/posts/*.md`
- Excludes: Draft posts (unless --include-drafts)
- Excludes: Non-markdown files

### Custom Scope

**Options:**
```
--scope content/           # All content
--scope content/pages/     # Only pages
--scope content/**/*.md    # All markdown recursively
--include-drafts           # Include draft posts
```

**Examples:**

```
# All content directories
/batch-edit find-replace "old" "new" --scope content/

# Only page content
/batch-edit frontmatter add layout "page" --scope content/pages/

# Include drafts in batch operation
/batch-edit frontmatter modify draft false --include-drafts
```

---

## Combining Operations

### Sequential Operations

Run multiple batch operations in sequence:

```
# First add author, then add default tags
/batch-edit frontmatter add author "Jane"
/batch-edit frontmatter add tags ["hugo"] --filter missing

# Clean up then modify
/batch-edit transform cleanup-whitespace
/batch-edit transform straight-quotes
```

### Verification Workflow

Recommended workflow for complex changes:

```
1. /batch-edit ... --dry-run     # Validate pattern
2. /batch-edit ...                # Preview changes
3. /batch-edit ... --apply       # Apply if correct
4. git diff                       # Verify changes
5. git commit -m "batch update"  # Commit if good
6. git checkout -- .              # Rollback if wrong
```
