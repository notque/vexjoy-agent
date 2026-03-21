---
name: decision-helper
description: |
  Weighted decision scoring framework for architectural and technology choices.
  Frames decisions with 2-4 options, scores against weighted criteria, detects
  close calls, and records decisions in the active ADR or task plan.

  Use when: "should I use X or Y", "which approach", "compare options",
  "trade-offs between", "help me decide", "evaluate alternatives"
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
---

# Decision Helper Skill

## Operator Context

This skill operates as an operator for structured decision-making, configuring Claude's behavior for weighted scoring of architectural and technology choices. Runs inline (no context fork) because users adjust criteria and weights interactively.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution
- **Option Limit**: Maximum 4 options. More than 4 = decompose into sub-decisions first
- **Close-Call Detection**: Always flag when top two options differ by <0.5 weighted score
- **No Gut Overrides**: If the matrix contradicts intuition, fix the criteria -- never override the math

### Default Behaviors (ON unless disabled)
- **Default Criteria**: Use the standard criteria table unless the user provides custom criteria
- **ADR Persistence**: Check `.adr-session.json` and append decision there; fall back to task plan
- **Score Justification**: Brief (1 sentence) justification for each score

### Optional Behaviors (OFF unless enabled)
- **Custom Criteria**: User replaces or supplements default criteria and weights
- **Sensitivity Analysis**: Re-score with adjusted weights to test recommendation stability
- **Skip Persistence**: Don't record the decision (for informal exploration)

---

## Instructions

### Step 1: Frame the Decision

**Goal**: Turn the user's question into a clear, scorable decision.

- State the decision in one sentence (e.g., "Which HTTP router should we use for the API service?")
- List 2-4 concrete options. If the user provides more than 4, help them eliminate or group options before proceeding
- Identify hard constraints that eliminate options immediately (e.g., "must be MIT licensed" eliminates Option C)

If the user's request is too vague to frame, ask clarifying questions. Do not guess at options.

**Gate**: Decision statement defined, 2-4 options listed, hard constraints applied.

### Step 2: Define Criteria

**Goal**: Establish what matters for this decision and how much.

Present the default criteria table. Ask the user if they want to adjust weights or add/remove criteria.

| Criterion | Weight | What It Measures |
|-----------|--------|-----------------|
| Correctness | 5 | Does it solve the actual problem? |
| Complexity | 3 | How much complexity does it add? (lower = better) |
| Maintainability | 3 | How easy to change/debug later? |
| Risk | 3 | What can go wrong? How bad is the failure mode? |
| Effort | 2 | Implementation time and difficulty |
| Familiarity | 2 | Team/user comfort with this approach |
| Ecosystem | 1 | Library support, documentation, community |

WHY these defaults: Correctness dominates because a wrong solution has zero value regardless of other factors. Complexity/Maintainability/Risk form a middle tier because they determine long-term cost. Effort/Familiarity are lower because they're temporary (teams learn, effort is one-time). Ecosystem is lowest because it rarely decides between otherwise-equal options.

**Gate**: Criteria and weights confirmed (default or custom).

### Step 3: Score Each Option

**Goal**: Rate each option against each criterion with justification.

Score every criterion 1-10 (1-3 poor, 4-6 adequate, 7-9 strong, 10 exceptional). Provide a one-sentence justification per score to prevent arbitrary numbers.

Calculate weighted score: `sum(score * weight) / sum(weights)`

**Gate**: All options scored, all scores justified, weighted scores calculated.

### Step 4: Analyze Results

**Goal**: Interpret the scores and provide a clear recommendation.

Apply these rules in order:

1. **No Good Option** (all weighted scores <6.0): Flag that none of the options are strong. Suggest the user explore alternatives or revisit constraints
2. **Close Call** (top two within 0.5): Flag as "close call -- additional factors should decide." Identify which criteria drive the difference and ask the user what matters most
3. **Clear Winner** (top option leads by >0.5): Recommend the winner. Note which high-weight criteria drove the result
4. **Dominant Option** (top option leads on ALL weight-5 criteria): Note the dominance -- this is a high-confidence recommendation

Present the output table:

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

**Recommendation**: Option A (7.0) — [key reasoning]
**Confidence**: High / Medium (scores within 0.5) / Low (no option >6.0)
```

**Gate**: Recommendation stated with confidence level. Close calls flagged.

### Step 5: Persist Decision

**Goal**: Record the decision for future reference.

Check for an active ADR session:

```bash
cat .adr-session.json 2>/dev/null
```

**If ADR exists**: Append a decision record (statement, options, winner, key reasoning, confidence, date) to the ADR's decisions section.

**If no ADR**: Note the decision in the active task plan (`plan/active/*.md`). If neither exists, present the record to the user for manual recording.

**Gate**: Decision recorded or presented. Workflow complete.

---

## Error Handling

### Error: "Too many options"
**Cause**: User presents 5+ options
**Solution**: Help decompose. Group similar options or eliminate clearly inferior ones first. Then score the remaining 2-4.

### Error: "Criteria don't fit this decision"
**Cause**: Default criteria aren't relevant (e.g., scoring a content strategy, not a technical choice)
**Solution**: Ask the user to define custom criteria. Suggest domain-appropriate alternatives.

### Error: "Scores feel wrong"
**Cause**: User disagrees with a score after seeing the matrix
**Solution**: Adjust the score and recalculate. The matrix is a tool for the user, not an authority over them. If many scores feel wrong, the criteria may need revisiting.

---

## Anti-Patterns

### Analysis Paralysis
**What it looks like**: User agonizes over whether Complexity should be weight 3 or 4
**Why wrong**: Weight differences of 1 rarely change the outcome. The framework exists to make decisions faster, not slower.
**Do instead**: Use defaults. Only customize weights when the user has a strong reason.

### False Precision
**What it looks like**: "Option A scores 7.21 vs Option B at 7.18, so A wins"
**Why wrong**: A 0.03 difference is noise. Scores are subjective estimates, not measurements.
**Do instead**: Close-call detection handles this. Scores within 0.5 are flagged as ties needing additional context.

### Gut Override
**What it looks like**: "The matrix says B, but I just feel like A is right"
**Why wrong**: If the matrix contradicts your intuition, the criteria or scores are wrong -- not the math. Overriding teaches you nothing about WHY your gut disagrees.
**Do instead**: Ask which criterion is missing or mis-weighted. Add it, re-score, and see if the matrix now agrees with intuition. If it does, you found the hidden factor. If it doesn't, trust the matrix.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The answer is obvious, no need to score" | Obvious answers don't need a skill; if you're here, it's not obvious | Run the full framework |
| "Close enough, just pick one" | Close calls deserve explicit acknowledgment, not hand-waving | Flag the close call, identify differentiating factors |
| "I'll adjust weights until my preferred option wins" | That's confirmation bias with extra steps | Set weights BEFORE scoring, don't adjust to fit a desired outcome |
| "This decision is too small for a matrix" | Then don't invoke the skill -- but if you did, commit to the process | Either skip the skill or run it fully |
