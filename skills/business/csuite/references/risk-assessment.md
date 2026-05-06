---
title: Risk Assessment — Pre-Mortem Analysis, Scenario Planning, Probability-Weighted Outcomes, Black Swan Identification
domain: strategic-decision
level: 3
skill: strategic-decision
---

# Risk Assessment Reference

> **Scope**: Structured risk assessment for CEO-level strategic decisions — pre-mortem templates, scenario planning matrices, probability-weighted expected value, and black swan identification. Use AFTER the decision matrix has selected an option and BEFORE committing resources. Does NOT cover project execution risk (see skills/project-evaluation/references/feasibility-scoring.md).
> **Version range**: Framework-agnostic — applies to market entry, partnership, acquisition, and major investment decisions.
> **Generated**: 2026-04-09 — validate probability estimates against current market data; gut-feel priors need external calibration.

---

## Overview

Strategic decisions are made with incomplete information. Risk assessment does not eliminate uncertainty — it makes uncertainty explicit so it can be priced into the decision. The most common failure is a decision that was scored correctly under a best-case scenario but was never tested against realistic downside cases. Pre-mortem analysis, scenario planning, and probability weighting are tools for stress-testing the winning option before commitment. Black swan identification catches the tail risks that structured frameworks miss because they are, by definition, outside the range of normal planning.

---

## Pre-Mortem Analysis Template

Run this AFTER selecting the winning option from the decision matrix, BEFORE committing budget or headcount.

**Setup**: Tell your team "Assume 18 months have passed. This decision failed. Not partially — badly. Revenue is down, a key relationship broke, or we reversed course publicly. What happened?"

```
## Pre-Mortem: [Decision Name]
## Date: [YYYY-MM-DD]
## Decision being stress-tested: [1 sentence description of the chosen option]

### Round 1: Individual brainstorm (silent, 10 minutes)
Each participant writes their top 3 failure modes independently.
(No discussion until all have written — anchoring bias prevention)

---

### Failure Mode Catalog (consolidated)

#### Failure Mode 1
- Scenario: [What happened in the world? Internal failure, external shock, or assumption error?]
- Which assumption was wrong: [The specific belief that was embedded in the original decision]
- Early warning signal: [What we could observe in months 1-3 that signals this is occurring]
- Detection trigger: [Specific metric, event, or threshold that would confirm this path]
- Mitigation: [What we add to the plan NOW to reduce probability or impact]
- Probability (1-10%): [Low/Medium/High or rough % if you have data]

#### Failure Mode 2
- Scenario: ___
- Which assumption was wrong: ___
- Early warning signal: ___
- Detection trigger: ___
- Mitigation: ___
- Probability: ___

#### Failure Mode 3
- Scenario: ___
- Which assumption was wrong: ___
- Early warning signal: ___
- Detection trigger: ___
- Mitigation: ___
- Probability: ___

### High-impact, low-probability failures (see black swan section)
- [Scenario that team said "this will never happen"]
- [Scenario that was immediately dismissed as "too extreme"]

### Pre-mortem summary
- Does any failure mode change the recommended option? [Yes / No]
- If Yes: which option becomes preferred, or what condition must be true before proceeding?
- Mitigations added to execution plan: [numbered list]
- New monitoring metrics added: [numbered list]
```

**Worked example** (SaaS company deciding to expand into EU market):

Failure Mode 1: Regulatory delay.
- Scenario: GDPR compliance requirements are stricter than legal review estimated. Full compliance requires 9 months, not 3. Launch delayed, sales team hired but generating no pipeline.
- Assumption wrong: Legal team used a competitor's compliance timeline without accounting for our data architecture.
- Early warning signal: Month 2 — data residency audit reveals gaps not in original scope.
- Mitigation added: Hire EU-based DPO before hiring sales team, not after.

Failure Mode 2: Currency risk compounds with sales cycle length.
- Scenario: EUR/USD shifts unfavorably during a 6-month enterprise sales cycle. Deals signed in EUR produce 12% less USD revenue than projected. Finance model breaks.
- Assumption wrong: EUR pricing was set at a fixed USD equivalent without currency hedging.
- Mitigation added: EUR contracts include currency adjustment clause at >8% movement.

---

## Scenario Planning Matrix

Use when the decision outcome depends heavily on external conditions that you cannot control.

**Step 1**: Identify the 2-3 most uncertain external variables (not the decision variables — the world variables).

```
## Scenario Matrix: [Decision Name]

### Key Uncertainties (choose the 2 most impactful and uncertain)
- Uncertainty A: [e.g., "Regulatory environment — favorable vs. unfavorable"]
- Uncertainty B: [e.g., "Market adoption speed — fast vs. slow"]

### Four Scenarios

| | Uncertainty A: Favorable | Uncertainty A: Unfavorable |
|-----|--------------------------|---------------------------|
| **Uncertainty B: Fast** | SCENARIO 1: Best case | SCENARIO 2: Regulatory headwind |
| **Uncertainty B: Slow** | SCENARIO 3: Patient build | SCENARIO 4: Worst case |
```

### Scenario Detail Sheets

For each scenario, fill in:

```
## Scenario [N]: [Name]
## Probability estimate: ___%

### What the world looks like
- [Uncertainty A description for this scenario]
- [Uncertainty B description for this scenario]
- [Any secondary effects]

### Our outcome in this scenario
- Revenue impact vs. plan: [+X% / -X% / +$Xm / -$Xm]
- Timeline impact: [ahead by X months / delayed by X months]
- Strategic position: [stronger / weaker / neutral] — why?

### Required adaptations
- [What we do differently if this scenario emerges]
- [Decision triggers: if signal Y appears, execute adaptation Z]

### Acceptable threshold
- Is this scenario acceptable given our constraints? [Yes / No / Conditional]
- If No: what would need to be true to make it acceptable?
```

**Probability check**: All four scenario probabilities must sum to 100%. If you cannot assign probabilities, the uncertainty is not well-defined enough for scenario planning — break it down further.

### Scenario Summary Table

| Scenario | Probability | Year 1 Revenue Impact | Strategic Outcome | Verdict |
|----------|-------------|----------------------|------------------|---------|
| 1: Best case | ___% | $___ | ___ | Accept |
| 2: Regulatory headwind | ___% | $___ | ___ | Accept / Conditional |
| 3: Patient build | ___% | $___ | ___ | Accept / Conditional |
| 4: Worst case | ___% | $___ | ___ | Accept / Reject |

**Decision rule**: If the weighted average outcome (probability × impact) is positive AND the worst-case scenario is survivable (company does not fail, strategic position does not collapse permanently), proceed with the decision. If worst-case is fatal, add structural protections before committing.

---

## Probability-Weighted Outcome Framework

Use when comparing a decision under uncertainty against a safer alternative.

```
## Probability-Weighted Expected Value: [Decision Name]

### Option A: [The strategic decision]

| Outcome | Probability | Value | Weighted Value |
|---------|-------------|-------|----------------|
| Upside (best 25%) | ___% | $___ | $___ |
| Base case | ___% | $___ | $___ |
| Downside (worst 25%) | ___% | $___ | $___ |
| Catastrophic | ___% | $___ | $___ |
| **Expected Value** | 100% | — | **$___** |

### Option B: [The safer alternative or "do nothing"]

| Outcome | Probability | Value | Weighted Value |
|---------|-------------|-------|----------------|
| Upside | ___% | $___ | $___ |
| Base case | ___% | $___ | $___ |
| Downside | ___% | $___ | $___ |
| **Expected Value** | 100% | — | **$___** |

### Comparison
Expected value difference (A - B): $___
Variance difference (A - B): $___ [Option A has higher/lower variance]
Recommendation: [choose based on EV if variance is acceptable; choose B if downside of A is survivability-threatening]
```

**Calibration pitfall**: Teams systematically overestimate "Upside" probability. Apply the outside view: across similar decisions in your industry, what fraction actually hit the upside case? Use that as your prior, then adjust for specifics.

---

## Black Swan Identification

Standard risk frameworks miss low-probability, high-impact events because they focus on the expected range of outcomes. Black swans are definitionally outside that range. This section forces deliberate attention to the tail.

### Black Swan Taxonomy for Strategic Decisions

| Category | Examples | How to Test for It |
|----------|----------|-------------------|
| **Technology discontinuity** | A new technology makes your core product irrelevant or dramatically reduces cost of entry | "What AI/automation capability, if it existed at 10× current performance, would make our strategy moot?" |
| **Regulatory shock** | A new law or enforcement action eliminates or transforms the market | "In which jurisdiction could a single regulator shut down our core model?" |
| **Key dependency failure** | A supplier, platform, or partner stops existing or changes terms dramatically | "What happens if [critical vendor/platform] doubles prices or exits the market?" |
| **Talent concentration** | Loss of 1-2 key people makes the strategy unexecutable | "If [critical person] left tomorrow, could we still execute?" |
| **Market definition shift** | Customers solve the problem in a completely different way | "What non-obvious substitute could eliminate the problem we're solving?" |
| **Macro shock** | Recession, currency crisis, pandemic, or geopolitical event changes the operating environment | "At what macroeconomic scenario does our plan require renegotiation?" |

### Black Swan Assessment Template

```
## Black Swan Log: [Decision Name]

For each category above, complete:

### Category: [Technology Discontinuity / Regulatory / etc.]

- Candidate event: [Specific scenario that would qualify]
- Probability: [Extremely low / Unmeasurable / "Will not happen in our planning horizon"]
- Impact if it occurs: [Catastrophic / Major / Manageable]
- Lead time to respond: [Days / Months / Years]
- Pre-commitment hedge: [Is there a low-cost action we can take now that reduces exposure?]
  - Yes: ___
  - No: [Accept the risk explicitly — document the conscious choice]

### Black Swan Investment Decision
- Total budget for black swan hedges: $___
  (Rule of thumb: 2-5% of decision budget for hedges; more than 5% = the "black swan" is not actually a tail risk)
- Hedges selected: ___
- Hedges explicitly declined: ___ [and why — this is as important as the ones accepted]
```

---

## Risk Register Integration

After pre-mortem, scenario planning, and black swan identification, consolidate into a risk register.

| Risk ID | Description | Probability (1-5) | Impact (1-5) | Risk Score (P×I) | Owner | Mitigation | Status |
|---------|-------------|------------------|--------------|-----------------|-------|------------|--------|
| R01 | ___ | ___ | ___ | ___ | ___ | ___ | Open |
| R02 | ___ | ___ | ___ | ___ | ___ | ___ | Mitigated |
| R03 | ___ | ___ | ___ | ___ | ___ | ___ | Accepted |

**Risk scoring interpretation**:
- Score 1-4: Accept (monitor only)
- Score 5-9: Mitigate (specific action required)
- Score 10-16: Address before committing (blocker if unresolved)
- Score 20-25: Escalate to board level or reverse decision

**Status definitions**:
- Open: Risk identified, no mitigation taken
- Mitigated: Specific action taken that reduces probability or impact
- Accepted: Explicitly decided not to mitigate — risk is within tolerance
- Closed: Risk condition no longer exists

---

## Patterns to Detect and Fix
<!-- no-pair-required: section header, not an individual anti-pattern -->

### Pre-mortem as validation exercise
**What it looks like**: Team runs pre-mortem but all proposed failure modes are minor and easily dismissed. The session feels like box-checking.
**Why wrong**: If your pre-mortem does not generate at least one uncomfortable insight — something that changes the plan or makes the team nervous — it was not conducted with intellectual honesty. Good pre-mortems hurt a little.
**Do instead**: Assign the most skeptical person in the room to lead Round 1. Give them explicit permission to name the failure mode everyone is privately thinking but not saying. The facilitator must reject any failure mode that does not name which assumption was wrong.
**Fix**: Require the most skeptical person in the room to lead Round 1. If no one is playing devil's advocate, assign the role explicitly. The facilitator should reject any failure mode that does not include "which assumption was wrong."

### Scenario planning without probability assignment
**What it looks like**: Four beautifully written scenarios with no probabilities. All scenarios treated as equally likely in discussion.
**Why wrong**: If all scenarios are equally likely, the expected value calculation cannot be done. The team defaults to discussing the most vivid scenario (usually worst-case) and either overcorrects or dismisses it.
**Do instead**: Assign probabilities before discussing any scenario's implications. Rough estimates ("~60%, ~20%, ~15%, ~5%") are sufficient. The disagreement that surfaces during assignment is more valuable than the scenarios themselves.
**Fix**: Require probability assignments before discussing scenario implications. Probabilities do not need to be precise — "~60%, ~20%, ~15%, ~5%" is enough. The act of assigning forces explicit disagreement about likelihood, which is more valuable than the scenarios themselves.

### Black swan conflated with low-probability planned risk
**What it looks like**: "The black swan scenario is that we only close 50% of our projected pipeline."
**Why wrong**: 50% pipeline miss is a normal risk, not a black swan. It belongs in the scenario planning matrix. Black swans are outside the planning range, not just the pessimistic end of the normal range.
**Do instead**: Apply the three-part black swan test before labeling any risk as one: it would not appear in a standard risk register, it falls outside the range of outcomes the team has experienced or planned for, and it would require a fundamentally different response rather than an adjusted plan. Everything else goes in the scenario matrix.
**Fix**: For a risk to qualify as a black swan, it must satisfy: (1) would not appear in a standard risk register, (2) is outside the range of outcomes the team has experienced or planned for, and (3) would require a fundamentally different response, not just an adjusted plan.

### Risk register without owners
**What it looks like**: 12-item risk register, all marked "Team" as owner.
**Why wrong**: Team ownership is no ownership. No one monitors the risk; no one detects early warning signals; no one escalates.
**Do instead**: Assign every risk to a single named individual before the register is considered complete. If no one will accept ownership of a high-probability risk, escalate it to the decision-maker immediately — that refusal is itself a signal worth surfacing.
**Fix**: Every risk in the register must have a single named individual as owner. If no one will own it, escalate the risk to decision-maker level immediately — unowned high-probability risks are the most dangerous items in any plan.

---

## Detection Commands Reference

```bash
# Check if pre-mortem was run for a decision (documentation audit)
grep -r "pre-mortem\|premortem\|failure mode" docs/decisions/ 2>/dev/null | head -20

# Check if risk register has unowned risks
# (For structured risk files in CSV format)
python3 -c "
import csv, sys
with open('risk_register.csv') as f:
    reader = csv.DictReader(f)
    unowned = [r for r in reader if not r.get('Owner') or r['Owner'] in ('Team', 'TBD', '')]
    print(f'Unowned risks: {len(unowned)}')
    for r in unowned:
        print(f'  {r[\"Risk ID\"]}: {r[\"Description\"]}')
" 2>/dev/null || echo "No risk_register.csv found — check decision docs"

# Calculate expected value from scenario probabilities
python3 -c "
scenarios = [
    ('Upside', 0.25, 500000),
    ('Base', 0.50, 200000),
    ('Downside', 0.20, -50000),
    ('Catastrophic', 0.05, -300000),
]
ev = sum(p * v for _, p, v in scenarios)
prob_check = sum(p for _, p, _ in scenarios)
print(f'Expected Value: \${ev:,.0f}')
print(f'Probability sum: {prob_check:.2f} (must be 1.0)')
"
```

---

## See Also

- `decision-matrices.md` — weighted scoring and pre-mortem integration with option selection
- `strategic-frameworks.md` — Porter's Five Forces and SWOT for market-level risk context
- `skills/project-evaluation/references/feasibility-scoring.md` — risk-adjusted feasibility for project execution risk
