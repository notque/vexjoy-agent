---
name: content
description: "Content operations: editorial calendar, marketing, publishing, social media management."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - WebFetch
routing:
  force_route: false
  not_for: "prose voice and style (use writing), code documentation (use docs-sync-checker)"
  triggers:
    - "editorial calendar"
    - "content pipeline"
    - "content schedule"
    - "marketing"
    - "SEO"
    - "campaign"
    - "email sequence"
    - "outline post"
    - "pre-publish check"
    - "upload to wordpress"
    - "wordpress draft"
    - "post to X"
    - "tweet this"
    - "post tweet"
    - "read Bluesky"
    - "Bluesky feed"
    - "moderate Reddit"
    - "modqueue"
    - "headline"
    - "content strategy"
    - "audit links"
    - "audit images"
    - "batch edit posts"
    - "repurpose this"
    - "news collection"
  category: content
  pairs_with:
    - writing
    - workflow
---

# Content Skill

Six modes: **Calendar** (editorial pipeline), **Marketing** (SEO, campaigns,
email, competitive), **Publish** (outline, pre-publish, SEO, audits, WordPress),
**Social-X** (X/Twitter posts and threads), **Social-Bluesky** (public feed
reading), **Social-Reddit** (moderation). Classify the request and follow the
matching section.

## Mode Selection

| Mode | Signals |
|------|---------|
| **Calendar** | editorial calendar, content pipeline, ideas, scheduling, topics, headlines, news, series, repurpose |
| **Marketing** | SEO audit, campaign, email sequence, content strategy, competitive analysis, brand review, performance |
| **Publish** | outline post, pre-publish check, SEO optimize, batch edit, audit links, audit images, taxonomy, WordPress upload |
| **Social-X** | post to X, tweet, thread, X API |
| **Social-Bluesky** | read Bluesky, Bluesky feed, search Bluesky |
| **Social-Reddit** | moderate Reddit, modqueue, reports |

---

## Calendar Mode

Manage editorial content through 6 pipeline stages: Ideas, Outlined, Drafted,
Editing, Ready, Published. All state lives in a single `content-calendar.md`
file.

### Workflow

1. **READ** -- Load and parse `content-calendar.md`. Validate all sections exist. Do not trust memory; always re-read the actual file.
2. **EXECUTE** -- Perform the requested operation:
   - **View**: count per stage, upcoming scheduled (14 days), in-progress, recent publications (30 days). Flag stuck content (14+ days in one stage).
   - **Add idea**: check for duplicate titles (case-insensitive), append to Ideas.
   - **Move**: forward only through defined sequence (Ideas -> Outlined -> Drafted -> Editing -> Ready -> Published). Record `YYYY-MM-DD` timestamp at each transition.
   - **Schedule**: set date on Ready items. Date must be today or future.
   - **Archive**: move Published entries older than current month to Historical sections.
3. **WRITE** -- Persist changes, re-read file to verify.

### Calendar Sub-modes

| Request | Load |
|---------|------|
| Topic brainstorming, idea generation | `references/topic-brainstormer.md` |
| Headlines, title generation | `references/headlines.md` |
| Series planning, multi-part content | `references/series-planner.md` |
| Content repurposing, platform variants | `references/content-engine.md` |
| News collection, item qualification | `references/news-collection.md` |

---

## Marketing Mode

Seven sub-modes. Always load `references/llm-marketing-failure-modes.md`
alongside mode-specific references for detection heuristics against generic
copy, keyword stuffing, fabricated metrics.

| Sub-mode | Signals | Framework | Load |
|----------|---------|-----------|------|
| SEO_AUDIT | SEO audit, keywords, content gaps, technical SEO | RESEARCH -> AUDIT -> PRIORITIZE | `references/seo-audit.md` |
| CAMPAIGN | Campaign plan, product launch, lead gen, budget | BRIEF -> PLAN -> CALENDAR | `references/campaign-planning.md` |
| CONTENT | Content strategy, editorial calendar, funnel mapping | AUDIT -> PLAN -> DELIVER | `references/content-strategy.md` |
| EMAIL | Email sequence, drip campaign, nurture flow | SEQUENCE -> DRAFT -> AUTOMATE | `references/email-sequences.md` |
| COMPETITIVE | Competitor research, battlecard, positioning | RESEARCH -> COMPARE -> POSITION | `references/seo-audit.md` + `references/campaign-planning.md` |
| BRAND | Brand review, voice check, messaging consistency | AUDIT -> EVALUATE -> RECOMMEND | `references/content-strategy.md` |
| PERFORMANCE | Marketing report, campaign results, ROI | GATHER -> ANALYZE -> REPORT | `references/campaign-planning.md` |

### SEO Audit Quick Steps

1. Gather: URL/domain, audit type, target keywords, competitors (identify 2-3 via web search if not provided).
2. Keyword research: classify by intent (informational, navigational, commercial, transactional). Assess difficulty and opportunity.
3. On-page audit: title tags, meta descriptions, H1/H2, keyword usage, internal linking, image alt text, URL structure.
4. Technical: page speed, mobile, structured data, crawlability, HTTPS, Core Web Vitals.
5. Content gaps: competitor topic coverage, freshness, thin content, funnel gaps.
6. Output: executive summary, keyword table (15-25), issues table, content gap recommendations, technical checklist, competitor matrix, prioritized action plan.

---

## Publish Mode

Eight sub-modes covering the blog publishing pipeline.

| Sub-mode | Signals | Load |
|----------|---------|------|
| Outline | outline post, blog structure, article outline | `references/outline.md` |
| Pre-publish | pre-publish check, Hugo validation, frontmatter | `references/pre-publish.md` |
| SEO | check SEO, optimize SEO, meta description | `references/seo.md` |
| Batch-edit | batch edit posts, bulk frontmatter, find/replace | `references/batch-edit.md` |
| Link-audit | audit links, broken links, link health | `references/link-audit.md` |
| Image-audit | audit images, alt text, image accessibility | `references/image-audit.md` |
| Taxonomy | audit taxonomy, fix tags, merge categories | `references/taxonomy.md` |
| WordPress | upload to WordPress, create draft, edit post | `references/wordpress-upload.md` |

### Outline Quick Steps

1. Gather: topic, target audience, desired format, word count range, SEO target keyword.
2. Research: check existing coverage, identify gaps, gather supporting data.
3. Structure: working title, hook, thesis, 3-7 sections with sub-points, conclusion CTA.
4. Validate: logical flow, sufficient depth per section, SEO keyword placement plan.

### Pre-publish Quick Steps

1. Check: title, date, slug, description, tags, categories, featured image, author, draft=false.
2. Content: spell check, broken internal links, image paths, code blocks render, meta descriptions.
3. SEO: title tag (<60 chars), meta description (120-160 chars), keyword in H1 and first paragraph.

---

## Social-X Mode

OAuth-authenticated X/Twitter posting via `x-api-poster.py`. 4-phase pipeline
with confirmation gate.

### Workflow

1. **VALIDATE** -- Check credentials: `python3 $HOME/.claude/scripts/x-api-poster.py post --dry-run --text "ping"`. Requires `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`, `X_BEARER_TOKEN`. Read-only ops need only `X_BEARER_TOKEN`.
2. **CONFIRM** -- Show user the exact text. For threads: `python3 $HOME/.claude/scripts/x-api-poster.py thread --dry-run --texts "part 1" "part 2"`. Enforce 280-char limit per tweet. Wait for explicit user confirmation.
3. **POST** -- Execute with `--confirmed` flag: `python3 $HOME/.claude/scripts/x-api-poster.py post --confirmed --text "text"`. For media: `--media /path/to/image.png`.
4. **VERIFY** -- Report tweet URL and rate limit status.

---

## Social-Bluesky Mode

Read public Bluesky feeds via AT Protocol. No auth required.

### Commands

```bash
# Fetch recent posts
python3 ~/.claude/scripts/bluesky_reader.py feed --handle HANDLE --limit 20

# Search posts
python3 ~/.claude/scripts/bluesky_reader.py search --handle HANDLE --query "terms"

# JSON output for pipelines
python3 ~/.claude/scripts/bluesky_reader.py feed --handle HANDLE --json
```

Endpoint: `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed`. Limit: 1-100 posts. Search is local keyword filter (all words must appear, case-insensitive).

---

## Social-Reddit Mode

Reddit moderation via PRAW. Three modes:

| Mode | Command | Behavior |
|------|---------|----------|
| Interactive | invoke directly | Fetch, classify, present, confirm actions |
| Auto | `/loop 10m /reddit-moderate --auto` | Auto-action high-confidence, flag rest |
| Dry-run | `--dry-run` | Show recommendations without acting |

### Workflow

1. **FETCH** -- `python3 scripts/reddit-moderate/reddit-mod.py queue --json --limit 25 | python3 scripts/reddit-moderate/reddit-mod.py classify`. Loads subreddit context from `reddit-data/{subreddit}/`.
2. **CLASSIFY** -- Fill `classification`, `confidence`, and `reasoning` for each item using the assembled prompt.
3. **PRESENT** -- Group by confidence tier (high/medium/low). Show: title, author, report reason, classification, action, reasoning.
4. **ACT** -- Execute confirmed actions: `python3 scripts/reddit-moderate/reddit-mod.py action --item-id ID --action approve|remove|spam`.

---

## Deep References

Load when the task needs detailed patterns, specifications, or examples.

### Calendar

| Signal | Reference |
|--------|-----------|
| Pipeline stage definitions, transitions | `references/pipeline-stages.md` |
| Calendar file format, sections | `references/calendar-format.md` |
| Operation execution details | `references/operations.md` |
| Pipeline health, velocity metrics | `references/metrics.md` |
| Calendar error recovery | `references/error-handling.md` |

### Marketing

| Signal | Reference |
|--------|-----------|
| SEO audit methodology | `references/seo-audit.md` |
| Campaign planning, budget | `references/campaign-planning.md` |
| Content strategy, frameworks | `references/content-strategy.md` |
| Email sequences, drip campaigns | `references/email-sequences.md` |
| LLM marketing failure modes | `references/llm-marketing-failure-modes.md` |

### Publish

| Signal | Reference |
|--------|-----------|
| Blog outline methodology | `references/outline.md` |
| Pre-publish Hugo checklist | `references/pre-publish.md` |
| Post-level SEO | `references/seo.md` |
| Batch editing methodology | `references/batch-edit.md` |
| Link health scanning | `references/link-audit.md` |
| Image audit, alt text | `references/image-audit.md` |
| Taxonomy management | `references/taxonomy.md` |
| WordPress API upload | `references/wordpress-upload.md` |

### Social

| Signal | Reference |
|--------|-----------|
| X API details | `references/x-api.md` |
| AT Protocol endpoints | `references/at-protocol-api.md` |
| AT Protocol troubleshooting | `references/at-protocol-preferred-patterns.md` |
| Reddit classification categories | `references/classification-prompt.md` |
| Reddit script commands | `references/script-commands.md` |

## Scripts

| Domain | Script | Location |
|--------|--------|----------|
| Reddit moderation | `reddit-mod.py` | `scripts/reddit-moderate/reddit-mod.py` |
| Link scanning | `link_scanner.py` | `scripts/publish/link_scanner.py` |
| PageSpeed | `pagespeed.py` | `scripts/publish/pagespeed.py` |
| WordPress upload | `wordpress-upload.py` | `scripts/publish/wordpress-upload.py` |
| WordPress edit | `wordpress-edit-post.py` | `scripts/publish/wordpress-edit-post.py` |
| WordPress media | `wordpress-media-upload.py` | `scripts/publish/wordpress-media-upload.py` |
| X API poster | `x-api-poster.py` | `$HOME/.claude/scripts/x-api-poster.py` |
| Bluesky reader | `bluesky_reader.py` | `$HOME/.claude/scripts/bluesky_reader.py` |
