# Russell Density Standard

The toolkit's universal writing standard. Bertrand Russell's prose rules ("How I Write"), applied to every LLM generation.

## Scope

This standard governs **every generation**, with no exception:

- Replies to the user
- Plain-text output and reports
- The model's own thinking
- Skill, instruction, and reference files the agent writes or edits
- Code comments

This file holds the canonical wording. Surfaces that must guarantee the rules are present every turn — `CLAUDE.md`, `agents/base-instructions.md`, the `/do` router injection (`skills/meta/do/SKILL.md`) — reproduce all five rules verbatim, because the model will not open this file each turn and the rules must sit in context. The duplication is intentional. Propagation rule: edit the canonical wording here first, then update those three high-traffic surfaces to match. Reference docs that the model reads on demand — `docs/PHILOSOPHY.md`, `skill-creator` — carry a one-line summary plus a pointer here instead.

## The Five Rules

1. Shortest accurate word; never a long word where a short one serves.
2. Cut every word that carries no instruction, rule, or decision.
3. Plain English, not jargon.
4. Concrete over abstract.
5. Put heavy qualifications in separate short sentences.

## The Test

Say everything the task needs — omit no required instruction — and not one word more. Dense, complete, clear.

This is not minimalism, which drops information for aesthetics. Density keeps all information and drops everything else.

## Attribution

Bertrand Russell, "How I Write" (1956). Complements Orwell's six rules (1946), which the `/do` router also applies. Russell adds rule 5 — heavy qualifications go in their own sentences — and the concrete-over-abstract bias.
