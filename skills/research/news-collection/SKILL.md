---
name: news-collection
promoted_to: content
description: "Compatibility contract for evidence-preserving news triage; new work routes through content."
user-invocable: false
routing:
  triggers: [news collection, collect news, qualify news items, news triage, filter news feed, check news freshness]
  not_for: "general research reports"
  pairs_with: [research]
  complexity: Medium
  category: research
---

# News Collection

This workflow is promoted to `content`; retain this contract for existing pipeline consumers and eval fixtures.

Every item carries `id`, `title`, `url`, `outlet`, `author`, `published_at`, `confidence`, `evidence_notes`, triage verdict/reason, freshness evidence, and duplicate linkage. Extract publication time from source metadata; represent absence as `null` with low confidence rather than guessing. An unreachable source is a collection failure; a reachable empty feed is a valid empty result.

Triage is `keep | monitor_only | reject`. High-magnitude uncertain/off-topic stories can become `monitor_only`, not `reject`, because silent drops cost more than an extra freshness check. Freshness is `fresh | stale | unclear`; require two independent origins for fresh/stale, since syndicated copies are one source. Prefer `unclear` to an inferred date. Consolidate the same story to originating outlet, then earliest publication, then best evidence record; keep a genuine new development separate.

Deliver every verdict, including rejected and unclear items. Enforce conservation:

```text
collected == keep + monitor_only + reject
```

Report counts for all verdicts, unclear freshness, and consolidated duplicates. Pair with fact-check before publishing claims.
