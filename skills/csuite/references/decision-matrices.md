---
title: Decision Matrices and Scoring Models
domain: strategic-decision
level: 3
skill: strategic-decision
---

# Decision Matrices and Scoring Models

> **Scope**: Structured decision scoring, opportunity evaluation matrices, and pre-mortem analysis for CEO-level strategic decisions. Does NOT cover financial modeling (see strategic-frameworks.md) or operational project decisions.
> **Version range**: Framework-agnostic — applies to any strategic decision with 2-5 options.
> **Generated**: 2026-04-09 — validate weights against your organization's actual priorities.

---

## Overview

Strategic decisions fail most often because they stay qualitative too long. "This feels right" and "my gut says no" are not frameworks — they are ways to avoid accountability. Decision matrices force explicit weight assignments before scoring, which exposes hidden assumptions and surfaces disagreement early. The pre-mortem technique catches the most common failure: decisions optimized for the scenario where everything works.

---

## Weighted Decision Scoring Matrix

Fill in weights (must sum to 100%) and scores (1-10) before discussion. Filling in collaboratively introduces anchoring bias.

| Criterion | Weight | Option A | Option B | Option C |
|-----------|--------|----------|----------|----------|
| Strategic fit | 30% | ___ | ___ | ___ |
| Technical feasibility | 25% | ___ | ___ | ___ |
| Cost (3-year TCO) | 20% | ___ | ___ | ___ |
| Time to value | 15% | ___ | ___ | ___ |
| Reversibility | 10% | ___ | ___ | ___ |
| **Weighted score** | 100% | **calc** | **calc** | **calc** |

**Calculation**: `weighted_score = sum(criterion_weight * option_score)` for each option.

**Worked example** (market entry decision — enter APAC vs. expand EU vs. deepen US):

| Criterion | Weight | APAC | EU | US |
|-----------|--------|------|----|----|
| Strategic fit | 30% | 8 | 7 | 9 |
| Technical feasibility | 25% | 5 | 8 | 9 |
| Cost (3-year TCO) | 20% | 4 | 7 | 8 |
| Time to value | 15% | 6 | 7 | 9 |
| Reversibility | 10% | 4 | 7 | 9 |
| **Weighted score** | 100% | **5.95** | **7.30** | **8.90** |

Result: Deepen US wins on current resources. APAC revisit in 18 months when localization team is hired.

---

## Opportunity Scoring Model (ICE)

Use when comparing multiple opportunities to prioritize which deserves full decision matrix treatment.

| Opportunity | Impact (1-10) | Confidence (1-10) | Ease (1-10) | ICE Score |
|-------------|---------------|-------------------|-------------|-----------|
| ___ | ___ | ___ | ___ | **calc** |
| ___ | ___ | ___ | ___ | **calc** |
| ___ | ___ | ___ | ___ | **calc** |

**ICE Score** = (Impact + Confidence + Ease) / 3

**Impact**: How significant is the upside if this succeeds? (1 = marginal improvement, 10 = transformative)
**Confidence**: How certain are you in the impact estimate? (1 = pure guess, 10 = validated data)
**Ease**: How easy is execution relative to available resources? (1 = requires 2 years and $2M, 10 = one week, in-house)

**Cutoffs**: ICE < 4 = don't analyze further. ICE 4-6 = low priority. ICE 7+ = run full decision matrix.

---

## RICE Scoring for Strategic Opportunity Ranking

More precise than ICE when you have effort data. Use when resource allocation is the core question.

| Opportunity | Reach | Impact | Confidence | Effort (person-months) | RICE Score |
|-------------|-------|--------|------------|----------------------|------------|
| ___ | ___ | ___ | ___ | ___ | **calc** |
| ___ | ___ | ___ | ___ | ___ | **calc** |

**RICE** = (Reach × Impact × Confidence) / Effort

**Reach**: Users/customers impacted per quarter (absolute number or 1-10 scale, consistent across rows)
**Impact**: 0.25 (minimal) / 0.5 (low) / 1 (medium) / 2 (high) / 3 (massive)
**Confidence**: 0.5 (low) / 0.8 (medium) / 1.0 (high)
**Effort**: Person-months to complete

---

## Pre-Mortem Analysis Template

Run this AFTER scoring but BEFORE committing. It catches the most common failure mode: decisions that optimize for success scenarios.

**Setup**: Tell your team "Imagine 12 months have passed. This decision failed spectacularly. What happened?"

```
## Pre-Mortem: [Decision Name]

### Failure Mode 1 (Most Likely)
- What went wrong: ___
- Which assumption was wrong: ___
- Early warning signal we could have detected: ___
- Mitigation to add to the plan: ___

### Failure Mode 2 (Most Catastrophic)
- What went wrong: ___
- Which assumption was wrong: ___
- Early warning signal we could have detected: ___
- Mitigation to add to the plan: ___

### Failure Mode 3 (Most Unexpected)
- What went wrong: ___
- Which assumption was wrong: ___
- Early warning signal we could have detected: ___
- Mitigation to add to the plan: ___

### Decision change
Does any failure mode change the recommended option? [yes/no]
If yes, which option becomes preferred: ___
```

**Real-but-anonymized example**: A SaaS company scored "build partner integrations" as their top ICE opportunity (score: 8.1). Pre-mortem revealed failure mode 2: "Partners deprioritize the integration after signing the agreement, leaving us with dead listings." Mitigation added: co-marketing commitment required before integration goes live. Decision unchanged, but execution plan materially different.

---

## Reversibility Classification

Apply before scoring. Changes how much analysis is warranted.

| Decision | Reversibility | Analysis Depth | Time Box |
|----------|--------------|----------------|----------|
| Hire a VP of Sales | Low — severance + disruption | Full matrix + pre-mortem | 2-4 weeks |
| New pricing tier | Medium — churn risk, but revertable | Full matrix | 1 week |
| A/B test new homepage | High — can roll back in hours | Skip matrix, just do it | 1 day |
| Acquire a company | Irreversible — culture + integration | Full matrix + pre-mortem + external validation | 4-12 weeks |
| New market entry (pilot) | High if scoped correctly | Matrix on go/no-go, light on details | 3-5 days |

**Classification test**: "If this turns out to be wrong, how long does it take to undo and what is the cost?" Under 2 weeks and under $10K: high reversibility. Over 6 months or over $100K: low reversibility.

---

## Anti-Patterns

### Criteria added after scoring
**What it looks like**: Team scores options, then someone says "shouldn't we also consider X?" and adds it — but only because option they preferred scored low.
**Detection**: Track criteria list from start of session. Any addition after first score row is filled = suspect.
**Fix**: Lock criteria before any scoring. New criteria trigger a full restart.

### Equal weighting as a default
**What it looks like**: 5 criteria, each gets 20% because "everything matters equally."
**Why wrong**: Hides real priorities. If cost and strategic fit genuinely matter equally, that is an unusual organization — say so explicitly. Usually it means the weighter avoided a political conversation about what actually matters.
**Fix**: Force-rank criteria first. Top criterion gets at least 2× weight of bottom criterion.

### Scoring without evidence
**What it looks like**: Team assigns scores in 60 seconds per criterion without citing data.
**Why wrong**: Scores become opinions wearing the costume of analysis.
**Fix**: Require a one-sentence evidence statement for any score above 7 or below 4. "I scored technical feasibility 3 because we have zero experience with Kubernetes and our last infrastructure project overran by 3x" is valid.

### Ignoring the default option
**What it looks like**: Matrix compares Option A vs. Option B but does not include "do nothing."
**Why wrong**: Every decision has a status quo. If the status quo scores higher than the options, that is the most important finding in the analysis.
**Fix**: Always include "do nothing / stay the course" as an explicit option.

---

## Detection Commands Reference

These are for use in structured workshops to spot rationalization in real time:

```bash
# Check if "do nothing" was included as an explicit option
# (manual review — check option list at top of decision doc)

# Check if criteria weights sum to 100%
python3 -c "weights=[30,25,20,15,10]; print('OK' if sum(weights)==100 else f'ERROR: sums to {sum(weights)}')"

# Check weighted scores for each option
python3 -c "
weights=[0.30,0.25,0.20,0.15,0.10]
option_a=[8,5,4,6,4]
score = sum(w*s for w,s in zip(weights,option_a))
print(f'Option A weighted: {score:.2f}')
"
```

---

## See Also

- `strategic-frameworks.md` — Porter's Five Forces, SWOT scoring, OKR alignment for market context
- `skills/decision-helper/SKILL.md` — lightweight decision support for technical choices
