# Topic Sources Reference

## Source 1: Problem Mining

Mine topics from real technical struggles. This is the richest source of YourBlog content.

### Where to Look

| Signal Source | How to Access | What to Look For |
|--------------|---------------|------------------|
| Git commit messages | `git log --oneline -50` | "fix:", "workaround:", repeated attempts |
| Shell history | `history \| grep -i error` | Commands run many times, frustrated searches |
| Browser bookmarks | Stack Overflow saves | Problems you needed to reference |
| Slack/Discord | Search your questions | "anyone know why..." messages |
| Meeting notes | Retros, standups | "This took longer than expected" |
| Error logs | Application logs, CI output | Recurring errors, cryptic messages |

### Mining Prompts

Ask the user these questions to surface topics:

**Recent struggles:**
- "What broke in the last week that took more than 30 minutes to fix?"
- "What error message did you see more than twice?"
- "What config change seemed simple but turned into hours of debugging?"

**Recurring frustrations:**
- "What problem keeps coming back?"
- "What do you have to Google every time?"
- "What workaround do you keep using?"

**Near misses:**
- "What almost went wrong but you caught it?"
- "What would have been a disaster if you hadn't noticed X?"
- "What rookie mistake did you almost make (or did make)?"

### Signal Strength

| Signal | Topic Potential | Why |
|--------|-----------------|-----|
| "I spent 4 hours on this" | HIGH | Significant vex, likely deep resolution |
| "The docs were wrong" | HIGH | Common pain, valuable correction |
| "Worked locally, failed in CI" | HIGH | Universal developer experience |
| "Took a few tries" | MEDIUM | Some frustration, may lack depth |
| "That was confusing" | MEDIUM | Depends on transferability |
| "New to me" | LOW | Learning, not struggling |

### Example Mining Session

```
USER INPUT: "I was debugging why my Hugo site wouldn't deploy to Cloudflare"

FOLLOW-UP QUESTIONS:
1. What was the error message?
2. How long did it take to figure out?
3. What did you try first that didn't work?
4. What was the actual fix?
5. Why did it work locally but not in CI?

MINED TOPICS:
- "Hugo Version Mismatch Between Local and Cloudflare Pages"
- "Cloudflare Pages Build Command Silent Failures"
- "Hugo Extended vs Regular: The Binary You Didn't Know You Needed"
```

---

## Source 2: Gap Analysis

Find topics by analyzing what's missing from existing content.

### Gap Types

**1. Explicit "See Also" References**
Posts often mention related topics that don't exist yet.

How to find:
```
Search existing posts for:
- "see also"
- "in a future post"
- "covered elsewhere"
- "for more on this"
- "assuming you know"
```

**2. Prerequisite Assumptions**
Posts assume knowledge that isn't documented.

How to find:
```
Look for:
- "Assuming you have X installed"
- "If you're familiar with Y"
- "This builds on Z"
- Links that 404 or go to external sites
```

**3. Incomplete Series**
"Part 1" posts without follow-ups.

How to find:
```
Look for:
- "Part 1" in titles
- "In the next post"
- "Continued in"
- Numbered series
```

**4. Reader Questions**
Questions in comments, emails, or feedback.

How to find:
```
Look for:
- Comment sections
- Email responses
- Social media replies
- "I tried this but..."
```

### Gap Analysis Process

```
STEP 1: List all existing posts
   content/posts/*.md

STEP 2: For each post, extract:
   - Technologies mentioned
   - "See also" references
   - Prerequisites assumed
   - Follow-up promises

STEP 3: Cross-reference:
   - Which references have no matching post?
   - Which prerequisites are undocumented?
   - Which promises are unfulfilled?

STEP 4: Prioritize gaps:
   - High: Mentioned multiple times
   - Medium: Mentioned once, high traffic post
   - Low: Mentioned once, low traffic post
```

### Example Gap Analysis

```
EXISTING POST: "Setting Up Hugo on Cloudflare Pages"

MENTIONS:
- PaperMod theme (external link, no internal doc)
- Git submodules (assumed knowledge)
- "For custom domains, see [link]" (link to external)

GAPS IDENTIFIED:
1. "PaperMod Theme Customization Without Forking"
   - Referenced but not documented internally
2. "Git Submodules for Hugo Themes: A Sane Workflow"
   - Assumed knowledge, common struggle
3. "Cloudflare Custom Domain Setup: The DNS Gotchas"
   - Referenced external, should be internal
```

---

## Source 3: Technology Expansion

Expand from technologies already covered to adjacent ones.

### Expansion Strategies

**Same Tool, Different Feature**
```
COVERED: Hugo basics
EXPAND TO:
- Hugo partials and caching
- Hugo shortcodes
- Hugo taxonomies
- Hugo modules
- Hugo data files
```

**Same Category, Different Tool**
```
COVERED: Hugo (static site generator)
EXPAND TO:
- Comparing Hugo to Zola
- Migrating from Jekyll to Hugo
- When Hugo isn't enough (Astro, Next.js)
```

**Integration Points**
```
COVERED: Hugo + Cloudflare Pages
EXPAND TO:
- Hugo + Cloudflare Workers
- Hugo + Cloudflare R2 for assets
- Hugo + Cloudflare Analytics
```

**Common Ecosystem Pain**
```
COVERED: Hugo
ECOSYSTEM PAIN:
- Markdown rendering quirks
- TOML vs YAML config
- Theme update management
- Build time optimization
```

### Technology Adjacency Map

For YourBlog's current stack:

```
Hugo
├── Themes
│   ├── PaperMod (current)
│   ├── Theme customization
│   └── Theme switching
├── Deployment
│   ├── Cloudflare Pages (current)
│   ├── GitHub Actions
│   └── Vercel/Netlify alternatives
├── Content
│   ├── Markdown extensions
│   ├── Shortcodes
│   └── Data-driven content
└── Development
    ├── Local preview
    ├── Hot reload
    └── Debug modes
```

### Expansion Validation

Not every adjacent topic passes the YourBlog filter. Validate:

```
EXPANSION CANDIDATE: Hugo shortcodes

FILTER CHECK:
- Frustration potential? YES - Syntax is confusing, errors are cryptic
- Resolution satisfaction? YES - Understanding the template context
- Helps others? YES - Common need, poor docs

VERDICT: VALID EXPANSION
```

```
EXPANSION CANDIDATE: Hugo history (why it was created)

FILTER CHECK:
- Frustration potential? NO - Just interesting information
- Resolution satisfaction? N/A - No problem to solve
- Helps others? NO - Not actionable

VERDICT: INVALID - Too meta, no vex
```

---

## Source Combination

The best topics often come from combining sources:

### Pattern: Problem + Gap

```
PROBLEM: Spent 2 hours debugging theme CSS
GAP: No internal doc on theme customization
COMBINED TOPIC: "PaperMod Theme Overrides: The layouts/ Directory"
```

### Pattern: Problem + Expansion

```
PROBLEM: Hugo build slow on large site
EXPANSION: Build optimization techniques
COMBINED TOPIC: "Hugo Build Time Went from 45s to 3s"
```

### Pattern: Gap + Expansion

```
GAP: Referenced submodules but no doc
EXPANSION: Git tooling in Hugo context
COMBINED TOPIC: "Git Submodules for Hugo: Why They Break and How to Fix"
```

---

## Source Priority by Project Maturity

### New Blog (< 10 posts)

Priority order:
1. **Problem Mining** - Establish identity with real struggles
2. **Tech Expansion** - Fill out the core technology coverage
3. Gap Analysis - Limited gaps to analyze

### Established Blog (10-50 posts)

Priority order:
1. **Gap Analysis** - Fulfill cross-references, complete series
2. **Problem Mining** - Continue adding fresh content
3. Tech Expansion - Strategic growth

### Mature Blog (50+ posts)

Priority order:
1. **Gap Analysis** - Comprehensive coverage, reader questions
2. **Problem Mining** - Keep content current and real
3. **Tech Expansion** - Careful not to dilute focus
