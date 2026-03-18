# Hugo Front Matter Reference

## Delimiter Formats

Hugo supports three front matter formats. YourBlog uses TOML or YAML.

### TOML (Recommended for YourBlog)

```toml
+++
title = "Post Title"
date = 2025-01-15T10:30:00-05:00
draft = false
description = "Meta description for SEO"
tags = ["tag1", "tag2", "tag3"]
categories = ["category1"]
+++
```

### YAML

```yaml
---
title: "Post Title"
date: 2025-01-15T10:30:00-05:00
draft: false
description: "Meta description for SEO"
tags:
  - tag1
  - tag2
  - tag3
categories:
  - category1
---
```

---

## Required Fields

### title (string)

The post title. Displayed in listings and as the page H1.

```toml
title = "Debugging Kubernetes Networking"
```

**Validation:**
- Must be present
- Must be non-empty
- Recommended: 50-60 characters for SEO

### date (datetime)

Publication date. Controls sort order and display.

```toml
# Full ISO 8601
date = 2025-01-15T10:30:00-05:00

# Date only (midnight assumed)
date = 2025-01-15

# Hugo also accepts
date = "2025-01-15"
```

**Validation:**
- Must be present
- Must be valid date format
- Future dates: Post won't appear until that date

### draft (boolean)

Controls whether post is included in production build.

```toml
draft = false    # Include in production
draft = true     # Exclude from production
```

**Validation:**
- Must be `false` for publication
- Hugo dev server shows drafts with `-D` flag
- Production build (`hugo`) excludes drafts by default

---

## Recommended Fields

### description (string)

Meta description for SEO and social sharing.

```toml
description = "A deep dive into debugging Kubernetes networking issues including DNS, service discovery, and network policies."
```

**Validation:**
- Recommended: 150-160 characters
- Used in: `<meta name="description">`, social cards
- If missing: Hugo may auto-generate from content (suboptimal)

### tags (array)

Keywords for content categorization.

```toml
tags = ["kubernetes", "networking", "debugging", "devops"]
```

**Validation:**
- Recommended: 3-5 tags
- Use existing taxonomy when possible
- Lowercase, hyphenated for consistency

### categories (array)

Broader content groupings.

```toml
categories = ["technical-notes"]
```

**Validation:**
- Recommended: 1-2 categories
- More general than tags
- Creates section-like organization

---

## Optional Fields

### slug (string)

Override the URL path derived from filename.

```toml
slug = "k8s-networking"
```

**Default:** Derived from filename (minus date prefix)
**Use case:** When filename is verbose but URL should be concise

### summary (string)

Explicit summary for listings (alternative to auto-excerpt).

```toml
summary = "How I debugged a complex Kubernetes networking issue."
```

### weight (integer)

Manual sort order within a section.

```toml
weight = 10
```

**Lower = earlier** in listings
**Use case:** Pinning important posts

### aliases (array)

Redirect URLs to this page.

```toml
aliases = ["/old-url/", "/alternate-path/"]
```

**Use case:** After renaming/restructuring without breaking links

### cover (object)

Post cover image for listings and social sharing.

```toml
[cover]
image = "images/cover.png"
alt = "Kubernetes network diagram"
caption = "Network topology visualization"
```

### author (string)

Post author (if multi-author site).

```toml
author = "author-name"
```

### showToc (boolean)

Override site-wide table of contents setting.

```toml
showToc = true   # Show ToC for this post
showToc = false  # Hide ToC for this post
```

### canonicalURL (string)

Set canonical URL for republished content.

```toml
canonicalURL = "https://original-site.com/original-post/"
```

---

## YourBlog-Specific Conventions

### Filename Pattern

```
YYYY-MM-descriptive-slug.md
```

Examples:
- `2025-01-kubernetes-debugging.md`
- `2025-01-15-quick-tip-git.md`

### Default Archetype

YourBlog's `archetypes/default.md`:

```toml
+++
title = '{{ replace .File.ContentBaseName "-" " " | title }}'
date = {{ .Date }}
draft = true
+++
```

**Notes:**
- Title auto-generated from filename
- Draft defaults to true (safety)
- Date auto-populated

### Recommended Additions

After creating a new post, add:

```toml
+++
title = "Your Refined Title"
date = 2025-01-15
draft = true
description = "150-160 character description for SEO"
tags = ["tag1", "tag2", "tag3"]
categories = ["technical-notes"]
+++
```

Change `draft = false` only when ready to publish.

---

## Parsing Notes for Validation

### TOML Parsing

```
Front matter starts: +++
Front matter ends: +++ (second occurrence)
```

Key patterns:
- String: `key = "value"` or `key = 'value'`
- Boolean: `key = true` or `key = false`
- Array: `key = ["item1", "item2"]`
- Date: `key = 2025-01-15` (no quotes)

### YAML Parsing

```
Front matter starts: ---
Front matter ends: --- (second occurrence)
```

Key patterns:
- String: `key: "value"` or `key: value`
- Boolean: `key: true` or `key: false`
- Array inline: `key: ["item1", "item2"]`
- Array block:
  ```yaml
  key:
    - item1
    - item2
  ```
- Date: `key: 2025-01-15`

### Edge Cases

1. **Multi-line strings:**
   ```toml
   description = """
   This is a long description
   that spans multiple lines.
   """
   ```

2. **Nested tables (TOML):**
   ```toml
   [cover]
   image = "path.png"
   alt = "description"
   ```

3. **Empty arrays:**
   ```toml
   tags = []
   ```
   Treated as "missing" for suggestion purposes.
