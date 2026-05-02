---
name: decision-helper
description: "Weighted decision scoring for architectural choices."
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
    - "weigh options"
    - "decision matrix"
    - "compare approaches"
    - "help me decide"
    - "pros and cons"
    - "trade-offs"
    - "which is better"
    - "should I use"
    - "evaluate options"
  category: process
  pairs_with:
    - multi-persona-critique
    - adr-consultation
    - planning
---

# Decision Helper Skill

Structured weighted scoring for architectural and technology choices. Runs inline (no context fork) -- users adjust criteria and weights interactively.

## Instructions

### Step 1: Frame the Decision

**Goal**: Turn the question into a clear, scorable decision.

- State the decision in one sentence
- List 2-4 concrete options. More than 4: help eliminate or group before proceeding -- larger matrices dilute focus and invite paralysis
- Identify hard constraints that eliminate options immediately (e.g., "must be MIT licensed")

If the request is too vague, ask clarifying questions. Do not guess at options. Run the full framework even when a quick answer feels tempting.

**Gate**: Decision defined, 2-4 options listed, hard constraints applied.

### Step 2: Define Criteria

**Goal**: Establish what matters and how much.

Present default criteria unless the user provides custom ones. Ask if they want to adjust.

| Criterion | Weight | What It Measures |
|-----------|--------|-----------------|
| Correctness | 5 | Does it solve the actual problem? |
| Complexity | 3 | How much complexity does it add? (lower = better) |
| Maintainability | 3 | How easy to change/debug later? |
| Risk | 3 | What can go wrong? How bad is the failure mode? |
| Effort | 2 | Implementation time and difficulty |
| Familiarity | 2 | Team/user comfort with this approach |
| Ecosystem | 1 | Library support, documentation, community |

Correctness dominates because a wrong solution has zero value. Complexity/Maintainability/Risk are long-term cost. Effort/Familiarity are temporary. Ecosystem rarely decides between otherwise-equal options.

Use defaults unless strong reason to change. Set weights before scoring -- adjusting weights after seeing results to make a preferred option win is confirmation bias.

For sensitivity analysis, re-score with adjusted weights after the initial pass to test stability.

**Gate**: Criteria and weights confirmed.

### Step 3: Score Each Option

**Goal**: Rate each option 1-10 per criterion with justification.

Score 1-3 poor, 4-6 adequate, 7-9 strong, 10 exceptional. One-sentence justification per score.

Calculate: `sum(score * weight) / sum(weights)`

Scores are subjective estimates. A 0.03 difference is noise, not signal.

**Gate**: All options scored, all scores justified, weighted scores calculated.

### Step 4: Analyze Results

**Goal**: Interpret scores and recommend.

Apply in order:

1. **No Good Option** (all <6.0): Flag. Suggest alternatives or revisiting constraints.
2. **Close Call** (top two within 0.5): Flag as "close call -- additional factors should decide." Identify which criteria drive the difference. Never dismiss with "just pick one."
3. **Clear Winner** (leads by >0.5): Recommend. Note which high-weight criteria drove it.
4. **Dominant Option** (leads on ALL weight-5 criteria): Note dominance -- high-confidence recommendation.

If the matrix contradicts intuition, do not override the math. Ask which criterion is missing or mis-weighted. Add it, re-score. If still disagrees, trust the matrix.

```
## Decision: [statement]

| Criterion (weight) | Option A | Option B | Option C |
|---------------------|----------|----------|----------|
| Correctness (5)     | 8        | 7        | 9        |
| Complexity (3)      | 6        | 8        | 4        |
| Maintainability (3) | 7        | 7        | 5        |
| Risk (3)            | 6        | 8        | 4        |
| Effort (2)          | 7        | 5        | 3        |
| Familiarity (2)     | 8        | 4        | 2        |
| Ecosystem (1)       | 7        | 6        | 8        |
| **Weighted Score**  | **7.0**  | **6.7**  | **5.2**  |

**Recommendation**: Option A (7.0) -- [key reasoning]
**Confidence**: High / Medium (scores within 0.5) / Low (no option >6.0)
```

**Gate**: Recommendation stated with confidence. Close calls flagged.

### Step 5: Persist Decision

**Goal**: Record the decision for future reference.

```bash
cat .adr-session.json 2>/dev/null
```

**If ADR exists**: Append decision record (statement, options, winner, reasoning, confidence, date).

**If no ADR**: Note in active task plan (`plan/active/*.md`). If neither exists, present the record to the user.

User can skip persistence for informal exploration.

**Gate**: Decision recorded or presented. Workflow complete.

---

## Error Handling

### Error: "Too many options"
**Cause**: 5+ options
**Solution**: Group similar options or eliminate clearly inferior ones. Score remaining 2-4.

### Error: "Criteria don't fit this decision"
**Cause**: Default criteria irrelevant (e.g., scoring a content strategy)
**Solution**: Ask for custom criteria. Suggest domain-appropriate alternatives.

### Error: "Scores feel wrong"
**Cause**: User disagrees with a score
**Solution**: Adjust and recalculate. If many feel wrong, revisit criteria.

---

## References

- Repository CLAUDE.md files (read before execution for project-specific constraints)

### Reference Loading Table

| Signal | Reference File | What It Adds |
|--------|---------------|-------------|
| "build vs buy", "vendor", "SaaS", "self-host", database, cloud provider, framework, library, API design | `references/decision-archetypes.md` | Archetype-specific weight adjustments, hard-constraint checklists, detection commands |
| User adjusts weights after scoring, adds options mid-scoring, scores feel arbitrary | `references/decision-preferred-patterns.md` | Anti-pattern identification, intervention scripts, error-fix mappings |
| 5+ options, close call (<0.5 margin), repeated score changes | `references/decision-preferred-patterns.md` | Structural anti-patterns and fixes |
