---
name: project-evaluation
description: "Cross-role project evaluation: feasibility analysis, effort estimation, ROI assessment, priority ranking, go/no-go decisions."
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
    - "feasibility"
    - "is it worth"
    - "effort estimate"
    - "ROI"
    - "priority"
    - "should we start"
    - "project evaluation"
    - "go no go"
    - "viability"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# Project Evaluation Skill

## Overview

Cross-role project evaluation for feasibility analysis, effort estimation, ROI assessment, priority ranking, and go/no-go decisions. Turns "should we start this project?" into a structured assessment with a clear verdict.

**Scope**: Project feasibility, effort estimation, ROI analysis, project prioritization, go/no-go decisions for new initiatives. Do NOT use for strategic business decisions beyond project scope (use strategic-decision), technology selection (use build-vs-buy), or marketing/growth planning (use growth-strategy).

---

## Instructions

### Phase 1: SCOPE

**Goal**: Define what the project is and what success looks like before evaluating feasibility.

**Core Constraints**:
- **Define done before estimating effort** -- "build an app" is not a project; "ship a mobile app with user auth, 3 core screens, and push notifications by Q3" is a project
- **Separate the vision from the MVP** -- evaluate the minimum viable version, not the dream version; the dream version is always feasible "in theory" and never feasible in practice
- **Name the constraint** -- every project has a binding constraint (time, money, skills, attention); identify it early because it determines the evaluation framework

**Step 1: Define the project**

```markdown
## Project Definition

### What
- Project name: [descriptive name]
- One-sentence description: [what this project delivers]
- Success criteria: [how you know it worked -- be specific and measurable]

### Why
- Problem it solves: [what pain point or opportunity]
- Who benefits: [specific audience or stakeholder]
- Why now: [what makes this timely vs. "someday"]

### Constraints
- Timeline: [hard deadline or flexible?]
- Budget: [dollars, hours, or both]
- Team: [who does the work? what skills are available?]
- Dependencies: [what must exist before this can start?]
```

**Step 2: Define the MVP scope**

Strip the project to its minimum viable version:
- What is the smallest version that delivers the core value?
- What features can wait for v2?
- What would you cut if the timeline halved?

**Gate**: Project defined with measurable success criteria. MVP scope identified. Binding constraint named.

### Phase 2: EVALUATE

**Goal**: Assess feasibility, estimate effort, and calculate ROI.

**Core Constraints**:
- **Estimate in ranges, not points** -- "3 weeks" is false precision; "2-5 weeks, most likely 3" is honest
- **Include the hidden costs** -- maintenance, support, opportunity cost of not doing other things
- **ROI must compare against alternatives** -- a 200% ROI sounds great until the alternative project offers 500%

**Step 1: Feasibility assessment**

Evaluate across three dimensions:

```markdown
## Feasibility Assessment

### Technical Feasibility
- Can this be built with available technology? [yes / yes with risk / no]
- Are there unsolved technical problems? [list if any]
- What is the hardest technical challenge? [name it]
- Confidence: [High / Medium / Low]

### Resource Feasibility
- Do we have the skills? [yes / need to hire / need to learn]
- Do we have the time? [fits in schedule / requires trade-offs / impossible in timeline]
- Do we have the budget? [within budget / needs approval / exceeds capacity]
- Confidence: [High / Medium / Low]

### Market Feasibility (if applicable)
- Is there demand? [validated / assumed / unknown]
- Can we reach the audience? [established channel / need to build / unclear]
- Is the timing right? [market ready / too early / too late]
- Confidence: [High / Medium / Low]
```

**Step 2: Effort estimation**

Load reference files based on estimation needs:

| Signal | Reference to Load | Content |
|--------|-------------------|---------|
| Feasibility assessment, risk evaluation, go/no-go verdict | `references/feasibility-scoring.md` | Three-dimension feasibility model, confidence calibration, go/no-go decision tree |
| Effort estimation, ROI calculation, project comparison | `references/roi-frameworks.md` | T-shirt sizing, three-point estimation, risk-adjusted NPV, planning fallacy mitigation |

Break the MVP into work packages and estimate each:

```markdown
## Effort Estimate

| Work Package | Optimistic | Most Likely | Pessimistic |
|-------------|-----------|-------------|-------------|
| [package 1] | [days]    | [days]      | [days]      |
| [package 2] | [days]    | [days]      | [days]      |
| [package 3] | [days]    | [days]      | [days]      |
| **Total**   | **[sum]** | **[sum]**   | **[sum]**   |

### Hidden costs (add 20-40% to total)
- Learning curve: [hours for unfamiliar technology or domain]
- Integration: [hours for connecting with existing systems]
- Testing: [hours for quality assurance beyond unit tests]
- Documentation: [hours for user docs, runbooks, handoff]
```

**Step 3: ROI assessment**

```markdown
## ROI Assessment

### Value delivered
- Direct value: [revenue, cost savings, time saved -- quantify]
- Indirect value: [learning, positioning, capability building]
- Strategic value: [enables future projects, opens markets]

### Total cost
- Build cost: [effort estimate * rate]
- Ongoing cost: [maintenance hours/month * rate * 12 months]
- Opportunity cost: [what you cannot do while building this]

### ROI calculation
- Net value: [value - total cost]
- Payback period: [months until value exceeds cost]
- Confidence: [High / Medium / Low -- based on assumption quality]
```

**Gate**: Feasibility assessed across all dimensions. Effort estimated in ranges. ROI calculated with confidence level.

### Phase 3: VERDICT

**Goal**: Deliver a clear go/no-go recommendation with conditions.

**Step 1: Apply the verdict framework**

| Verdict | Criteria |
|---------|----------|
| **GO** | Feasible on all dimensions. ROI positive with medium+ confidence. Binding constraint manageable. |
| **GO WITH CONDITIONS** | Feasible but one dimension has medium confidence. Specify conditions that must be met before committing fully. |
| **DEFER** | Feasible but timing is wrong -- another project has higher ROI, or a dependency is not ready. Specify what triggers re-evaluation. |
| **NO-GO** | Not feasible on one or more dimensions, or ROI is negative/uncertain. Specify what would need to change for this to become viable. |

**Step 2: Produce the verdict**

```markdown
## Project Verdict: [project name]

**Verdict**: [GO / GO WITH CONDITIONS / DEFER / NO-GO]
**Confidence**: [High / Medium / Low]

### Summary
[2-3 sentences explaining the verdict]

### Key factors
- [Factor 1 that drove the verdict]
- [Factor 2 that drove the verdict]
- [Factor 3 that drove the verdict]

### Conditions (if GO WITH CONDITIONS)
- [Condition 1 that must be met]
- [Condition 2 that must be met]

### What would change this verdict
- [Condition 1 that would flip the decision]
- [Condition 2 that would flip the decision]

### Recommended next step
- [The one concrete action to take this week]
```

**Step 3: Priority ranking (when evaluating multiple projects)**

If the user is comparing multiple projects, rank them using RICE scoring:

| Project | Reach | Impact | Confidence | Effort | RICE Score |
|---------|-------|--------|------------|--------|------------|
| [A]     | [1-10]| [1-10] | [0.5-1.0]  | [weeks]| [calc]     |
| [B]     | [1-10]| [1-10] | [0.5-1.0]  | [weeks]| [calc]     |

RICE = (Reach * Impact * Confidence) / Effort

**Gate**: Verdict stated with confidence. Conditions specified if conditional. Next step identified.

---

## Error Handling

### Error: "Scope creep during evaluation"
**Cause**: User keeps adding features to the project definition during evaluation
**Solution**: Freeze the scope at the end of Phase 1. Evaluate what was defined. Additional features can be evaluated as a separate v2 project.

### Error: "Optimism bias"
**Cause**: Effort estimates are too low because the user assumes everything will go smoothly
**Solution**: Apply the "reference class" test. Ask: "How long did a similar project take last time?" If no similar project exists, add 50% to the pessimistic estimate. Humans systematically underestimate novel work.

### Error: "Sunk cost fallacy"
**Cause**: User has already started the project and resists a NO-GO verdict
**Solution**: Evaluate from today forward. Past investment is irrelevant to whether future investment is worthwhile. Frame it as: "Given where you are now, is continuing the best use of your next 100 hours?"

### Error: "Comparing incomparable projects"
**Cause**: User wants to rank a content project against a software project against a business partnership
**Solution**: Normalize to a common currency: hours of effort and expected value in dollars (or a proxy like "subscriber growth" or "capability unlocked"). Different project types can be compared if measured on the same axes.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/feasibility-scoring.md` | Feasibility assessment, risk evaluation, go/no-go criteria | Three-dimension feasibility model, risk-adjusted scoring, go/no-go decision tree |
| `references/roi-frameworks.md` | Effort estimation, ROI calculation, project comparison | T-shirt sizing, three-point estimation, risk-adjusted NPV, planning fallacy mitigation |
