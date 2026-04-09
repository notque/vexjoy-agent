---
title: Market Positioning — Positioning Maps, Differentiation Scoring, Win/Loss Analysis
domain: competitive-intel
level: 3
skill: competitive-intel
---

# Market Positioning Reference

> **Scope**: Positioning map templates, differentiation scoring frameworks, and win/loss analysis for competitive intelligence. Use when determining how to differentiate from specific competitors and where to position in a market.
> **Version range**: Framework-agnostic — applies to SaaS, content, services, and product markets.
> **Generated**: 2026-04-09 — positioning strategy should be refreshed quarterly; this framework is stable.

---

## Overview

Positioning is not marketing copy. "The leading platform for..." is not a position — it is a claim. A position is a specific place in the customer's mind relative to alternatives: "When I need X, I use them because Y, unlike Z which gives me W." Positioning strategy finds a defensible location in the competitive landscape that you can own before competitors can replicate it. The three tools here — positioning maps, differentiation scoring, and win/loss analysis — build that location from evidence rather than aspiration.

---

## Positioning Statement Template

The standard Geoffrey Moore template, made concrete.

```
## Positioning Statement

For [target customer segment]
who [have a specific problem or need]
[product/content name] is a [category]
that [key differentiator — one concrete, specific thing]
unlike [primary competitor]
which [competitor's specific limitation].
```

**Worked examples**:

Bad (generic):
> "For developers who want to learn Go, GoLearn is a platform that provides high-quality tutorials, unlike other resources which are low quality."

Good (specific):
> "For platform engineers at series A-C startups who need to debug Kubernetes production incidents, PlatformNotes is a technical blog that publishes post-mortem analyses with actual root-cause investigation, unlike the Official Kubernetes docs which explain what to do but not why failures occur."

**Test**: Can your target reader fill in the blank: "I read [you] when ___"? If they can, positioning is working.

---

## Positioning Map Templates

### Template 1: 2×2 Quadrant Map

Choose axes that genuinely separate players in your market.

```
## Positioning Map: [Category]
## Updated: [YYYY-MM-DD]

High [Y-axis]
         |
         |  [Aspirational A]   [US target position]
         |
         |         [Direct Competitor B]
         |
         |  [Adjacent C]
         |                     [Legacy D]
         |
         +--------------------------------> High [X-axis]
Low [Y-axis]
  Low [X-axis]

### Player coordinates
| Player | X (1-10) | Y (1-10) | Notes |
|--------|----------|----------|-------|
| Our current | ___ | ___ | |
| Our target | ___ | ___ | 12-month goal |
| Competitor A | ___ | ___ | |
| Competitor B | ___ | ___ | |
```

### Template 2: Value Curve (Blue Ocean Canvas)

Compare offerings on 5-8 factors. Reveals where you are competing on the same terms vs. where you offer something unique.

| Factor | Competitor A | Competitor B | Industry Avg | Us |
|--------|-------------|-------------|--------------|-----|
| Price | High | Medium | Medium | Low |
| Depth of content | High | Medium | Low | High |
| Publication frequency | Low | High | Medium | Medium |
| Community | None | Large | Small | Medium |
| Interactivity (Q&A, office hours) | None | None | None | **High** |
| Industry-specific focus | Broad | Broad | Broad | **Narrow** |

**Interpretation**: Where your line is distinct from competitors, you have differentiation. Where it follows the industry average, you are competing on commodity terms — and losing.

---

## Differentiation Scoring Framework

Score your differentiation on each dimension to determine what is defensible vs. vulnerable.

| Differentiation Dimension | Our Advantage (1-10) | Ease for Competitor to Copy (1-10) | Defensibility Score |
|---------------------------|---------------------|-----------------------------------|---------------------|
| Brand/voice/trust | ___ | ___ | ___ - ___ = ___ |
| Proprietary data/research | ___ | ___ | ___ - ___ = ___ |
| Community/network effects | ___ | ___ | ___ - ___ = ___ |
| Technical depth/expertise | ___ | ___ | ___ - ___ = ___ |
| Speed/responsiveness | ___ | ___ | ___ - ___ = ___ |
| Price | ___ | ___ | ___ - ___ = ___ |
| Breadth of coverage | ___ | ___ | ___ - ___ = ___ |

**Defensibility Score** = Our Advantage − Ease to Copy. Higher = more defensible.

| Score Range | Classification | Strategy |
|-------------|---------------|---------|
| 7-10 | Core moat — protect and amplify | Double down, use in all positioning |
| 4-6 | Competitive advantage — maintain | Defend, monitor for competitor improvement |
| 1-3 | Temporary advantage | Do not build strategy on this; find moat |
| Negative | Vulnerability | Address or concede this dimension |

**Worked example** (technical content creator):

| Dimension | Our Advantage | Ease to Copy | Defensibility |
|-----------|--------------|--------------|---------------|
| Authentic voice (10 years same author) | 9 | 1 | **8** — core moat |
| Proprietary production incident data | 8 | 2 | **6** — strong |
| Community Slack (2,000 members) | 7 | 4 | **3** — defend |
| SEO (2,000 pages indexed) | 6 | 5 | **1** — temporary |
| Price (free) | 10 | 9 | **1** — not a moat |

Conclusion: Build strategy on voice + proprietary data. The community is valuable but replicable. Price and SEO are not differentiators.

---

## Win/Loss Analysis Framework

Collect data on decisions where you won or lost. For content: subscribe vs. bounce. For product: bought vs. churned.

### Win Analysis Template

```
## Win Record: [Date/Cohort]

### Why they chose us (ask or infer)
- Factor 1: ___
- Factor 2: ___
- Factor 3: ___

### What they tried before (alternatives considered)
- Alternative 1: ___ — why rejected: ___
- Alternative 2: ___ — why rejected: ___

### Trigger (what made them choose now)
- ___

### Segment match
- Does this winner match our ICP? [Yes / Partially / No]
- If no: why did they engage and is this a segment worth expanding to?
```

### Loss Analysis Template

```
## Loss Record: [Date/Cohort]

### Why they did NOT choose us (ask or infer)
- Factor 1: ___
- Factor 2: ___

### Who they chose instead
- Competitor: ___
- Why: ___

### What we would need to offer to win this segment
- ___

### Should we compete for this segment?
- [Yes — add to roadmap / No — outside our ICP / Maybe — investigate further]
```

### Win/Loss Pattern Table

After 10+ records, aggregate:

| Decision Factor | % Won when present | % Lost when present | Action |
|-----------------|-------------------|---------------------|--------|
| [Factor A] | 80% | 20% | Amplify in positioning |
| [Factor B] | 40% | 60% | Not a differentiator |
| [Factor C] | 10% | 90% | Address or stop competing on it |
| [Factor D] | 95% | 5% | Core moat — protect |

---

## Positioning Validation Checklist

Before finalizing positioning:

```
[ ] Can you name 3 real competitors and state clearly why a customer would choose you over each?
[ ] Does your positioning statement pass the "for who" test? (specific segment, not "developers")
[ ] Does your differentiation score show at least 2 defensibility scores of 5+?
[ ] Have you validated positioning with 3 real customers/readers? ("Why do you read/use us?")
[ ] Is your positioning distinct on the value curve from industry average on at least 2 factors?
[ ] Does your positioning avoid competing on price as primary differentiator? (price = race to bottom)
[ ] Is your target position on the positioning map currently unoccupied or weakly occupied?
```

---

## Anti-Patterns

### Positioning by negation only
**What it looks like**: "We're not like those enterprise tools. We're different."
**Why wrong**: Negation tells the customer what you are not. It does not tell them what you are. The brain cannot hold "not X" — it has to form a positive association.
**Fix**: Every positioning statement must have a positive claim: "We are the [specific thing] for [specific people] who need [specific outcome]." The competitor reference is a clarifier, not the definition.

### Claiming differentiation on commodity dimensions
**What it looks like**: "We differentiate on quality, service, and reliability."
**Why wrong**: Every competitor claims quality, service, and reliability. These are table stakes, not differentiators. Scoring these high in the differentiation matrix with low ease-to-copy is usually wishful thinking.
**Detection**: Run the defensibility scoring. Any dimension where "ease for competitor to copy" is above 7 is not a strategic differentiator.

### Win/loss analysis from memory instead of data
**What it looks like**: "We think we lose to Competitor A because of price." No records, no patterns, just team consensus.
**Why wrong**: Teams systematically attribute losses to price because it is the most face-saving reason. Actual win/loss data frequently reveals positioning and capability gaps are more important than price.
**Fix**: Collect win/loss data at the point of decision. For content: exit surveys. For products: cancel surveys with forced-choice options. Analyze at 10+ records before concluding.

---

## Detection Commands Reference

```bash
# Check Google Search Console for branded vs. non-branded traffic split
# (Manual: Search Console > Performance > filter "type: web" > compare queries with/without brand name)

# Find what competitors rank for that you don't (requires ahrefs/semrush or similar)
# Manual: search "[competitor] vs [your brand]" — see what comparison content exists

# Monitor competitor brand mentions on Reddit
curl -s "https://www.reddit.com/search.json?q={competitor-name}&sort=new&limit=10" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  [print(p['data']['title'], p['data']['created_utc']) for p in d['data']['children']]"
```

---

## See Also

- `competitive-mapping.md` — competitive landscape mapping, feature comparison matrices
- `skills/strategic-decision/references/strategic-frameworks.md` — SWOT scoring and Porter's Five Forces
- `skills/growth-strategy/references/audience-segmentation.md` — ICP scoring for segment selection
