---
name: growth-strategy
description: "CMO-level growth decisions: content strategy, audience development, channel selection, SEO, community building, brand positioning."
version: 1.0.0
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
    - "grow audience"
    - "content strategy"
    - "marketing"
    - "SEO strategy"
    - "growth"
    - "brand"
    - "positioning"
    - "community building"
    - "social media strategy"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# Growth Strategy Skill

## Overview

CMO-level decision support for audience growth, content strategy, channel selection, SEO strategy, community building, and brand positioning. Designed for independent creators and small teams who need to make smart growth decisions without a marketing department.

**Scope**: Content strategy, audience growth, channel prioritization, SEO approach, community building, brand positioning, publication strategy. Do NOT use for technical architecture (use build-vs-buy or decision-helper), business strategy beyond marketing (use strategic-decision), or project feasibility (use project-evaluation).

---

## Instructions

### Phase 1: ASSESS

**Goal**: Understand the current state before recommending growth actions.

**Core Constraints**:
- **Measure before prescribing** -- generic advice ("post consistently!") is useless without understanding what exists and what is working
- **One publication, one voice** -- growth strategy must respect the established voice profile; tactics that require abandoning voice authenticity are off-limits
- **Creator capacity is the binding constraint** -- a solo operator cannot execute a 15-channel strategy; recommend what one person can sustain

**Step 1: Audit the current state**

```markdown
## Current State Audit

### Assets
- Publications: [list sites, blogs, newsletters]
- Content volume: [posts/month, total archive]
- Existing audience: [subscribers, followers, traffic estimates]
- Voice profiles: [established voices, if any]

### Channels
- Active: [where content is published/shared today]
- Dormant: [channels with accounts but no activity]
- Absent: [channels with no presence]

### Performance (if data available)
- Top-performing content: [which pieces get the most engagement]
- Traffic sources: [where does audience come from]
- Conversion patterns: [what turns readers into subscribers/followers]
```

**Step 2: Identify the growth constraint**

Every growth system has one binding constraint. Identify it before proposing tactics:

| Constraint | Signal | Implication |
|------------|--------|-------------|
| **Discovery** | Good content exists but nobody finds it | Focus on distribution and SEO |
| **Content** | Audience exists but there is nothing new to read | Focus on content production cadence |
| **Conversion** | Traffic exists but nobody subscribes/returns | Focus on calls-to-action and retention |
| **Retention** | People subscribe but never come back | Focus on content quality and engagement |
| **Capacity** | The creator is maxed out | Focus on leverage (repurposing, automation) |

**Gate**: Current state audited. Binding constraint identified.

### Phase 2: STRATEGIZE

**Goal**: Design a growth approach that matches the creator's capacity and binding constraint.

**Core Constraints**:
- **Solve the constraint, not everything** -- a strategy that addresses discovery, content, conversion, and retention simultaneously will execute none of them well
- **Compound over campaign** -- prefer strategies that compound (SEO, evergreen content, community) over one-shot campaigns (viral posts, paid ads)
- **90-day horizons** -- growth strategies should be evaluated at 90 days, not 90 minutes; set realistic timelines

**Step 1: Select the strategic approach**

Based on the binding constraint, recommend one primary approach:

| Constraint | Primary Approach |
|------------|-----------------|
| Discovery | SEO + content distribution strategy |
| Content | Content calendar with sustainable cadence |
| Conversion | Landing page optimization + lead magnets |
| Retention | Email sequences + community building |
| Capacity | Content repurposing pipeline + selective automation |

**Step 2: Design the channel strategy**

Load references based on the approach:

| Signal | Reference to Load | Content |
|--------|-------------------|---------|
| Content planning, cadence design, editorial calendar | `references/content-frameworks.md` | Content frameworks, cadence templates, editorial planning |
| Audience analysis, growth modeling, community patterns | `references/audience-growth.md` | Audience segmentation, growth models, community building patterns |
| SEO strategy, keyword planning, technical SEO | `references/seo-patterns.md` | SEO frameworks, keyword research methods, technical SEO checklists |

Recommend a maximum of 3 active channels. For each:

```markdown
## Channel: [name]

### Why this channel
- [How it addresses the binding constraint]
- [Why this audience is here]

### Content format
- [What type of content works on this channel]
- [Cadence: how often]

### Success metric
- [One measurable outcome at 90 days]

### Effort estimate
- [Hours per week to sustain]
```

**Gate**: Strategy selected. Maximum 3 channels chosen. Effort estimated against capacity.

### Phase 3: PLAN

**Goal**: Convert strategy into a 90-day executable plan with checkpoints.

**Step 1: Define the 90-day outcome**

```markdown
## 90-Day Growth Plan

### Objective
[One sentence: what changes in 90 days if this plan works]

### Primary metric
[The one number that matters most -- e.g., "organic traffic from 500 to 2000 monthly visits"]

### Secondary metrics
[2-3 supporting indicators -- e.g., "email subscribers", "average time on page"]
```

**Step 2: Break into 30-day phases**

```markdown
### Days 1-30: Foundation
- [Setup tasks: create accounts, establish cadence, build first batch of content]
- Checkpoint: [What should be true at day 30?]

### Days 31-60: Execution
- [Sustain cadence, optimize based on early data, double down on what works]
- Checkpoint: [What should be true at day 60?]

### Days 61-90: Evaluate
- [Full measurement against primary metric, decide to continue/pivot/stop]
- Decision point: [Continue this strategy, adjust, or try a different approach?]
```

**Step 3: Define the abandon criteria**

Every growth strategy needs explicit failure conditions so the creator does not throw good time after bad:

- **Abandon if**: [specific condition -- e.g., "zero organic traffic growth after 60 days of consistent publishing"]
- **Pivot if**: [partial success condition -- e.g., "traffic grows but from unexpected keyword cluster -- follow that signal"]
- **Double down if**: [success condition -- e.g., "primary metric hits 50% of target by day 45"]

**Gate**: 90-day plan with checkpoints. Primary metric defined. Abandon criteria explicit.

---

## Error Handling

### Error: "No data to audit"
**Cause**: User is starting from scratch with no existing content or audience
**Solution**: Skip the audit. Focus Phase 2 on "Day Zero" strategy: pick one channel, one content format, and commit to a 30-day test before expanding. The audit comes at day 30.

### Error: "Too many channels"
**Cause**: User wants to be on every platform simultaneously
**Solution**: Apply the capacity constraint. Calculate hours per week for each channel, sum them, and compare against available time. Something must go. Help the user rank channels by constraint-fit and cut the rest.

### Error: "Vanity metrics"
**Cause**: User optimizes for followers/likes instead of meaningful outcomes
**Solution**: Redirect to the "one metric that matters" framework. Ask: "What action do you want your audience to take?" (subscribe, buy, share, hire you). That action is the metric. Followers who never take the action are not growth.

### Error: "Voice conflict"
**Cause**: Growth tactic conflicts with established voice profile
**Solution**: The voice wins. If a growth tactic requires writing clickbait and the voice profile is analytical, the tactic is wrong for this creator. Find growth approaches that amplify the existing voice rather than fighting it.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/content-frameworks.md` | Content planning, cadence, editorial calendar | Content strategy frameworks, cadence templates, editorial planning models |
| `references/audience-growth.md` | Audience analysis, growth modeling, community building | Audience segmentation, growth models, retention patterns, community playbooks |
| `references/seo-patterns.md` | SEO strategy, keyword planning, technical optimization | SEO frameworks, keyword research methods, technical SEO checklists |
