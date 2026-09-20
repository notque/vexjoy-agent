---
summary: "Jev-guided refinement record for public guides and human-facing READMEs."
read_when:
  - "reviewing the September 2026 documentation reduction"
  - "repeating the human-document evaluation"
---

# Human-document refinement, 2026-09-20

## Scope

The primary set was the public README, the two onboarding guides, and the three human audience guides. Secondary review covered human-maintained setup and operational READMEs. Generated catalogs, machine instructions, evidence ledgers, evaluation fixtures, archives, and contracts were excluded because ordinary prose optimization would damage their jobs or edit generated truth at the wrong source.

## Method

The primary documents were split at heading boundaries into 29 local segments of roughly 350 words. Jev 1.13 received only the segment, its document purpose, and 50 independent questions about reader value, clarity, audience fit, duplication, volatile facts, model-era assumptions, compression risk, and disposition. Code collected the judgments; a generative model drafted changes; repository validators supplied factual truth.

After editing, the six full documents were evaluated with one frozen 50-question battery three times each. All 18 repeated dispositions selected **keep**. There were no disposition flips. Readiness probabilities ranged from 0.60 to 0.77; the lower values belonged to the public README and the intentionally detailed architecture guide. This supports stopping broad revision, not claiming ground truth.

The smaller READMEs used the same local-context pattern. `.local.example/README.md` received a baseline and revised pass for each section. `hooks/README.md`, `hooks/afk-mode/README.md`, `services/README.md`, and `scripts/README.md` each received 50 questions per local document or segment. `scripts/README.md` was intentionally unchanged after Jev strongly preferred keeping it.

## Result

| Document | Before | After | Decision |
|---|---:|---:|---|
| `README.md` | 1,829 | 1,421 | Tighten and move volatile detail |
| `docs/start-here.md` | 703 | 482 | Tighten onboarding |
| `docs/QUICKSTART.md` | 745 | 115 | Keep only the shortest complete path |
| `docs/for-knowledge-workers.md` | 822 | 580 | Remove implementation detail |
| `docs/for-developers.md` | 1,011 | 795 | Moderate compression |
| `docs/for-ai-wizards.md` | 2,770 | 1,929 | Preserve depth; remove inventories and history |
| `hooks/README.md` | 1,255 | 700 | Replace stale catalog with stable lifecycle guide |
| `hooks/afk-mode/README.md` | 340 | 247 | Remove unsupported claims; clarify boundaries |
| `.local.example/README.md` | 442 | 402 | Correct setup semantics and make copying safe |

The six primary documents fell from 7,880 to 5,322 words, a 32.5% reduction. The edits also corrected script counts, Codex hook coverage, Reasonix registration counts, installer behavior, local configuration semantics, and stale service paths.

## Stopping decision

Broad compression has converged for this set: the repeated whole-document battery was stable, material-rewrite probabilities stayed at or below 0.23, and further compression scores were near the light-editing end. Remaining work should be triggered by factual drift, observed reader failure, or a changed document purpose rather than another self-evaluation loop.

Jev supplied judgments, not facts. Claims about paths, counts, commands, installer behavior, and hook support were accepted only after deterministic repository checks. A future iteration should use reader task completion or human labels as an external holdout.
