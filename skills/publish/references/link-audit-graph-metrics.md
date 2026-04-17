# Link Graph Metrics

Understanding link graph analysis and its SEO impact.

---

## Why Link Graph Matters

Search engines discover content by following links. A page with no inbound links is **invisible** to crawlers that enter your site through other pages. Internal linking also distributes "link equity" - the SEO value that flows through your site.

---

## Metric Definitions

### Orphan Pages (Critical)

**Definition**: Pages with 0 inbound internal links from other content pages.

**SEO Impact**: CRITICAL
- Crawlers cannot discover these pages by following links
- Pages must be found through sitemap only
- Lower crawl priority, slower indexing
- Lost opportunity to pass link equity

**Common Causes**:
- Old content that was never linked
- New content where author forgot to add contextual links
- Content that doesn't fit site themes
- Deleted pages that were linking sources

**Fix Strategies**:
1. Add contextual link from related content
2. Include in navigation or category listing
3. Create "Related Posts" section
4. Add to pillar/hub page
5. If truly irrelevant, consider removing

---

### Under-Linked Pages

**Definition**: Pages with fewer than N inbound links (configurable, default 2).

**SEO Impact**: MEDIUM
- May be indexed but with lower authority
- Lost opportunity for internal PageRank distribution
- Indicates missed cross-linking opportunities

**Threshold Guidance**:
- Small site (<20 pages): 1 inbound minimum
- Medium site (20-100 pages): 2 inbound minimum
- Large site (100+ pages): 3 inbound minimum

**Fix Strategies**:
1. Identify topic clusters and cross-link
2. Add to "Further Reading" sections
3. Create series that link between parts
4. Build resource/hub pages that aggregate links

---

### Link Sinks

**Definition**: Pages that receive inbound links but have no outbound internal links.

**SEO Impact**: LOW-MEDIUM
- May indicate incomplete or stub content
- Concentrates link equity without distribution
- Not necessarily bad (detailed reference pages)

**When Acceptable**:
- Comprehensive reference pages
- Landing pages designed for conversion
- Content with external-only links

**When Problematic**:
- Short posts that should link to related content
- Pages in a series that don't link forward/back
- Pages with obvious related content

**Fix Strategies**:
1. Add "Related" or "See Also" section
2. Link to next/previous in series
3. Add contextual links within content

---

### Hub Pages

**Definition**: Pages with many outbound internal links (5+ by default).

**SEO Impact**: POSITIVE (usually)
- Good for site navigation
- Distribute link equity to many pages
- Help crawlers discover content

**Types of Hubs**:
- **Index/Archive Pages**: List all posts in category
- **Pillar Content**: Comprehensive guides linking to subtopics
- **Resource Pages**: Curated link collections
- **Series Introductions**: Link to all parts

**Potential Issues**:
- Too many links may dilute individual link value
- User experience if links aren't organized
- Maintenance burden keeping links current

**Best Practices**:
- Organize links by topic/section
- Keep to 100 links maximum per page (Google guideline)
- Prioritize most important links earlier in content

---

## Link Equity Flow

Understanding how value flows through your site:

```
                    [Homepage]
                    Link Equity: 100
                         |
           +-------------+-------------+
           |             |             |
     [Category A]  [Category B]  [Category C]
     Equity: 33    Equity: 33    Equity: 33
           |             |             |
       +---+---+     +---+---+     +---+---+
       |       |     |       |     |       |
    [Post]  [Post] [Post]  [Post] [Post]  [Orphan]
    Eq:16   Eq:16  Eq:16   Eq:16  Eq:33   Eq: 0
```

The orphan page receives NO equity from the internal link structure.

---

## Analysis Workflow

### 1. Generate Report
```bash
# TODO: scripts/link_scanner.py not yet implemented
# Use manual grep-based link extraction as described in SKILL.md
```

### 2. Priority Order
1. Fix orphan pages (critical SEO issue)
2. Fix broken internal links (broken crawl paths)
3. Add links to under-linked pages (opportunity)
4. Review link sinks (may be acceptable)

### 3. Validation
After fixes, re-run audit to verify:
- No new orphans created
- Orphans now have inbound links
- Broken links resolved

---

## Metrics Reference

| Metric | Threshold | Severity | Action |
|--------|-----------|----------|--------|
| Orphan Pages | 0 inbound | Critical | Immediate fix required |
| Under-Linked | < 2 inbound | Medium | Fix during content updates |
| Link Sinks | 0 outbound, >0 inbound | Low | Review, fix if appropriate |
| Hub Pages | 5+ outbound | Info | Usually positive, monitor count |

---

## Related Concepts

**PageRank**: Google's algorithm for measuring page importance based on link structure.

**Crawl Budget**: How much time/resources search engines allocate to crawling your site.

**Link Equity**: The value passed from one page to another through links.

**Topic Clusters**: Content strategy organizing pages around pillar content.
