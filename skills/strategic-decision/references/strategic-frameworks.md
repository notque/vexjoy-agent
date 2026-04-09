---
title: Strategic Frameworks — Porter's Five Forces, SWOT, OKR Alignment
domain: strategic-decision
level: 3
skill: strategic-decision
---

# Strategic Frameworks Reference

> **Scope**: Porter's Five Forces checklist, SWOT scoring templates, and OKR alignment matrices for CEO-level strategic decisions. Use when analyzing market position, competitive dynamics, or organizational direction-setting.
> **Version range**: Framework-agnostic — these frameworks are stable; the templates here adapt them for small-team use.
> **Generated**: 2026-04-09 — validate competitive data freshness before using Five Forces output.

---

## Overview

Porter's Five Forces is misused more often than it is useful. Most applications list generic observations per force without weighting them or drawing a conclusion. SWOT analyses similarly produce four lists that nobody acts on. This reference contains opinionated, scored versions of each framework that produce a decision-ready output, not a slide deck. OKR alignment matrices answer the question practitioners actually need: "Does this strategic option move our OKRs, or does it just sound strategic?"

---

## Porter's Five Forces — Scored Checklist

**Purpose**: Assess industry attractiveness and your competitive position within it. Run before major market entry or expansion decisions.

Rate each force 1-5: 1 = very low pressure on you (good), 5 = very high pressure (bad).

### Force 1: Threat of New Entrants

| Factor | Your Assessment (1-5) | Evidence |
|--------|-----------------------|----------|
| Capital requirements to enter | ___ | ___ |
| Economies of scale advantage for incumbents | ___ | ___ |
| Network effects protecting incumbents | ___ | ___ |
| Regulatory/compliance barriers | ___ | ___ |
| Brand loyalty / switching costs for customers | ___ | ___ |
| **Force Score (average)** | **___** | |

Score 1-2: High barriers, you are protected. Score 4-5: Low barriers, expect new competitors.

### Force 2: Bargaining Power of Suppliers

| Factor | Your Assessment (1-5) | Evidence |
|--------|-----------------------|----------|
| Number of alternative suppliers | ___ | ___ |
| Switching cost to change supplier | ___ | ___ |
| Supplier concentration vs. industry concentration | ___ | ___ |
| Supplier's ability to forward-integrate | ___ | ___ |
| **Force Score (average)** | **___** | |

### Force 3: Bargaining Power of Buyers

| Factor | Your Assessment (1-5) | Evidence |
|--------|-----------------------|----------|
| Buyer concentration (few large buyers vs many small) | ___ | ___ |
| Switching cost for buyers | ___ | ___ |
| Price sensitivity of buyers | ___ | ___ |
| Buyer's ability to backward-integrate | ___ | ___ |
| Availability of substitutes for buyers | ___ | ___ |
| **Force Score (average)** | **___** | |

### Force 4: Threat of Substitutes

| Factor | Your Assessment (1-5) | Evidence |
|--------|-----------------------|----------|
| Number of substitute products/services | ___ | ___ |
| Price-performance of substitutes vs. yours | ___ | ___ |
| Buyer propensity to switch | ___ | ___ |
| **Force Score (average)** | **___** | |

### Force 5: Competitive Rivalry

| Factor | Your Assessment (1-5) | Evidence |
|--------|-----------------------|----------|
| Number and size of competitors | ___ | ___ |
| Industry growth rate | ___ | ___ |
| Product differentiation | ___ | ___ |
| Exit barriers (sunk costs, specialization) | ___ | ___ |
| **Force Score (average)** | **___** | |

### Five Forces Summary

| Force | Score (1-5) | Weight | Weighted |
|-------|-------------|--------|----------|
| Threat of New Entrants | ___ | 20% | ___ |
| Supplier Power | ___ | 15% | ___ |
| Buyer Power | ___ | 25% | ___ |
| Threat of Substitutes | ___ | 20% | ___ |
| Competitive Rivalry | ___ | 20% | ___ |
| **Overall Pressure Score** | | 100% | **___** |

**Interpretation**: Score 1.0-2.0 = attractive industry, favorable position. 2.1-3.5 = moderate pressure, monitor. 3.6-5.0 = high pressure, requires active differentiation or exit plan.

**Worked example** (indie SaaS tool in crowded productivity space):
- New Entrants: 4.2 (low capital, no network effects)
- Supplier Power: 1.5 (AWS/GCP compete for business)
- Buyer Power: 3.8 (price-sensitive, many alternatives)
- Substitutes: 4.0 (spreadsheets, free tools)
- Rivalry: 4.5 (hundreds of competitors)
- **Overall: 3.6** — high pressure; conclusion: must differentiate on vertical specificity, not features.

---

## SWOT Scoring Matrix

Replace the traditional 4-box with scored, prioritized output. Each item gets a score and an action assignment.

### Scoring Method

| Category | Items (max 5 each) | Score (1-10) | Actionable? | Owner |
|----------|--------------------|--------------|-------------|-------|
| **Strength** | Strong brand trust in niche | 8 | Amplify in sales collateral | ___ |
| **Strength** | Proprietary data set | 9 | Build moat, protect via ToS | ___ |
| **Weakness** | No enterprise sales motion | 7 | Hire AE or partner channel | ___ |
| **Weakness** | Single-founder dependency | 6 | Document processes, hire #2 | ___ |
| **Opportunity** | Regulatory change opens market | 8 | Launch compliance feature Q2 | ___ |
| **Opportunity** | Competitor product discontinued | 7 | Outreach to their user base | ___ |
| **Threat** | Large competitor entering space | 9 | Accelerate differentiation | ___ |
| **Threat** | API dependency on third party | 6 | Build abstraction layer | ___ |

**Prioritization**: Address Weaknesses with score 7+ that block top Opportunities first. Ignore Threats with score < 5 until Strengths and Opportunities are capitalized.

### SWOT → Strategic Actions Matrix

|  | **Strengths (S)** | **Weaknesses (W)** |
|--|-------------------|--------------------|
| **Opportunities (O)** | **SO Strategies**: Use strengths to capture opportunities | **WO Strategies**: Overcome weaknesses to capture opportunities |
| **Threats (T)** | **ST Strategies**: Use strengths to mitigate threats | **WT Strategies**: Minimize weaknesses + avoid threats (defensive) |

Fill each quadrant with 1-2 concrete actions, not generic statements.

---

## OKR Alignment Matrix

Use before committing to a strategic initiative. Confirms the initiative actually moves the objectives, or reveals it is a distraction.

### Template

| Strategic Initiative | O1: [Objective 1] | O2: [Objective 2] | O3: [Objective 3] | Alignment Score |
|---------------------|-------------------|-------------------|-------------------|-----------------|
| Initiative A | High (3) | Medium (2) | Low (1) | 6 |
| Initiative B | Low (1) | High (3) | High (3) | 7 |
| Initiative C | None (0) | Low (1) | Medium (2) | 3 |

**Scoring**: None = 0, Low = 1, Medium = 2, High = 3. Max score = 3 × number of objectives.

**Decision rule**: Initiatives with alignment score < 30% of maximum should be questioned. They may be operationally necessary but are not "strategic" — be honest about what you are doing.

**Worked example** (content startup with 3 OKRs):
- O1: Reach 10,000 organic monthly readers by Q4
- O2: Launch paid newsletter tier by Q3
- O3: Establish 3 brand partnerships by Q4

| Initiative | O1 | O2 | O3 | Score |
|------------|----|----|-----|-------|
| Weekly long-form SEO articles | High (3) | Medium (2) | Low (1) | 6 |
| Twitter presence | Medium (2) | None (0) | Low (1) | 3 |
| Podcast series | Low (1) | Medium (2) | High (3) | 6 |
| Email list building | Medium (2) | High (3) | Medium (2) | 7 |

Conclusion: Twitter presence scores 3/9 — keep it under 2 hours/week. Email list building is the highest-leverage initiative at 7/9.

---

## Strategy Horizon Framework

For decisions that span multiple time horizons, use McKinsey's Three Horizons adapted for small teams.

| Horizon | Time Frame | Focus | Investment Level | Resource Split |
|---------|-----------|-------|-----------------|----------------|
| H1: Core | 0-12 months | Defend and extend current business | 70% of resources | Non-negotiable floor |
| H2: Adjacent | 12-36 months | Emerging opportunities with proven demand | 20% of resources | Adjustable quarterly |
| H3: Transformational | 36+ months | Options on future business models | 10% of resources | Can pause if H1 at risk |

**Trap to avoid**: Teams under pressure collapse all resources into H1 and wonder why they have no future. H3 investment survives pressure because it is small — protect it deliberately.

---

## Anti-Patterns

### Five Forces as a one-time exercise
**What it looks like**: Five Forces analysis done at company founding, cited 3 years later.
**Why wrong**: Industry forces shift. A 3-year-old analysis of supplier power in cloud infrastructure predates major pricing moves. Forces should be re-run at every major strategic inflection.
**Detection**: Check the date on any Five Forces document. Over 18 months old = must refresh before citing.

### SWOT without prioritization
**What it looks like**: 20-item SWOT with equal visual weight given to "strong team culture" and "no enterprise sales motion."
**Why wrong**: Without scores, SWOT becomes a list that feels like analysis but produces no action.
**Fix**: Every SWOT item must have a score and an owner. Items below score 5 are archived, not acted on.

### OKRs set after strategy, not before
**What it looks like**: Leadership decides the strategy in Q4, then writes OKRs in January to match it.
**Why wrong**: OKRs should constrain strategy choice, not validate it retroactively. If OKRs are written to match decisions already made, the alignment matrix is theater.
**Fix**: Set OKRs for the period before running the OKR alignment matrix. If OKRs don't exist, the matrix is not useful — run the decision matrix instead.

### "We have no competitors" (Porter's Forces Denial)
**What it looks like**: Founder refuses to name competitors; "we're unique."
**Why wrong**: No competitors = no market, or no market research. Porter's Threat of Substitutes force always has content even in novel markets (the substitute is "doing nothing" or "using the old way").
**Fix**: Replace "competitors" with "alternatives the buyer considers." Every buyer has alternatives, even if not commercial products.

---

## See Also

- `decision-matrices.md` — weighted scoring matrices and pre-mortem templates
- `skills/competitive-intel/references/competitive-mapping.md` — competitor landscape mapping
- `skills/competitive-intel/references/market-positioning.md` — positioning maps and differentiation scoring
