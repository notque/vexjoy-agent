---
title: SEO Audit — Keyword Research, On-Page Analysis, Technical SEO, Content Gaps, Competitor Benchmarking
domain: marketing
level: 3
skill: marketing
---

# SEO Audit Reference

> **Scope**: Complete SEO audit methodology covering keyword research with intent classification, on-page analysis, technical SEO evaluation, content gap identification, and competitor benchmarking. Use when running any SEO audit mode.
> **Generated**: 2026-05-05 — SEO best practices evolve; validate against current Google documentation for algorithm-specific guidance.

---

## Keyword Research Methodology

### Intent Classification

Every keyword must be classified by search intent before assessing opportunity. Intent determines content type, not the other way around.

| Intent | Signal Words | Content Match | Conversion Proximity |
|--------|-------------|---------------|---------------------|
| **Informational** | how to, what is, why does, guide, tutorial, examples | Blog post, guide, explainer, video | Low — awareness stage |
| **Navigational** | [brand name], [product name], login, pricing page | Homepage, product page, docs | Varies — brand-dependent |
| **Commercial** | best, vs, comparison, review, alternative, top 10 | Comparison page, review, listicle | Medium — consideration stage |
| **Transactional** | buy, pricing, demo, trial, sign up, discount, coupon | Landing page, pricing page, checkout | High — decision stage |

**Intent classification rules**:
- A keyword can have mixed intent. "best CRM software" is commercial + informational. Match the dominant intent.
- Google the keyword. The SERP layout reveals intent: featured snippets = informational, shopping results = transactional, comparison tables = commercial.
- Misclassified intent produces content that ranks but doesn't convert (informational content targeting transactional keywords) or content that never ranks (transactional pages targeting informational queries).

### Keyword Opportunity Assessment

For each keyword, evaluate five dimensions:

| Dimension | Assessment Method | Scoring |
|-----------|------------------|---------|
| **Relevance** | Does this keyword match the user's product/service and audience? | Must-have: direct match. Nice-to-have: adjacent topic. Skip: tangential. |
| **Search volume signals** | Relative demand based on available data (SERP features, autocomplete depth, PAA count) | High: multiple autocomplete suggestions, rich SERP features. Medium: some suggestions. Low: sparse. |
| **Difficulty** | Evaluate top 10 results: domain authority, content depth, page optimization | Easy: thin content in top 5, low-authority sites ranking. Moderate: mixed quality. Hard: all top 10 are authoritative, deep content. |
| **Intent alignment** | Does the keyword's intent match content you can/should produce? | Strong: intent matches your content capabilities. Weak: intent requires content type you can't produce well. |
| **Business value** | Does ranking for this keyword drive meaningful business outcomes? | High: directly related to product/service. Medium: adjacent topic that builds authority. Low: tangential traffic. |

**Opportunity score** = Business value (primary) + Difficulty inversion (secondary). High-value, lower-difficulty keywords surface first.

### Keyword Grouping

Group keywords into topic clusters, not flat lists:

```
Pillar Topic: "email marketing"
├── Cluster: "email subject lines"
│   ├── how to write email subject lines
│   ├── email subject line examples
│   ├── best email subject line length
│   └── email subject line A/B testing
├── Cluster: "email deliverability"
│   ├── how to improve email deliverability
│   ├── email spam score checker
│   └── email authentication SPF DKIM
└── Cluster: "email automation"
    ├── email automation tools comparison
    ├── drip campaign examples
    └── email sequence best practices
```

Each cluster becomes a content brief. The pillar topic becomes the pillar page. Internal links connect cluster pages to the pillar.

### Question-Based Keywords

Mine "People Also Ask" results and autocomplete for question keywords. These have three advantages:
1. Lower competition than head terms
2. Direct featured snippet opportunity (answer in 40-60 words, then elaborate)
3. Mirror actual user language and pain points

Question keyword template:

| Question | Intent | Current Coverage | SERP Feature | Priority |
|----------|--------|-----------------|--------------|----------|
| How do I [X]? | Informational | None | Featured snippet available | High |
| What is [X] vs [Y]? | Commercial | Thin content | Comparison table | High |
| Why does [X] happen? | Informational | Not covered | PAA box | Medium |

---

## On-Page SEO Analysis

### Element-by-Element Checklist

| Element | Standard | Common Failures | How to Check |
|---------|----------|----------------|--------------|
| **Title tag** | 50-60 chars, includes primary keyword, unique per page | Duplicate titles, keyword-stuffed, truncated in SERPs | View source or SEO crawler |
| **Meta description** | 150-160 chars, includes CTA, compelling, unique | Missing, duplicate, truncated, no call to action | View source |
| **H1** | Exactly one per page, includes primary keyword | Multiple H1s, missing H1, H1 doesn't match title tag intent | DOM inspection |
| **H2/H3 hierarchy** | Logical outline, secondary keywords where natural | Skipped levels (H1 -> H3), all H2s identical, no subheadings | DOM inspection |
| **Keyword usage** | Primary keyword in first 100 words, natural density 1-2% | Keyword stuffing (>3%), keyword absent from intro, unnatural phrasing | Manual read + word count |
| **Internal links** | 2-5 contextual links to related content per page | Orphan pages (no internal links), generic anchor text ("click here"), broken links | Crawl report |
| **Image alt text** | Descriptive, includes keyword where relevant, under 125 chars | Missing alt attributes, alt text = filename, keyword-stuffed alt text | Accessibility audit |
| **URL structure** | Short, readable, includes primary keyword, no parameters | Long URLs, parameter strings, stop words, uppercase | URL inspection |
| **Content depth** | Comprehensive coverage of the topic, answers related questions | Thin content (<300 words for informational), surface-level treatment | Word count + topic coverage comparison |
| **Structured data** | Schema markup matching content type (Article, FAQ, HowTo, Product) | Missing schema, incorrect schema type, validation errors | Schema.org validator |

### Content Quality Signals

Beyond technical elements, assess content quality factors that affect rankings:

- **E-E-A-T signals**: Experience (first-hand), Expertise (demonstrated knowledge), Authoritativeness (citations, credentials), Trustworthiness (accuracy, transparency)
- **Content freshness**: Last updated date visible, information current, no stale references
- **User engagement indicators**: Does the content answer the query without requiring a back-button click?
- **Readability**: Short paragraphs, subheadings every 200-300 words, bullet/numbered lists, active voice

### Severity Classification for On-Page Issues

| Severity | Definition | Examples |
|----------|-----------|----------|
| **Critical** | Directly preventing indexation or destroying rankings | Noindex on important pages, canonical pointing to wrong page, blocked by robots.txt |
| **High** | Significant ranking impact | Missing title tags, duplicate H1s across multiple pages, no internal links to key pages |
| **Medium** | Best practice violation with moderate impact | Title tags over 60 chars, missing meta descriptions, generic alt text |
| **Low** | Minor optimization opportunity | URL contains stop words, subheadings could include secondary keywords |

---

## Technical SEO Evaluation

### Crawlability and Indexation

| Check | Pass Criteria | Failure Indicators | Remediation |
|-------|--------------|--------------------:|-------------|
| **robots.txt** | Exists, allows critical paths, blocks only intended content | Missing, overly restrictive, blocking CSS/JS | Create/fix robots.txt with explicit allow/disallow |
| **XML sitemap** | Exists, submitted to Search Console, includes all indexable URLs, excludes noindex URLs | Missing, stale, includes 404s/redirects/noindex pages | Generate sitemap, submit, automate updates |
| **Canonical tags** | Self-referencing on all pages, correct on duplicates | Missing, pointing to wrong URL, conflicting with noindex | Audit all canonicals, fix conflicts |
| **Noindex/nofollow** | Applied intentionally to non-indexable content only | Accidentally applied to important pages | Audit meta robots tags, remove unintended |
| **Redirect chains** | Max 1 redirect between any two URLs | 3+ redirect hops, redirect loops | Flatten chains to single 301 |
| **404 pages** | Custom 404 with navigation, no important pages returning 404 | Default server 404, broken internal links pointing to 404s | Fix broken links, implement 301s for removed content |
| **Pagination** | rel=next/prev or load-more pattern, all pages accessible | Orphaned paginated pages, infinite scroll without crawlable links | Implement proper pagination signals |

### Performance and Core Web Vitals

| Metric | Good | Needs Improvement | Poor | Common Causes |
|--------|------|--------------------|------|--------------|
| **LCP** (Largest Contentful Paint) | < 2.5s | 2.5-4.0s | > 4.0s | Unoptimized images, render-blocking resources, slow server |
| **INP** (Interaction to Next Paint) | < 200ms | 200-500ms | > 500ms | Heavy JavaScript, long tasks, excessive DOM size |
| **CLS** (Cumulative Layout Shift) | < 0.1 | 0.1-0.25 | > 0.25 | Missing image dimensions, dynamic content injection, web fonts |

**Performance diagnosis checklist**:
- Image optimization: format (WebP/AVIF), compression, lazy loading, explicit dimensions
- Render-blocking resources: defer non-critical CSS/JS, inline critical CSS
- Server response time: TTFB < 200ms, CDN usage, caching headers
- JavaScript impact: bundle size, unused JS, third-party script audit
- Font loading: font-display: swap, preload critical fonts, subset fonts

### Mobile SEO

| Check | Standard | Failure Mode |
|-------|----------|-------------|
| Responsive design | Same content on mobile and desktop | Separate mobile site with content parity issues |
| Tap targets | Min 48x48px, 8px spacing | Overlapping links, tiny buttons |
| Font size | Min 16px body text | 12px text requiring pinch-zoom |
| Viewport | `<meta name="viewport" content="width=device-width, initial-scale=1">` | Missing or fixed-width viewport |
| Content parity | All content accessible on mobile | Hidden content, collapsed sections with no expand option |

### Structured Data Opportunities

| Content Type | Schema Type | Key Properties | SERP Feature Unlocked |
|-------------|------------|----------------|----------------------|
| Articles | Article, BlogPosting | headline, author, datePublished, image | Rich result with author, date |
| FAQ pages | FAQPage | Question, acceptedAnswer | FAQ accordion in SERP |
| How-to guides | HowTo | step, tool, supply | Step-by-step in SERP |
| Products | Product | name, price, availability, review | Price, availability, rating in SERP |
| Reviews | Review | itemReviewed, ratingValue | Star rating in SERP |
| Events | Event | startDate, location, performer | Event details in SERP |
| Breadcrumbs | BreadcrumbList | itemListElement | Breadcrumb trail in SERP |
| Organization | Organization | name, url, logo, sameAs | Knowledge panel |

---

## Content Gap Analysis

### Gap Identification Framework

| Gap Type | How to Identify | Priority Signal |
|----------|----------------|-----------------|
| **Competitor topic coverage** | Topics where competitors rank in top 10 and you don't appear in top 50 | High volume + commercial intent = high priority |
| **Content freshness** | Pages not updated in 12+ months with declining traffic | High if page historically drove significant traffic |
| **Thin content** | Pages under 300 words for informational queries; pages that don't adequately address the query | High if topic has search demand |
| **Missing content types** | Formats competitors use that you don't (comparison pages, calculators, templates, glossaries) | High if format matches dominant SERP type for your keywords |
| **Funnel gaps** | Missing content at buyer journey stages (awareness, consideration, decision) | Critical if you have bottom-funnel content but no top-funnel |
| **Topic cluster gaps** | Pillar topic exists but supporting pages are sparse | Medium-high -- cluster depth affects pillar ranking |

### Content Audit Comparison Template

| Topic | Your Coverage | Competitor A | Competitor B | Gap Type | Priority | Recommended Action |
|-------|-------------|--------------|--------------|----------|----------|-------------------|
| | Depth/format | Depth/format | Depth/format | | H/M/L | Create/update/expand |

### Content Gap Prioritization

Score each gap on three dimensions:

1. **Search demand**: How many people search for this topic? (High/Medium/Low)
2. **Competition**: How hard will it be to rank? (Easy/Moderate/Hard)
3. **Business alignment**: How closely does this topic relate to your product/service? (Direct/Adjacent/Tangential)

Prioritize: High demand + Easy competition + Direct alignment = immediate action. Low demand + Hard competition + Tangential = deprioritize.

---

## Competitor SEO Benchmarking

### Comparison Dimensions

| Dimension | What to Compare | Data Source |
|-----------|----------------|-------------|
| **Keyword overlap** | Keywords both sites rank for; where each ranks higher | SERP analysis for target keywords |
| **Keyword gaps** | Terms competitor ranks for that you don't | Competitor content audit |
| **Content depth** | Average content length, topic coverage breadth, publishing frequency | Manual content audit |
| **Backlink signals** | Types of sites linking, link-worthy content produced | SERP analysis, manual inspection |
| **Technical SEO** | Site speed, mobile experience, structured data usage | PageSpeed Insights, mobile test |
| **SERP features** | Featured snippets, PAA, image packs, knowledge panels owned | SERP inspection per keyword |
| **Content freshness** | How recently content is updated, publishing cadence | Blog/resource center inspection |

### Competitor Comparison Output Template

| Dimension | Your Site | Competitor A | Competitor B | Winner | Gap Size |
|-----------|-----------|--------------|--------------|--------|----------|
| Keyword count | | | | | |
| Content depth (avg words) | | | | | |
| Publishing frequency | | | | | |
| Backlink signals | | | | | |
| Technical score | | | | | |
| SERP feature presence | | | | | |
| Content freshness | | | | | |

### Competitor Strategy Extraction

Look for patterns in competitor SEO strategy:
- **Content clusters they're building**: repeated topics over 3+ months indicate strategic bets
- **Keyword trajectory**: are they moving upmarket (enterprise terms) or downmarket (SMB terms)?
- **Content format investments**: increasing video, tools, or interactive content signals a format strategy
- **Link acquisition patterns**: guest posts, original research, tools/calculators -- reveals their link-building approach
- **Technical investments**: AMP adoption, PWA, Core Web Vitals optimization -- reveals technical priorities

---

## Prioritized Action Plan Framework

### Quick Wins (This Week, <2 Hours Each)

Typical quick wins sorted by impact:
1. Fix title tags missing primary keywords
2. Add meta descriptions to pages without them
3. Fix broken internal links
4. Add alt text to images missing it
5. Fix redirect chains (flatten to single 301)
6. Add structured data to pages matching schema types
7. Update stale content with current information
8. Fix duplicate H1 tags

### Strategic Investments (This Quarter)

Typical strategic investments:
1. Build topic cluster with pillar page + 5-10 supporting pages
2. Create comparison/alternative pages for high-intent commercial keywords
3. Develop original research or data study for link acquisition
4. Overhaul site architecture for better internal linking
5. Implement comprehensive structured data across content types
6. Launch content refresh program for top 20 pages by traffic
7. Build interactive tools or calculators for link-worthy content

### Action Item Template

| Action | Expected Impact | Effort | Dependencies | Priority |
|--------|----------------|--------|--------------|----------|
| Specific action | H/M/L with reasoning | Hours/days | What must happen first | Quick win / Strategic |
