---
name: pre-publish-checker
description: |
  Pre-publication validation for Hugo posts: front matter, SEO, links, images,
  draft status, and taxonomy. Use when user wants to check a post before
  publishing, validate blog content, or run pre-publish checks. Use for
  "pre-publish", "check post", "ready to publish", "validate post", or
  "publication check". Do NOT use for content writing, editing prose, or
  generating new posts.
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
  - Skill
---

# Pre-Publish Checker Skill

## Operator Context

This skill operates as an operator for Hugo blog post validation, configuring Claude's behavior for rigorous pre-publication quality assurance. It implements a **Sequential Validation** architectural pattern — assess structure, validate fields, check assets, report — with **Domain Intelligence** embedded in Hugo-specific rules and SEO best practices.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before validation
- **Non-Destructive**: Never modify post files without explicit user request
- **Complete Output**: Show all validation results; never summarize or skip categories
- **Blocker Classification**: Clearly distinguish BLOCKER from SUGGESTION severity
- **Reproduce Findings**: Every reported issue must reference the exact line or field

### Default Behaviors (ON unless disabled)
- **Full Validation**: Run all check categories (front matter, SEO, content, links, images, draft)
- **Taxonomy Suggestions**: Suggest tags/categories based on existing site taxonomy
- **Reading Time Calculation**: Calculate at 200 WPM for prose, 50% weight for code blocks
- **Skip External Links**: Do not validate external URLs (use `--check-external` to enable)
- **Severity Separation**: Count blockers and suggestions independently in final report

### Optional Behaviors (OFF unless enabled)
- **External Link Validation**: Check that external URLs are reachable (`--check-external`)
- **Auto-Fix**: Offer to fix suggestion-level issues automatically (`--auto-fix`)
- **Strict Mode**: Treat all suggestions as blockers (`--strict`)

## What This Skill CAN Do
- Parse Hugo TOML (+++) and YAML (---) front matter and validate required fields
- Calculate word count and reading time with code block weighting
- Analyze header structure (H2/H3 hierarchy) for logical organization
- Detect draft status, TODO/FIXME comments, and placeholder text
- Verify internal links point to existing content in content/ or static/
- Verify image files exist and have alt text
- Suggest tags/categories from existing site taxonomy
- Generate structured validation report with clear pass/fail/skip status

## What This Skill CANNOT Do
- Validate external URLs by default (network latency, rate limiting concerns)
- Judge content quality beyond structural and metadata checks
- Automatically publish posts or change draft status
- Modify files without explicit user consent
- Replace editorial review for prose quality or accuracy

---

## Instructions

### Usage

```
/pre-publish [path-to-post]
/pre-publish content/posts/2025-01-my-post.md
/pre-publish --check-external content/posts/2025-01-my-post.md
```

If no path provided, prompt user to specify the post file.

### Phase 1: ASSESS

**Goal**: Parse post structure and extract all validatable elements.

**Step 1: Read the target markdown file**

Verify the file exists. If not, list available posts and ask user to confirm.

**Step 2: Extract front matter**

Hugo supports both TOML and YAML front matter. Detect delimiter type:
- TOML: enclosed in `+++` delimiters
- YAML: enclosed in `---` delimiters

Parse all fields into structured data.

**Step 3: Extract body content**

Everything after front matter closing delimiter. Inventory:
- Word count (prose only, exclude code fences)
- Header hierarchy (H2, H3 levels)
- Internal links, external links, image references
- TODO/FIXME markers and placeholder patterns

**Gate**: File parsed successfully. Front matter extracted. Body content inventoried. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Run all validation checks with correct severity classification.

**Step 1: Front matter validation**

| Field | Requirement | Severity |
|-------|-------------|----------|
| title | Present, non-empty | BLOCKER |
| date | Present, valid format | BLOCKER |
| draft | Must be `false` | BLOCKER |
| description | Present, 150-160 chars | SUGGESTION |
| tags | Present, 3-5 items | SUGGESTION |
| categories | Present, 1-2 items | SUGGESTION |

**Step 2: SEO validation**

| Check | Optimal Range | Severity |
|-------|---------------|----------|
| Title length | 50-60 characters | SUGGESTION |
| Description length | 150-160 characters | SUGGESTION |
| Slug format | URL-friendly, no special chars | SUGGESTION |

Derive slug from filename: `2025-01-my-post.md` becomes `my-post`.

**Step 3: Content quality validation**

| Check | Requirement | Severity |
|-------|-------------|----------|
| Word count | Minimum 500 words | SUGGESTION |
| Reading time | Calculate at 200 WPM | INFO |
| Header structure | H2/H3 present, logical hierarchy | SUGGESTION |
| Opening paragraph | No preamble phrases | SUGGESTION |

Preamble detection phrases: "In this post, I will...", "Today I'm going to...", "Let me explain...", "Welcome to...", "First of all...", "Before we begin..."

**Step 4: Link validation**

- **Internal links**: Pattern `](/posts/...)` or `](/images/...)`. Verify target exists. Severity: BLOCKER if missing.
- **External links**: Pattern `](https://...)`. Skip by default. Severity: WARNING if unreachable (when enabled).
- **Image links**: Pattern `![alt](path)` or Hugo shortcodes. Verify file exists in static/. Severity: BLOCKER if missing.

**Step 5: Image validation**

| Check | Requirement | Severity |
|-------|-------------|----------|
| Alt text | All images must have non-empty alt | SUGGESTION |
| File existence | All referenced images exist in static/ | BLOCKER |
| Path format | Correct Hugo static path convention | SUGGESTION |

Hugo image path patterns: `/images/filename.png` (absolute from static/), `images/filename.png` (relative), `{{< figure src="..." >}}` (shortcode).

**Step 6: Draft status validation**

| Check | Requirement | Severity |
|-------|-------------|----------|
| draft field | Must be `false` | BLOCKER |
| TODO comments | None present | WARNING |
| FIXME comments | None present | WARNING |
| Placeholder text | None present | BLOCKER |

Placeholder patterns: `[insert X here]`, `[TBD]`, `[TODO]`, `XXX`, `PLACEHOLDER`, `Lorem ipsum`.

**Gate**: All validation checks executed. Each check produced a status (PASS, FAIL, WARN, SKIP, INFO). Proceed only when gate passes.

### Phase 3: SUGGEST TAXONOMY

**Goal**: Provide actionable taxonomy suggestions when tags or categories are missing.

**Step 1: Build taxonomy index**

Read existing posts to collect all tags and categories currently in use.

**Step 2: Analyze content**

Match current post content against existing taxonomy terms. Prefer established terms over inventing new ones.

**Step 3: Generate suggestions**

Suggest 3-5 tags and 1-2 categories. Avoid over-suggesting popular tags; distribute evenly across the taxonomy.

**Gate**: Taxonomy suggestions generated from existing site data (not invented). Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate structured validation report with clear outcome.

Format the report as:

```
===============================================================
 PRE-PUBLISH CHECK: [file path]
===============================================================

 FRONT MATTER:
   [status] field: "value" (details)

 SEO:
   [status] check: result (optimal range)

 CONTENT:
   [status] metric: value

 LINKS:
   [status] type: count valid/invalid

 IMAGES:
   [status] check: result

 DRAFT STATUS:
   [status] check: result

===============================================================
 RESULT: [READY FOR PUBLISH | NOT READY - N blockers]
===============================================================
```

**Status icons**: `[PASS]`, `[WARN]`, `[FAIL]`, `[SKIP]`, `[INFO]`

**Result classification**:
- READY FOR PUBLISH: Zero blockers (suggestions and warnings are acceptable)
- NOT READY: One or more blockers present; list all blockers after result

**Gate**: Report generated with accurate blocker count. Result matches blocker tally.

---

## Examples

### Example 1: Clean Post
User says: "Check my kubernetes post before I publish"
Actions:
1. Parse front matter and body content (ASSESS)
2. Validate all fields, links, images, draft status (VALIDATE)
3. All tags present, skip taxonomy (SUGGEST)
4. Report: READY FOR PUBLISH with all PASS (REPORT)
Result: Structured report, zero blockers, post cleared for publication

### Example 2: Post With Blockers
User says: "Is my draft ready?"
Actions:
1. Parse front matter — draft: true detected (ASSESS)
2. Validate — draft blocker, missing image, TODO found (VALIDATE)
3. Tags missing — suggest from existing taxonomy (SUGGEST)
4. Report: NOT READY - 3 blockers listed (REPORT)
Result: Structured report with blocker list and suggestions

---

## Error Handling

### Error: "File Not Found"
Cause: Wrong path, running from wrong directory, or file moved
Solution:
1. Verify the path is correct and absolute
2. List available posts with `ls content/posts/`
3. Check if running from repository root
4. Ask user to confirm the correct file path

### Error: "Cannot Parse Front Matter"
Cause: Syntax errors in TOML/YAML, mismatched delimiters, invalid date
Solution:
1. Check for matching delimiters (`+++` or `---`)
2. Validate TOML/YAML syntax (unclosed quotes, bad indentation)
3. Verify date format matches Hugo expectations
4. Report the parse error location and suggest correction

### Error: "Image Path Cannot Be Verified"
Cause: Non-standard path format, Hugo shortcode variant, or missing static/ directory
Solution:
1. Normalize path (strip leading `/`, resolve relative paths)
2. Check both `static/` and `assets/` directories
3. Handle Hugo shortcode `figure` and `img` variants
4. Report as SKIP with explanation if path format is unrecognizable

---

## Anti-Patterns

### Anti-Pattern 1: Blocking on Optional Fields
**What it looks like**: Marking post as NOT READY because tags are missing
**Why wrong**: Tags are recommendations, not requirements. Users may have valid reasons to omit them.
**Do instead**: Classify as SUGGESTION, count separately from blockers in the final result.

### Anti-Pattern 2: Inventing Taxonomy Instead of Reading
**What it looks like**: Suggesting generic tags like "programming" or "tech" without checking the site
**Why wrong**: Creates inconsistent taxonomy, fragments content organization, ignores established patterns.
**Do instead**: Always read existing posts first. Suggest from established taxonomy when possible.

### Anti-Pattern 3: Skipping Draft Status Check
**What it looks like**: Reporting READY FOR PUBLISH when `draft: true`
**Why wrong**: Hugo excludes draft posts from production builds. This is the highest-priority blocker.
**Do instead**: Check draft field first. Treat as a non-negotiable blocker.

### Anti-Pattern 4: Modifying Files Without Consent
**What it looks like**: Automatically adding missing description or fixing tags during validation
**Why wrong**: Validation is read-only. User must approve all changes to their content.
**Do instead**: Report findings, suggest fixes, wait for explicit user request before modifying.

### Anti-Pattern 5: Silent Skip Without Reporting
**What it looks like**: Not reporting when a check could not be performed (directory not found, parse error)
**Why wrong**: User assumes check passed when it was actually skipped. False confidence.
**Do instead**: Always report `[SKIP]` with a reason when any check cannot complete.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Front matter looks fine" | Looking ≠ validating each field | Parse and check every required field |
| "Images are probably there" | Probably ≠ file system check | Verify each path exists on disk |
| "No need to check taxonomy" | Missing context creates bad suggestions | Read existing posts before suggesting |
| "Draft is obvious, skip it" | Obvious checks prevent obvious mistakes | Always validate draft field explicitly |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/seo-guidelines.md`: SEO length requirements and best practices
- `${CLAUDE_SKILL_DIR}/references/hugo-frontmatter.md`: Hugo front matter fields and formats
- `${CLAUDE_SKILL_DIR}/references/checklist.md`: Complete validation checklist reference
