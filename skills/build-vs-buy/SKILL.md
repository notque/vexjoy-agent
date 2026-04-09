---
name: build-vs-buy
description: "CTO-level technology decisions: build vs buy, vendor evaluation, architecture choices, tech stack selection."
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
    - "build or buy"
    - "build vs buy"
    - "vendor evaluation"
    - "adopt"
    - "SaaS vs"
    - "technology choice"
    - "tech stack"
    - "architecture decision"
    - "should we use"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# Build vs Buy Skill

## Overview

CTO-level decision support for technology choices: build internally vs adopt SaaS/OSS, vendor evaluation, architecture decisions, and tech stack selection. Cuts through vendor marketing and internal bias to reach the decision that actually serves the project.

**Scope**: Technology adoption decisions, vendor evaluation, build-vs-buy trade-offs, architecture choices that involve external dependencies. Do NOT use for pure business strategy (use strategic-decision), content/marketing decisions (use growth-strategy), or general project feasibility (use project-evaluation).

---

## Instructions

### Phase 1: SCOPE

**Goal**: Define exactly what capability is needed, stripped of solution bias.

**Core Constraints**:
- **Start with the need, not the product** -- "we need Kafka" is a solution; "we need reliable async message delivery between 3 services" is a need
- **Quantify the requirements** -- "scalable" is meaningless; "handle 10K messages/second with 99.9% delivery guarantee" is a requirement
- **Identify the real driver** -- sometimes "build vs buy" is actually "build vs convince management to buy" or "buy vs hire someone who can build"

**Step 1: Define the capability needed**

```markdown
## Capability Needed
- What problem does this solve? (in one sentence)
- Who uses it? (internal team, end users, both)
- What are the hard requirements? (latency, throughput, compliance, etc.)
- What is the timeline? (need it next week vs next quarter)
- What is the budget constraint? (time, money, team capacity)
```

**Step 2: Identify the real options**

Most "build vs buy" decisions actually have 3-5 options:

| Option Type | Example |
|-------------|---------|
| Build from scratch | Write a custom solution in-house |
| Build on OSS | Use an open-source project as a foundation, customize it |
| Buy SaaS | Pay for a managed service |
| Buy + customize | License software and extend it |
| Do nothing | Accept the current limitation |

List the actual options available. Include "do nothing" when the status quo is survivable -- it forces honest comparison against the pain of change.

**Gate**: Capability defined without solution bias. Options enumerated. Hard requirements quantified.

### Phase 2: EVALUATE

**Goal**: Score each option on the dimensions that actually matter for technology decisions.

**Core Constraints**:
- **Total cost of ownership, not sticker price** -- the SaaS that costs $500/month but saves 20 hours/month of engineering time is cheap; the "free" OSS that needs a full-time engineer to operate is expensive
- **Evaluate at year 3, not day 1** -- building is cheap to start and expensive to maintain; buying is expensive to start and cheap to maintain; this inverts over time
- **Weight team reality** -- a theoretically superior solution that nobody on the team can operate is inferior to a simpler solution that the team can run confidently

**Step 1: Total Cost of Ownership analysis**

For each option, estimate:

```markdown
## TCO: [option name]

### Year 1
- Implementation cost: [hours * rate, or license + integration cost]
- Operational cost: [hosting, maintenance, monitoring hours]
- Hidden costs: [training, migration, integration with existing systems]

### Year 2-3 (annual)
- Ongoing license/hosting: [recurring costs]
- Maintenance burden: [hours/month for updates, patches, scaling]
- Opportunity cost: [what the team cannot do while maintaining this]

### 3-Year Total: [$X or Y engineering-hours]
```

Load `references/tco-framework.md` for detailed TCO calculation templates when financial rigor is needed.

**Step 2: Evaluate on core dimensions**

| Dimension | Weight | What to Assess |
|-----------|--------|----------------|
| Fit | 5 | Does it solve the actual problem? Gaps that need workarounds? |
| TCO | 4 | 3-year total cost including hidden costs |
| Operational burden | 4 | Who runs it? How much ongoing effort? What breaks at 3 AM? |
| Team capability | 3 | Can the team build/operate this? Learning curve? |
| Lock-in risk | 3 | How hard is it to switch later? Data portability? |
| Time to value | 3 | How quickly does the team get the capability? |
| Flexibility | 2 | Can it adapt to future needs? Extensibility? |

Load reference files based on evaluation needs:

| Signal | Reference to Load | Content |
|--------|-------------------|---------|
| Detailed TCO modeling, cost projections, build vs buy scorecard | `references/tco-framework.md` | TCO templates, hidden cost checklists, migration cost models |
| Vendor comparison, evaluation criteria, integration complexity | `references/vendor-evaluation.md` | Vendor scorecards, RFP criteria, red flag detection, contract checklist |

**Step 3: Apply the build-vs-buy heuristic**

| Factor | Favors Build | Favors Buy |
|--------|-------------|------------|
| Core competency | This IS our product differentiator | Commodity capability we need but don't compete on |
| Requirements stability | Requirements change monthly | Requirements are well-understood and stable |
| Team capacity | Team has capacity and expertise | Team is at capacity or lacks domain expertise |
| Timeline | No urgency, can invest in quality | Need it operational within weeks |
| Scale | Predictable, modest scale | Unpredictable or massive scale (vendor handles elasticity) |
| Compliance | Internal data control required | Vendor has certifications you'd need years to obtain |

**Gate**: TCO estimated for each option. Dimensions scored. Build-vs-buy heuristic applied.

### Phase 3: RECOMMEND

**Goal**: Deliver a clear recommendation with the reasoning that supports it.

**Step 1: Synthesize the evaluation**

Present the scoring matrix:

```markdown
## Evaluation: [capability needed]

| Dimension (weight) | Build | OSS + Customize | Buy SaaS |
|--------------------|-------|-----------------|----------|
| Fit (5)            | 9     | 7               | 6        |
| TCO (4)            | 4     | 6               | 7        |
| Ops burden (4)     | 3     | 5               | 8        |
| Team capability (3)| 7     | 6               | 8        |
| Lock-in risk (3)   | 9     | 7               | 4        |
| Time to value (3)  | 3     | 5               | 9        |
| Flexibility (2)    | 9     | 7               | 4        |
| **Weighted Score**  | **5.8** | **6.0**       | **6.5**  |
```

**Step 2: State the recommendation**

```markdown
## Recommendation

**Decision**: [capability] -- [build / buy / OSS]
**Confidence**: High / Medium / Low

### Why this option
- [2-3 key factors that drove the recommendation]

### Watch for
- [1-2 risks specific to this option]

### Migration path
- [How to switch if this doesn't work out]

### First step
- [The concrete next action within one week]
```

**Step 3: Define the exit criteria**

For any technology adoption, define when to reconsider:
- **Buy**: "Reconsider building when monthly cost exceeds $X or vendor fails SLA 3+ times"
- **Build**: "Reconsider buying when maintenance exceeds X hours/month or the team lacks capacity"
- **OSS**: "Reconsider when upstream project stalls (no release in 6+ months) or security patches lag"

**Gate**: Recommendation stated. Exit criteria defined. First step identified.

---

## Error Handling

### Error: "Comparing apples to oranges"
**Cause**: Options at different abstraction levels (comparing a database to a SaaS platform)
**Solution**: Normalize to the capability level. Compare what each option gives you for the specific capability needed, not the products as wholes.

### Error: "Vendor lock-in fear dominates"
**Cause**: User over-weights lock-in risk and under-weights time-to-value
**Solution**: Quantify the actual switching cost. Often "lock-in" means "6 weeks of migration work," which is far less scary than the abstract fear. Compare the concrete switching cost against the concrete benefit of moving faster now.

### Error: "Build bias" (NIH syndrome)
**Cause**: Team wants to build because building is more interesting than integrating
**Solution**: Apply the "core competency" test directly. Ask: "If this capability disappeared tomorrow, would your customers notice?" If no, it is not a differentiator and building it is engineering tourism.

### Error: "Sunk cost on existing solution"
**Cause**: Team has invested heavily in current approach and resists switching
**Solution**: Ignore past investment. Evaluate only from today forward: given where you are now, which path has the best outcome? Past costs are spent regardless of the decision.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/tco-framework.md` | TCO analysis, cost projections, build vs buy decision scorecard | TCO calculation templates, hidden cost checklists, migration cost models |
| `references/vendor-evaluation.md` | Vendor comparison, RFP evaluation, integration complexity scoring | Vendor scorecards, RFP criteria matrices, red flag detection, contract checklist |
