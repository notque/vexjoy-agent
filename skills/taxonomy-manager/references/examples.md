# Taxonomy Examples: Good vs Bad

Real-world examples illustrating taxonomy best practices and anti-patterns.

---

## Category Examples

### Good: Focused Categories

```yaml
# Post 1: Debugging journey
categories:
  - technical-notes

# Post 2: Step-by-step guide
categories:
  - tutorials

# Post 3: Tool comparison
categories:
  - tools
```

**Why good:**
- Each post has one clear category
- Categories are distinct and non-overlapping
- Easy for readers to navigate

### Bad: Overlapping Categories

```yaml
# Post 1: Over-categorized
categories:
  - technical-notes
  - tutorials
  - how-to
  - guides

# Result: Post appears in 4 different category pages
# Reader confusion: "Is this a tutorial or technical notes?"
```

**Why bad:**
- `tutorials`, `how-to`, `guides` are synonyms
- Post appears in multiple places, diluting each category
- Forces reader to check multiple categories

### Bad: Category Explosion

```yaml
# Site with 15+ categories after 20 posts:
categories: [
  debugging, hugo, cloudflare, git, deployment,
  tutorials, quick-tips, deep-dives, opinions,
  tools, comparisons, security, performance,
  frontend, backend, devops
]

# Each category has 1-2 posts
```

**Why bad:**
- Too granular - categories should be broad
- Most categories are topics, not content types
- Navigation becomes overwhelming

---

## Tag Examples

### Good: Balanced Tags

```yaml
---
title: "Debugging Hugo Template Rendering"
categories:
  - technical-notes
tags:
  - hugo
  - templates
  - debugging
  - static-sites
---
```

**Why good:**
- 4 tags, each broadly applicable
- Mix of technology (`hugo`), concept (`debugging`), and topic (`templates`)
- Each tag likely used in other posts

### Good: Consistent Naming

```yaml
# Post 1
tags:
  - cloudflare
  - deployment
  - cicd

# Post 2
tags:
  - cloudflare
  - dns
  - configuration

# Post 3
tags:
  - cloudflare
  - performance
  - caching
```

**Why good:**
- Consistent casing (`cloudflare` always lowercase)
- Tags are reusable across posts
- Creates meaningful "cloudflare" tag page with 3+ posts

### Bad: Inconsistent Naming

```yaml
# Post 1
tags:
  - CloudFlare
  - DEPLOYMENT

# Post 2
tags:
  - cloudflare
  - deploy

# Post 3
tags:
  - Cloud-Flare
  - Deploying
```

**Why bad:**
- `CloudFlare`, `cloudflare`, `Cloud-Flare` are treated as 3 different tags
- `DEPLOYMENT`, `deploy`, `Deploying` fragment the content
- Each tag page shows only 1 post instead of 3

### Bad: Over-Specific Tags

```yaml
---
title: "Fixing Hugo Template Context in Range Loops"
tags:
  - hugo-template-context-issue-in-range-loops
  - debugging-hugo-templates
  - hugo-range-loop-fix
  - solving-template-context-problems
---
```

**Why bad:**
- Tags mirror the title - no reuse value
- Each tag will only ever have 1 post
- Better approach: `hugo`, `templates`, `debugging`

### Bad: Over-Tagging

```yaml
---
title: "Quick Hugo Deployment Guide"
tags:
  - hugo
  - deployment
  - static-sites
  - jamstack
  - netlify
  - cloudflare
  - github-actions
  - cicd
  - devops
  - automation
  - web-development
  - frontend
  - build-tools
---
```

**Why bad:**
- 13 tags is excessive
- Many are redundant (`jamstack`, `static-sites`, `frontend`)
- Dilutes each tag's signal
- Better: Pick 3-5 most specific tags

### Bad: Under-Tagging

```yaml
---
title: "Complete Guide to Hugo Theme Customization"
tags:
  - hugo
---
```

**Why bad:**
- Only 1 tag provides minimal classification
- Misses obvious tags: `themes`, `customization`, `css`
- Reduces discoverability

---

## Taxonomy Audit Examples

### Healthy Taxonomy Output

```
===============================================================
 TAXONOMY AUDIT: YourBlog
===============================================================

 CATEGORIES (4 total):
   technical-notes:  8 posts  ||||||||..
   tutorials:        5 posts  |||||.....
   opinion:          2 posts  ||........
   tools:            1 post   |.........

 TAGS (18 total):
   hugo:             12 posts ||||||||||||
   debugging:        6 posts  ||||||....
   deployment:       5 posts  |||||.....
   cloudflare:       4 posts  ||||......
   git:              4 posts  ||||......
   templates:        3 posts  |||.......
   performance:      3 posts  |||.......
   configuration:    2 posts  ||........
   [... 10 more tags ...]

 HEALTH METRICS:
   Total posts:           16
   Posts with categories: 16/16 (100%)
   Posts with tags:       16/16 (100%)
   Avg tags per post:     3.8
   Avg categories/post:   1.0

 ISSUES FOUND: None

===============================================================
 STATUS: Healthy taxonomy - no action needed
===============================================================
```

### Problematic Taxonomy Output

```
===============================================================
 TAXONOMY AUDIT: YourBlog
===============================================================

 CATEGORIES (9 total):
   technical-notes:  3 posts  |||.......
   tutorials:        2 posts  ||........
   how-to:           2 posts  ||........     ! overlaps with tutorials
   guides:           1 post   |.........     ! overlaps with tutorials
   opinion:          1 post   |.........
   tools:            1 post   |.........
   reviews:          0 posts  ..........     ! empty
   meta:             0 posts  ..........     ! empty
   misc:             1 post   |.........     ! vague

 TAGS (42 total):
   hugo:             6 posts  ||||||....
   Hugo:             2 posts  ||........     ! case variation
   HUGO:             1 post   |.........     ! case variation
   debugging:        4 posts  ||||......
   debug:            2 posts  ||........     ! synonym
   troubleshooting:  1 post   |.........     ! synonym
   cloudflare:       3 posts  |||.......
   CloudFlare:       1 post   |.........     ! case variation
   git-submodules:   1 post   |.........     ! orphan
   toml-config:      1 post   |.........     ! orphan
   first-post:       1 post   |.........     ! orphan, non-reusable
   [... 31 more tags ...]

 HEALTH METRICS:
   Total posts:           11
   Posts with categories: 11/11 (100%)
   Posts with tags:       11/11 (100%)
   Avg tags per post:     5.8                ! too high
   Avg categories/post:   1.3
   Orphan tag ratio:      38%                ! too high

 ISSUES FOUND:

 ORPHAN TAGS (used once - consider removing or merging):
   ! "git-submodules" -> merge into "git"?
   ! "toml-config" -> merge into "configuration"?
   ! "first-post" -> remove (not reusable)?

 SIMILAR TAGS (consider consolidating):
   ! "Hugo" and "hugo" and "HUGO" -> standardize to "hugo"
   ! "CloudFlare" and "cloudflare" -> standardize to "cloudflare"
   ! "debug" and "debugging" and "troubleshooting" -> standardize to "debugging"

 OVERLAPPING CATEGORIES:
   ! "tutorials", "how-to", "guides" -> consolidate to "tutorials"

 EMPTY CATEGORIES:
   ! "reviews" - defined but unused
   ! "meta" - defined but unused

===============================================================
 RECOMMENDATIONS:
   1. Standardize "Hugo/hugo/HUGO" -> "hugo" (9 posts affected)
   2. Merge "how-to" and "guides" into "tutorials" (3 posts affected)
   3. Standardize "debug/debugging/troubleshooting" -> "debugging" (7 posts)
   4. Remove empty categories "reviews", "meta"
   5. Merge orphan tags or remove non-reusable ones
===============================================================
```

---

## Before/After Examples

### Example 1: Case Standardization

**Before:**
```yaml
# post-1.md
tags: ["Hugo", "deployment"]

# post-2.md
tags: ["hugo", "configuration"]

# post-3.md
tags: ["HUGO", "themes"]
```

**After:**
```yaml
# post-1.md
tags: ["hugo", "deployment"]

# post-2.md
tags: ["hugo", "configuration"]

# post-3.md
tags: ["hugo", "themes"]
```

**Result:** "hugo" tag page now shows all 3 posts instead of 3 separate pages.

### Example 2: Orphan Tag Merge

**Before:**
```yaml
# post-about-submodules.md
tags: ["git-submodules", "version-control"]
```

**After:**
```yaml
# post-about-submodules.md
tags: ["git", "version-control"]
```

**Result:** Post now appears on the well-populated "git" tag page.

### Example 3: Category Consolidation

**Before:**
```yaml
# tutorial-post-1.md
categories: ["tutorials"]

# tutorial-post-2.md
categories: ["how-to"]

# tutorial-post-3.md
categories: ["guides"]
```

**After:**
```yaml
# tutorial-post-1.md
categories: ["tutorials"]

# tutorial-post-2.md
categories: ["tutorials"]

# tutorial-post-3.md
categories: ["tutorials"]
```

**Result:** "tutorials" category now shows all 3 posts, easier navigation.

### Example 4: Adding Missing Tags

**Before:**
```yaml
# theme-post-1.md
title: "Customizing Hugo Themes"
tags: ["hugo", "css"]

# theme-post-2.md
title: "Creating a Hugo Theme from Scratch"
tags: ["hugo", "development"]

# theme-post-3.md
title: "Hugo Theme Performance Tips"
tags: ["hugo", "performance"]
```

**After:**
```yaml
# theme-post-1.md
title: "Customizing Hugo Themes"
tags: ["hugo", "css", "themes"]

# theme-post-2.md
title: "Creating a Hugo Theme from Scratch"
tags: ["hugo", "development", "themes"]

# theme-post-3.md
title: "Hugo Theme Performance Tips"
tags: ["hugo", "performance", "themes"]
```

**Result:** New "themes" tag page with all 3 related posts.

---

## YourBlog Recommended Taxonomy

### Categories

```yaml
# Only use these 4-5 categories:
categories:
  - technical-notes  # Deep dives, debugging, how-it-works
  - tutorials        # Step-by-step guides
  - opinion          # Perspectives, commentary
  - tools            # Reviews, recommendations
```

### Core Tags

```yaml
# Technology tags (the tools):
- hugo
- cloudflare
- git
- github-actions
- docker
- nginx

# Concept tags (the activities):
- debugging
- deployment
- performance
- configuration
- security

# Topic tags (the subjects):
- templates
- themes
- static-sites
- dns
- caching
```

### Tag Limits

- Per post: 3-5 tags
- Create new tag only if expected to use in 2+ posts
- Review orphan tags quarterly
