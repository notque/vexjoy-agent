# Multi-Persona Critique — Templates, Examples, and Error Handling

## Phase 2: Persona Prompt Construction

For each persona, construct a prompt that includes:

1. **Identity block**: The persona's name, intellectual tradition, core values, evaluation criteria, and suspicions (from personas.md)
2. **Proposal block**: ALL proposals, numbered exactly as presented in Phase 1
3. **Rating requirement**: Rate each proposal as STRONG / PROMISING / WEAK / REJECT with 2-3 sentence justification per rating
4. **Ranking requirement**: Order all proposals from strongest to weakest
5. **Fairness mandate**: "Be 100% fair. If something is genuinely good, say so. If it's bad, say why with precision. Stay aligned with the evidence rather than forcing contrarianism."
6. **Output format**: Structured output matching the persona template from personas.md

## Phase 4: Consensus Matrix Template

```
| Proposal | Logician | Builder | Purist | User Advocate | Philosopher |
|----------|----------|---------|--------|---------------|-------------|
| 1. X     | STRONG   | STRONG  | WEAK   | PROMISING     | REJECT      |
| 2. Y     | PROMISING| STRONG  | STRONG | STRONG        | PROMISING   |
```

## Phase 5: Synthesis Report Sections

Load the synthesis template and populate all sections:

**Section 1: Consensus Matrix**
The full matrix from Phase 4, showing every proposal x persona x rating.

**Section 2: "The Features You Should Build"**
Proposals with unanimous or near-unanimous STRONG ratings (consensus score 12+). These have survived scrutiny from all 5 lenses.

**Section 3: "Worth Investigating"**
PROMISING consensus (score 8-11) with specific conditions extracted from critics. What would need to be true for these to become STRONG?

**Section 4: "Interesting Disagreements"**
CONTESTED proposals where personas diverge. Present both sides with the reasoning each persona used. Present the disagreement without forcing a premature resolution.

**Section 5: "Shelve"**
WEAK consensus (score 0-7) with brief reasons from the most critical personas. Not "bad ideas" — ideas that did not survive this particular gauntlet.

**Section 6: Cross-Cutting Insights**
Meta-observations that cut across multiple proposals:
- Themes the personas collectively surfaced
- Blind spots in the proposal set (what is missing?)
- Tensions between proposals (does building X undermine Y?)

**Section 7: The Deepest Insight**
What did the critics collectively reveal that was not obvious from any single perspective? This is the highest-value output of the entire exercise.

---

## Examples

### Example 1: Critique Provided Proposals
User says: "Critique these 4 feature ideas for the monitoring system"
```
skill: multi-persona-critique
```
Actions:
1. Extract and number the 4 proposals (Phase 1)
2. Construct 5 persona prompts, each containing all 4 proposals (Phase 2)
3. Launch 5 agents in parallel (Phase 3)
4. Build consensus matrix, classify patterns, rank proposals (Phase 4)
5. Present synthesis with agreement, disagreement, and cross-cutting insights (Phase 5)
Result: Consensus report showing which features survived philosophical scrutiny and why

### Example 2: Generate and Critique Ideas
User says: "Generate 6 ideas for improving the CI pipeline and critique them"
```
skill: multi-persona-critique generate 6 ideas about CI pipeline improvements
```
Actions:
1. Research the existing CI setup — read configs, workflows, scripts (Phase 1)
2. Generate 6 grounded proposals based on actual codebase context (Phase 1)
3. Brief and dispatch 5 personas on all 6 proposals (Phases 2-3)
4. Synthesize and present ranked consensus (Phases 4-5)
Result: Ideas generated from real context, then stress-tested from 5 philosophical angles

### Example 3: Evaluate Architectural Options
User says: "We're deciding between microservices and a modular monolith — stress test both"
```
skill: multi-persona-critique evaluate microservices vs modular monolith for our system
```
Actions:
1. Frame each option as a proposal with clear description (Phase 1)
2. Optionally add hybrid approaches as additional proposals (Phase 1)
3. Dispatch 5 personas to evaluate all options (Phases 2-3)
4. The consensus matrix reveals which option survives more lenses (Phases 4-5)
Result: Multi-lens comparison where disagreements highlight the real tradeoffs

---

## Patterns to Detect and Fix

| Pattern | Why It Matters | Preferred Action |
|--------------|----------------|-------------------|
| Averaging away disagreement | The disagreements ARE the insight | Preserve and present disagreements as first-class findings |
| Post-hoc rationalization of persona views | Each persona's output is final | Report persona outputs as-is; synthesize across them, do not edit them |
| Treating consensus as truth | 5 agents from the same model share blind spots | Note the consensus but acknowledge the shared-model limitation |
| Skipping the "why" | A rating without justification is worthless | Require 2-3 sentence justification for every rating |
| Resolving contested items for the user | The user needs to see the tension, not a premature resolution | Present both sides and let the user decide |
| Running personas sequentially | Sequential execution allows context bleed | Always use parallel dispatch |

---

## Error Handling

### Error: "Persona Returns Ratings Without Justification"
Cause: Agent produced bare STRONG/WEAK labels without reasoning
Solution:
1. Dismiss unjustified ratings — they cannot inform synthesis
2. Re-run that specific persona with explicit instruction to provide 2-3 sentence justifications
3. Never include bare ratings in the consensus matrix

### Error: "Persona Skips Proposals"
Cause: Agent rated only some proposals, not all
Solution:
1. Re-run that persona with explicit instruction: "You must rate ALL N proposals"
2. If re-run fails, note the gap in the consensus matrix with "NOT RATED"
3. Adjust consensus calculations to account for missing data

### Error: "All Personas Agree on Everything"
Cause: Insufficient persona differentiation or proposals are genuinely unambiguous
Solution:
1. Check that persona prompts included full identity and suspicion specifications
2. If prompts were correct, the agreement is genuine — report it but note the shared-model caveat
3. Consider suggesting user add a domain-specific sixth persona for a different lens

### Error: "User Provides Fewer Than 2 Proposals"
Cause: Not enough proposals for comparative ranking
Solution:
1. If 1 proposal: still run all 5 personas for depth, skip ranking, focus on ratings and justifications
2. Suggest user add alternatives: "Would you like me to generate 2-3 alternative approaches for comparison?"
