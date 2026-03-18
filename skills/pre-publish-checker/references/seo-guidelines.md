# SEO Guidelines for Blog Posts

## Title Tag (Front Matter `title`)

| Metric | Value | Notes |
|--------|-------|-------|
| Optimal length | 50-60 characters | Google truncates at ~60 |
| Minimum | 30 characters | Too short lacks context |
| Maximum | 70 characters | Gets truncated in SERPs |

**Best Practices:**
- Front-load important keywords
- Make it compelling and clickable
- Avoid clickbait that doesn't deliver
- Include brand only if space allows

**Examples:**
- Good: "Debugging Kubernetes Networking: A Complete Guide" (51 chars)
- Too short: "K8s Networking" (14 chars)
- Too long: "The Complete and Comprehensive Guide to Understanding and Debugging Kubernetes Networking Issues" (97 chars)

---

## Meta Description (Front Matter `description`)

| Metric | Value | Notes |
|--------|-------|-------|
| Optimal length | 150-160 characters | Sweet spot for display |
| Minimum | 120 characters | Under-utilizes space |
| Maximum | 165 characters | May truncate |

**Best Practices:**
- Summarize the post value proposition
- Include primary keyword naturally
- Add a call to action when appropriate
- Make it unique per page
- Don't just repeat the title

**Examples:**
- Good: "Learn how to diagnose and fix common Kubernetes networking issues including DNS failures, service discovery problems, and network policies. Practical debugging steps included." (169 chars - slightly over but okay)
- Too short: "A post about Kubernetes." (24 chars)
- Missing call to action: "This article covers Kubernetes networking topics."

---

## URL Slug

| Metric | Requirement |
|--------|-------------|
| Characters | lowercase, hyphens only |
| Length | 3-5 words ideal, max 60 chars |
| Keywords | Include primary keyword |

**Best Practices:**
- Use hyphens, not underscores
- Remove stop words (a, the, and, etc.)
- Keep it readable and memorable
- Don't change after publication (breaks links)

**YourBlog Convention:**
- Format: `YYYY-MM-descriptive-slug.md`
- Slug extracted from filename minus date prefix
- Example: `2025-01-kubernetes-debugging.md` -> `/posts/kubernetes-debugging/`

**Examples:**
- Good: `kubernetes-networking-debug`
- Bad: `kubernetes_networking` (underscores)
- Bad: `the-complete-guide-to-debugging-kubernetes-networking-issues-and-problems` (too long)
- Bad: `post1` (not descriptive)

---

## Content Length

| Content Type | Minimum | Optimal | Notes |
|--------------|---------|---------|-------|
| Blog post | 500 words | 1500-2500 | Depends on topic depth |
| Tutorial | 1000 words | 2000-3500 | Needs complete coverage |
| Quick tip | 300 words | 500-800 | Focused, actionable |

**Notes:**
- Quality over quantity
- Longer isn't always better
- Match length to topic complexity
- YourBlog focus: Technical depth over padding

---

## Headers (H2/H3)

**Best Practices:**
- One H1 only (title)
- Use H2 for major sections
- Use H3 for subsections within H2
- Don't skip levels (H2 -> H4)
- Include keywords in headers naturally
- Make headers scannable

**Structure Example:**
```markdown
# Post Title (H1 - from front matter)

Introduction paragraph...

## Problem Statement (H2)
Context...

### Symptoms (H3)
Details...

### Root Cause (H3)
Details...

## Solution (H2)
Implementation...

## Conclusion (H2)
Wrap up...
```

---

## Image SEO

**Alt Text:**
- Describe the image content
- Include keywords naturally
- Keep under 125 characters
- Don't start with "Image of..."

**File Names:**
- Use descriptive names: `kubernetes-network-diagram.png`
- Not: `image1.png`, `screenshot-2025-01-15.png`

**File Size:**
- Optimize images before upload
- Target under 200KB for most images
- Use WebP format when possible

---

## Quick Reference Checklist

```
SEO Pre-Publish Checklist:

[ ] Title: 50-60 characters
[ ] Description: 150-160 characters
[ ] Slug: URL-friendly, keyword-rich
[ ] Content: 500+ words (topic appropriate)
[ ] Headers: Logical H2/H3 structure
[ ] Images: Alt text on all images
[ ] Internal links: 2-3 per post
[ ] External links: Authoritative sources only
```
