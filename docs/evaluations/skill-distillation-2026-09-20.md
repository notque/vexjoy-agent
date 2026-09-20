# Skill distillation evaluation — 2026-09-20

## Objective

Keep knowledge that changes a capable model's behavior: repository contracts,
domain facts, exact commands and schemas, version/provider quirks, and observed
failure modes. Remove general knowledge, tutorials, duplicated procedure, stale
alternatives, and exhaustive examples.

## Method

- Unit: each of the 59 tracked skill directories, including textual references.
- Baseline: exactly 50 independent Jev judgments per skill.
- Revision: edit the complete skill rather than optimizing isolated sentences,
  then run exactly 50 revised judgments and make a targeted final refinement.
- Final audit: `scripts/jev-skill-distill.py` distributes every textual block
  across 50 bounded local evidence bundles. Each bundle receives one independent
  Noul about general knowledge, unique value, duplication, action-changing
  specificity, or stale/brittle prescription. Small skills reuse a local block;
  no head receives empty state.
- Guardrail: Jev guides selection; deterministic validators and tests protect
  runtime contracts. Machine-consumed schemas and fixtures are restored when a
  deletion breaks behavior, even when Jev favors further compression.

## Result

| Measure | Before | After | Change |
|---|---:|---:|---:|
| Skill entrypoints | 59 | 59 | preserved |
| Reference files | 794 | 267 | -66.4% |
| Skill words | 77,128 | 20,347 | -73.6% |
| Reference words | 941,595 | 154,473 | -83.6% |
| Total reviewed words | 1,018,723 | 174,820 | -82.8% |

Final Jev fleet averages across 2,950 nonempty judgments:

| Dimension | Probability |
|---|---:|
| General model-known material is materially present | 0.216 |
| Substantial duplication is materially present | 0.105 |
| Stale or brittle prescription is materially present | 0.279 |
| Unique/local/domain knowledge is materially present | 0.506 |
| Guidance changes an action or decision | 0.615 |

`workflow` and `game-dev` remain the largest and score high on both brittleness
and unique/actionable value. Their surviving bulk is primarily typed registries,
schemas, templates, generators, game APIs, and incident-derived contracts. This
is an explicit tradeoff: executable or machine-consumed specificity outranks a
lower prose score.

## Verification

- 59 final reports, 50 answers each, zero empty evidence bundles.
- Routing benchmark: 129/129 valid targets; zero unaccounted indexed skills.
- Focused regression repair: 664 passed, 2 expected xfails.
- Reference-loading migration suite: 480 passed, 3 expected xfails.
- Ruff check and format: passed.
- Frontmatter, index integrity, promoted successors, pipeline index, routing
  drift, documentation links/counts/commands, and workflow conformance: passed.

The full local test run included untracked private overlays and therefore failed
installer/index tests on private trigger collisions that are absent from a clean
checkout. Its genuine distillation regressions were isolated, repaired, and
rerun in the focused suites above.
