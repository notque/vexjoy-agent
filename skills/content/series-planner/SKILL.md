---
name: series-planner
promoted_to: content
description: "Plan a 3–7 part Hugo content series whose parts retain standalone value."
user-invocable: false
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
command: /series
routing:
  triggers: ["plan series", "multi-part content", "content series", "article series", "content arc"]
  category: content-creation
  pairs_with: [content]
---

# Series planner

Use a series only when the topic has at least three non-filler divisions. Keep
the plan to 3–7 parts; otherwise recommend one post or multiple narrower series.
Every part must deliver a complete insight or working result to a reader who
lands there directly. Merge or add local context when a part requires earlier
reading, ends mid-implementation, or defers the actual answer.

For each part provide title, one-sentence scope, standalone payoff, and adjacent
links. Choose cadence from the user's production capacity and timeliness rather
than a universal default.

For this repository's Hugo implementation, use front matter:

```yaml
series: "Series Title"
series_part: 1
```

Use a landing page at `content/series/<series-slug>/_index.md` only when requested.
Each post's navigation names its part number, previous/next part where present,
and `/series/<series-slug>/`. Do not emit shortcodes or partials unless they
exist in the target site.
