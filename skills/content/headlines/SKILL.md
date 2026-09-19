---
name: headlines
promoted_to: content-calendar
description: "Generate headlines, titles, and subject lines: charge, volume, tighten."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "headline"
    - "headlines"
    - "article title"
    - "title options"
    - "subject line"
    - "better title"
  category: content-creation
  pairs_with:
    - writing
    - content
---

# Headlines

Generate headlines, article titles, social posts, and email subject lines from a brief or draft. Four phases: find the charge, generate volume across named moves, tighten survivors, output per format. Core rule: **volume over polish** -- breadth beats optimization because word-level features predict winners weakly.

## Phase 1: FIND THE CHARGE

Identify the single most compelling tension or stake in the material.

1. Read the brief, draft, or topic statement in full.
2. List every tension candidate: surprise, reversal, cost, conflict, a number that changes the picture, a stake the reader holds.
3. Pick ONE -- the charge. Write it as one sentence naming who is affected and what is at stake.
4. Test: would a reader who saw only this sentence want the rest? A topic label ("Kubernetes networking") fails; a live tension ("DNS resolved yesterday, fails today, nothing changed") passes.

**Gate**: Charge is one sentence, names a specific tension, is true to source. A weak charge produces 20 weak headlines.

## Phase 2: GENERATE VOLUME

Produce 15-25 candidate headlines spread across these ten named moves. Write fast; judge later.

### The Ten Headline Moves

| Move | Reflex | Example |
|------|--------|---------|
| **Curiosity gap** | Opens a question only reading can close | "The One-Line Nginx Default That Took Our API Down" |
| **Specificity** | Carries the concrete detail into the headline | "CoreDNS Returns NXDOMAIN for Internal Services After Upgrading to 1.31" |
| **Stakes** | Names what the reader loses or gains | "Your Postgres Backups May Be Silently Unrestorable" |
| **Contrast** | Two true things that should not coexist | "Local Build Passes, Cloudflare Deploy Fails -- Same Commit" |
| **Question** | Asks what the reader already wonders | "Is Your Standup Meeting Just a Status Email With Legs?" |
| **How-to** | Promises a capability, named precisely | "How to Cut Go CLI Startup From 400ms to 40ms" |
| **Number** | Count or measurement as the spine | "Three Config Lines That Halved Our CI Bill" |
| **Voice-of-reader** | Phrased in the reader's own words | "I Rotated the API Key and Production Still Worked. That's the Problem." |
| **News peg** | Anchored to a current event | "What the AWS Outage Reveals About Your Single-Region Bet" |
| **Negative space** | Leads with what is absent or refused | "The Test Suite Had No Test for the Thing That Broke" |

Rules:
1. Cover at least 6 of the 10 moves. Tag each candidate with its move.
2. Keep every candidate anchored to the Phase 1 charge.
3. Pull concrete material from the brief: numbers, names, error messages, dates.

**Gate**: 15-25 candidates, each tagged, at least 6 moves represented. Fewer than 15 means the charge is under-mined -- return to the brief.

## Phase 3: TIGHTEN

Select and sharpen 3-5 survivors.

1. Score every candidate 1-5 on: specificity, tension, accuracy to the brief. Sum the three.
2. Keep the top 3-5. Require move diversity -- two candidates from the same move compete for the same reader reflex; keep the stronger one.
3. Tighten each survivor:
   - Cut filler; front-load the charge into the first 3-4 words.
   - Replace any vague noun with the concrete one from the brief.
   - Verify every claim against the brief. The headline promises only what the content delivers.
4. Drop any survivor that needs a hedge to stay accurate. Promote the next by score.

**Gate**: 3-5 survivors, each accurate, each from a distinct move where possible.

## Phase 4: OUTPUT PER FORMAT

Adapt survivors to the formats the task needs.

| Format | Constraint | Adjustment |
|--------|-----------|------------|
| Article title | ~60-70 chars; sentence case | Full charge; specificity over wordplay |
| Social post | Platform length; standalone | Add the stake or number; end with pull, not summary |
| Email subject line | ~30-50 chars | Front-load the charge; cut articles and qualifiers first |

Per-platform specs from content-engine (`references/platform-specs.md`) win on length when both apply.

Output format:

```markdown
## Headline Options

**Charge**: [one-sentence charge]

### Article titles
1. "[title]" -- [move]
2. ...

### Social posts
1. "[post]"

### Subject lines
1. "[subject]"

**Recommendation**: [pick one, one sentence why]
```

**Gate**: Each requested format has 2+ options. Recommendation given with reasoning.

## Integration

- **voice-writer**: when voice-writer's hook scores below 8, the HOOK-GATE agent may run Phases 1-3 here against the article body to surface the concrete detail the opening should lead with.
- **content-engine**: supplies titles and subject lines for pipeline output; content-engine owns per-platform format specs.
- **Standalone**: usable directly on any brief, draft, or topic.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Brief has no tension | Input is a topic label or flat release notes | Ask for the one fact that surprised the author, the cost of the problem, or what changed. If none exists, produce plain utilitarian titles. |
| All candidates sound the same | Generation stayed in 1-2 moves | Walk the move catalog in order; force one candidate per unused move. |
| Accurate headlines feel flat | Charge is weak, not the wording | Return to Phase 1. Find a sharper tension or report that the brief needs a stronger finding. |
