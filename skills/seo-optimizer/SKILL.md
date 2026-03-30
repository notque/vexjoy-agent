---
name: seo-optimizer
description: "Blog post SEO: keywords, titles, meta descriptions, internal linking."
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
routing:
  triggers:
    - "check SEO"
    - "optimize SEO"
    - "keyword analysis"
  category: seo
---

# SEO Optimizer Skill

This skill operates as an SEO analysis and optimization workflow for blog posts. It implements a **4-phase ASSESS-DECIDE-APPLY-VERIFY** cycle that balances search visibility improvements with content quality and authentic author voice.

**Key Principles**:
- Voice preservation is hardcoded—never suggest changes that compromise the author's authentic tone
- Complete analysis with data before proposing changes—no optimization without baseline metrics
- Confirm changes before applying—always show user exactly what will change
- Focus on high-impact, low-effort improvements only; skip marginal optimizations

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

Calculate keyword density with this formula:
```
Density = (keyword occurrences / total words) * 100
Target: 1-2%  |  Warning: > 2.5%  |  Critical: > 3%
```

**Constraint**: Never recommend keyword density above 2.5%. Over-optimization hurts readability and search rankings (search engines penalize stuffing). Aim for 1-2% density with natural placement in title, first paragraph, and occasional headers.

**Step 4: Evaluate title**

| Criteria | Target |
|----------|--------|
| Length | 50-60 characters |
| Keyword position | Front-loaded (first half) |
| Specificity | Specific problem/outcome over vague topic |
| Click potential | Conveys clear value to searcher |

**Constraint**: Never suggest clickbait titles that misrepresent content (e.g., "You Won't BELIEVE These Hugo Debugging Secrets!"). Violates technical, authentic tone and misleads readers. Suggest specific, descriptive titles that accurately convey content value.

**Step 5: Check meta description**

If description exists: verify 150-160 characters, contains primary keyword, accurately reflects content, compels click.

If missing: flag for generation in Phase 3.

**Constraint**: Meta descriptions must accurately reflect content. No clickbait. Description is the SERP sales pitch—always analyze and optimize. Vague descriptions do not differentiate content or compel clicks. Include specific outcomes, techniques, or problems addressed. Reference the primary keyword naturally.

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

**Constraint**: Drop any suggestion where the existing content is already good. Do not force changes for the sake of completeness. If existing structure is logical and readable, forcing keywords into every header damages content quality for marginal SEO gain. Only suggest header changes where keywords fit naturally AND improve clarity.

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

**Constraint**: Always show current vs suggested changes before applying modifications. Confirmation required before modifying any file.

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

**Constraint**: SEO is one factor among many. Never let search optimization override content quality or readability. If changes reduce natural language flow, revert them.

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

## References

### Domain-Specific Reference Files
- `${CLAUDE_SKILL_DIR}/references/seo-guidelines.md`: Length requirements, density targets, and best practices
- `${CLAUDE_SKILL_DIR}/references/keyword-placement.md`: Priority locations and placement techniques
- `${CLAUDE_SKILL_DIR}/references/title-patterns.md`: Effective title structures for technical blogs
