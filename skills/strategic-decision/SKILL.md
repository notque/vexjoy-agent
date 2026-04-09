---
name: strategic-decision
description: "CEO-level strategic decision support: market entry, partnerships, resource allocation, opportunity evaluation."
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
    - "should I"
    - "should we"
    - "evaluate opportunity"
    - "decision"
    - "trade-off"
    - "worth it"
    - "invest in"
    - "strategy"
    - "strategic"
  pairs_with: []
  complexity: Medium
  category: decision-support
---

# Strategic Decision Skill

## Overview

CEO-level decision support for business strategy: market entry, partnerships, resource allocation, opportunity evaluation, and strategic pivots. Uses a structured framework to move from fuzzy intent to a clear, reasoned recommendation.

**Scope**: Business decisions with meaningful consequences -- market entry, partnerships, product direction, resource allocation, investment of time or money, strategic pivots. Do NOT use for technical architecture choices (use build-vs-buy or decision-helper), content strategy (use growth-strategy), or project feasibility (use project-evaluation).

---

## Instructions

### Phase 1: FRAME

**Goal**: Convert the user's question into a structured decision with clear stakes and timeline.

**Core Constraints**:
- **Name the actual decision** -- users often present symptoms ("should I learn Rust?") when the real decision is broader ("should I expand into systems programming?")
- **Identify the irreversibility** -- reversible decisions deserve less analysis; irreversible decisions deserve more
- **Set a time horizon** -- a 3-month decision and a 3-year decision need different frameworks

**Step 1: Clarify the decision**

Ask the user to state:
- What are you deciding between? (2-4 concrete options)
- What happens if you do nothing? (the default path has its own risks)
- When must this be decided? (urgency drives analysis depth)
- What makes this hard? (the tension that creates the decision)

If the user cannot articulate options, help them generate 2-3 plausible paths before proceeding. Never evaluate a single option in isolation -- comparison reveals what matters.

**Step 2: Classify the decision type**

| Type | Signal | Framework Emphasis |
|------|--------|--------------------|
| **Expansion** | "Should we enter...", "new market", "new product" | Market analysis, resource requirements, opportunity cost |
| **Partnership** | "Should we work with...", "partner", "collaborate" | Alignment, dependency risk, value exchange |
| **Allocation** | "Where should I spend...", "invest time", "focus on" | Opportunity cost, ROI comparison, constraint identification |
| **Pivot** | "Should we change...", "switch to", "abandon" | Sunk cost awareness, switching cost, future value |
| **Timing** | "Should we do this now...", "wait", "when to" | Market timing, readiness, cost of delay |

**Gate**: Decision framed as one sentence. Options listed (2-4). Type classified. Proceed only when gate passes.

### Phase 2: ANALYZE

**Goal**: Evaluate each option through multiple lenses with evidence, not opinion.

**Core Constraints**:
- **Separate facts from assumptions** -- label each clearly; assumptions need validation before they can drive decisions
- **Quantify where possible** -- "significant revenue" is noise; "$50K ARR in 12 months" is a testable claim
- **Name the opportunity cost** -- every option chosen means other options not chosen; make this explicit

**Step 1: For each option, assess these dimensions**

```markdown
## Option: [name]

### Upside
- What is the best realistic outcome? (not the fantasy scenario)
- What is the expected outcome? (most likely result)
- What evidence supports this assessment?

### Downside
- What is the worst realistic outcome?
- What is the recovery path if this fails?
- What do you lose that you cannot get back? (time, money, reputation, relationships)

### Requirements
- What resources does this need? (time, money, skills, attention)
- What must be true for this to work? (assumptions to validate)
- What dependencies does this create?

### Opportunity Cost
- What can you NOT do if you choose this?
- What other options does this foreclose?
```

**Step 2: Apply relevant analysis lenses**

Load reference files based on decision type:

| Signal | Reference to Load | Content |
|--------|-------------------|---------|
| Financial projections, revenue, cost modeling | `references/financial-models.md` | ROI frameworks, break-even analysis, financial projection templates |
| Risk assessment, downside scenarios, failure modes | `references/risk-frameworks.md` | Risk matrices, pre-mortem analysis, scenario planning |
| Market entry, competitive dynamics, positioning | `references/market-analysis.md` | Market sizing, TAM/SAM/SOM, competitive landscape frameworks |

**Gate**: All options analyzed across dimensions. Facts and assumptions labeled. Opportunity costs explicit.

### Phase 3: DECIDE

**Goal**: Synthesize the analysis into a clear recommendation with stated confidence.

**Step 1: Apply the reversibility test**

- **One-way door** (irreversible): Require high confidence. If confidence is not high, recommend the smallest testable step instead of the full commitment
- **Two-way door** (reversible): Recommend acting faster with a checkpoint. Define the checkpoint trigger ("if X hasn't happened by date Y, revisit")

**Step 2: Produce the recommendation**

```markdown
## Recommendation

**Decision**: [one sentence]
**Recommended option**: [name]
**Confidence**: High / Medium / Low

### Why this option
- [2-3 key reasons, tied to the analysis]

### What must be true
- [assumptions that would invalidate this recommendation if wrong]

### First move
- [the smallest concrete action to take within 48 hours]

### Revisit trigger
- [the condition or date that should prompt re-evaluation]
```

**Step 3: Identify what would change your mind**

State explicitly: "This recommendation changes if..." followed by 2-3 conditions. This transforms the decision from static to adaptive -- the user knows when to re-evaluate instead of second-guessing indefinitely.

**Gate**: Recommendation stated with confidence level. Reversibility classified. First action identified. Revisit trigger set.

---

## Error Handling

### Error: "Too many options"
**Cause**: User presents 5+ options, creating decision paralysis
**Solution**: Help eliminate obviously inferior options first. Group similar options. Get to 2-4 before running the full framework.

### Error: "Not enough information"
**Cause**: User cannot answer framing questions
**Solution**: Identify the 2-3 most critical unknowns. Recommend a time-boxed research sprint to answer those specific questions before deciding.

### Error: "Analysis paralysis"
**Cause**: User keeps adding criteria or second-guessing scores
**Solution**: Apply the reversibility test. If the decision is reversible, recommend the best current option with a checkpoint. If irreversible, help identify the single most important unknown and how to resolve it.

### Error: "Emotional attachment to an option"
**Cause**: User has already decided but wants validation
**Solution**: Name the pattern directly. Ask: "It sounds like you're leaning toward X. Should we stress-test that choice specifically, or genuinely evaluate all options?" Either answer is valid -- sometimes people need confirmation, sometimes they need a reality check.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/financial-models.md` | Financial projections, revenue modeling, cost analysis | ROI frameworks, break-even analysis, projection templates |
| `references/risk-frameworks.md` | Risk assessment, downside scenarios, failure modes | Risk matrices, pre-mortem techniques, scenario planning |
| `references/market-analysis.md` | Market entry, competitive dynamics, positioning decisions | Market sizing, TAM/SAM/SOM, competitive landscape frameworks |
