---
name: seo-optimizer
description: |
  Analyze and optimize blog post SEO: keywords, titles, meta descriptions,
  headers, and internal linking. Use when user says "check seo", "optimize
  for search", "improve search visibility", or when publishing a new post
  that needs search optimization. Do NOT use for writing new content,
  major content edits, or site-wide technical SEO (robots.txt, sitemaps).
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
---

# SEO Optimizer Skill

## Operator Context

This skill operates as an operator for SEO optimization workflows, configuring Claude's behavior for search visibility improvements without compromising content quality. It implements a **4-phase ASSESS-DECIDE-APPLY-VERIFY** workflow with evidence-based analysis at each step.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Voice Preservation**: Never suggest changes that compromise the author's authentic tone
- **No Keyword Stuffing**: Never recommend keyword density above 2.5%
- **Honest Descriptions**: Meta descriptions must accurately reflect content — no clickbait
- **Preview Before Modify**: Always show current vs suggested changes before applying modifications
- **Over-Engineering Prevention**: Focus on high-impact SEO changes only; skip marginal optimizations

### Default Behaviors (ON unless disabled)
- **Complete Analysis**: Show all findings with data, never summarize without evidence
- **Alternative Generation**: Provide 3 title alternatives using different title patterns
- **Internal Link Discovery**: Scan related posts for linking opportunities
- **Confirmation Required**: Require explicit user confirmation before modifying any file

### Optional Behaviors (OFF unless enabled)
- **Auto-Apply**: Apply changes without confirmation (requires explicit --apply flag)
- **Batch Mode**: Analyze multiple posts at once (requires explicit --batch flag)
- **Generate Missing**: Create meta descriptions for posts that lack them

## What This Skill CAN Do
- Analyze keyword placement across title, headers, first paragraph, and body
- Calculate keyword density and flag over-optimization
- Evaluate title length, specificity, and click potential
- Generate or improve meta descriptions within 150-160 character targets
- Audit header hierarchy (H1/H2/H3 structure and nesting)
- Identify internal linking opportunities to related posts
- Show before/after comparisons for all proposed changes

## What This Skill CANNOT Do
- Modify post body content beyond front matter and headers — voice belongs to the author
- Guarantee search rankings — SEO is one factor among many
- Replace human judgment on content quality or brand fit
- Auto-publish changes without explicit user review and confirmation
- Handle site-wide technical SEO (robots.txt, sitemap, redirects)

---

## Instructions

### Phase 1: ASSESS — Analyze Current SEO State

**Goal**: Build a complete picture of the post's current search optimization.

**Step 1: Read and parse the post**

Read the target post file. Extract:
- Title from front matter
- Existing description/summary (if any)
- All headers (H2, H3, etc.) and their hierarchy
- First paragraph content (first 100 words)
- Full body text for keyword analysis

**Step 2: Identify primary keyword**

Determine the primary keyword/phrase by:
1. Most repeated relevant phrase (excluding stop words)
2. Topic implied by the title
3. Technical term most central to the content

Document the result:
```
Primary keyword: "hugo debugging"
Secondary keywords: "template errors", "build failures", "hugo troubleshooting"
```

**Step 3: Analyze keyword placement**

Check keyword presence in each priority location:

| Location | Weight | Check |
|----------|--------|-------|
| Title | Critical | Exact match or close variation, front-loaded preferred |
| First paragraph | High | Within first 100 words |
| H2 headers | Medium | Present in 2-3 of main section headers |
| Body text | Medium | Natural usage throughout |
| URL slug | Medium | Keyword in filename |

Calculate keyword density:
```
Density = (keyword occurrences / total words) * 100
Target: 1-2%  |  Warning: > 2.5%  |  Critical: > 3%
```

**Step 4: Evaluate title**

| Criteria | Target |
|----------|--------|
| Length | 50-60 characters |
| Keyword position | Front-loaded (first half) |
| Specificity | Specific problem/outcome over vague topic |
| Click potential | Conveys clear value to searcher |

**Step 5: Check meta description**

If description exists: verify 150-160 characters, contains primary keyword, accurately reflects content, compels click.

If missing: flag for generation in Phase 3.

**Step 6: Audit header structure**

Verify: exactly one H1 (the title), 3-7 H2s for main sections, H3s for subsections, no skipped levels (no H1 to H3 without H2).

**Step 7: Scan for internal linking opportunities**

List all related posts. For each candidate:
- Identify relevant anchor text in current post
- Note the link target
- Flag if current post is an orphan (zero inbound links)

**Gate**: Complete analysis with data for every check. Do not proceed to Phase 2 without keyword density calculated and all locations assessed.

### Phase 2: DECIDE — Prioritize Changes

**Goal**: Rank findings by impact and effort, select actionable improvements.

**Step 1: Score each issue**

| Issue | Impact | Effort |
|-------|--------|--------|
| Missing meta description | High | Low |
| Title too short/long or missing keyword | High | Low |
| No keyword in first paragraph | Medium | Low |
| Missing internal links | Medium | Low |
| Header structure problems | Medium | Medium |
| Low keyword density | Low | Medium |

**Step 2: Prioritize high-impact, low-effort first**

1. Add or fix meta description
2. Optimize title if needed
3. Add internal links
4. Adjust headers only if clearly beneficial

Drop any suggestion where the existing content is already good. Do not force changes for the sake of completeness.

**Gate**: Prioritized list of changes with rationale for each. Skip items that would not materially improve search visibility.

### Phase 3: APPLY — Present Recommendations and Execute

**Goal**: Show the user exactly what will change, get confirmation, apply.

**Step 1: Generate output report**

```
===============================================================
 SEO ANALYSIS: {file_path}
===============================================================

 CURRENT STATE:

 Title: "{current_title}" ({char_count} chars)
   {assessment}

 Description: "{current_description}" or "(missing)"
   {assessment}

 Primary Keyword: "{keyword}"
   - In title: yes/no
   - In H2s: {count} of {total}
   - In first paragraph: yes/no
   - Density: {percentage}%

 Headers: H2({count}), H3({count})
   {assessment}

 Internal Links: {count}
   {assessment}

===============================================================
 SUGGESTIONS:

 Title (pick one):
   1. "{alternative_1}" ({chars} chars) — [pattern used]
   2. "{alternative_2}" ({chars} chars) — [pattern used]
   3. "{alternative_3}" ({chars} chars) — [pattern used]

 Description:
   "{generated_description}" ({chars} chars)

 Internal Links:
   - Link "{anchor_text}" -> {target_post}

 Keyword Improvements:
   - {specific_suggestion}

===============================================================
 Apply changes? [preview / apply / skip]
===============================================================
```

**Step 2: Handle user response**

- **preview**: Show exact diff of all proposed front matter and content changes
- **apply**: Make changes to front matter fields and insert internal links
- **skip**: Exit without changes

**Step 3: Apply confirmed changes**

Only modify:
- `title` in front matter (if user selected an alternative)
- `description` in front matter (add or update)
- `summary` in front matter (sync with description for Hugo/PaperMod)
- Internal link insertions at suggested anchor points

**Gate**: All applied changes shown to user. No changes made without explicit confirmation.

### Phase 4: VERIFY — Confirm Changes Are Valid

**Goal**: Ensure changes did not break the post or introduce problems.

**Step 1**: Show the diff of all modified files

**Step 2**: Verify front matter is valid YAML (no unclosed quotes, no broken structure)

**Step 3**: Check that keyword density did not exceed 2.5% after changes

**Step 4**: If Hugo is available, run a build to confirm no breakage:
```bash
hugo --quiet
```

**Step 5**: If build fails, revert changes immediately:
```bash
git checkout {file_path}
```

**Gate**: Post builds successfully with all changes applied. Keyword density within target range. All verification steps pass.

---

## Error Handling

### Error: "Post File Not Found"
Cause: Specified post path does not exist or was misspelled
Solution:
1. List available posts in the content directory
2. Present candidates to user
3. Ask user to specify correct filename

### Error: "Hugo Build Failed After Changes"
Cause: Applied changes broke front matter YAML or content structure
Solution:
1. Revert changes with `git checkout {file_path}`
2. Show the Hugo error output
3. Identify which specific change caused the failure
4. Re-apply changes individually to isolate the problem

### Error: "Keyword Density Exceeds Threshold"
Cause: Post is already over-optimized or changes would push density above 2.5%
Solution:
1. Do not add any changes that increase keyword frequency
2. Suggest removing redundant keyword occurrences instead
3. Focus recommendations on structural improvements (title, description, links)

---

## Anti-Patterns

### Anti-Pattern 1: Keyword Stuffing
**What it looks like**: "Add 'hugo debugging' 15 more times to reach optimal density"
**Why wrong**: Over-optimization hurts readability and search rankings. Search engines penalize stuffing.
**Do instead**: Aim for 1-2% density with natural placement in title, first paragraph, and occasional headers.

### Anti-Pattern 2: Clickbait Titles
**What it looks like**: "You Won't BELIEVE These Hugo Debugging Secrets!"
**Why wrong**: Violates technical, authentic tone. Misleads readers and damages trust.
**Do instead**: Suggest specific, descriptive titles that accurately convey content value using patterns from `references/title-patterns.md`.

### Anti-Pattern 3: Generic Meta Descriptions
**What it looks like**: "Learn about Hugo debugging in this comprehensive guide."
**Why wrong**: Vague descriptions do not differentiate content or compel clicks from search results.
**Do instead**: Include specific outcomes, techniques, or problems addressed. Reference the primary keyword naturally.

### Anti-Pattern 4: Forcing Changes on Good Structure
**What it looks like**: "Restructure all headers to include the primary keyword"
**Why wrong**: If existing structure is logical and readable, forcing keywords into every header damages content quality for marginal SEO gain.
**Do instead**: Only suggest header changes where keywords fit naturally AND improve clarity.

### Anti-Pattern 5: Optimizing Without Data
**What it looks like**: Suggesting title changes without measuring current length or keyword presence
**Why wrong**: Changes without baseline data cannot be evaluated for improvement. May make things worse.
**Do instead**: Complete Phase 1 analysis fully before proposing any changes.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) — Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) — Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This title is fine, no need to measure" | Fine is subjective; measure character count | Run length and keyword checks |
| "Description isn't that important" | Description is the SERP sales pitch | Always analyze and optimize |
| "Just add keywords everywhere" | Stuffing hurts rankings | Calculate density, stay under 2.5% |
| "SEO is more important than readability" | Readers bounce from unnatural content | Voice preservation is hardcoded |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/seo-guidelines.md`: Length requirements, density targets, and best practices
- `${CLAUDE_SKILL_DIR}/references/keyword-placement.md`: Priority locations and placement techniques
- `${CLAUDE_SKILL_DIR}/references/title-patterns.md`: Effective title structures for technical blogs
