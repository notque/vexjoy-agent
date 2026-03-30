---
name: taxonomy-manager
description: "Audit and maintain blog taxonomy: categories, tags, orphans, duplicates."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - "audit taxonomy"
    - "fix tags"
    - "merge categories"
  category: seo
---

# Taxonomy Manager Skill

## Instructions

This skill audits and maintains blog taxonomy on Hugo-based sites using the **Scan-Analyze-Report-Act** workflow. Apply this skill when users ask to audit tags, fix inconsistencies, or consolidate taxonomy terms.

### Phase 1: SCAN - Collect Taxonomy Data

**Goal**: Build a complete index of all taxonomy terms and their usage.

**Step 1: Identify all content files**

Locate every Markdown file in the Hugo content directory (because Hugo requires explicit file discovery to avoid missing nested structures).

```bash
find /path/to/content -name "*.md" -type f | sort
```

**Step 2: Extract front matter from each post**

For each file, parse the YAML front matter and extract:
- `title` (for reference in reports)
- `categories` (list)
- `tags` (list)

**Step 3: Build taxonomy index**

Construct an in-memory mapping of every taxonomy term to its list of posts (because this index is the foundation for all downstream analysis):

```
CATEGORIES:
  technical-notes: [post1.md, post2.md, post3.md]
  tutorials: [post4.md, post5.md]

TAGS:
  hugo: [post1.md, post2.md, post4.md]
  debugging: [post1.md, post3.md]
```

**Step 4: Check Hugo taxonomy configuration**

Read `hugo.toml` (or `config.toml`) for any custom taxonomy definitions or overrides (because Hugo may define non-standard taxonomies beyond categories/tags).

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

**Goal**: Execute approved taxonomy modifications safely and verify correctness.

**Step 1: Preview every change**

Before any file modification, show the change in diff format (because previewing prevents accidental mass edits that break navigation):

```
File: content/posts/example.md
  Current tags: ["Hugo", "debugging", "templates"]
  New tags:     ["hugo", "debugging", "templates"]
  Change: Standardize "Hugo" -> "hugo"
```

**Step 2: Get confirmation**

Wait for explicit user approval before proceeding (because taxonomy modifications affect site navigation and SEO).

**Step 3: Apply operations**

Execute the approved operation (merge, rename, add, or remove). See `references/consolidation-rules.md` for operation semantics. Apply operations individually, not in batches, to isolate errors:

- **Merge**: Replace source tag(s) with target in all posts; skip if post already has target
- **Rename**: Replace old name with new in all posts
- **Add**: Add tag to matching posts (skip if already present)
- **Remove**: Remove term from front matter or config (only if unused)

**Step 4: Verify build**

After each operation, run Hugo to confirm the site still builds (because taxonomy modifications can break Hugo's site generation):

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

### Taxonomy Formatting Standards

Apply these constraints throughout all phases because Hugo is case-sensitive and requires consistent formatting:

- **Case Normalization**: Standardize all terms to `lowercase-with-hyphens` (not PascalCase, UPPERCASE, or spaces). Hugo treats `Hugo`, `hugo`, and `HUGO` as three separate tags, each with its own page.
- **Non-Destructive Operations**: Never delete or rename taxonomy terms without explicit user confirmation (because accidental deletions create orphan link targets in content).
- **Complete Output**: Show full taxonomy audit with visual charts, never summarize (because partial audits miss subtle issues like orphan tags or synonyms).
- **Similarity Detection**: Flag potentially duplicate tags including case variations, plurals, and synonyms (because similar tags fragment navigation and SEO value).
- **Orphan Detection**: Identify tags used only once or categories with no posts (because orphans accumulate into taxonomy debt).
- **Confirmation Required**: Require explicit confirmation before modifying any content files (because bulk edits without review create unintended side effects).

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

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/taxonomy-guidelines.md`: Naming conventions, category/tag best practices, maintenance cadence
- `${CLAUDE_SKILL_DIR}/references/consolidation-rules.md`: When and how to merge, rename, add, or remove terms with priority matrix
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Good vs bad taxonomy examples, before/after comparisons, audit output samples
- `${CLAUDE_SKILL_DIR}/references/audit-report-format.md`: Visual report template and bar chart generation rules
