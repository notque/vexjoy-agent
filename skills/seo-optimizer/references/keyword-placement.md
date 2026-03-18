# Keyword Placement Reference

## Priority Locations

### 1. Title Tag (Critical)
**Weight**: Highest
**Recommendation**: Include primary keyword, preferably front-loaded

**Good Examples**:
```
"Hugo Debugging: How to Fix Common Template Errors"
 ^^^^^^^^^^^^^^^  <- Primary keyword at start

"Fix Hugo Build Errors: A Practical Debugging Guide"
     ^^^^^ <- Keyword variation near start
```

**Bad Examples**:
```
"A Comprehensive Guide to Various Techniques for Hugo Debugging"
                                                 ^^^^^^^^^^^^^^^
                                                 <- Keyword buried at end

"My Journey Through Template Problems"
  <- No keyword at all
```

### 2. First Paragraph (High)
**Weight**: High
**Recommendation**: Primary keyword within first 100 words, ideally first 2 sentences

**Good Example**:
```markdown
Hugo debugging can be frustrating when error messages don't clearly
point to the problem. This guide covers practical techniques for
tracking down template errors, build failures, and content issues.
```

**Bad Example**:
```markdown
When I started building static sites, I encountered many challenges.
The learning curve was steep. Eventually, after much trial and error,
I found some useful approaches that helped me understand what was
happening when things went wrong with my templates.
[... 150 words later ...]
Hugo debugging is what this post covers.
```

### 3. H2 Headers (Medium)
**Weight**: Medium
**Recommendation**: 2-3 H2s should contain keyword or variations

**Good Structure**:
```markdown
## Common Hugo Debugging Scenarios        <- Contains keyword
## Template Error Messages Explained       <- Related topic
## Debugging Hugo Partial Templates        <- Keyword variation
## Build-Time vs Runtime Errors            <- Topic without keyword (fine)
## Debugging Tools and Techniques          <- Partial keyword
```

**Bad Structure**:
```markdown
## Introduction                            <- Generic
## The Problem                             <- Generic
## My Approach                             <- Generic
## What I Learned                          <- Generic
## Conclusion                              <- Generic
```

### 4. URL Slug (Medium)
**Weight**: Medium
**Recommendation**: Include primary keyword in filename

**Good**:
```
content/posts/2024-12-hugo-debugging.md
                     ^^^^^^^^^^^^^^^ <- Keyword in slug
```

**Acceptable**:
```
content/posts/2024-12-debugging-hugo-templates.md
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ <- Variation
```

**Bad**:
```
content/posts/2024-12-my-experience.md
                     ^^^^^^^^^^^^^^ <- No keyword
```

### 5. Body Content (Medium)
**Weight**: Medium
**Recommendation**: Natural usage throughout, 1-2% density

**Natural Placement Opportunities**:
- When introducing new sections
- When referencing the topic directly
- In code comments
- In image alt text
- In concluding summaries

**Avoid**:
- Forcing keywords into unrelated sentences
- Repeating exact phrase when variation is more natural
- Breaking sentence flow for keyword insertion

### 6. Image Alt Text (Low-Medium)
**Weight**: Low-Medium (helps with image search)
**Recommendation**: Describe image, include keyword if relevant

**Good**:
```markdown
![Hugo debugging output showing template error](image.png)
```

**Bad** (keyword stuffing):
```markdown
![Hugo debugging hugo debug hugo template debugging](image.png)
```

**Bad** (no description):
```markdown
![Screenshot](image.png)
```

---

## Keyword Variations

### Why Variations Matter
Search engines understand semantic relationships. Using variations:
- Avoids keyword stuffing
- Sounds natural to readers
- Captures related search queries

### Example Variation Set
**Primary Keyword**: "hugo debugging"

**Variations**:
- "debug Hugo sites"
- "debugging Hugo templates"
- "Hugo troubleshooting"
- "fix Hugo errors"
- "Hugo build problems"
- "template debugging in Hugo"

### When to Use Variations
- When exact keyword sounds awkward
- When discussing specific aspects (templates, builds, etc.)
- When the context is clear
- In headers after primary keyword is established

---

## Keyword Cannibalization

### What It Is
Multiple posts targeting the same primary keyword compete with each other in search results.

### How to Avoid
- Each post should target unique primary keyword
- Related posts can share secondary keywords
- Use internal links to establish hierarchy

### Example Problem
```
Post 1: "Hugo Debugging Guide" (keyword: hugo debugging)
Post 2: "Hugo Debugging Tips" (keyword: hugo debugging)
Post 3: "Advanced Hugo Debugging" (keyword: hugo debugging)
         ^^^ All competing for same term
```

### Example Solution
```
Post 1: "Hugo Template Debugging" (keyword: hugo template debugging)
Post 2: "Hugo Build Error Fixes" (keyword: hugo build errors)
Post 3: "Hugo Performance Debugging" (keyword: hugo performance)
         ^^^ Each targets distinct long-tail keyword
```

---

## Placement Checklist

Before publishing, verify:

| Location | Check |
|----------|-------|
| Title | Contains primary keyword? |
| Title | Keyword front-loaded (first half)? |
| URL | Contains keyword or variation? |
| First paragraph | Keyword in first 100 words? |
| H2 headers | 2-3 contain keyword/variations? |
| Body | Natural usage (1-2% density)? |
| Meta description | Contains primary keyword? |
| Image alt | Relevant images described with keyword? |

---

## Technical Content Specifics

### Error Messages as Keywords
Technical readers often search for exact error messages:
```markdown
## "template not found" Error

When Hugo reports `template "layouts/..." not found`, the issue is...
```

This captures searches for the exact error.

### Version-Specific Keywords
Include versions when relevant:
```markdown
## Hugo 0.120+ Debugging Changes

In Hugo 0.120, the debugging output format changed...
```

### Command/Code Keywords
Include actual commands people might search:
```markdown
## Using `hugo --debug`

The `--debug` flag enables verbose output...
```

This captures searches for "hugo --debug" and "hugo debug flag".
