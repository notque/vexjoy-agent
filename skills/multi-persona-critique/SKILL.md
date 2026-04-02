---
name: multi-persona-critique
description: "Parallel critique of proposals via 5 philosophical personas with consensus synthesis."
version: 1.0.0
user-invocable: true
argument-hint: "<proposals to critique, or 'generate N ideas about X'>"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
context: fork
routing:
  triggers:
    - "critique these ideas"
    - "multi-persona review"
    - "philosophical critique"
    - "devil's advocate on ideas"
    - "stress test proposals"
    - "evaluate from multiple perspectives"
    - "get different viewpoints"
    - "critique proposals"
  pairs_with:
    - roast
    - decision-helper
  complexity: Complex
  category: analysis
---

# Multi-Persona Critique: Parallel Philosophical Review of Proposals

## Overview

This skill takes a set of proposals — feature ideas, architectural decisions, design choices, strategy options — and sends ALL of them to 5 distinct intellectual personas for parallel, independent critique. Each persona brings a different philosophical lens. The skill then synthesizes all critiques into a consensus report showing where personas agree, where they disagree, and what the disagreements reveal.

**This is NOT the roast skill.** Key differences:
- `roast` critiques CODE with HackerNews personas and validates file:line claims
- This skill critiques IDEAS/PROPOSALS with philosophical/methodological personas and evaluates logical coherence, practical viability, and human impact
- `roast` is evidence-based (checking actual code); this is argument-based (evaluating reasoning)

**Key constraints baked into the workflow:**
- Every persona sees ALL proposals — no cherry-picking
- Personas run in parallel with no awareness of each other — independence is the source of value
- Ratings are mandatory: STRONG / PROMISING / WEAK / REJECT for every proposal from every persona
- Rankings are mandatory: each persona orders proposals from strongest to weakest
- Fairness mandate: genuine strengths must be acknowledged, genuine weaknesses explained with precision
- Disagreements are preserved, not averaged away — the disagreements ARE the insight
- The synthesis phase adds cross-cutting analysis, it does not edit persona outputs

---

## Instructions

### Phase 1: UNDERSTAND PROPOSALS

**Goal**: Extract or generate clear, numbered proposals ready for critique.

**Step 1: Determine input mode**

| Input | Action |
|-------|--------|
| User provides proposals directly | Extract and number them |
| User says "generate N ideas about X" | Research the domain, read relevant code/docs, then generate proposals |
| Ambiguous input | Ask user to clarify before proceeding |

**Step 2: Normalize proposals**

Each proposal must be a clear, self-contained description (2-4 sentences) that any of the 5 personas can evaluate independently. If user-provided proposals are vague, expand them to include:
- What the proposal does
- Why it matters (the problem it solves)
- How it differs from the status quo

If generating proposals, research the domain first:
- Use Glob and Grep to understand existing code, docs, and architecture
- Use Read to examine key files relevant to the domain
- Generate proposals grounded in actual context, not hypotheticals

**Step 3: Number and present**

Present the numbered proposal list back to the user before proceeding. Format:

```
Proposals for critique:
1. [Title] — [2-4 sentence description]
2. [Title] — [2-4 sentence description]
...
```

**Gate**: Numbered list of proposals ready. Each proposal is self-contained with 2-4 sentences. Proceed only when gate passes.

### Phase 2: BRIEF PERSONAS

**Goal**: Construct prompts for each of the 5 personas.

Load the full persona specifications from `${CLAUDE_SKILL_DIR}/references/personas.md`.

For each persona, construct a prompt that includes:

1. **Identity block**: The persona's name, intellectual tradition, core values, evaluation criteria, and suspicions (from personas.md)
2. **Proposal block**: ALL proposals, numbered exactly as presented in Phase 1
3. **Rating requirement**: Rate each proposal as STRONG / PROMISING / WEAK / REJECT with 2-3 sentence justification per rating
4. **Ranking requirement**: Order all proposals from strongest to weakest
5. **Fairness mandate**: "Be 100% fair. If something is genuinely good, say so. If it's bad, say why with precision. Do not be contrarian for its own sake."
6. **Output format**: Structured output matching the persona template from personas.md

**Gate**: 5 persona prompts constructed, each containing all proposals and the full persona specification. Proceed only when gate passes.

### Phase 3: DISPATCH (Parallel)

**Goal**: Launch all 5 personas in parallel and collect independent critiques.

Launch 5 agents using the Agent tool, one per persona. Each agent runs independently with no awareness of other personas.

**The 5 parallel agents:**

1. **The Logician** (Bertrand Russell)
   Focus: Logical coherence, hidden assumptions, falsifiability, necessity vs novelty

2. **The Pragmatic Builder** (20-year staff engineer)
   Focus: Build cost vs value, maintenance burden, simpler alternatives, user need

3. **The Systems Purist** (Edsger Dijkstra)
   Focus: Accidental complexity, separation of concerns, elegance, failure modes

4. **The End User Advocate** (8-hours-a-day tool user)
   Focus: Daily impact, friction, delight, whether the problem is already solved

5. **The Skeptical Philosopher** (Illich/Postman/Franklin)
   Focus: Human agency, dependency risk, genuine vs manufactured problems, unintended consequences

**Each agent must produce:**
- A rating (STRONG / PROMISING / WEAK / REJECT) for every proposal with 2-3 sentence justification
- A ranked list of all proposals from strongest to weakest
- Any cross-cutting observations that apply to multiple proposals

**CRITICAL**: Wait for ALL 5 agents to complete before proceeding to Phase 4. Do not begin synthesis on partial results. Every persona must contribute before consensus can be determined.

**Gate**: All 5 persona reports received. Each report contains ratings for all proposals and a ranked list. Proceed only when gate passes.

### Phase 4: SYNTHESIZE

**Goal**: Build a consensus matrix and identify agreement, disagreement, and cross-cutting patterns.

**Step 1: Build the consensus matrix**

Create a matrix: proposals (rows) x personas (columns) x ratings.

```
| Proposal | Logician | Builder | Purist | User Advocate | Philosopher |
|----------|----------|---------|--------|---------------|-------------|
| 1. X     | STRONG   | STRONG  | WEAK   | PROMISING     | REJECT      |
| 2. Y     | PROMISING| STRONG  | STRONG | STRONG        | PROMISING   |
```

**Step 2: Classify consensus patterns**

For each proposal, classify:
- **CONSENSUS** (4+ personas agree within one tier): Strong signal
- **CONTESTED** (2-3 split): The disagreement itself is informative
- **OUTLIER** (1 disagrees with 4): Worth understanding why one persona sees differently

**Step 3: Extract disagreement specifics**

For CONTESTED and OUTLIER proposals, extract the specific disagreement:
- What does each side see that the other does not?
- Is the disagreement about values (what matters) or facts (what is true)?
- Does one persona have domain-relevant insight the others lack?

**Step 4: Calculate weighted consensus score**

Assign numeric values: STRONG=3, PROMISING=2, WEAK=1, REJECT=0

For each proposal: sum all 5 ratings, giving a score from 0-15.

**Step 5: Rank proposals by consensus score**

Sort proposals from highest to lowest weighted score. Note ties and what distinguishes tied proposals.

**Gate**: Consensus matrix complete with classifications, disagreement analysis, and ranked scores. Proceed only when gate passes.

### Phase 5: PRESENT

**Goal**: Deliver the synthesis report using the template from `${CLAUDE_SKILL_DIR}/references/synthesis-template.md`.

Load the synthesis template and populate all sections:

**Section 1: Consensus Matrix**
The full matrix from Phase 4, showing every proposal x persona x rating.

**Section 2: "The Features You Should Build"**
Proposals with unanimous or near-unanimous STRONG ratings (consensus score 12+). These have survived scrutiny from all 5 lenses.

**Section 3: "Worth Investigating"**
PROMISING consensus (score 8-11) with specific conditions extracted from critics. What would need to be true for these to become STRONG?

**Section 4: "Interesting Disagreements"**
CONTESTED proposals where personas diverge. Present both sides with the reasoning each persona used. Do not resolve the disagreement — present it.

**Section 5: "Shelve"**
WEAK consensus (score 0-7) with brief reasons from the most critical personas. Not "bad ideas" — ideas that did not survive this particular gauntlet.

**Section 6: Cross-Cutting Insights**
Meta-observations that cut across multiple proposals:
- Themes the personas collectively surfaced
- Blind spots in the proposal set (what is missing?)
- Tensions between proposals (does building X undermine Y?)

**Section 7: The Deepest Insight**
What did the critics collectively reveal that was not obvious from any single perspective? This is the highest-value output of the entire exercise.

**Gate**: Report complete with all sections populated. Critique done.

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

## Anti-Patterns

| Anti-Pattern | Why It Is Wrong | What To Do Instead |
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

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/personas.md`: Full persona specifications, identity, evaluation criteria, prompt templates
- `${CLAUDE_SKILL_DIR}/references/synthesis-template.md`: Consensus matrix format and synthesis report structure

### Related Skills
- `roast`: Code critique with evidence-based validation (complementary — roast critiques code, this critiques ideas)
- `decision-helper`: Weighted decision scoring for architectural choices (narrower — single-dimension scoring vs multi-persona critique)
