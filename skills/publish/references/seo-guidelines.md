# SEO Guidelines Reference

## Length Requirements

### Title Tag
| Status | Character Count |
|--------|-----------------|
| Too short | < 30 chars |
| Suboptimal | 30-49 chars |
| Optimal | 50-60 chars |
| Too long | > 60 chars (truncated in SERPs) |

**Why it matters**: Search engines display ~60 characters in results. Truncated titles lose impact and may cut off key information.

### Meta Description
| Status | Character Count |
|--------|-----------------|
| Too short | < 120 chars |
| Suboptimal | 120-149 chars |
| Optimal | 150-160 chars |
| Too long | > 160 chars (truncated in SERPs) |

**Why it matters**: Descriptions are the "sales pitch" in search results. Too short wastes opportunity; too long gets cut off.

### URL Slug
| Status | Character Count |
|--------|-----------------|
| Optimal | 3-5 words |
| Acceptable | Up to 75 chars |
| Too long | > 75 chars |

**Why it matters**: Short, descriptive URLs are easier to share and may rank slightly better.

---

## Keyword Density

### Target Ranges
| Density | Assessment |
|---------|------------|
| 0-0.5% | Too low - keyword may not be recognized |
| 0.5-1% | Acceptable - natural usage |
| 1-2% | Optimal - good balance |
| 2-2.5% | Borderline - review for naturalness |
| 2.5-3% | Warning - likely over-optimized |
| > 3% | Critical - keyword stuffing territory |

### Calculation
```
Keyword Density = (Number of keyword occurrences / Total word count) * 100
```

### Counting Rules
- Count exact phrase matches: "hugo debugging" = 1 occurrence
- Partial matches don't count: "hugo" alone or "debugging" alone
- Variations count separately: "debug hugo" vs "hugo debugging"
- Headers count same as body text
- Alt text on images counts

---

## Header Hierarchy Best Practices

### Structure Rules
1. **H1**: Title only - exactly one per page
2. **H2**: Main sections - 3-7 is typical for blog posts
3. **H3**: Subsections within H2s
4. **H4+**: Rarely needed, use sparingly

### Common Mistakes
| Issue | Problem | Fix |
|-------|---------|-----|
| Multiple H1s | Confuses document structure | Use H2 for sections |
| Skipping levels | H1 -> H3 breaks hierarchy | Add H2 between |
| Too many H2s | Dilutes importance | Consolidate sections |
| No H2s | No clear structure | Add section headers |

### Keyword in Headers
- Primary keyword should appear in 1-2 H2s naturally
- Don't force keywords into every header
- Variations are fine: "Debugging Hugo" vs "Hugo Debugging"

---

## Content Structure

### First Paragraph Requirements
- Should contain primary keyword within first 100 words
- Should establish what problem/topic the post addresses
- Should give reader reason to continue

### Ideal Blog Post Structure
```
Title (H1) - contains primary keyword
Introduction - primary keyword in first 100 words
Section 1 (H2) - optionally contains keyword
  Content with natural keyword usage
  Subsection (H3) if needed
Section 2 (H2) - primary keyword variation
  Content
Section 3 (H2)
  Content
Conclusion (H2)
  Summary, call to action, internal links
```

---

## Internal Linking Best Practices

### Link Quantity
| Post Length | Recommended Links |
|-------------|-------------------|
| < 500 words | 1-2 internal links |
| 500-1500 words | 2-4 internal links |
| 1500-3000 words | 4-6 internal links |
| > 3000 words | 6-10 internal links |

### Anchor Text Rules
| Type | Example | Quality |
|------|---------|---------|
| Descriptive | "Hugo template debugging guide" | Best |
| Keyword-based | "debugging Hugo templates" | Good |
| Contextual | "I covered this in a previous post" | Acceptable |
| Generic | "click here", "read more" | Avoid |
| Naked URL | "https://example.com/post" | Avoid |

### Orphan Pages
- Every post should have at least one inbound internal link
- Posts with zero inbound links are "orphans"
- Orphans may not be discovered by search engines crawling the site

---

## Hugo/PaperMod Specifics

### Front Matter Fields for SEO
```yaml
---
title: "Primary Keyword: Descriptive Subtitle"  # H1, appears in browser tab
date: 2024-12-24
description: "150-160 char meta description with primary keyword"
summary: "Short summary for list views (can match description)"
tags: ["keyword1", "keyword2"]
keywords: ["optional", "additional", "keywords"]
---
```

### PaperMod-Specific
- `summary`: Shows on list pages, home page
- `description`: Used for meta description in head
- If only `summary` is set, PaperMod may use it for both
- Set both for full control

### URL Structure
- Hugo creates URLs from filename by default
- `content/posts/2024-12-hugo-debugging.md` -> `/posts/2024-12-hugo-debugging/`
- Use lowercase, hyphens, include keyword in slug

---

## Technical Blog SEO Considerations

### What Works for Technical Content
- Specific, problem-focused titles ("Fix Hugo Build Error X")
- Code examples (searchable, shareable)
- Error messages as headers (people search exact errors)
- Version numbers when relevant ("Hugo 0.120+")
- Comparison posts ("X vs Y")

### What to Avoid
- Vague titles ("My Thoughts on Hugo")
- Excessive jargon without explanation
- Outdated information without date context
- Promises that content doesn't deliver
- Clickbait that contradicts technical brand

### Long-Tail Keywords
Technical blogs often rank for long-tail keywords:
- "hugo template not found error" (specific error)
- "hugo partial not rendering" (specific symptom)
- "migrate from jekyll to hugo" (specific task)

These are often more valuable than generic terms like "hugo tutorial".
