# /do Skill Second Halving A/B — VERDICT (runs: do-skill-reduction-v2 REJECT → v2.1 PROMOTE)

Date: 2026-07-03. Question: can the round-1 router (23,891 B, PR #860) halve
again with no behavior loss? Arms differ ONLY by hot SKILL.md text prepended to
an identical manifest; sonnet both arms.

## Variant construction (tournament)

Three strategies raced in parallel worktrees (opus, each keeping
`validate-do-references.py` + full `scripts/tests` green in-tree):

| Candidate | Strategy | Hot size | Judge score |
|---|---|---|---|
| A | script-extraction + 3 cold refs | 13,372 B | 7.9 |
| **B** | **dense-rewrite (single file)** | **13,491 B** | **8.5 — WINNER** |
| C | hot/cold split, 11 cold refs | 12,497 B (+12,296 cold) | 2.4 — eliminated |

Adversarial judge (opus, read-only): C moved every-request routing content
(force-route examples, creation detection, interview spec, banner) behind load
triggers — effective per-invocation cost WORSE than baseline. B won; grafts
applied from A: `scripts/get-routing-manifest.sh` (hash-gated cache logic
extracted, SDIR self-resolving, 3 structural tests) and two genuinely-cold
refs (`references/error-handling.md`, `references/learning-capture.md`,
<10% fire rate). Judge must-fixes restored (~500 B: self-check guardrail,
completeness directives, banner format contract, outcome stop-fallback,
health activation gate). Validator extended to phantom-scan the cold refs
(55 names checked vs 45 before).

## Run mechanics

- Harness: `routing-ab-test.py` manifest-arm mode, corpus v3, 178 cases,
  one sample per (arm, query), blind opus judge per run, uid map withheld.
- v2 (candidate at 12,438 B): **REJECT** — gate (c) safety: one new
  false-positive-guard miss (q33 "go ahead and merge the branches in your
  head" → pr-workflow). Root cause: git rule over-compressed to
  "Git→pr-workflow; metaphor→never", dropping the metaphorical examples.
- Fix: restored GENUINE-vs-metaphorical rule with the three guard examples
  (+213 B → hot 12,651 B). Gates unchanged (fixed in code).
- v2.1: full-arm answers carried over from v2 — full-arm prompts verified
  byte-identical (`cmp` on emitted prompts); only the reduced arm re-collected.
- Bridge: 536 calls total across v2+v2.1, $110.24 (`call-log.jsonl` both dirs).

## Results (v2.1, deterministic gate scoring)

| Metric | full (baseline, 23,891 B) | reduced (challenger, 12,651 B) |
|---|---|---|
| Overall accuracy | 87/178 (48.9%) | 103/178 (57.9%) |

Paired: D=0.090, 95% CI [0.039, 0.146], help=21, harm=5, discordant=26,
McNemar p=0.0025 (challenger-favoring). Safety buckets: zero new misses
(q33 now guarded). Stub-tier 10 → 10. Gates a/b/c/d all PASS; discordant 26 ≥ 6.

## VERDICT: PROMOTE (exit 0)

Cumulative: 40,924 B (pre-round-1) → 12,651 B hot = **30.9% of the original
router — a 3.2× compression** — while measured routing accuracy rose each
round. Same limitation as v1: the harness tests routing decisions; execution
behavior guarded by inventory + adversarial judge + validator/test coverage
instead. The v2 REJECT is the safety gate working: a single lost guard example
was caught and fixed before promotion. Watch `route-events.jsonl`; rollback =
git revert.
