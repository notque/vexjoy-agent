# Fix-Strategy A/B (quality-loop Phase 7) — VERDICT

Date: 2026-07-04. Question: does same-context fixing (the reviewer that found
the bug fixes it with its own reasoning in context — the Lovable claim) beat
the current Phase 7 design (fresh agent gets only the finding text)?

## Design

- 8 paired trials (16 runs). Fixture: `fixtures/fix-strategy-ab/` — 8 Python
  modules, one seeded bug each (off-by-one, missing escaping, wrong operator,
  bad split, stale-cache, zero-multiplier default, unset flag, undrained
  merge), each pinned by a failing pytest. Baseline: 14 failed / 16 passed.
- Arm `fresh` (current design): sonnet agent gets finding text + file paths only.
- Arm `same-ctx` (challenger): identical prompt plus the reviewer's root-cause
  reasoning ("YOUR REVIEW REASONING: ..."). Same model, isolated trial dirs.
- Correctness verified deterministically by the orchestrator re-running pytest
  in every trial dir (exit codes observed, not agent self-reports).
- Blind judge: opus, read-only, saw `judge-input.json` (anonymized diffs,
  balanced 4/4 X/Y arm positions, paths stripped); `uid-map.json` withheld.

## Results

| Metric | fresh (baseline) | same-ctx (challenger) |
|---|---|---|
| Fix correct (pytest exit 0) | 8/8 | 8/8 |
| Collateral damage (new failures) | 0 | 0 |
| Total diff lines (16 files) | 46 | 39 |
| Tool calls per trial | ~3-4 | ~3 (3 captured exactly) |
| Blind judge wins | 2 | 4 (+2 ties) |

Judge detail: 6 of 8 verdicts turned on which arm also deleted the module
docstring's "Bug: ..." text — a fixture artifact, not the treatment variable.
One diff pair (T03) was character-identical across arms. Sign test on 4-2
(6 discordant): p ≈ 0.69.

## VERDICT: INCONCLUSIVE → RETAIN current Phase 7 (fresh agent)

- **Ceiling-bound**: both arms scored 100% correctness with zero collateral
  damage. Per PHILOSOPHY.md ("Ceiling-bound evals judge nothing"), this null
  judges the corpus, not the variants: single-file, single-cause, test-pinned
  bugs are too easy for reasoning-context to matter.
- The claimed same-context benefit (no re-discovery cost) did not appear:
  tool-call counts and latency were indistinguishable — the finding text alone
  was sufficient context for re-discovery in one Read.
- The judge's 4-2 lean toward same-ctx is inside noise and confounded by the
  docstring artifact.
- No evidence justifies changing Phase 7. The current design's rationale
  (anchoring-bias avoidance) was not tested here — that failure mode needs
  bugs the reviewer *misdiagnoses*, which this corpus cannot produce.

## Limitations (read before re-running)

1. **Simulated same-context.** Arm B injected reviewer reasoning into a fresh
   prompt; a true same-context arm continues the reviewer agent's session
   (SendMessage). Injection tests "reasoning transfer," not "warm context."
2. **Corpus too easy.** Hardening path per the fact-check precedent
   (what-didnt-work 2026-06-12): multi-file bugs, misleading findings
   (reviewer's proposed fix is wrong), bugs where the obvious fix breaks a
   different test — these give anchoring bias something to anchor on.
3. **n=8, one sample per (trial, arm)**: no self-consistency estimate.
4. Tool-call usage metadata retained for only 3/16 trials; the rest are
   agent self-reports (~3-4 calls each, both arms).

Re-run bar: a hardened corpus where the fresh baseline drops below ~80%
correctness, and a true same-context arm. Until then Phase 7 stands.

## Artifacts

- `experiment.json` — design + trial roster
- `findings.json` — the 8 findings and reviewer reasoning (arm B payload)
- `trial-data.json` — per-trial raw data (exit codes, diff sizes, tool calls)
- `trials/*.diff` — all 16 fix diffs
- `judge-input.json` / `judge-output.json` / `uid-map.json` / `scoreboard.json`
- Fixture (buggy code + tests): `fixtures/fix-strategy-ab/`
