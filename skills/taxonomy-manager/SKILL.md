---
name: taxonomy-manager
description: |
  Audit and maintain blog taxonomy (categories/tags) for consistency, SEO,
  and navigation: scan content, detect orphans and duplicates, merge and
  rename terms, verify builds. Use when user asks to "audit tags", "fix
  taxonomy", "consolidate categories", "merge tags", or "clean up taxonomy".
  Do NOT use for writing new content, individual post SEO optimization, or
  major content restructuring.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
---

# Taxonomy Manager Skill

## Operator Context

This skill operates as an operator for taxonomy management workflows on Hugo-based blogs, configuring Claude's behavior for consistent, SEO-friendly categorization. It implements the **Scan-Analyze-Report-Act** architectural pattern with preview-first safety and build verification gates.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Fix actionable taxonomy issues only; no elaborate classification redesigns without explicit request
- **Preview-First Workflow**: Always show current state and proposed changes before modifying any files
- **Case Normalization**: Hugo taxonomies are case-sensitive; standardize all terms to `lowercase-with-hyphens`
- **Non-Destructive Operations**: Never delete or rename taxonomy terms without explicit user confirmation
- **Build Verification**: Run `hugo --quiet` after every batch of changes to confirm site still builds

### Default Behaviors (ON unless disabled)
- **Complete Output**: Show full taxonomy audit with visual charts, never summarize
- **Similarity Detection**: Flag potentially duplicate tags (case variations, plurals, synonyms)
- **Orphan Detection**: Identify tags used only once or categories with no posts
- **Confirmation Required**: Require explicit confirmation before modifying any content files
- **One Operation at a Time**: Apply merge/rename/add/remove operations individually, verify between each

### Optional Behaviors (OFF unless enabled)
- **Auto-Apply**: Apply suggested changes without per-file confirmation
- **Batch Mode**: Process all detected issues in a single pass
- **Aggressive Merge**: Merge all similar tags automatically (requires explicit opt-in)

## What This Skill CAN Do
- Audit all categories and tags across a Hugo site's content directory
- Count posts per taxonomy term and generate visual usage statistics
- Detect orphan tags (single-use), empty categories, case variations, and synonym pairs
- Suggest and execute merge, rename, add, and remove operations on taxonomy terms
- Show before/after diffs for every proposed change
- Verify Hugo build integrity after modifications

## What This Skill CANNOT Do
- Create new categories without explicit instruction (taxonomy design is intentional)
- Auto-merge tags without review (similar tags may have distinct meanings)
- Modify post content beyond front matter (preserves author's voice)
- Guarantee SEO improvements (taxonomy is one factor among many)
- Skip confirmation or build verification gates

---

## Instructions

### Phase 1: SCAN - Collect Taxonomy Data

**Goal**: Build a complete index of all taxonomy terms and their usage.

**Step 1: Identify all content files**

Locate every Markdown file in the Hugo content directory.

```bash
find /path/to/content -name "*.md" -type f | sort
```

**Step 2: Extract front matter from each post**

For each file, parse the YAML front matter and extract:
- `title` (for reference in reports)
- `categories` (list)
- `tags` (list)

**Step 3: Build taxonomy index**

Construct an in-memory mapping of every taxonomy term to its list of posts:

```
CATEGORIES:
  technical-notes: [post1.md, post2.md, post3.md]
  tutorials: [post4.md, post5.md]

TAGS:
  hugo: [post1.md, post2.md, post4.md]
  debugging: [post1.md, post3.md]
```

**Step 4: Check Hugo taxonomy configuration**

Read `hugo.toml` (or `config.toml`) for any custom taxonomy definitions or overrides.

**Gate**: Taxonomy index is complete with all terms mapped to their posts. Proceed only when gate passes.

### Phase 2: ANALYZE - Detect Issues

**Goal**: Identify all taxonomy health problems from the index.

**Step 1: Calculate usage statistics**

For each taxonomy term compute: post count, percentage of total, and staleness (months since last use).

**Step 2: Detect issues**

Run these checks against the index:

| Check | Criteria | Severity |
|-------|----------|----------|
| Orphan tags | Used in only 1 post | Low |
| Empty categories | Defined in config but 0 posts | Medium |
| Case variations | Same word, different casing (`Hugo` vs `hugo`) | High |
| Plural variations | `template` vs `templates` | Medium |
| Synonym pairs | `debugging` vs `troubleshooting` | Medium |
| Abbreviation pairs | `cicd` vs `ci-cd` | Low |
| Hierarchical overlap | `git-submodules` under broader `git` | Medium |

**Step 3: Assess health metrics**

| Metric | Healthy | Warning |
|--------|---------|---------|
| Total categories | 3-7 | <3 or >10 |
| Total active tags | 10-30 | <5 or >50 |
| Tags per post (avg) | 3-5 | <2 or >7 |
| Categories per post (avg) | 1-2 | 0 or >3 |
| Orphan tag ratio | <20% | >30% |

**Gate**: All issues catalogued with severity. Health metrics computed. Proceed only when gate passes.

### Phase 3: REPORT - Generate Audit Output

**Goal**: Present findings in a structured, actionable report.

Generate the visual audit report following the format in `references/audit-report-format.md`. The report must include:

1. Category usage with bar charts
2. Tag usage with bar charts
3. Health metrics dashboard
4. Issues found (orphans, duplicates, similar terms, empty categories)
5. Prioritized recommendations ordered by impact (High > Medium > Low)

Present the report to the user. If no issues are found, state the taxonomy is healthy.

**Gate**: Report presented. User has reviewed findings. Proceed to Phase 4 only if user requests changes.

### Phase 4: ACT - Apply Changes

**Goal**: Execute approved taxonomy modifications safely.

**Step 1: Preview every change**

Before any file modification, show:
```
File: content/posts/example.md
  Current tags: ["Hugo", "debugging", "templates"]
  New tags:     ["hugo", "debugging", "templates"]
  Change: Standardize "Hugo" -> "hugo"
```

**Step 2: Get confirmation**

Wait for explicit user approval before proceeding.

**Step 3: Apply operations**

Execute the approved operation (merge, rename, add, or remove). See `references/consolidation-rules.md` for operation semantics:
- **Merge**: Replace source tag(s) with target in all posts; skip if post already has target
- **Rename**: Replace old name with new in all posts
- **Add**: Add tag to matching posts (skip if already present)
- **Remove**: Remove term from front matter or config (only if unused)

**Step 4: Verify build**

```bash
hugo --quiet
```

If build fails, immediately roll back:
```bash
git checkout content/
```

**Step 5: Show diff**

```bash
git diff content/
```

**Gate**: All changes applied, build verified, diff reviewed. Operation complete.

---

## Examples

### Example 1: Routine Taxonomy Audit
User says: "Audit my blog tags"
Actions:
1. Scan all content files and build taxonomy index (SCAN)
2. Detect case variations, orphan tags, empty categories (ANALYZE)
3. Generate visual report with health metrics and recommendations (REPORT)
4. User reviews report; no changes requested
Result: Clean audit report, user informed of taxonomy health

### Example 2: Tag Consolidation
User says: "I have Hugo, hugo, and HUGO as separate tags, fix it"
Actions:
1. Scan content to find all posts using each variant (SCAN)
2. Confirm these are case variations of the same term (ANALYZE)
3. Report: 3 variants found across N posts, recommend standardizing to `hugo` (REPORT)
4. Preview per-file changes, get confirmation, apply, verify build (ACT)
Result: All posts use `hugo`, single tag page shows all related content

### Example 3: Post-Publication Cleanup
User says: "I just published 10 new posts, clean up the taxonomy"
Actions:
1. Scan all content including new posts (SCAN)
2. Detect new orphan tags, inconsistencies introduced by recent posts (ANALYZE)
3. Report new issues separately from pre-existing ones (REPORT)
4. Apply approved merges and renames, verify build after each batch (ACT)
Result: New posts integrated into existing taxonomy structure

---

## Error Handling

### Error: "No Content Files Found"
Cause: Content directory missing, empty, or wrong path
Solution:
1. Verify the content directory path exists
2. Check for nested content structures (e.g., `content/posts/` vs `content/`)
3. Confirm files use `.md` extension

### Error: "Invalid Front Matter in {file}"
Cause: Malformed YAML in a content file
Solution:
1. Check for missing closing `---` delimiter
2. Look for tabs (YAML requires spaces)
3. Check for unquoted special characters (colons, brackets)
4. Skip the file with a warning and continue processing remaining files

### Error: "Hugo Build Failed After Changes"
Cause: Taxonomy modifications broke the site build
Solution:
1. Roll back immediately: `git checkout content/`
2. Read the Hugo error output to identify the specific failure
3. Re-apply changes one file at a time to isolate the problem
4. Fix the problematic file before retrying the batch

### Error: "Tag Not Found: {tag}"
Cause: User requested merge/rename of a tag that does not exist in any post
Solution:
1. List all existing tags that are similar (fuzzy match)
2. Suggest closest match: `Did you mean "{similar_tag}"?`
3. If no close match exists, report that the tag is absent and list available tags

---

## Anti-Patterns

### Anti-Pattern 1: Tag Explosion
**What it looks like**: Creating `hugo-themes`, `hugo-templates`, `hugo-debugging`, `hugo-config` instead of using `hugo` + `themes`
**Why wrong**: Fragments the taxonomy; users browsing "hugo" miss related posts scattered across subtags
**Do instead**: Use broader tags in combination (`hugo` + `debugging`) and let post content provide specificity

### Anti-Pattern 2: Case Inconsistency
**What it looks like**: `Hugo` in one post, `hugo` in another, `HUGO` in a third
**Why wrong**: Hugo treats these as separate tags, creating three different tag pages each showing a fraction of the posts
**Do instead**: Standardize all terms to `lowercase-with-hyphens`; run this skill regularly to catch drift

### Anti-Pattern 3: Single-Use Tags as Description
**What it looks like**: `fixing-hugo-template-rendering-issues` as a tag on a post titled "Fixing Hugo Template Rendering Issues"
**Why wrong**: The tag duplicates the title, will never be reused, and provides zero navigation value
**Do instead**: Use generic, reusable tags: `hugo`, `templates`, `debugging`

### Anti-Pattern 4: Merging Without Understanding
**What it looks like**: Automatically merging `debugging` and `troubleshooting` because they seem similar
**Why wrong**: Near-synonyms may carry distinct connotations in context; aggressive merging can lose meaningful distinctions
**Do instead**: Present similar terms to the user with usage context; let them decide which to keep

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "These tags are obviously the same" | Similar does not mean identical; context matters | Show usage examples, let user decide |
| "Just a quick rename, no need to preview" | Renames can break Hugo taxonomy pages | Always preview, always verify build |
| "One orphan tag doesn't matter" | Orphans accumulate into taxonomy debt | Address during audit or document exception |
| "The build passed, taxonomy must be fine" | Build success does not validate semantic correctness | Review the diff, confirm navigation works |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/taxonomy-guidelines.md`: Naming conventions, category/tag best practices, maintenance cadence
- `${CLAUDE_SKILL_DIR}/references/consolidation-rules.md`: When and how to merge, rename, add, or remove terms with priority matrix
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Good vs bad taxonomy examples, before/after comparisons, audit output samples
- `${CLAUDE_SKILL_DIR}/references/audit-report-format.md`: Visual report template and bar chart generation rules
