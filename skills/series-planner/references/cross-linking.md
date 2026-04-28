# Cross-Linking Reference

Navigation patterns and Hugo implementation for series posts.

---

## In-Post Navigation

### Header Element

Place at the top of each post, immediately after the title.

**Pattern:**
```markdown
*Part 2 of 4 in the [Series Title](/series/series-slug/) series*
```

**Hugo shortcode (if available):**
```go-html-template
{{ partial "series-header.html" . }}
```

**Implementation:**
```go-html-template
{{/* layouts/partials/series-header.html */}}
{{ if .Params.series }}
<p class="series-header">
  <em>Part {{ .Params.series_part }} of {{ len (where .Site.RegularPages "Params.series" .Params.series) }}
  in the <a href="/series/{{ .Params.series | urlize }}/">{{ .Params.series }}</a> series</em>
</p>
{{ end }}
```

---

### Footer Navigation

Place at the end of each post, before comments.

**Pattern:**
```markdown
---

**Series Navigation:**
- Previous: [Part 1: Installing Hugo](/posts/hugo-from-scratch-part-1/)
- Next: [Part 3: Content Types](/posts/hugo-from-scratch-part-3/)
- [View all parts in this series](/series/hugo-from-scratch/)
```

**For first post:**
```markdown
---

**Series Navigation:**
- Next: [Part 2: Themes and Templates](/posts/hugo-from-scratch-part-2/)
- [View all parts in this series](/series/hugo-from-scratch/)
```

**For last post:**
```markdown
---

**Series Navigation:**
- Previous: [Part 3: Content Types](/posts/hugo-from-scratch-part-3/)
- [View all parts in this series](/series/hugo-from-scratch/)

This is the final part of the series.
```

---

### Hugo Shortcode Implementation

**Shortcode file:** `layouts/shortcodes/series-nav.html`

```go-html-template
{{ $series := .Page.Params.series }}
{{ $currentPart := .Page.Params.series_part }}
{{ $allParts := where .Site.RegularPages "Params.series" $series }}
{{ $sortedParts := sort $allParts "Params.series_part" }}

<nav class="series-navigation">
  <hr>
  <strong>Series Navigation:</strong>
  <ul>
    {{ range $sortedParts }}
      {{ if eq .Params.series_part (sub $currentPart 1) }}
        <li>Previous: <a href="{{ .RelPermalink }}">Part {{ .Params.series_part }}: {{ .Title }}</a></li>
      {{ end }}
    {{ end }}
    {{ range $sortedParts }}
      {{ if eq .Params.series_part (add $currentPart 1) }}
        <li>Next: <a href="{{ .RelPermalink }}">Part {{ .Params.series_part }}: {{ .Title }}</a></li>
      {{ end }}
    {{ end }}
    <li><a href="/series/{{ $series | urlize }}/">View all parts</a></li>
  </ul>
</nav>
```

**Usage in post:**
```markdown
{{</* series-nav */>}}
```

---

## Forward References

### Good Patterns

Reference future parts without creating dependency:

```markdown
For deploying this setup to production, see Part 4.
```

```markdown
Part 3 covers error handling for these edge cases.
```

```markdown
If you want to customize templates further, Part 2 goes deep on that.
```

### Preferred Forward References

Keep content available on the current page instead of gating it behind a future part:

```markdown
<!-- BAD: Cliff-hanger -->
...but the real solution is in Part 2!

<!-- BAD: Required reading -->
To understand this, you MUST read Part 3 first.

<!-- BAD: Empty promise -->
The code will be provided in the next part.
```

---

## Backward References

### Good Patterns

Keep context inline and avoid repeating content the reader already has:

```markdown
Building on the configuration from Part 1, we now add template overrides.
```

```markdown
If you haven't set up the base project yet, see Part 1 first.
```

```markdown
Using the CLI we built in Part 2:
```

### Preferred Backward References

Keep references brief and avoid re-explaining material the reader already has:

```markdown
<!-- BAD: Re-explanation -->
As we discussed extensively in Part 1, Hugo is a static site generator that...

<!-- BAD: Excessive callbacks -->
Remember in Part 1 when we set up the config? And in Part 2 when we added templates?

<!-- BAD: Assumes complete reading -->
Following the exact steps from Part 2's error handling section...
```

---

## Series Landing Page

### Purpose

Provides overview and navigation hub for entire series.

### Location

```
content/series/series-slug/_index.md
```

### Structure

```yaml
---
title: "Hugo from Scratch: Complete Series"
date: 2024-12-01
draft: false
type: series
---

A four-part series taking you from zero to a production Hugo blog.

## What You'll Learn

- Part 1: Basic Hugo setup and your first post
- Part 2: Themes, templates, and customization
- Part 3: Content types and taxonomies
- Part 4: Deployment and automation

## Prerequisites

- Basic command line familiarity
- A text editor
- 2-3 hours total

## Parts

{{</* series-list */>}}
```

### Series List Shortcode

```go-html-template
{{/* layouts/shortcodes/series-list.html */}}
{{ $series := .Page.Title | replaceRE ": Complete Series$" "" }}
{{ $allParts := where .Site.RegularPages "Params.series" $series }}
{{ $sortedParts := sort $allParts "Params.series_part" }}

<ol class="series-list">
{{ range $sortedParts }}
  <li>
    <a href="{{ .RelPermalink }}">{{ .Title }}</a>
    <span class="word-count">{{ .WordCount }} words</span>
    {{ if .Params.summary }}<p>{{ .Params.summary }}</p>{{ end }}
  </li>
{{ end }}
</ol>
```

---

## Frontmatter for Series Posts

### Required Fields

```yaml
---
title: "Hugo from Scratch: Part 2 - Themes and Templates"
date: 2024-12-08
draft: false
tags: ["hugo", "static-sites", "series:hugo-from-scratch"]
series: "Hugo from Scratch"
series_part: 2
summary: "Installing themes, overriding layouts, and creating custom partials."
---
```

### Field Descriptions

| Field | Purpose |
|-------|---------|
| `series` | Series name (used for grouping and linking) |
| `series_part` | Part number (integer, for ordering) |
| `summary` | Brief description for landing page and list views |
| `tags` | Include `series:slug` for easy filtering |

---

## URL Patterns

### Option A: Part Number in Slug

```
/posts/hugo-from-scratch-part-1/
/posts/hugo-from-scratch-part-2/
```

Advantages: Clear ordering, simple
Disadvantages: Part number in URL, less descriptive

### Option B: Descriptive Slugs

```
/posts/hugo-first-site/
/posts/hugo-themes-templates/
```

Advantages: SEO-friendly, descriptive
Disadvantages: Order not obvious from URL

### Recommendation

Use Option B with series metadata for navigation. URLs should describe content, navigation handles ordering.

---

## Cross-Series References

When one series references another:

```markdown
For the basics of Hugo templating, see the [Hugo from Scratch](/series/hugo-from-scratch/) series, particularly Part 2.
```

Prefer:
```markdown
<!-- BAD: Assumes reading order -->
After completing the Hugo from Scratch series, you're ready for this advanced content.
```

---

## Updating Series After Publication

### Adding a New Part

1. Create new post with next `series_part` number
2. Update previous "final" part's navigation
3. Landing page auto-updates if using shortcode

### Inserting a Part

Use only when the reference truly needs the future context:
1. Renumber `series_part` values for subsequent posts
2. Update all navigation references
3. Add redirects if URLs change

### Removing a Part

1. Remove post file
2. Update surrounding parts' navigation
3. Update landing page if manual content exists
4. Add redirect to landing page
