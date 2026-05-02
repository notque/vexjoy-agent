---
name: multi-persona-critique
description: "Parallel critique of proposals via 5 philosophical personas with consensus synthesis."
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

Takes proposals -- feature ideas, architectural decisions, design choices, strategy options -- and sends ALL to 5 distinct intellectual personas for parallel, independent critique. Synthesizes all critiques into a consensus report showing agreement, disagreement, and what disagreements reveal.

**Not the roast skill.** `roast` critiques CODE with HackerNews personas and validates file:line claims. This skill critiques IDEAS/PROPOSALS with philosophical personas and evaluates logical coherence, practical viability, and human impact.

**Key constraints:**
- Every persona sees ALL proposals
- Personas run in parallel with no awareness of each other
- Ratings mandatory: STRONG / PROMISING / WEAK / REJECT for every proposal from every persona
- Rankings mandatory: each persona orders proposals strongest to weakest
- Genuine strengths acknowledged, genuine weaknesses explained with precision
- Disagreements preserved, not averaged away -- disagreements ARE the insight
- Synthesis adds cross-cutting analysis; it does not edit persona outputs

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| example-driven tasks, errors | `examples-and-errors.md` | Loads detailed guidance from `examples-and-errors.md`. |
| tasks related to this reference | `personas.md` | Loads detailed guidance from `personas.md`. |
| tasks related to this reference | `synthesis-template.md` | Loads detailed guidance from `synthesis-template.md`. |

## Instructions

### Phase 1: UNDERSTAND PROPOSALS

**Goal**: Extract or generate clear, numbered proposals ready for critique.

**Step 1: Determine input mode**

| Input | Action |
|-------|--------|
| User provides proposals directly | Extract and number them |
| User says "generate N ideas about X" | Research the domain, read relevant code/docs, then generate proposals |
| Ambiguous input | Ask user to clarify |

**Step 2: Normalize proposals**

Each proposal must be self-contained (2-4 sentences) for independent evaluation. If vague, expand to include: what it does, why it matters, how it differs from status quo.

If generating proposals, research first: Glob/Grep existing code and docs, Read key files. Ground proposals in actual context.

**Step 3: Number and present**

Present numbered list before proceeding:

```
Proposals for critique:
1. [Title] — [2-4 sentence description]
2. [Title] — [2-4 sentence description]
...
```

**Gate**: Numbered list ready. Each proposal self-contained with 2-4 sentences.

### Phase 2: BRIEF PERSONAS

**Goal**: Construct prompts for each of the 5 personas.

Load full persona specs from `${CLAUDE_SKILL_DIR}/references/personas.md`. For each persona, construct a prompt with identity block, numbered proposals, rating/ranking requirements, fairness mandate, and structured output format -- see `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` (Phase 2: Persona Prompt Construction) for the complete recipe.

**Gate**: 5 persona prompts constructed, each containing all proposals and full persona spec.

### Phase 3: DISPATCH (Parallel)

**Goal**: Launch all 5 personas in parallel and collect independent critiques.

Launch 5 agents using the Agent tool, one per persona, independently:

1. **The Logician** (Bertrand Russell) -- logical coherence, hidden assumptions, falsifiability
2. **The Pragmatic Builder** (20-year staff engineer) -- build cost vs value, maintenance burden, simpler alternatives
3. **The Systems Purist** (Edsger Dijkstra) -- accidental complexity, separation of concerns, elegance, failure modes
4. **The End User Advocate** (8-hours-a-day tool user) -- daily impact, friction, delight, solved-problem check
5. **The Skeptical Philosopher** (Illich/Postman/Franklin) -- human agency, dependency risk, manufactured problems, unintended consequences

**Each agent must produce:**
- Rating (STRONG / PROMISING / WEAK / REJECT) for every proposal with 2-3 sentence justification
- Ranked list of all proposals strongest to weakest
- Cross-cutting observations across multiple proposals

Wait for ALL 5 agents before proceeding. Do not synthesize partial results.

**Gate**: All 5 persona reports received with ratings for all proposals and ranked lists.

### Phase 4: SYNTHESIZE

**Goal**: Build consensus matrix and identify agreement, disagreement, and patterns.

**Step 1: Build consensus matrix** -- proposals (rows) x personas (columns) x ratings. See template in `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`.

**Step 2: Classify consensus patterns**
- **CONSENSUS** (4+ agree within one tier): Strong signal
- **CONTESTED** (2-3 split): Disagreement is informative
- **OUTLIER** (1 disagrees with 4): Worth understanding why

**Step 3: Extract disagreement specifics** for CONTESTED and OUTLIER proposals:
- What does each side see that the other does not?
- Is it about values (what matters) or facts (what is true)?
- Does one persona have domain-relevant insight the others lack?

**Step 4: Calculate weighted consensus score** -- STRONG=3, PROMISING=2, WEAK=1, REJECT=0. Sum all 5 ratings per proposal (range 0-15).

**Step 5: Rank proposals** by consensus score. Note ties and distinguishing factors.

**Gate**: Consensus matrix complete with classifications, disagreement analysis, ranked scores.

### Phase 5: PRESENT

**Goal**: Deliver synthesis report using `${CLAUDE_SKILL_DIR}/references/synthesis-template.md`.

Load template and populate all 7 sections (Consensus Matrix; Features to Build; Worth Investigating; Interesting Disagreements; Shelve; Cross-Cutting Insights; Deepest Insight). See `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` (Phase 5) for section purposes and score-band criteria.

**Gate**: Report complete with all sections populated.

---

<!-- no-pair-required: section-header-only; individual anti-patterns below carry Do-instead blocks -->
## Examples, Error Handling, and Detection

See `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md` for:

- **Examples**: critique provided proposals, generate+critique ideas, evaluate architectural options
- **Failure modes**: averaging disagreement, post-hoc rationalization, consensus-as-truth, skipping justification, resolving contested items, sequential execution
- **Error Handling**: bare ratings, skipped proposals, uniform agreement, fewer than 2 proposals

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/personas.md`: Full persona specifications, identity, evaluation criteria, prompt templates
- `${CLAUDE_SKILL_DIR}/references/synthesis-template.md`: Consensus matrix format and synthesis report structure
- `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`: Worked examples, anti-patterns, error handling

### Related Skills
- `roast`: Code critique with evidence-based validation (roast critiques code, this critiques ideas)
- `decision-helper`: Weighted decision scoring (single-dimension scoring vs multi-persona critique)
