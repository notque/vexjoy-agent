---
name: news-collection
promoted_to: content
description: "Collect, filter, and freshness-qualify news items."
user-invocable: false
routing:
  triggers:
    - "news collection"
    - "collect news"
    - "qualify news items"
    - "news triage"
    - "filter news feed"
    - "check news freshness"
  not_for: "general research reports — that is research-pipeline. Pick this when the input is a stream of news items to qualify for a content pipeline."
  pairs_with:
    - research
  complexity: Medium
  category: research
---

# News Collection

Gather news items on a topic, filter junk cheaply, verify freshness, and emit
qualified items under an evidence contract. Pipeline-shaped: four phases, a
gate between each. Content pipelines consume the JSON artifact; pair with
fact-check to verify what this skill qualifies.

## Instructions

### Phase 1: COLLECT

**Goal**: gather candidate items from available sources (feeds, search
results, provided fixtures). Every item carries the five-fact evidence
contract: **title, url, outlet, author, published_at**.

Rule (verbatim from the design): publish times are extracted (article
metadata), never guessed; missing timestamp → recorded as unknown, confidence
lowered and disclosed. A guessed timestamp poisons every downstream freshness
verdict; an honest `"published_at": null` keeps the item usable with known
uncertainty.

Record each item as one JSON object per the item schema below. Fill
`evidence_notes` with where each fact came from (meta tag, byline, JSON-LD,
sitemap).

Distinguish outcomes: zero items because sources were unreachable is a
collection failure (report it, stop); zero items from reachable sources is a
valid empty feed (deliver an empty artifact with counts of zero).

Gate: every collected item has all five fields present — value or explicit
`null` with a `confidence` downgrade and a disclosure note. Items with silent
gaps stay in COLLECT until the gap is recorded.

### Phase 2: COARSE FILTER

**Goal**: cheap, high-recall pass over collected items. Three verdicts:
`keep` / `monitor_only` / `reject`, each with a reason code (see
Coarse Filter below).

Rule (verbatim from the design): high-magnitude stories are downgraded to
monitor_only at most, never rejected — a false keep is cheap, a silent drop is
expensive. A keep costs one extra freshness check; a wrongly dropped major
story costs the whole pipeline its value.

This phase runs on a cheap model when dispatched -- it needs recall, not
judgment depth. Give the dispatched model: topic, verdict/code tables,
asymmetry rule, and items' five facts plus a text excerpt.

Gate: every item has exactly one verdict and one reason code. `reject`
verdicts on items that look high-magnitude get re-checked once before the
phase closes.

### Phase 3: FRESHNESS CHECK

**Goal**: for each `keep` and `monitor_only` item, establish when the story
first became public and whether this page is the original coverage.

- First-public time vs page date -- a page can carry today's date on old news.
- Syndication and aggregator reposts detected; select the canonical coverage.
- Same-story vs new-development rubric -- consolidate duplicates, keep genuine
  developments. See Freshness Forensics below.

Rule (verbatim from the design): two independent sources or verdict "unclear".
Conservative default: unclear over guessed. An "unclear" verdict is
recoverable downstream; a confidently wrong "fresh" verdict ships stale news.

Gate: every surviving item carries `freshness: fresh | stale | unclear`, a
`first_public_estimate` (or `null`), and the count of sources backing the
verdict. Duplicate clusters are consolidated to one canonical item with
`duplicates_of` links.

### Phase 4: DELIVER

**Goal**: emit qualified items as a structured JSON artifact (see Artifact
Schema below) plus a summary table. Every verdict state
appears in the artifact — `monitor_only`, `unclear`, and `reject` items ship
with their verdicts rather than vanishing, so consumers see the full triage.

Gate (deterministic phase checkpoint — emit this table before delivering the
artifact; delivery without it is incomplete):

| Verdict | Count |
|---------|-------|
| keep | n |
| monitor_only | n |
| reject | n |
| unclear (freshness) | n |
| duplicates consolidated | n |

The counts make silent drops visible: collected total must equal
keep + monitor_only + reject. If it does not, return to the phase that lost
items.

## Error Handling

**No items collected**
- Cause: sources unreachable, or feed genuinely empty.
- Solution: unreachable sources → report collection failure and stop;
  reachable but empty → deliver an empty artifact with zero counts. The two
  outcomes stay distinct so an outage is not read as a quiet news day.

**No timestamp found anywhere for an item**
- Cause: page has no metadata, byline date, or sitemap entry.
- Solution: set `published_at: null`, `confidence: low`, disclose in
  `evidence_notes`; freshness verdict for that item is `unclear`.

**Two sources disagree on first-public time**
- Cause: syndication chain or republished update.
- Solution: apply canonical-coverage selection
  (`references/freshness-forensics.md`); if still split, verdict `unclear`.

**Item count mismatch at DELIVER**
- Cause: an item was dropped without a verdict.
- Solution: diff item ids against the COLLECT record; assign the missing item
  a verdict with reason code.

---

## Evidence Contract

Every collected item carries five facts:

| Fact | Type | Missing value handling |
|------|------|------------------------|
| `title` | string | Empty string only if page truly has none; note in `evidence_notes` |
| `url` | string | Required -- no URL means unverifiable; exclude from artifact |
| `outlet` | string | Derive from domain when no masthead found; note derivation |
| `author` | string or null | `null` when no byline; note where you looked |
| `published_at` | ISO 8601 or null | Extracted from metadata, never guessed. `null` when absent; lower `confidence`, disclose |

Confidence: `high` (all five extracted), `medium` (one derived or weak), `low` (`published_at` null or 2+ derived).

### Item Schema

```json
{
  "id": "string", "title": "string", "url": "string",
  "outlet": "string", "author": "string|null",
  "published_at": "ISO 8601|null", "confidence": "high|medium|low",
  "evidence_notes": "string", "verdict": "keep|monitor_only|reject",
  "reason_code": "string", "freshness": "fresh|stale|unclear|null",
  "first_public_estimate": "ISO 8601|null",
  "freshness_sources": "integer", "duplicates_of": "string id|null"
}
```

### Artifact Schema

```json
{
  "schema_version": "1.0", "topic": "string",
  "collected_at": "ISO 8601",
  "counts": {"collected":0,"keep":0,"monitor_only":0,"reject":0,"unclear_freshness":0,"duplicates_consolidated":0},
  "items": []
}
```

Conservation rule: `collected == keep + monitor_only + reject`.

---

## Coarse Filter

| Verdict | Meaning | Goes to freshness check |
|---------|---------|-------------------------|
| `keep` | On-topic, substantive, plausibly fresh | Yes |
| `monitor_only` | Worth watching: off-topic but high-magnitude, thin, or uncertain | Yes |
| `reject` | Junk: spam, ads, dead pages, clearly irrelevant | No |

Asymmetry rule: high-magnitude stories downgrade to `monitor_only` at most, never `reject`. A false keep is cheap; a silent drop is expensive.

### Reason Codes

| Code | Pairs with | Meaning |
|------|-----------|---------|
| `RC-ONTOPIC` | keep | Directly on topic |
| `RC-DEV` | keep | New development of known story |
| `RC-OFFTOPIC-BIG` | monitor_only | Off-topic but high-magnitude |
| `RC-THIN` | monitor_only | On-topic but little substance |
| `RC-UNCERTAIN` | monitor_only | Relevance unclear |
| `RC-SPAM` | reject | Promotional, SEO bait |
| `RC-IRRELEVANT` | reject | Outside topic, low magnitude |
| `RC-NOCONTENT` | reject | Dead link, paywall stub, empty page |

---

## Freshness Forensics

### First-public time vs page date

A syndicated repost or refreshed CMS page can carry today's date on old news. Establish first-public time from (in trust order):

1. Article metadata (`article:published_time`, JSON-LD `datePublished`) on the originating outlet's page.
2. Earliest `published_at` across collected items covering the same story.
3. In-text anchors ("announced Tuesday") tied to a known date.

Two independent sources or verdict `unclear`. Independent means separately reported -- two copies of the same wire story count as one.

| Verdict | Condition |
|---------|-----------|
| `fresh` | Two sources put first-public time inside the freshness window |
| `stale` | Two sources put it outside, or page repackages older coverage |
| `unclear` | <2 sources, conflicting evidence, or no usable timestamp |

### Syndication detection

Signals of a repost: wire credit in byline, `rel=canonical` pointing elsewhere, body near-identical to an earlier item, aggregator framing ("read more at"), outlet with no original bylines across beats. A repost inherits the original's first-public time.

### Canonical-coverage selection

When several items cover one story, deliver one canonical item, link the rest via `duplicates_of`. Pick canonical by: originating outlet > earliest `published_at` > most complete five-fact record.

### Same-story vs new-development

| Question | Same story (consolidate) | New development (keep separate) |
|----------|--------------------------|---------------------------------|
| New named facts? | No | Yes |
| New primary source? | No | Yes |
| Event advanced? | No | Yes |
| Only framing/outlet changed? | Yes | -- |

Two+ "new development" answers = separate item.
