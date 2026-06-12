# Freshness Forensics

Methods for Phase 3: establish when a story first became public, detect
reposts, pick canonical coverage, and separate duplicates from genuine
developments.

## First-public time vs page date

The date printed on a page answers "when was this page generated", not "when
did this story break". A syndicated repost, a refreshed CMS page, or an
aggregator wrapper can carry today's date on week-old news.

Establish first-public time from, in order of trust:

1. Article metadata (`article:published_time`, JSON-LD `datePublished`) on the
   originating outlet's page.
2. The earliest `published_at` across all collected items covering the same
   story.
3. In-text anchors ("announced Tuesday", "in a filing dated …") tied to a
   known date.

Verdict standard: two independent sources or verdict "unclear". Independent
means separately reported — two copies of the same wire story count as one
source. Conservative default: unclear over guessed, because an "unclear"
passes downstream for human judgment while a wrong "fresh" ships stale news.

| Verdict | Condition |
|---------|-----------|
| `fresh` | Two independent sources put first-public time inside the freshness window |
| `stale` | Two independent sources put first-public time outside the window, or the page repackages older coverage |
| `unclear` | Fewer than two independent sources, conflicting evidence, or no usable timestamp |

## Syndication and aggregator detection

Signals that a page is a repost rather than original coverage:

- Wire credit in byline or footer ("Reuters", "AP", "— Staff and agencies").
- `rel=canonical` or `og:url` pointing at a different domain.
- Body text identical or near-identical to an earlier item in the feed.
- Aggregator framing: a paragraph of summary plus "read more at" link.
- Outlet that publishes across many unrelated beats with no original bylines.

A repost inherits the original's first-public time, whatever date the repost
page shows.

## Canonical-coverage selection

When several items cover one story, deliver one canonical item and link the
rest via `duplicates_of`. Pick the canonical by, in order:

1. The originating outlet (the one others credit or canonicalize to).
2. The earliest extracted `published_at` among originals.
3. The most complete five-fact record at equal age.

## Same-story vs new-development rubric

| Question | Same story (consolidate) | New development (keep separate) |
|----------|--------------------------|---------------------------------|
| New named facts (figures, names, dates)? | No — restates known facts | Yes — adds material facts |
| New primary source (filing, statement, data)? | No | Yes |
| Event advanced (ruling issued, deal closed, response published)? | No | Yes |
| Only the framing or outlet changed? | Yes — consolidate | — |

Two or more "new development" answers → separate item, verdict on its own
merits. Otherwise consolidate into the canonical with `duplicates_of`.
