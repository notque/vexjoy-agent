# Dense-Complete Writing standard

The toolkit's universal writing standard. Russell's five density rules plus a measured Completeness clause, applied to every LLM generation.

## Scope

This standard governs **every generation**, with no exception:

- Replies to the user
- Plain-text output and reports
- The model's own thinking
- Skill, instruction, and reference files the agent writes or edits
- Code comments

## The Five Density Rules

1. Shortest accurate word; never a long word where a short one serves.
2. Cut every word that carries no instruction, rule, or decision.
3. Plain English, not jargon.
4. Concrete over abstract.
5. Put heavy qualifications in separate short sentences.

## Completeness

Treat content as fixed and wording as negotiable: carry every required point through the draft, then choose the shortest plain words that say those points exactly.

## The Test

Say everything the task needs — omit no required instruction — and not one word more. Dense, complete, clear.

This is not minimalism, which drops information for aesthetics. Density keeps all information and drops everything else.

## Attribution

Density rules: Bertrand Russell, "How I Write" (1956). Russell adds rule 5 — heavy qualifications go in their own sentences — and the concrete-over-abstract bias. Complements Orwell's six rules (1946), which the `/do` router also applies.

Completeness clause: the measured winner of a 2026 clause race — control plus ten candidate phrasings, graded blind dual-track on a 20-point coverage rubric and a dense-and-complete score. The winning family decouples content from wording, hitting top coverage at the fewest words.

## Propagation

This file holds the canonical wording. The model will not open it each turn, so surfaces that must guarantee the rules sit in context reproduce the five rules and the Completeness clause verbatim: `CLAUDE.md`, `agents/base-instructions.md`, and the `/do` router injection (`skills/meta/do/SKILL.md`). The duplication is intentional. Reference docs the model reads on demand — `docs/PHILOSOPHY.md` and `skill-creator` — carry a summary plus a pointer here.

Propagation rule: edit this canonical wording first, then update the three verbatim surfaces to match.
