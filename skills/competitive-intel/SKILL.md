---
name: competitive-intel
description: "Cross-role competitive intelligence: market landscape, competitor analysis, positioning, differentiation strategy."
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
    - "competitor"
    - "competition"
    - "market landscape"
    - "competitive analysis"
    - "differentiation"
    - "positioning against"
    - "market share"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# Competitive Intel Skill

## Overview

Cross-role competitive intelligence for market landscape analysis, competitor monitoring, positioning strategy, and differentiation. Transforms "who else is doing this?" into structured intelligence that drives decisions.

**Scope**: Competitor analysis, market landscape mapping, positioning strategy, differentiation opportunities, competitive response planning. Do NOT use for internal business strategy (use strategic-decision), technology stack choices (use build-vs-buy), or audience/content growth (use growth-strategy).

---

## Instructions

### Phase 1: MAP

**Goal**: Build a structured picture of the competitive landscape before analyzing individual competitors.

**Core Constraints**:
- **Map the landscape before zooming in** -- analyzing one competitor in isolation misses positioning gaps and market structure
- **Distinguish direct from indirect competition** -- a blog post and a YouTube video can be competitors if they answer the same question for the same audience
- **Observe behavior, not claims** -- competitor marketing copy describes aspirations; their actual product, pricing, and content reveals strategy

**Step 1: Define the competitive arena**

```markdown
## Competitive Arena

### What we compete on
- [The specific value proposition or capability -- e.g., "technical blog content about Kubernetes for SAP engineers"]

### Who we serve
- [Target audience segment -- be specific]

### Where we compete
- [Channels, platforms, markets where competition happens]
```

**Step 2: Identify competitors by tier**

| Tier | Definition | Analysis Depth |
|------|-----------|----------------|
| **Direct** | Same audience, same problem, same format | Full analysis (Phase 2) |
| **Adjacent** | Same audience, different approach to the same problem | Positioning analysis only |
| **Aspirational** | Where you want to be; larger players in the space | Strategy extraction only |
| **Emerging** | New entrants that could become direct competitors | Watch list only |

For each competitor identified:

```markdown
## Competitor: [name]

- Tier: [direct / adjacent / aspirational / emerging]
- What they offer: [one sentence]
- Their audience: [who they serve]
- Their strength: [what they do better than anyone]
- Their weakness: [where they fall short]
```

**Gate**: Arena defined. Competitors identified and tiered. At least 2 direct competitors mapped.

### Phase 2: ANALYZE

**Goal**: Extract actionable intelligence from competitor behavior, not surface impressions.

**Core Constraints**:
- **Focus on what they DO, not what they SAY** -- pricing, feature launches, content cadence, and hiring patterns reveal real strategy; press releases reveal desired perception
- **Analyze for gaps, not imitation** -- the goal is to find what competitors miss or do poorly, not to copy what they do well
- **Time-bound the analysis** -- competitive intelligence stales fast; focus on the last 6-12 months of activity

**Step 1: Analyze direct competitors**

For each direct competitor, evaluate:

```markdown
## Deep Analysis: [competitor name]

### Product/Content Analysis
- Core offering: [what exactly do they provide?]
- Quality signal: [evidence of quality -- user reviews, engagement, technical depth]
- Update cadence: [how often do they ship/publish? is it accelerating or stalling?]
- Pricing: [free / freemium / paid -- and what does each tier include?]

### Audience Analysis
- Who engages: [evidence from comments, shares, community activity]
- Community health: [active, growing, stagnant, or declining?]
- Sentiment: [what do users praise and complain about?]

### Strategy Signals
- Recent moves: [product launches, pivots, partnerships, hires in last 6 months]
- Content themes: [what topics are they investing in? what did they stop covering?]
- Growth approach: [SEO, social, community, paid, partnerships?]
```

Load references based on analysis needs:

| Signal | Reference to Load | Content |
|--------|-------------------|---------|
| Landscape mapping, competitor profiling, feature comparison | `references/competitive-mapping.md` | Landscape map templates, feature matrices, competitor activity tracker |
| Positioning strategy, differentiation scoring, win/loss analysis | `references/market-positioning.md` | Positioning maps, differentiation scoring, win/loss frameworks |

**Gate**: Direct competitors analyzed. Gaps and weaknesses identified. Strategy signals documented.

### Phase 3: POSITION

**Goal**: Convert competitive intelligence into a positioning strategy that creates defensible differentiation.

**Step 1: Build the positioning map**

Plot competitors on two dimensions that matter most for this market. Choose dimensions where you can differentiate -- not dimensions where everyone clusters together.

Common useful axes:
- Technical depth vs. accessibility
- Breadth vs. specialization
- Free vs. premium
- Community-driven vs. authority-driven
- Established vs. emerging

```markdown
## Positioning Map

Axes: [dimension 1] vs. [dimension 2]

| Player | [Dimension 1] | [Dimension 2] |
|--------|---------------|---------------|
| Us     | [position]    | [position]    |
| Comp A | [position]    | [position]    |
| Comp B | [position]    | [position]    |

### White space
[Where on this map is underserved? Which quadrant has demand but no strong player?]
```

**Step 2: Define the differentiation strategy**

```markdown
## Differentiation Strategy

### Our positioning statement
For [target audience] who need [specific need], [our offering] is the [category] that [key differentiator] unlike [primary competitor] which [competitor limitation].

### Defensible advantages
- [What we do that is hard to copy -- authentic voice, unique expertise, community trust]

### Vulnerable advantages
- [What we do well but competitors could replicate -- features, content topics, pricing]

### Strategic gaps to exploit
- [Specific competitor weaknesses we can address]
```

**Step 3: Define the monitoring cadence**

Competitive intelligence is perishable. Set a review cadence:

- **Monthly**: Check direct competitor activity (new content, features, pricing changes)
- **Quarterly**: Full landscape review (new entrants, departures, tier changes)
- **Trigger-based**: Re-analyze when a competitor makes a major move (funding, pivot, acquisition)

**Gate**: Positioning map built. Differentiation strategy defined. Monitoring cadence set.

---

## Error Handling

### Error: "No visible competitors"
**Cause**: User operates in a niche with no obvious direct competition
**Solution**: Expand the definition. Look for adjacent competitors (different format, same audience) and aspirational competitors (larger players in a broader version of the space). If truly no competition exists, question whether there is demand.

### Error: "Too many competitors to analyze"
**Cause**: User identifies 10+ competitors across all tiers
**Solution**: Tier ruthlessly. Full analysis only on direct competitors (3 max). Adjacent and aspirational get one-paragraph summaries. Emerging go on a watch list with no analysis.

### Error: "Competitor obsession"
**Cause**: User spends more time analyzing competitors than building their own product
**Solution**: Set a time box. Competitive analysis should take hours, not weeks. The output is a positioning strategy, not an encyclopedia. Once positioning is clear, execute -- the next analysis happens at the quarterly cadence.

### Error: "Imitation temptation"
**Cause**: User sees a successful competitor and wants to copy their approach
**Solution**: Redirect to the gap analysis. Copying puts you in a race you cannot win against an incumbent with a head start. Instead, find what they do poorly or do not do at all -- that is where differentiation lives.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/competitive-mapping.md` | Landscape mapping, feature comparison, competitor profiling | Landscape map templates, feature comparison matrices, activity tracker |
| `references/market-positioning.md` | Positioning strategy, differentiation scoring, win/loss analysis | Positioning maps, differentiation scoring, win/loss frameworks |
