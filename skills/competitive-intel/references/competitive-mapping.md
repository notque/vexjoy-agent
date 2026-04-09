---
title: Competitive Landscape Mapping — Templates and Feature Comparison Matrices
domain: competitive-intel
level: 3
skill: competitive-intel
---

# Competitive Landscape Mapping Reference

> **Scope**: Competitive landscape mapping templates, feature comparison matrices, and competitive intelligence collection frameworks. Use at the start of any competitive analysis to structure the landscape before diving into individual competitor profiles.
> **Version range**: Framework-agnostic — platform and product specifics change; the mapping structure does not.
> **Generated**: 2026-04-09 — competitive landscapes change fast; date-stamp all data you collect.

---

## Overview

Most competitive analyses drown in detail about individual competitors and never produce a map of the overall landscape. A landscape map reveals structure that individual profiles miss: where the market is clustered, where it is empty, which segments are contested vs. undefended, and what the dominant competitive dimensions are. Build the map before profiling individuals.

---

## Competitive Landscape Map Template

**Step 1: Identify the competitive dimensions**

Before placing anyone on the map, choose the two dimensions that best explain why customers choose between options. Bad dimensions: "quality" and "price" (every market). Good dimensions are specific to the category.

| Market Type | Dimension Examples |
|-------------|-------------------|
| SaaS tools | Feature depth vs. ease of use; Self-serve vs. sales-led; SMB vs. Enterprise |
| Content / media | Technical depth vs. accessibility; Broad vs. niche; Free vs. paid |
| Services | Speed vs. quality; Specialization vs. breadth; Async vs. synchronous |
| Consumer products | Premium vs. value; Established vs. emerging; B2C direct vs. retail |

**Step 2: Map the landscape**

```
## Competitive Landscape: [Market/Category Name]
## Date: [YYYY-MM-DD] — refresh every 6 months

### Competitive Dimensions
- X-axis: [Dimension 1] — Low (left) to High (right)
- Y-axis: [Dimension 2] — Low (bottom) to High (top)

### Players Mapped

| Player | X-axis position (1-10) | Y-axis position (1-10) | Tier | Notes |
|--------|------------------------|------------------------|------|-------|
| Us | ___ | ___ | — | Current position |
| [Competitor A] | ___ | ___ | Direct | |
| [Competitor B] | ___ | ___ | Direct | |
| [Competitor C] | ___ | ___ | Adjacent | |
| [Competitor D] | ___ | ___ | Aspirational | |
| [Emerging E] | ___ | ___ | Emerging | |

### White Space Analysis
- Underserved quadrant: [describe position that has demand but no strong player]
- Overcrowded quadrant: [describe where competition is densest]
- Our target position: [where we aim to be vs. where we are]
```

**Worked example** (indie technical blog in Go/cloud-native space):

X-axis: Accessibility (1 = expert-only, 10 = beginner-friendly)
Y-axis: Technical depth (1 = surface overview, 10 = production-grade detail)

| Player | Accessibility | Depth | Tier |
|--------|--------------|-------|------|
| Our blog | 4 | 8 | — |
| GoByExample.com | 9 | 3 | Adjacent |
| Official Go Blog | 3 | 7 | Aspirational |
| Dave Cheney's blog | 3 | 9 | Aspirational |
| Ardan Labs | 4 | 9 | Direct |
| Random medium posts | 7 | 3 | Adjacent |

White space: High accessibility + high depth (position 7-8, 7-8). No current player makes production-grade content accessible to mid-level engineers. That is the target position.

---

## Competitor Tier Classification

| Tier | Definition | Research Depth | Review Cadence |
|------|-----------|----------------|----------------|
| **Direct** | Same audience, same problem, same format/channel | Full profile (see template) | Monthly |
| **Adjacent** | Same audience, different approach | 1-paragraph summary | Quarterly |
| **Aspirational** | Larger player in a broader version of your space | Strategy extraction only | Quarterly |
| **Emerging** | New entrant showing directional signals | Watch list only | Quarterly |
| **Legacy** | Established player in decline | Monitor for opportunities | Semi-annually |

**Direct competitor cap**: Limit full analysis to 3 direct competitors max. Above 3, you are doing competitive research tourism instead of strategy.

---

## Feature Comparison Matrix

Use when technical/product capability comparison is the primary decision. Adapt feature list to your market.

| Feature / Capability | Us | Competitor A | Competitor B | Notes |
|---------------------|-----|--------------|--------------|-------|
| **Core Features** | | | | |
| [Feature 1] | ✓ Full | ✓ Full | ✗ Missing | |
| [Feature 2] | ~ Partial | ✓ Full | ✓ Full | |
| [Feature 3] | ✗ Missing | ✓ Full | ✓ Full | Roadmap Q3 |
| **Differentiating Features** | | | | |
| [Our strength] | ✓ Full | ✗ Missing | ✗ Missing | Core differentiator |
| [Their strength] | ✗ Missing | ✓ Full | ~ Partial | |
| **Price / Packaging** | | | | |
| Entry price | $0 | $29/mo | $49/mo | |
| Enterprise tier | Contact | $500/mo | $800/mo | |
| Free tier | Yes | No | Yes (limited) | |
| **Support / Community** | | | | |
| Documentation quality | High | Medium | Low | |
| Community size | Small | Large | Medium | |
| Support SLA | None | 48h | 24h | |

**Legend**: ✓ Full = complete implementation. ~ Partial = limited or early. ✗ Missing = not offered. ? = unknown.

**Decision use**: A feature matrix reveals where you are competitive, where you are weak, and what you can win on. Never use it to claim superiority on features you are "partial" on.

---

## Competitor Activity Tracker

Track what competitors actually do, not just what they claim. Update this monthly.

```
## [Competitor Name] — Activity Log

### Product Activity
- Date | Change | Signal
- [YYYY-MM-DD] | Launched [feature] | [what it means for their strategy]
- [YYYY-MM-DD] | Deprecated [feature] | [what it means]
- [YYYY-MM-DD] | Changed pricing to [model] | [impact on our positioning]

### Content Activity
- Date | Topic/Format | Engagement | Signal
- [YYYY-MM-DD] | [post title] | [high/med/low] | [what topics they're doubling down on]

### Company Activity
- Date | Event | Signal
- [YYYY-MM-DD] | Hired [role] | [capability they're building]
- [YYYY-MM-DD] | Raised [amount] | [runway and ambition signal]
- [YYYY-MM-DD] | Partnership with [company] | [market expansion or channel signal]

### Sentiment Signals
- Most praised (G2/Reddit/HN): [what users love]
- Most criticized: [what users complain about — your opportunity]
- Recent sentiment shift: [positive/negative trajectory]
```

---

## Market Structure Analysis

Classify your market structure before setting positioning strategy.

| Structure | Characteristics | Implications for Strategy |
|-----------|----------------|--------------------------|
| **Monopoly** | One dominant player (>60% share) | Differentiate or find underserved niche; don't compete head-on |
| **Duopoly** | Two dominant players sharing the market | Third-player positioning: both incumbents have weaknesses; find the gap |
| **Oligopoly** | 3-5 significant players | Specialization wins; compete in a narrow segment where you can be #1 |
| **Fragmented** | Many small players, no dominant leader | Consolidation opportunity OR signal of unmet need without viable solution |
| **Emerging** | Market being defined in real-time | Speed matters; first-mover into clearly defined niche wins |

---

## Anti-Patterns

### Analyzing features, ignoring momentum
**What it looks like**: Competitor B has fewer features than us today. No further analysis.
**Why wrong**: Momentum matters more than current state. A competitor shipping 10 features/quarter with high user satisfaction will surpass a feature-rich stagnant product within 12-18 months.
**Detection**: Check competitor's changelog/release notes. If releases are accelerating and quality is high, treat them as stronger than their current position suggests.
**Fix**: Add "velocity" to your competitive tracker. Rate each competitor's development and distribution momentum separately from their current capability.

### Mapping on irrelevant dimensions
**What it looks like**: Positioning map uses "enterprise vs. SMB" and "cloud vs. on-premise" when all relevant players are SMB-focused SaaS. Everyone clusters in one quadrant.
**Why wrong**: If dimensions don't separate the competitors, the map reveals nothing.
**Fix**: Require that the chosen dimensions separate at least 50% of plotted players. If everyone clusters, try different dimensions.

### Static competitive landscape
**What it looks like**: Competitive analysis document dated 18 months ago, still being cited in strategy discussions.
**Why wrong**: Companies pivot, funding changes strategies, new entrants emerge, and products get discontinued. A stale map actively misleads.
**Detection**: Check the date on any competitive document. Over 12 months = must refresh core data before using. Over 18 months = discard and redo.

---

## Detection Commands Reference

```bash
# Check competitor content velocity (RSS feed)
curl -s "https://{competitor-domain}/feed.xml" | grep -c "<item>"
# Higher count = more content output

# Check competitor's web presence (Wayback Machine for changes)
# Manual: https://web.archive.org/web/*/{competitor-domain} — compare snapshots

# Check competitor's GitHub activity (for OSS or dev tool companies)
curl -s "https://api.github.com/orgs/{competitor-org}/repos" | \
  python3 -c "import json,sys; repos=json.load(sys.stdin); \
  [print(r['name'], r['pushed_at']) for r in sorted(repos, key=lambda x: x['pushed_at'], reverse=True)[:5]]"

# Check Hacker News mentions
curl -s "https://hn.algolia.com/api/v1/search?query={competitor}&tags=story&hitsPerPage=5" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(h['title'], h['created_at']) for h in d['hits']]"
```

---

## See Also

- `market-positioning.md` — positioning map templates, differentiation scoring, win/loss analysis
- `skills/strategic-decision/references/strategic-frameworks.md` — Porter's Five Forces for market structure
