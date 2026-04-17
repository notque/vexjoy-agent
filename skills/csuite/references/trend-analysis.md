---
title: Trend Analysis — Market Trend Detection, Technology Adoption Curves, Disruption Pattern Recognition
domain: competitive-intel
level: 3
skill: competitive-intel
---

# Trend Analysis Reference

> **Scope**: Market trend detection signals, technology adoption curve positioning, and disruption pattern recognition for competitive intelligence. Use when determining whether a market signal is a durable trend, a fad, or a disruption precursor. Complements competitive-mapping.md (which covers landscape analysis) and market-positioning.md (which covers positioning response).
> **Version range**: Framework-agnostic — applies to SaaS, consumer, content, and infrastructure markets. Technology-specific adoption benchmarks are from empirical research; validate against current analogues.
> **Generated**: 2026-04-09 — trend signals require continuous refresh; any analysis older than 6 months should be treated as hypothesis, not conclusion.

---

## Overview

Trend analysis fails most often by confusing noise for signal, or signal for sustained trend. A competitor shipping one feature is noise. A competitor changing their pricing model, hiring a new VP of Sales, and launching in a new market simultaneously is a signal cluster. Technology adoption curves explain why early signals look small and why acting on them feels premature — the correct reading of "this is still early" depends entirely on which phase of adoption you are in. Disruption pattern recognition adds the most valuable layer: identifying when a market is not just growing or shrinking, but about to be restructured.

---

## Market Trend Detection Signal Framework

### Signal Tier Classification

| Tier | Type | Reliability | Lag | Examples |
|------|------|-------------|-----|---------|
| Tier 1 — Leading | Behavior signals | Low (noisy) | 12-24 months ahead | Search volume spikes, VC investment thesis, early startup counts |
| Tier 2 — Confirming | Adoption signals | Medium | 6-12 months ahead | Enterprise pilot programs, conference session count, GitHub stars growth rate |
| Tier 3 — Lagging | Market signals | High (reliable) | 0-6 months | Gartner/Forrester coverage, mainstream press articles, incumbent product response |

**Rule**: Act on Tier 1 signals only when supported by at least one Tier 2 signal. Act on Tier 2 signals when supported by at least one Tier 3 signal. Tier 3 alone means the trend is confirmed but you may be late.

### Signal Collection Template

```
## Trend Signal Log: [Topic/Technology]
## Collection date: [YYYY-MM-DD]
## Analyst: ___

### Tier 1 Signals (Leading)
| Signal | Source | Value | Trend (↑/↓/→) | Date | Notes |
|--------|--------|-------|---------------|------|-------|
| Google Trends score (keyword) | Google Trends | ___ | ___ | ___ | Normalize to 100 = peak interest |
| GitHub repo star growth rate | GitHub | +___/month | ___ | ___ | Compare to 3-month prior |
| VC deals in space (new, 90 days) | Crunchbase/PitchBook | ___ | ___ | ___ | Count, not dollar volume |
| New GitHub repos on topic | GitHub search | ___ | ___ | ___ | repos created in last 90 days |
| ArXiv papers (if technical) | ArXiv | ___/quarter | ___ | ___ | Research = 18-36 months ahead |

### Tier 2 Signals (Confirming)
| Signal | Source | Value | Trend | Date | Notes |
|--------|--------|-------|-------|------|-------|
| Enterprise pilot count | LinkedIn Jobs, press releases | ___ | ___ | ___ | "Seeking X experience" in JDs |
| Major conference tracks/sessions | Conf agendas | ___ | ___ | ___ | New track = mainstream adjacent |
| Stack Overflow questions/week | Stack Overflow | ___ | ___ | ___ | New question velocity = active use |
| npm/PyPI download growth | Package registries | ___% MoM | ___ | ___ | Library adoption proxy |
| SaaS startups in space count | ProductHunt, AngelList | ___ | ___ | ___ | Launched last 12 months |

### Tier 3 Signals (Lagging)
| Signal | Source | Value | Trend | Date | Notes |
|--------|--------|-------|-------|------|-------|
| Gartner/Forrester mention | Analyst reports | In/Out of Hype Cycle | ___ | ___ | Position in Hype Cycle |
| Enterprise vendor product launch | Press release | Yes/No | ___ | ___ | Incumbent response signal |
| Major media coverage | TechCrunch, WSJ, NYT | ___ articles | ___ | ___ | Count in last 90 days |

### Signal Cluster Summary
Tier 1 supporting signals: ___ of ___
Tier 2 supporting signals: ___ of ___
Tier 3 supporting signals: ___ of ___
Overall trend assessment: [Emerging / Building / Confirmed / Mainstream / Declining]
```

---

## Technology Adoption Curve Positioning

Based on the Rogers Diffusion of Innovations model. Position your market accurately before setting strategy.

### Adoption Phase Reference Table

| Phase | % of Market | Characteristics | Duration (typical) | Strategic Implication |
|-------|-------------|-----------------|-------------------|----------------------|
| **Innovators** | 2.5% | Hobbyists, researchers, experimenters; willing to accept broken products | 1-3 years | Build the core; don't optimize for UX yet |
| **Early Adopters** | 13.5% | Visionaries seeking competitive advantage; pay premium; provide feedback | 2-4 years | Reference customers, case studies, category definition |
| **Early Majority** | 34% | Pragmatists; need proof, peers, integrations; risk-averse | 3-5 years | Crossing the chasm — reduce friction, add integrations |
| **Late Majority** | 34% | Conservatives; adopt because they must; price-sensitive | 3-6 years | Volume play; commoditization pressure begins |
| **Laggards** | 16% | Last to move; often forced by regulation or ecosystem pressure | Indefinite | Sustain or exit; do not invest in growth here |

### Current Phase Diagnosis

```
## Adoption Phase Assessment: [Technology/Market]

### Phase Indicators (check all that apply)

INNOVATORS phase signals:
[ ] Primary users are developers or researchers (not business buyers)
[ ] Products require technical setup; no one-click install
[ ] No vendor offers enterprise support
[ ] Community is primarily on GitHub, HN, or academic forums
[ ] Use cases are experimental, not production-critical

EARLY ADOPTER phase signals:
[ ] First conference talks appearing at major industry events
[ ] 2-5 vendors have achieved product-market fit with specific use cases
[ ] Early reference customers willing to be named publicly
[ ] Enterprise pilots (unpaid or nearly unpaid) are happening
[ ] Content about this technology is growing on technical blogs

EARLY MAJORITY phase signals:
[ ] Multiple vendors offering commercial support and SLAs
[ ] Integration with major platforms (Salesforce, AWS, etc.)
[ ] HR departments posting job descriptions requiring this skill
[ ] Industry analysts (Gartner, Forrester) have named a category
[ ] First acquisition of a player in the space

LATE MAJORITY phase signals:
[ ] Incumbent vendors (not just startups) have launched products here
[ ] Price competition is the primary marketing lever
[ ] Certification programs exist (vendor + third-party)
[ ] Community growth rate has slowed; questions on Stack Overflow more rote
[ ] Enterprise procurement (RFPs, competitive bidding) is standard

### Diagnosis
Current phase: ___
Evidence for this phase: ___
Time to next phase (estimate): ___
```

### "Crossing the Chasm" Detection

The chasm exists between Early Adopters and Early Majority. Signals that a market is AT the chasm:

```
[ ] Early adopter growth has stalled (the enthusiasts who will try anything have all tried it)
[ ] Mainstream buyers ask for references from companies like them (not just any reference)
[ ] Integration requests outpace feature requests
[ ] Support burden is growing faster than new customer acquisition
[ ] Pricing pressure emerging even though market is not yet saturated
[ ] Multiple vendors competing for the same Early Adopter segment with near-identical products
```

**Chasm crossing strategy**: Pick one vertical or use case. Own it completely with deep integrations, specific references, and specialized support. Do not try to cross the chasm with a horizontal product — it is too undifferentiated. Once the vertical is captured, use it as a beachhead.

---

## Disruption Pattern Recognition

Based on Clayton Christensen's disruption theory, extended for software and content markets. Disruption follows observable patterns before incumbents respond.

### Disruption Signal Matrix

| Pattern | Early Signal | Midpoint Signal | Late Signal (Too Late for Incumbents) |
|---------|-------------|-----------------|---------------------------------------|
| **Low-end disruption** | New entrant prices 60-80% cheaper; incumbent ignores them (wrong customers) | New entrant's product improves; incumbent's low-end customers switch | New entrant moves upmarket; incumbent loses profitability |
| **New-market disruption** | Entirely new user type that incumbent never served; product is "worse" by incumbent metrics | New-market grows; some incumbent customers defect | Incumbent's core market erodes from below and adjacent |
| **Platform disruption** | Aggregator platform pulls customers between you and your buyer | Platform starts competing with you directly for top customers | Platform controls discovery; you have no direct customer relationship |
| **Business model disruption** | Competitor offers your product's function as a feature of a larger bundle | Customers start buying the bundle instead of your standalone | Your market becomes a feature line item, not a product category |

### Disruption Diagnostic Template

```
## Disruption Risk Assessment: [Your Market]
## Date: [YYYY-MM-DD]

### Low-End Disruption Check
- Is there a competitor entering at 50%+ lower price? [Yes / No]
- Are they targeting a customer segment you consider unprofitable? [Yes / No]
- Is their product improving faster than your low-end customer's needs are increasing? [Yes / No]

If 2+ Yes: Low-end disruption risk is REAL. Assess within 6 months.

### New-Market Disruption Check
- Is there a new category of user who cannot use incumbent products (including yours) due to cost/complexity? [Yes / No]
- Is anyone building a "worse but simpler" version targeting those non-consumers? [Yes / No]
- Is that simpler product improving 20%+ annually in the dimension incumbents optimize for? [Yes / No]

If 2+ Yes: New-market disruption risk is REAL.

### Platform Disruption Check
- Does a platform (marketplace, OS, cloud provider, social network) now intermediate between you and your customer? [Yes / No]
- Is that platform showing any signal of building features that overlap with your product? [Yes / No]
- Do your customers use your product primarily through or within that platform? [Yes / No]

If 2+ Yes: Platform disruption risk is HIGH. Examine differentiation urgently.

### Business Model Disruption Check
- Is a competitor offering your core function as part of a larger suite at the same or lower price? [Yes / No]
- Are customers already buying that suite for other components, making your standalone look redundant? [Yes / No]

If 2 Yes: Business model disruption is underway. Evaluate bundling, partnership, or exit.

### Disruption Risk Summary
| Type | Risk Level | Time Horizon | Primary Action |
|------|-----------|--------------|----------------|
| Low-end | Low / Medium / High | ___ months | ___ |
| New-market | Low / Medium / High | ___ months | ___ |
| Platform | Low / Medium / High | ___ months | ___ |
| Business model | Low / Medium / High | ___ months | ___ |
```

---

## Trend Decay Recognition

Not every trend sustains. Identify decay early to avoid investing in a declining market.

| Decay Signal | Measurement | Threshold for Concern |
|-------------|-------------|----------------------|
| Search volume decline | Google Trends | >20% decline from peak over 6 months |
| GitHub star growth rate falling | Stars per month | Growth rate declining 3+ consecutive months |
| Conference tracks being removed | Agenda comparison YoY | Removal from 2+ major conferences |
| VC investments tapering | Deal count by quarter | 40%+ fewer deals than peak quarter |
| Acquisitions exceeding new entrants | M&A vs. new company formation | More acquisitions than new companies for 2+ quarters |
| Incumbent products discontinued | Product announcements | 2+ major vendors exiting the space |

**Note**: Decline in early signals (search volume) while late signals remain high (enterprise adoption) is NOT decay — it is maturation. Decay occurs when both lead and lag signals decline together.

```
## Trend Decay Audit: [Technology/Market]
## Date: ___

| Decay Signal | Current Value | Peak Value | % Change | Trend |
|-------------|--------------|------------|----------|-------|
| Google Trends score | ___ | ___ | ___% | ↑/↓ |
| GitHub stars/month | ___ | ___ | ___% | ↑/↓ |
| VC deals/quarter | ___ | ___ | ___% | ↑/↓ |
| Conference sessions count | ___ | ___ | ___% | ↑/↓ |
| New startups launched | ___ | ___ | ___% | ↑/↓ |

Decay signals active: ___ of 5
Assessment: [Growing / Maturing / Plateau / Early Decay / Late Decay]
```

---

## Patterns to Detect and Fix
<!-- no-pair-required: section header, not an individual anti-pattern -->

### Treating Hype Cycle peak as confirmation of sustained growth
**What it looks like**: "Gartner put us at the Peak of Inflated Expectations — that means we're mainstream."
**Why wrong**: Gartner's Peak of Inflated Expectations precedes the Trough of Disillusionment. Being at the peak means hype has outpaced delivery and a correction is coming. Companies that raise at peak valuations and expand at peak rates are maximally exposed to the trough.
**Do instead**: Treat Hype Cycle peak placement as a signal to reduce cost structure and extend runway. The question to ask is: "How do we survive the trough?" not "How fast can we grow into this moment?"
**Fix**: Treat Hype Cycle peak as a warning to reduce cost structure and extend runway, not as a signal to accelerate.

### Confusing single-vendor activity for market trend
**What it looks like**: "Competitor X launched three features this month. This space is growing fast."
**Why wrong**: A single vendor's product velocity is company signal, not market signal. A competitor may be launching features because they are desperate, because they have a new head of product, or because a large customer demanded it. None of those explain the market.
**Do instead**: Require signal from at least 3 independent sources across different tiers before classifying something as a market trend. One vendor's activity is a Tier 2 signal at most; it needs Tier 1 corroboration before it becomes actionable.
**Fix**: Market trends require signal from at least 3 independent sources across different tiers before classification as a trend. One vendor's activity is a Tier 2 signal at most, requiring Tier 1 support to be actionable.

### Ignoring disruption until it is in your customer segment
**What it looks like**: Disruption is identified in the low-end segment. Team says "that's not our market" and takes no action.
**Why wrong**: Disruption moves upmarket. The low-end is where it starts, not where it stays. Christensen documented this across 20+ industries: the disruption that starts at the bottom reliably migrates into the incumbent's core market within 3-8 years.
**Do instead**: When low-end disruption is identified, immediately run a response window calculation: assume the disruptor improves 20% per year on the dimension that matters to your customers. Determine when it reaches your customers' threshold. That date is your deadline for a strategic response.
**Fix**: When low-end disruption is identified, run a "future competitive landscape" exercise: assume the disruptor's product improves 20% per year in the dimension you care about. At that rate, when does it reach your customer's requirements? That is your response window.

### Trend analysis without refresh cadence
**What it looks like**: Trend analysis done in Q1, cited in Q4 as the basis for strategy decisions.
**Why wrong**: Tech markets move faster than annual strategy cycles. A signal logged as "Emerging" in January can be "Confirmed" by April.
**Do instead**: Establish a refresh cadence when you publish any trend analysis: Tier 1 signals monthly, Tier 2 quarterly, full report every 6 months. Attach a freshness warning to any report before it is cited in a decision if it exceeds those thresholds.
**Fix**: Tier 1 signals: check monthly. Tier 2 signals: check quarterly. Full trend report: refresh every 6 months. Any trend report over 6 months old should include a freshness warning before it is cited in a decision.

---

## Detection Commands Reference

```bash
# Google Trends export (manual: trends.google.com > download CSV)
# Then parse:
python3 -c "
import csv
with open('trends_data.csv') as f:
    reader = csv.reader(f)
    rows = list(reader)
# Find peak and current
values = [int(r[1]) for r in rows[3:] if r[1].isdigit()]
peak = max(values)
current = values[-1]
print(f'Peak: {peak}, Current: {current}, % of peak: {current/peak*100:.0f}%')
" 2>/dev/null

# GitHub star growth rate for a repo
curl -s "https://api.github.com/repos/{owner}/{repo}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Stars: {d[\"stargazers_count\"]}')
print(f'Watchers: {d[\"subscribers_count\"]}')
print(f'Open issues: {d[\"open_issues_count\"]}')
print(f'Last push: {d[\"pushed_at\"]}')
print(f'Created: {d[\"created_at\"]}')
"

# Count new GitHub repos on a topic (last 90 days)
curl -s "https://api.github.com/search/repositories?q={topic}+created:>$(date -d '90 days ago' +%Y-%m-%d)&sort=stars&per_page=1" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'New repos (90d): {d[\"total_count\"]}')"

# Hacker News mention count for a technology
curl -s "https://hn.algolia.com/api/v1/search?query={technology}&tags=story&numericFilters=created_at_i>$(date -d '90 days ago' +%s)" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'HN stories (90d): {d[\"nbHits\"]}')"

# Stack Overflow question velocity
curl -s "https://api.stackexchange.com/2.3/questions?tagged={technology}&site=stackoverflow&fromdate=$(date -d '30 days ago' +%s)" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'SO questions (30d): {d[\"total\"]}')" 2>/dev/null
```

---

## See Also

- `competitive-mapping.md` — landscape mapping and competitor activity tracking
- `market-positioning.md` — positioning response to confirmed market trends
- `skills/strategic-decision/references/risk-assessment.md` — scenario planning for trend uncertainty
