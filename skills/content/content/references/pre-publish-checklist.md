# Pre-Publish Validation Checklist

Complete reference for all validation checks performed by the pre-publish-checker skill.

---

## Severity Levels

| Level | Symbol | Meaning | Action |
|-------|--------|---------|--------|
| BLOCKER | `[FAIL]` | Must fix before publish | Cannot publish |
| WARNING | `[WARN]` | Should fix, but optional | Review and decide |
| SUGGESTION | `[WARN]` | Recommendation only | Optional improvement |
| INFO | `[INFO]` | Informational | No action needed |
| PASS | `[PASS]` | Check passed | Continue |
| SKIP | `[SKIP]` | Check not performed | May need manual review |

---

## Front Matter Checks

### Required Fields

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| title present | BLOCKER | Field exists and non-empty |
| date present | BLOCKER | Field exists |
| date valid | BLOCKER | Parseable date format |
| draft status | BLOCKER | `draft = false` |

### Recommended Fields

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| description present | SUGGESTION | Field exists and non-empty |
| description length | SUGGESTION | 150-160 characters |
| tags present | SUGGESTION | Array with 1+ items |
| tags count | SUGGESTION | 3-5 items recommended |
| categories present | SUGGESTION | Array with 1+ items |
| categories count | SUGGESTION | 1-2 items recommended |

---

## SEO Checks

| Check | Severity | Optimal | Warning Range |
|-------|----------|---------|---------------|
| Title length | SUGGESTION | 50-60 chars | <30 or >70 |
| Description length | SUGGESTION | 150-160 chars | <120 or >165 |
| Slug format | SUGGESTION | Lowercase, hyphens | Special chars, spaces |
| Slug length | SUGGESTION | 3-5 words | >60 chars |

### Slug Validation

**Pass criteria:**
- Lowercase letters only
- Hyphens for word separation
- No special characters: `! @ # $ % ^ & * ( ) + = [ ] { } | \ : " ; ' < > , . ? /`
- No spaces
- No consecutive hyphens
- No leading/trailing hyphens

**Derivation:**
Slug is extracted from filename by removing date prefix:
- `2025-01-my-post.md` -> `my-post`
- `2025-01-15-another-post.md` -> `another-post`

---

## Content Quality Checks

### Word Count

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| Minimum words | SUGGESTION | 500+ words |

**Calculation:**
- Count words in body content (after front matter)
- Exclude code blocks from word count
- Count words in regular paragraphs, lists, headers

### Reading Time

| Check | Severity | Calculation |
|-------|----------|-------------|
| Reading time | INFO | Word count / 200 WPM |

**Display format:** "~N minutes"

**Notes:**
- Round to nearest minute
- Minimum: 1 minute
- Code blocks optionally weighted at 50% (scan vs read)

### Header Structure

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| H2 present | SUGGESTION | At least 1 H2 in body |
| H3 under H2 | SUGGESTION | H3 appears after H2, not before |
| No skipped levels | SUGGESTION | No H4 before H3 |

**Detection patterns:**
- H2: Line starting with `## `
- H3: Line starting with `### `
- H4: Line starting with `#### `

### Opening Paragraph

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| No preamble | SUGGESTION | First paragraph doesn't start with preamble phrase |

**Preamble phrases to detect:**
```
In this post
In this article
Today I'm going to
Today we'll
Let me explain
Let me show you
Welcome to
Welcome back
First of all
Before we begin
Before we start
I'm going to
I want to
I'd like to
So you want to
Have you ever
```

**Why this matters:**
Preamble phrases waste the reader's time. Start with the value proposition or key insight.

---

## Link Checks

### Internal Links

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| Path exists | BLOCKER | Target file exists in content/ or static/ |

**Detection patterns:**
- Markdown: `[text](/posts/slug/)` or `[text](../other-post/)`
- Relative to content/: `[text](../other-category/post.md)`

**Validation:**
1. Extract path from link
2. Resolve relative paths
3. Check if file exists

### External Links

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| URL reachable | WARNING | HTTP 200 response |

**Detection patterns:**
- `[text](https://...)`
- `[text](http://...)`

**Default behavior:** SKIP (use `--check-external` to enable)

**When enabled:**
- HEAD request to URL
- Timeout: 5 seconds
- Accept: 2xx, 3xx responses
- Fail: 4xx, 5xx, timeout, connection error

### Image Links

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| Image exists | BLOCKER | File exists in static/ |

**Detection patterns:**
- Markdown: `![alt](/images/file.png)`
- Hugo shortcode: `{{< figure src="/images/file.png" >}}`

**Path resolution:**
- `/images/...` -> `static/images/...`
- `images/...` -> `static/images/...`

---

## Image Checks

### Alt Text

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| Alt present | SUGGESTION | Alt text is non-empty |
| Alt meaningful | INFO | Alt text is not just filename |

**Detection:**
- `![alt text](path)` - alt text between `![]`
- `{{< figure alt="text" >}}` - alt attribute in shortcode

**Empty alt patterns to flag:**
- `![](path)` - completely empty
- `![ ](path)` - whitespace only
- `![image](path)` - generic word

### File Existence

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| File exists | BLOCKER | File found at resolved path |

**Common issues:**
- Wrong extension (`.jpg` vs `.jpeg`)
- Case sensitivity (`Image.PNG` vs `image.png`)
- Wrong directory (`/img/` vs `/images/`)

---

## Draft Status Checks

### Draft Field

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| draft = false | BLOCKER | Explicitly set to false |

**Notes:**
- Missing draft field may default to false (check Hugo config)
- Always explicitly set for clarity

### TODO/FIXME Comments

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| No TODOs | WARNING | No `TODO` in content |
| No FIXMEs | WARNING | No `FIXME` in content |

**Detection patterns (case-insensitive):**
- `TODO:`
- `TODO -`
- `FIXME:`
- `FIXME -`
- `XXX:`
- `XXX -`

### Placeholder Text

| Check | Severity | Pass Criteria |
|-------|----------|---------------|
| No placeholders | BLOCKER | No placeholder patterns found |

**Placeholder patterns:**
```
[insert X here]
[TBD]
[TODO]
[TODO: X]
[PLACEHOLDER]
[ADD X]
[REPLACE]
XXX
PLACEHOLDER
Lorem ipsum
```

**Case-insensitive matching for all patterns.**

---

## Result Classification

### READY FOR PUBLISH

All true:
- [ ] No BLOCKER-level failures
- [ ] draft = false
- [ ] All referenced files exist

### NOT READY

Any true:
- [ ] One or more BLOCKER failures
- [ ] draft = true
- [ ] Missing required front matter

### Result Message Format

```
READY FOR PUBLISH
READY FOR PUBLISH (N suggestions)
NOT READY - N blockers
NOT READY - N blockers, M warnings
```

---

## Quick Validation Summary

```
BLOCKERS (must fix):
[ ] title present and non-empty
[ ] date present and valid
[ ] draft = false
[ ] No placeholder text
[ ] All internal links valid
[ ] All images exist

WARNINGS (should fix):
[ ] No TODO/FIXME comments
[ ] External links reachable (if checked)

SUGGESTIONS (optional):
[ ] Title 50-60 chars
[ ] Description 150-160 chars
[ ] Tags 3-5 items
[ ] Categories 1-2 items
[ ] Word count 500+
[ ] Good header structure
[ ] No preamble opening
[ ] All images have alt text
```
