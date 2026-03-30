---
name: link-auditor
description: "Hugo site link health: scan markdown, build link graph, validate paths."
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
    - "audit links"
    - "find broken links"
    - "link health"
  category: content-publishing
---

# Link Auditor Skill

Hugo site link health analysis through a 4-phase pipeline: Scan, Analyze, Validate, Report. Extracts internal, external, and image links from Hugo markdown content; builds an adjacency matrix of internal link relationships; identifies orphan pages, under-linked pages, link sinks, and hub pages; validates that link targets resolve to real files; and generates audit reports with actionable fix suggestions.

Read and follow the repository CLAUDE.md before starting any audit.

## Instructions

### Phase 1: SCAN

**Goal**: Extract all links from every markdown file and classify them by type.

**Step 1: Identify content root**

Scan all markdown files in `content/` because even small sites with 10 posts can have orphan pages, and partial scans miss graph-level issues. Locate the Hugo content directory and enumerate all markdown files:

```bash
# TODO: scripts/link_scanner.py not yet implemented
# Manual alternative: extract links from markdown files
grep -rn '\[.*\](.*' ~/your-blog/content/ --include="*.md"
```

**Step 2: Extract links by type**

Parse each markdown file for three link categories. Classify by type to understand link distribution:

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

Always build the adjacency matrix and compute inbound link counts because orphan pages are invisible to search crawlers and this is often the highest-impact finding an audit produces. Map every internal link to its source and target:

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
| Under-Linked | < N inbound links (default 2, adjustable with --min-inbound N) | Missed SEO opportunity |
| Link Sinks | Receives links, no outbound | May indicate incomplete content |
| Hub Pages | Many outbound links | Good for navigation |

**Step 3: Classify findings by severity**

Clearly distinguish critical issues from suggestions because they require different urgency levels. Organize all findings by impact:

- **Critical**: Orphan pages, broken internal links, missing images
- **Warning**: Under-linked pages, link sinks
- **Info**: Hub pages, external link stats

**Gate**: Adjacency matrix built. All pages classified with inbound/outbound counts. Proceed only when gate passes.

### Phase 3: VALIDATE

**Goal**: Verify link targets resolve to real files or live URLs.

**Step 1: Validate internal links**

For each internal link target, try all Hugo path resolutions before reporting a link as broken because Hugo resolves paths through multiple conventions. Check these resolutions in order:

1. Parse the link target path
2. Try Hugo path resolutions: `content/posts/slug.md`, `content/posts/slug/index.md`, `content/posts/slug/_index.md`
3. Mark as broken only if ALL resolutions fail
4. Record source file and line number for broken links

**Step 2: Validate image paths**

Check all image paths against `static/` because missing images are critical issues. Validate both absolute and relative interpretations:

1. Parse image source path (absolute or relative)
2. Map to static/ directory, checking both absolute and relative interpretations
3. Check file exists
4. Record source file and line number for missing images

**Step 3: Validate external links (optional)**

Skip external URL validation by default because network latency, rate limiting, and bot-blocking make results unreliable. Only run validation when explicitly enabled with `--check-external` flag. When enabled, follow these steps:

1. HTTP HEAD request to URL
2. Follow redirects (up to 3)
3. Check response status code
4. Report known bot-blocked sites as "blocked (expected)" not broken because LinkedIn (403), Twitter/X (403/999), and Facebook actively block automated requests while links work fine in browsers

Use `--verbose` to include valid links in the output (default: issues only).

**Gate**: All link targets checked. Broken links have file and line numbers. External results (if enabled) distinguish real failures from false positives. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Present findings in a structured, actionable audit report.

Never modify content files during this phase because users must approve all content changes. Report findings with specific suggestions and let the user decide which fixes to apply.

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

List critical issues first (orphans, broken links, missing images), then warnings (under-linked, sinks), then info (hubs, valid external counts). Show all findings without summarizing or abbreviating because partial issue lists hide problems.

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

Always run the full 4-phase audit regardless of how few issues appear because link rot is progressive and orphan pages are invisible without graph analysis.

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

## References

- `${CLAUDE_SKILL_DIR}/references/link-graph-metrics.md`: Graph metrics definitions and SEO impact
- `${CLAUDE_SKILL_DIR}/references/false-positives.md`: Sites known to block validation requests
- `${CLAUDE_SKILL_DIR}/references/fix-strategies.md`: Resolution strategies for each issue type
