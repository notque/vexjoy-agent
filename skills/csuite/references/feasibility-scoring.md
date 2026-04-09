---
title: Feasibility Scoring — Models, Criteria, Weights, and Go/No-Go Frameworks
domain: project-evaluation
level: 3
skill: project-evaluation
---

# Feasibility Scoring Reference

> **Scope**: Feasibility scoring models with concrete criteria and weights, go/no-go decision frameworks, and risk-adjusted feasibility assessment. Use when evaluating whether a project should start, not when estimating effort (see roi-frameworks.md).
> **Version range**: Framework-agnostic — applies to software projects, content initiatives, business experiments, and infrastructure work.
> **Generated**: 2026-04-09 — validate scoring weights against your organization's actual constraint profile.

---

## Overview

Feasibility scoring fails when it is vague ("feasibility: high") or when it conflates feasibility with desirability. A project can be highly feasible (you can definitely build it) and deeply undesirable (nobody will use it). Separate these dimensions explicitly. The scoring models here produce a structured verdict across three independent dimensions: technical, resource, and market feasibility. Each dimension gets an independent confidence rating so you know where your uncertainty is concentrated.

---

## Three-Dimension Feasibility Scoring Model

Score each dimension independently on a 1-10 scale. Do not average them — each dimension is a separate gate.

### Dimension 1: Technical Feasibility

| Factor | Score (1-10) | Evidence / Notes |
|--------|-------------|-----------------|
| All required technologies exist and are proven | ___ | |
| Team has experience with core technical challenges | ___ | |
| Hardest technical problem has a known solution path | ___ | |
| Integration with existing systems is understood | ___ | |
| No unsolved research/novel engineering required | ___ | |
| Security and compliance approach is clear | ___ | |
| **Technical Feasibility Score (average)** | **___** | |
| **Confidence** | H / M / L | |

**Score interpretation**:
- 8-10: High technical feasibility. No material unknowns.
- 6-7: Medium. 1-2 technical risks exist; mitigations are possible.
- 4-5: Borderline. Significant unknowns; recommend spike/prototype first.
- 1-3: Low feasibility. Novel engineering or missing capabilities required.

### Dimension 2: Resource Feasibility

| Factor | Score (1-10) | Evidence / Notes |
|--------|-------------|-----------------|
| Team has required skills (or can hire/contract quickly) | ___ | |
| Timeline is achievable given current capacity | ___ | |
| Budget is allocated or approvable | ___ | |
| Dependencies are available when needed | ___ | |
| Key team members have capacity (not already overcommitted) | ___ | |
| **Resource Feasibility Score (average)** | **___** | |
| **Confidence** | H / M / L | |

### Dimension 3: Market / Demand Feasibility

| Factor | Score (1-10) | Evidence / Notes |
|--------|-------------|-----------------|
| Target audience has validated demand (not just assumed) | ___ | |
| Distribution channel to reach audience exists | ___ | |
| Timing is right (market ready; not too early, not too late) | ___ | |
| Success criteria can be measured within the timeline | ___ | |
| **Market Feasibility Score (average)** | **___** | |
| **Confidence** | H / M / L | |

---

## Feasibility Summary Table

| Dimension | Score (1-10) | Confidence | Gate Result |
|-----------|-------------|------------|-------------|
| Technical | ___ | H/M/L | PASS / FLAG / BLOCK |
| Resource | ___ | H/M/L | PASS / FLAG / BLOCK |
| Market | ___ | H/M/L | PASS / FLAG / BLOCK |

**Gate thresholds**:
- PASS: Score ≥ 7 with High or Medium confidence
- FLAG: Score 5-6, OR score ≥ 7 with Low confidence (must resolve uncertainty before committing)
- BLOCK: Score < 5 on any dimension — do not proceed until addressed

---

## Go / No-Go Decision Tree

```
START: All three dimensions scored

Is any dimension BLOCK (score < 5)?
├── YES → NO-GO
│       Specify: which dimension failed, what must change to re-evaluate
└── NO → Continue

Is any dimension FLAG?
├── YES → What is the flag type?
│   ├── Score 5-6 → GO WITH CONDITIONS
│   │   Specify: what must be validated before full commit
│   └── Score ≥ 7 but Low confidence → GO WITH CONDITIONS
│       Specify: what information would raise confidence to Medium+
└── NO → Continue

Are all three dimensions PASS?
├── YES → Does ROI justify proceeding?
│   ├── YES → GO
│   └── NO → DEFER (feasible but not worth it now)
└── NO → unreachable (handled above)
```

---

## Verdict Definitions

| Verdict | Criteria | Required Output |
|---------|----------|-----------------|
| **GO** | All 3 dimensions PASS, positive ROI | First action within 48 hours |
| **GO WITH CONDITIONS** | Any FLAG dimension | Named conditions + owner + deadline |
| **DEFER** | All PASS but ROI insufficient vs. alternatives | Trigger condition for re-evaluation |
| **NO-GO** | Any BLOCK dimension | Root cause + what must change |
| **SPIKE FIRST** | Technical dimension FLAG with Low confidence | 1-2 week prototype to resolve unknowns |

---

## Risk-Adjusted Feasibility Model

Use when a dimension has Medium or Low confidence. Adjusts the effective score for risk.

```
## Risk Adjustment Formula

Risk-adjusted score = Raw score × Confidence multiplier

Confidence multipliers:
- High confidence: 1.0 (no adjustment)
- Medium confidence: 0.85 (15% haircut)
- Low confidence: 0.65 (35% haircut)

Example:
Technical score: 7.5 (raw)
Confidence: Low
Risk-adjusted score: 7.5 × 0.65 = 4.9 → changes PASS to BLOCK
```

**Worked example** (new SaaS feature — async video review):

| Dimension | Raw | Confidence | Multiplier | Adjusted | Gate |
|-----------|-----|------------|------------|----------|------|
| Technical | 8.2 | High | 1.0 | 8.2 | PASS |
| Resource | 6.0 | Medium | 0.85 | 5.1 | FLAG |
| Market | 7.5 | Low | 0.65 | 4.9 | BLOCK |

Pre-adjustment verdict: GO. Post-adjustment verdict: NO-GO pending market validation.
Action: Run a 2-week user interview sprint to validate demand before committing engineers. Market score must reach 6.0+ with Medium confidence before re-evaluating.

---

## Rapid Feasibility Check (< 30 minutes)

For low-stakes decisions where full scoring would be overkill.

```
## Rapid Feasibility (5 questions)

1. Can this be built with technology the team already knows?
   YES / NO / UNSURE

2. Does the team have the time to do this without dropping other commitments?
   YES / NO / UNSURE

3. Is there evidence that people want this (conversations, search data, existing requests)?
   YES / NO / UNSURE

4. Can this be completed in the available timeline?
   YES / NO / UNSURE

5. If we started this and it failed, what is the worst-case impact?
   LOW (embarrassment) / MEDIUM (wasted weeks) / HIGH (significant cost or damage)

Verdict:
- 4-5 YES answers + LOW/MEDIUM worst-case → GO
- 3 YES answers OR 1+ UNSURE on questions 1-2 → SPIKE or CONDITIONS
- 2 or fewer YES answers → NO-GO or DEFER
- HIGH worst-case → full scoring model required before deciding
```

---

## Confidence Level Calibration

Use these anchors to score confidence consistently:

| Confidence | What It Means | Evidence Examples |
|------------|---------------|------------------|
| **High** | You have directly validated this claim | Customer interviews, historical data from similar projects, working prototype |
| **Medium** | You have indirect evidence or analogies | Industry benchmarks, team experience with similar work, positive conversations |
| **Low** | You are reasoning from first principles | No comparable data, novel market, new technology, team has never done this type of work |

**Warning**: Teams consistently rate confidence too high. If you have not spoken directly to potential users in the last 30 days, market feasibility confidence is at most Medium. If the technical approach has never been tested by your team, technical confidence is at most Medium.

---

## Anti-Patterns

### Feasibility conflated with desirability
**What it looks like**: "We can build it, so it's feasible." Team with strong engineering capability scores technical feasibility 9 for everything, ignoring whether the market wants it.
**Why wrong**: Feasibility and desirability are orthogonal. The most common startup failure is a product that was technically feasible and built on time, that nobody wanted.
**Fix**: Require three separate dimension scores. A project that is technically feasible but has market feasibility below 5 is a NO-GO, regardless of engineering capability.

### Feasibility assessed at vision scope, not MVP scope
**What it looks like**: "We can't build a real-time collaboration tool — that's too hard." But the MVP is just shared document state with 5-second polling, which is straightforward.
**Why wrong**: Feasibility must be assessed against the specific, scoped version of the project — the MVP — not the aspirational full version.
**Fix**: Before scoring, confirm the project definition is frozen at MVP scope (from Phase 1 of project-evaluation SKILL.md). Re-score when scope changes.

### High confidence on everything
**What it looks like**: All three dimensions rated High confidence. Team is decisive and agrees.
**Why wrong**: If you have not validated assumptions through direct evidence, high confidence is overconfidence. Teams in alignment often reinforce each other's assumptions rather than challenging them.
**Detection**: Ask "what evidence do we have that this is true?" for each High confidence rating. If the answer is "we believe" or "we've discussed," confidence is actually Medium.

---

## See Also

- `roi-frameworks.md` — ROI calculation templates, effort estimation, risk-adjusted NPV
- `skills/project-evaluation/SKILL.md` — full project evaluation workflow with RICE scoring
