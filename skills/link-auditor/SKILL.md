---
name: link-auditor
description: |
  Hugo site link health analysis: scan markdown, build internal link graph,
  validate paths, and report issues. Use when auditing site link structure,
  finding orphan pages, checking for broken internal/external links, or
  validating image paths. Use for "link audit", "orphan pages", "broken links",
  "link health", or "site link structure". Do NOT use for single-post
  pre-publish checks or content editing.
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

# Link Auditor Skill

## Operator Context

This skill operates as an operator for link health analysis on Hugo static sites, configuring Claude's behavior for comprehensive, non-destructive link auditing. It implements the **Pipeline** architectural pattern -- Scan, Analyze, Validate, Report -- with **Domain Intelligence** embedded in Hugo path resolution and SEO link graph metrics.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before auditing
- **Non-Destructive**: Never modify content files without explicit user request
- **Complete Output**: Show all findings; never summarize or abbreviate issue lists
- **Issue Classification**: Clearly distinguish critical issues (orphans, broken links) from suggestions (under-linked)
- **Hugo Path Awareness**: Try multiple path resolutions before reporting a link as broken

### Default Behaviors (ON unless disabled)
- **Full Scan**: Analyze all markdown files in content/
- **Graph Analysis**: Build and analyze internal link adjacency graph
- **Image Validation**: Check all image paths exist in static/
- **Skip External Validation**: Do not HTTP-check external URLs (enable with --check-external)
- **Issues-Only Output**: Show only problems, not all valid links

### Optional Behaviors (OFF unless enabled)
- **External Link Validation**: HTTP HEAD check on external URLs (--check-external)
- **Verbose Mode**: Show all links including valid ones (--verbose)
- **Custom Inbound Threshold**: Flag pages with fewer than N inbound links (--min-inbound N)

## What This Skill CAN Do
- Extract internal, external, and image links from Hugo markdown content
- Build adjacency matrix of internal link relationships
- Identify orphan pages (0 inbound internal links) and under-linked pages
- Detect link sinks (receive links, no outbound) and hub pages (many outbound)
- Validate internal link paths resolve to real content files
- Validate image files exist in static/
- Optionally validate external URLs via HTTP HEAD requests
- Handle known false positives (LinkedIn, Twitter block bot requests)
- Generate audit reports with actionable fix suggestions

## What This Skill CANNOT Do
- Validate external URLs by default (network latency, rate limiting concerns)
- Guarantee external link accuracy (social media sites block bots)
- Automatically fix broken links or add missing links
- Analyze JavaScript-rendered content or Hugo shortcodes beyond standard patterns
- Replace pre-publish-checker for single-post validation

---

## Instructions

### Phase 1: SCAN

**Goal**: Extract all links from markdown files and classify them by type.

**Step 1: Identify content root**

Locate the Hugo content directory and enumerate all markdown files:

```bash
# TODO: scripts/link_scanner.py not yet implemented
# Manual alternative: extract links from markdown files
grep -rn '\[.*\](.*' ~/your-blog/content/ --include="*.md"
```

**Step 2: Extract links by type**

Parse each markdown file for three link categories:

Internal Links:
- `[text](/posts/slug/)` -- absolute internal path
- `[text](../other-post/)` -- relative path
- `[text](/categories/tech/)` -- taxonomy pages
- `{{< ref "posts/slug.md" >}}` -- Hugo ref shortcode

External Links:
- `[text](https://example.com/path)`
- `[text](http://example.com/path)`

Image Links:
- `![alt](/images/filename.png)` -- static path
- `![alt](images/filename.png)` -- relative path
- `{{< figure src="/images/file.png" >}}` -- Hugo shortcode

**Step 3: Tally link counts per file**

Record total internal, external, and image links per file for the summary.

**Gate**: All markdown files scanned. Link extraction complete with counts by type. Proceed only when gate passes.

### Phase 2: ANALYZE

**Goal**: Build internal link graph and compute structural metrics.

**Step 1: Build adjacency matrix**

Map every internal link to its source and target:

```
Page A -> Page B (A links to B)
Page A -> Page C
Page B -> Page D
Page C -> (no outbound)
Page E -> (no outbound, no inbound = orphan)
```

**Step 2: Compute graph metrics**

| Metric | Definition | SEO Impact |
|--------|------------|------------|
| Orphan Pages | 0 inbound internal links | Critical -- invisible to crawlers |
| Under-Linked | < N inbound links (default 2) | Missed SEO opportunity |
| Link Sinks | Receives links, no outbound | May indicate incomplete content |
| Hub Pages | Many outbound links | Good for navigation |

**Step 3: Classify findings by severity**

- **Critical**: Orphan pages, broken internal links, missing images
- **Warning**: Under-linked pages, link sinks
- **Info**: Hub pages, external link stats

**Gate**: Adjacency matrix built. All pages classified with inbound/outbound counts. Proceed only when gate passes.

### Phase 3: VALIDATE

**Goal**: Verify link targets resolve to real files or live URLs.

**Step 1: Validate internal links**

For each internal link target:
1. Parse the link target path
2. Try Hugo path resolutions: `content/posts/slug.md`, `content/posts/slug/index.md`, `content/posts/slug/_index.md`
3. Mark as broken only if ALL resolutions fail
4. Record source file and line number for broken links

**Step 2: Validate image paths**

For each image reference:
1. Parse image source path (absolute or relative)
2. Map to static/ directory
3. Check file exists
4. Record source file and line number for missing images

**Step 3: Validate external links (optional)**

Only when `--check-external` is enabled:
1. HTTP HEAD request to URL
2. Follow redirects (up to 3)
3. Check response status code
4. Mark known false positives as "blocked (expected)" not broken

Known false positives: LinkedIn (403), Twitter/X (403/999), Facebook (varies).

**Gate**: All link targets checked. Broken links have file and line numbers. External results (if enabled) distinguish real failures from false positives. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Present findings in a structured, actionable audit report.

**Step 1: Generate summary header**

```
===============================================================
 LINK AUDIT: ~/your-blog/content/
===============================================================

 SCAN SUMMARY:
   Posts scanned: 15
   Internal links: 42
   External links: 28
   Image references: 12
```

**Step 2: Report by severity**

List critical issues first (orphans, broken links, missing images), then warnings (under-linked, sinks), then info (hubs, valid external counts).

Each issue must include:
- File path
- Line number (for broken links and missing images)
- Specific suggestion for resolution

**Step 3: Generate recommendations**

Conclude with numbered, actionable recommendations ordered by impact:

```
===============================================================
 RECOMMENDATIONS:
   1. Add internal links to 2 orphan pages
   2. Fix 1 broken internal link in /posts/example.md line 45
   3. Update or remove 1 dead external link
   4. Add missing image or fix path in /posts/images.md line 12
===============================================================
```

**Gate**: Report generated with all findings. Every issue has a file path and actionable suggestion. Audit is complete.

---

## Error Handling

### Error: "No markdown files found"
Cause: Wrong directory path or empty content root
Solution:
1. Verify the content/ directory exists at the given path
2. Check that .md files exist (not just subdirectories)
3. Confirm the path is the Hugo content root, not the project root

### Error: "External validation timeout"
Cause: Target site is slow, blocking requests, or unreachable
Solution:
1. Check if the site is in the known false-positives list (LinkedIn, Twitter)
2. Add persistently failing sites to the false-positives list
3. Use shorter timeout with `--timeout 5` for slow sites

### Error: "Image path ambiguous"
Cause: Path could be relative or absolute, unclear resolution
Solution:
1. The scanner checks both interpretations automatically
2. Report shows which interpretation was attempted
3. Verify the Hugo site's static directory structure matches expectations

---

## Anti-Patterns

### Anti-Pattern 1: Treating Bot-Blocked Sites as Broken
**What it looks like**: Reporting LinkedIn/Twitter links as broken when they return 403/999.
**Why wrong**: These sites actively block bot requests. Links work fine in browsers.
**Do instead**: Maintain false-positives list. Report as "blocked (expected)" not broken.

### Anti-Pattern 2: Skipping Graph Analysis
**What it looks like**: Only checking for broken links without analyzing the link graph.
**Why wrong**: Orphan pages are invisible to search crawlers. This is often the highest-impact finding.
**Do instead**: Always build the adjacency matrix and compute inbound link counts.

### Anti-Pattern 3: Literal Path Matching Without Hugo Resolution
**What it looks like**: Treating `/posts/slug/` as a literal file path and reporting it broken.
**Why wrong**: Hugo resolves paths through multiple conventions (slug.md, slug/index.md, slug/_index.md).
**Do instead**: Try all Hugo path resolutions before reporting a link as broken.

### Anti-Pattern 4: Modifying Content Without User Consent
**What it looks like**: Automatically adding links to orphan pages or fixing broken paths.
**Why wrong**: This skill is non-destructive. Users must approve all content changes.
**Do instead**: Report findings with specific suggestions. Let the user decide which fixes to apply.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Only 3 broken links, not worth a full audit" | Orphan pages are invisible without graph analysis | Run full 4-phase audit |
| "External links probably still work" | Link rot is progressive and silent | Validate with --check-external periodically |
| "Hugo will resolve it somehow" | Hugo path resolution has specific rules | Test all resolution patterns explicitly |
| "Small site doesn't need link auditing" | Even 10 posts can have orphans | Run audit regardless of site size |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/link-graph-metrics.md`: Graph metrics definitions and SEO impact
- `${CLAUDE_SKILL_DIR}/references/false-positives.md`: Sites known to block validation requests
- `${CLAUDE_SKILL_DIR}/references/fix-strategies.md`: Resolution strategies for each issue type
