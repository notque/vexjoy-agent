# Taxonomy Guidelines for Technical Blogs

Best practices for organizing categories and tags on a technical blog.

---

## Core Principles

### 1. Taxonomy Serves Navigation

The primary purpose of taxonomy is to help readers find related content. Every category and tag should answer: "What other posts would someone interested in this post want to read?"

### 2. Consistency Over Creativity

Consistent naming is more valuable than clever naming. Readers learn your taxonomy over time; changing or varying terms creates confusion.

### 3. Fewer Categories, More Tags

Categories = broad, stable, few (3-7)
Tags = specific, dynamic, many (10-30 active)

### 4. Lowercase with Hyphens

Standard format: `lowercase-with-hyphens`

Avoid:
- CamelCase: `HugoDebugging`
- Underscores: `hugo_debugging`
- Spaces: `hugo debugging`
- Mixed case: `Hugo-Debugging`

---

## Categories Best Practices

### Purpose

Categories represent the content pillars of your blog. They answer: "What type of content is this?"

### Guidelines

| Guideline | Recommendation |
|-----------|----------------|
| Total count | 3-7 categories |
| Per post | 1-2 categories (usually 1) |
| Stability | Rarely change after initial setup |
| Hierarchy | Keep flat (avoid sub-categories for small blogs) |

### Recommended Categories for Technical Blogs

| Category | Content Type |
|----------|--------------|
| `technical-notes` | Deep dives, explanations, debugging journeys |
| `tutorials` | Step-by-step guides, how-to content |
| `opinion` | Commentary, perspectives, industry thoughts |
| `tools` | Reviews, comparisons, recommendations |
| `meta` | Site updates, blogging about blogging |

### Category Red Flags

- **Too many categories**: More than 7 suggests over-categorization
- **Empty categories**: Defined but never used
- **Overlapping categories**: `tutorials` and `how-to-guides` are synonyms
- **Multi-category posts**: Posts with 3+ categories are unfocused

---

## Tags Best Practices

### Purpose

Tags provide cross-cutting classification. They answer: "What specific topics does this post cover?"

### Guidelines

| Guideline | Recommendation |
|-----------|----------------|
| Total active | 10-30 tags |
| Per post | 3-5 tags |
| Minimum usage | Each tag should apply to 2+ posts |
| Specificity | Specific enough to be useful, broad enough to be reusable |

### Tag Types

**Technology Tags**: The tools and platforms discussed
- `hugo`, `cloudflare`, `git`, `docker`, `nginx`

**Concept Tags**: The problems and activities covered
- `debugging`, `performance`, `deployment`, `security`, `configuration`

**Format Tags** (use sparingly): The content style
- `quick-tip`, `deep-dive`, `walkthrough`

### Tag Red Flags

- **Single-use tags**: Used only once (too specific)
- **Case variations**: `Hugo` and `hugo` as separate tags
- **Synonym duplicates**: `debugging` and `troubleshooting`
- **Title-as-tag**: Tag that mirrors the post title exactly
- **Over-tagging**: Posts with 7+ tags

---

## Naming Conventions

### Standard Format

All taxonomy terms should follow: `lowercase-with-hyphens`

### Transformation Rules

| Source | Becomes |
|--------|---------|
| Hugo | `hugo` |
| GitHub Actions | `github-actions` |
| CI/CD | `cicd` or `ci-cd` |
| S3 | `s3` |
| Node.js | `nodejs` |
| .NET | `dotnet` |

### Pluralization

Prefer singular forms:
- `template` not `templates`
- `tutorial` not `tutorials`
- `tool` not `tools`

Exception: When the plural is the common term:
- `kubernetes` (never `kubernete`)
- `analytics` (never `analytic`)

### Abbreviations

Use the most recognizable form:
- `k8s` OR `kubernetes` (pick one and be consistent)
- `cicd` OR `continuous-integration` (not both)
- `aws` not `amazon-web-services`

---

## Maintenance Cadence

### Monthly Review

- Check for new orphan tags
- Review tag counts (merge low-usage tags)
- Verify no case inconsistencies

### Quarterly Review

- Evaluate category structure
- Identify tag consolidation opportunities
- Update taxonomy documentation

### Per-Post Workflow

Before publishing:
1. Check if existing tags apply (reuse > create)
2. Verify tag naming matches conventions
3. Assign 1-2 categories maximum
4. Assign 3-5 tags

---

## SEO Considerations

### Tag Pages

Each tag generates a page listing all posts with that tag. For SEO value:
- Tags need 2+ posts to provide value
- Popular tags should have meaningful descriptions
- Tag slugs should be search-friendly terms

### Category Pages

Categories are major navigation entry points:
- Should have custom descriptions
- Consider adding featured posts
- Keep count balanced (avoid 1-post categories)

### Internal Linking

Taxonomy creates automatic internal linking:
- Related tags link related content
- Category pages consolidate topic clusters
- Cross-tag discovery helps readers explore

---

## Common Mistakes to Avoid

### 1. Over-Specific Tags

Bad: `hugo-template-debugging-with-console-log`
Good: `hugo`, `templates`, `debugging`

### 2. Under-Specific Tags

Bad: `programming`
Good: `go`, `python`, `javascript`

### 3. Redundant Tags

Bad: `hugo-themes`, `hugo-templates`, `hugo-shortcodes`, `hugo-config`
Good: `hugo` + `themes`, `hugo` + `templates`, etc.

### 4. Inconsistent Naming

Bad: `Cloudflare`, `cloudflare`, `CloudFlare`
Good: `cloudflare` (everywhere)

### 5. Category Creep

Bad: Adding new categories for each content type
Good: Mapping new content to existing categories

---

## References

- Hugo Taxonomies Documentation: https://gohugo.io/content-management/taxonomies/
- Google SEO Best Practices for Categories: https://developers.google.com/search/docs/specialty/ecommerce/best-practices
