# Clause Race Cases

One task, eleven arms. Each arm writes the same SKILL.md under the five density rules plus one Completeness clause (control uses no clause). Graded blind, dual-track.

## The task

Write a complete `SKILL.md` for a skill named `log-secret-auditor`.

Purpose: audit a Python web service (Flask/FastAPI/Django) for secrets that leak into logs and for missing redaction. The skill is for an AI coding agent that runs it on demand against a repository.

Deliverable: the full SKILL.md body only — frontmatter + workflow + everything the agent needs to perform the audit well. Output only the SKILL.md content.

Constraints:
- The host is a public web server; the audit must never print raw secret values.
- The skill must be self-contained and usable by an agent with no prior context.
- Assume the reader is the executing agent, not a human browsing docs.

## The arms

Control plus ten clause candidates (five from Codex, five from Claude), across four mechanism families: definition, contrast, test, rule-of-thumb.

| aid | gid | src | mechanism | clause |
|-----|-----|-----|-----------|--------|
| a04 | g00 | CONTROL | none | (bare five rules, no Completeness clause) |
| a01 | g02 | claude | definition | Keep every instruction, rule, decision, edge case, and fact; cut only the words that carry none of them. |
| a08 | g01 | codex | definition | Make density mean full coverage in fewer words: keep every required instruction, rule, decision, edge case, and fact, and cut only words that add none of them. |
| a05 | g10 | claude | definition | Density and completeness work together. Completeness sets what you must say: every instruction, rule, decision, edge case, fact. Density sets how: shortest accurate word, no padding. Say all of it, in as few words as the meaning allows. |
| a02 | g04 | claude | contrast | Density removes waste, not content. Strip filler, hedges, and long words. Keep all coverage: each rule, exception, and concrete fact stays, however terse you make it. |
| a09 | g03 | codex | contrast | Write dense, not merely brief. Dense writing keeps all needed information and removes waste; mere brevity makes the answer smaller by making it incomplete. |
| a11 | g06 | claude | test | Write the shortest version that still answers every question a user could ask from the task. After drafting, list each required fact, rule, and edge case; confirm the text states each one. If something is missing, the draft is too short, not too long. Trim wording, never coverage. |
| a03 | g05 | codex | test | First preserve the whole burden of the task: every instruction, rule, decision, edge case, and fact. Then shorten the wording until each remaining word does work. Test: if a reader could miss a required action or condition, restore the information; if a word adds no such information, cut it. |
| a10 | g09 | codex | test | Rule: compress wording, preserve meaning. Test: the final version must say everything the task needs, with no filler left. |
| a07 | g08 | claude | rule-of-thumb | Cut words, keep facts: shorten how you say it, never shrink what you say. |
| a06 | g07 | codex | rule-of-thumb | Treat content as fixed and wording as negotiable: carry every required point through the draft, then choose the shortest plain words that say those points exactly. |

## Result

**a06 (g07) won** — coverage 16/20, dense-and-complete 83.5, 1369 words. Top coverage at the fewest words. The rule-of-thumb family that decouples content from wording outscored definition, contrast, and test phrasings. Installed verbatim as the Completeness clause in `skills/shared-patterns/dense-complete-writing.md`.

Caveat: pilot N=1 per arm. Coverage held across all arms (15-16/20), so the clause is proven to raise density at equal coverage, not yet proven to prevent a coverage collapse.
