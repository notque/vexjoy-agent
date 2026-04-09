---
title: ROI Frameworks — Calculation Templates, Effort Estimation, Risk-Adjusted NPV
domain: project-evaluation
level: 3
skill: project-evaluation
---

# ROI Frameworks Reference

> **Scope**: ROI calculation templates, effort estimation methods (T-shirt sizing, three-point estimation, story points), and risk-adjusted NPV analysis for project evaluation. Use when determining whether a project is worth the investment, and how to compare multiple projects.
> **Version range**: Framework-agnostic — applies to software, content, and business projects equally.
> **Generated**: 2026-04-09 — validate hourly rate assumptions against current market rates before using.

---

## Overview

ROI calculations fail most often from underestimating cost (planning fallacy) and overestimating value (optimism bias). The frameworks here combat both: three-point estimation forces pessimistic scenarios into view; risk-adjusted NPV applies a confidence haircut to value claims. The goal is not to predict the future precisely — it is to identify which projects are clearly worth doing, which are clearly not, and which genuinely require more information before deciding.

---

## ROI Calculation Template

Fill this out for every project before the go/no-go verdict.

```
## ROI Analysis: [Project Name]

### Value Delivered

#### Direct Value
- Revenue generated: $___ / quarter (source: ___)
- Cost savings: $___ / quarter (source: ___)
- Time saved × fully-loaded rate: ___ hours/quarter × $___/hour = $___ / quarter
- Annual direct value: $___

#### Indirect Value
- Strategic capability enabled: [describe, estimate order of magnitude if possible]
- Team learning / skill building: [hours × future productivity multiplier]
- Positioning / brand value: [low / medium / high — qualitative]
- Options value (enables future projects): [list what this unlocks]

### Total Cost

#### Build / Implementation Cost
- Engineering effort (from estimation below): ___ hours × $___/hour = $___
- Design effort: ___ hours × $___/hour = $___
- QA / testing: ___ hours × $___/hour = $___
- Infrastructure / tooling: $___
- One-time total: $___

#### Ongoing Cost (Annual)
- Maintenance engineering: ___ hours/month × 12 × $___/hour = $___
- Infrastructure recurring: $___/year
- Support burden: ___ hours/month × 12 × $___/hour = $___
- Annual ongoing total: $___

#### Opportunity Cost
- What the team CANNOT do while working on this: [list 1-2 projects]
- Estimated value of foregone projects: $___

### ROI Calculation

| | Year 1 | Year 2 | Year 3 |
|-|--------|--------|--------|
| Value delivered | $___ | $___ | $___ |
| Implementation cost | -$___ | — | — |
| Ongoing cost | -$___ | -$___ | -$___ |
| Opportunity cost | -$___ | — | — |
| **Net value** | **$___** | **$___** | **$___** |
| **Cumulative** | **$___** | **$___** | **$___** |

Payback period: ___ months (when cumulative net value first turns positive)
3-Year ROI: (Total value - Total cost) / Total cost × 100 = ____%
```

---

## Effort Estimation Methods

### Method 1: T-Shirt Sizing

Fast and useful for early-stage project evaluation or when comparing many projects.

| Size | Hours Range | Definition | Examples |
|------|------------|------------|---------|
| XS | 1-8 hours | Single task, no unknowns, solo work | Fix a bug, write a post, add a field to a form |
| S | 8-40 hours | Small feature or initiative, well-understood | Simple API endpoint, 1-week content sprint |
| M | 40-160 hours | Medium feature, some unknowns | New user flow, data migration, 1-month content series |
| L | 160-400 hours | Large feature, significant complexity | New product vertical, major architecture change |
| XL | 400-1000 hours | Program-level work, multiple unknowns | New product line, major platform migration |
| XXL | 1000+ hours | Full initiative requiring multiple teams | Company pivots, multi-year roadmap items |

**T-shirt sizing rules**:
1. Size against the MVP scope, not the final vision
2. If you cannot place it in a size, it is not scoped well enough yet
3. Anything L or above requires three-point estimation before committing

### Method 2: Three-Point Estimation (PERT)

Use for any project M or larger. Forces consideration of realistic pessimistic scenario.

```
## Three-Point Estimate: [Work Package Name]

Optimistic (O): ___ hours
  (Best realistic case — no surprises, team is available, dependencies ready)

Most Likely (M): ___ hours
  (What you would bet money on if you had to — moderate friction expected)

Pessimistic (P): ___ hours
  (What happens when 1-2 things go wrong — unexpected complexity, key person absent)

PERT estimate: (O + 4M + P) / 6 = ___ hours
Standard deviation: (P - O) / 6 = ___ hours (uncertainty range)

95% confidence range: PERT ± 2σ = ___ to ___ hours
```

**Worked example** (new onboarding flow, mid-level team):

```
O: 40 hours (team knows this codebase, no major surprises)
M: 80 hours (need to refactor old flow, some unknown edge cases)
P: 160 hours (auth library has undocumented behaviors; mobile edge cases)

PERT: (40 + 4×80 + 160) / 6 = 520 / 6 ≈ 87 hours
σ: (160 - 40) / 6 = 20 hours
95% range: 47 to 127 hours
```

Report as: "87 hours most likely, 95% confident it lands in 47-127 hours."

### Method 3: Reference Class Forecasting

Most accurate for software projects. Uses historical data instead of bottom-up estimation.

```
## Reference Class: [Project Type]

Find 3 similar past projects:
1. [Project name]: planned ___ hours, actual ___ hours, ratio: ___
2. [Project name]: planned ___ hours, actual ___ hours, ratio: ___
3. [Project name]: planned ___ hours, actual ___ hours, ratio: ___

Average overrun ratio: ___
(If no history: use 1.5× for known tech/team, 2.0× for novel tech/team)

Current estimate (bottom-up or T-shirt): ___ hours
Reference-class adjusted: ___ hours × overrun ratio = ___ hours
```

---

## Risk-Adjusted NPV Template

Use when comparing projects with different risk profiles. Accounts for probability of success.

```
## Risk-Adjusted NPV: [Project Name]

### Success probability estimate
- Technical risk (failure probability): ___%
- Market risk (lower adoption than expected): ___%
- Execution risk (team/timeline failure): ___%
- Combined success probability (multiply complements):
  P(success) = (1 - tech_risk) × (1 - market_risk) × (1 - execution_risk)
  P(success) = ___

### Expected value calculation
Base case NPV (from ROI template): $___
P(success) × Base case NPV = $___

Failure cost (sunk cost if project abandoned):
- Resources consumed: $___
- Opportunity cost: $___
P(failure) × Failure cost = $___

Risk-adjusted NPV = Expected value - Failure cost = $___
```

**Comparison table** (when evaluating multiple projects):

| Project | Base NPV | P(success) | Risk-Adj NPV | Effort | RICE Score |
|---------|---------|-----------|--------------|--------|-----------|
| Project A | $50K | 85% | $42.5K | 3 mo | 14.2 |
| Project B | $80K | 50% | $40K | 4 mo | 10.0 |
| Project C | $20K | 95% | $19K | 1 mo | 19.0 |

Project C wins on RICE despite lowest base NPV. Lower risk + shorter effort = highest return per month invested.

---

## Planning Fallacy Mitigation Techniques

| Technique | When to Use | Application |
|-----------|-------------|-------------|
| **Reference class forecasting** | Any project M or larger | Compare against 3+ similar past projects; use their actual-to-planned ratio |
| **Add 50% buffer to novel work** | First time team does this type of project | If team has never done X before, multiply estimate by 1.5 automatically |
| **Separate estimation from planning** | Before timeline commitment | Have someone who did no planning estimate independently; compare |
| **Pre-mortem** | Before final commitment | "We're at launch day and we're 2 months late. What happened?" |
| **Explicit unknowns list** | During estimation | List every assumption. Each assumption is a risk that should inflate the pessimistic estimate. |

---

## Story Points to Hours Conversion (For Agile Teams)

When estimates are in story points and you need hours for ROI calculation.

```
## Velocity Calibration

Team's average velocity: ___ points/sprint
Sprint length: ___ weeks
Team size: ___ engineers

Hours per sprint (total): team_size × sprint_length × 40 hours/week = ___ hours
Hours per story point: total_hours_per_sprint / velocity = ___ hours/point

Story point estimate: ___ points
Converted to hours: ___ points × ___ hours/point = ___ hours
```

**Warning**: Story point conversion is only meaningful for teams with 6+ sprints of stable velocity. New teams or teams with changing composition should not use this conversion.

---

## Anti-Patterns

### Planning fallacy (systematic underestimation)
**What it looks like**: "This will take 2 weeks." Team has never shipped a project of this complexity in under 6 weeks.
**Detection**: Compare the current estimate against historical actuals for similar projects. If this team has a history of 2× overruns, this estimate needs to be doubled before being used in ROI calculations.
**Fix**: Use reference class forecasting. Require the estimator to name the 3 most similar past projects and their actual completion times before finalizing any estimate.

### ROI calculated at fantasy scope
**What it looks like**: ROI analysis uses the full product vision (V3 feature set) but effort estimate uses MVP scope (V1 feature set). Value is dramatically overstated.
**Why wrong**: The ROI analysis and the effort estimate must use the same scope definition.
**Fix**: Explicitly verify that the "value delivered" section and the "build cost" section reference the same project definition before finalizing.

### Opportunity cost excluded from total cost
**What it looks like**: ROI shows positive return. But the team has 3 other projects that must be delayed to work on this. Those delayed projects have their own value.
**Why wrong**: Every yes is a no to something else. Excluding opportunity cost inflates apparent ROI.
**Fix**: Always include a "what won't get done" row in the cost section. If you cannot name what gets delayed, the capacity assumption is wrong.

### Ignoring ongoing cost in 3-year model
**What it looks like**: Year 1 implementation cost is $50K. Year 2 and Year 3 show $0 cost because "it's built."
**Why wrong**: Every system requires maintenance. Every piece of content requires updating. Even "done" projects consume support time.
**Rule**: Year 2-3 minimum ongoing cost = 15-20% of Year 1 implementation cost for software projects. For content: 20-30% of creation cost for curation and updating.

---

## See Also

- `feasibility-scoring.md` — feasibility scoring models and go/no-go decision framework
- `skills/build-vs-buy/references/tco-framework.md` — TCO analysis for technology procurement decisions
- `skills/strategic-decision/references/decision-matrices.md` — decision matrices for comparing projects
