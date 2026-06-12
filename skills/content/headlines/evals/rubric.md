# Headlines Eval Rubric — Blind A/B

## Protocol

- Arm A: agent generates headlines from a brief without the skill loaded.
- Arm B: agent generates headlines with `skills/content/headlines/SKILL.md` loaded.
- One blind judge per brief receives both outputs labeled "Output 1" / "Output 2" (arm order randomized), with the brief. The judge sees outputs only — method notes, move tags, and phase vocabulary are stripped before judging, so the skill cannot win on rubric-matching vocabulary.
- Judge scores each dimension 1–5 per output, then picks a winner per brief. A tie scores 0 for both arms.

## Pre-registered win condition

B promotes on **≥7 wins of 10 briefs** (ties excluded from wins). 5–6 wins: iterate the skill and re-run. ≤4 wins: skill loses; structural checks alone cannot promote it.

## Dimensions

| Dimension | 5 looks like | 1 looks like |
|-----------|--------------|--------------|
| Specificity | Concrete number, name, or detail from the brief in the headline | Generic category words; could top any article on the topic |
| Tension | A live stake, surprise, or conflict the reader must resolve | Flat statement of topic; nothing at risk |
| Accuracy to brief | Every headline claim verifiable from the brief | Claims the brief does not support, or contradicts |
| Distinctness | Options differ in approach, not just wording | Options are rephrasings of one idea |
| Honesty | Headline promises exactly what the brief delivers; gaps the content closes | Overpromise, manufactured outrage, or a gap the content never closes |

## Briefs

Ten self-contained briefs in this directory, `brief-01` through `brief-10`. Domains: tech (01–03), sports (04–05), business (06–08), culture (09–10). Each brief carries premise, key facts, audience, and requested formats — the judge and both arms see the identical brief.
