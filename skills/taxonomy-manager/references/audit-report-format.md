# Taxonomy Audit Report Format

Standard visual format for taxonomy audit output.

---

## Report Template

```
===============================================================
 TAXONOMY AUDIT: {Site Name}
===============================================================

 CATEGORIES ({N} total):
   {category}:  {count} posts  {bar_chart}
   {category}:  {count} posts  {bar_chart}
   ...

 TAGS ({N} total):
   {tag}:             {count} posts  {bar_chart}
   {tag}:             {count} posts  {bar_chart}
   ...

 HEALTH METRICS:
   Total posts:           {N}
   Posts with categories: {N}/{N} ({percent}%)
   Posts with tags:       {N}/{N} ({percent}%)
   Avg tags per post:     {N}
   Avg categories/post:   {N}

 ISSUES FOUND:

 ORPHAN TAGS (used once - consider removing or merging):
   ! "{tag}" -> merge into "{suggested_tag}"?
   ! "{tag}" -> merge into "{suggested_tag}"?

 SIMILAR TAGS (consider consolidating):
   ! "{tag1}" and "{tag2}" -> standardize to "{preferred}"
   ! "{tag1}" and "{tag2}" -> standardize to "{preferred}"

 MISSING OPPORTUNITIES:
   -> {N} posts about {topic} have no "{tag}" tag
   -> {N} posts could share "{tag}" tag

 EMPTY CATEGORIES:
   ! "{category}" - defined but unused

===============================================================
 RECOMMENDATIONS:
   1. {action} ({N} posts affected)
   2. {action} ({N} posts affected)
   3. {action} ({N} posts affected)
===============================================================
```

---

## Bar Chart Generation

Use block characters for visual representation:

- Calculate: `blocks = round(count / max_count * 10)`
- Full: `|` repeated `blocks` times
- Empty: `.` repeated `(10 - blocks)` times

Example: 6 posts out of max 10 = `||||||....`

---

## Recommendation Priority

Order recommendations by impact:

1. **High Impact** (P1): Case inconsistencies — breaks navigation and SEO
2. **Medium Impact** (P2): Synonym duplicates — dilutes content discovery
3. **Low Impact** (P3): Orphan tags — minor navigation clutter

Within the same priority level, order by number of posts affected (descending).

---

## Change Preview Format

Before applying any modification, show per-file previews:

```
PROPOSED CHANGES:

File: content/posts/example.md
  Current tags: ["Hugo", "debugging", "templates"]
  New tags:     ["hugo", "debugging", "templates"]
  Change: Standardize "Hugo" -> "hugo"

File: content/posts/another.md
  Current tags: ["debug", "hugo"]
  New tags:     ["debugging", "hugo"]
  Change: Standardize "debug" -> "debugging"

Apply these changes? [y/n]
```

---

## Operations Syntax

### Audit (default)

Analyze current taxonomy state without changes.

```
/taxonomy audit
/taxonomy          # audit is default
```

### Merge

Combine similar tags into one.

```
/taxonomy merge "git-submodules" into "git"
/taxonomy merge "Hugo" "hugo" "hugo-ssg" into "hugo"
```

### Rename

Standardize capitalization or naming.

```
/taxonomy rename "Hugo" to "hugo"
/taxonomy rename "ci-cd" to "cicd"
```

### Add

Add tag to matching posts.

```
/taxonomy add "themes" to posts containing "theme"
/taxonomy add "tutorial" to posts in category "tutorials"
```

### Remove

Remove unused taxonomy terms.

```
/taxonomy remove "unused-tag"
/taxonomy remove empty-categories
```
