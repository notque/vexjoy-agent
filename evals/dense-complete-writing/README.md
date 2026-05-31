# Eval: Dense-Complete Writing standard

Tests whether the toolkit's writing standard improves output, and which Completeness clause phrasing best prevents over-compression.

## Why

The standard claims dense-and-complete output beats Claude's default. Visual review cannot measure coverage-vs-words tradeoffs. This eval measures them blind.

## Findings

**The standard helps on prose and judgment, not on ceiling-bound code.** Three blind dual-track (Claude + Codex) A/B runs:

| Task | Result |
|------|--------|
| Go token-bucket | No effect. Correctness ceiling — every variant passed build, vet, race. |
| Skill authoring | Guidance arm (PHILOSOPHY.md + standard) beat control +6.4/60, 80% cross-arm pairwise win-rate, Cliff's delta +0.60. |

One treatment run over-compressed: thinnest skill, dropped detail. That failure motivated a Completeness clause.

**Clause race.** Control plus ten candidate phrasings (five Codex, five Claude) ran one complex skill task (`log-secret-auditor`), graded blind dual-track on a 20-point coverage rubric plus a 0-100 dense-and-complete score. Winner: **g07** (Codex, rule-of-thumb) — top coverage (16/20) at the fewest words (1369), dense-and-complete 83.5. The winning family decouples content from wording.

Installed clause (verbatim):

> Treat content as fixed and wording as negotiable: carry every required point through the draft, then choose the shortest plain words that say those points exactly.

**Caveat.** Pilot N=1 per arm. Coverage held across all arms (15-16/20), so the clause is proven to raise density at equal coverage, not yet proven to prevent a coverage collapse.

## Methodology

**Dual-track blind.** Each output graded by two independent graders (Claude and Codex), neither knowing which arm produced which output. Arm-to-output keys stay sealed until grading completes. Scores combine across both tracks.

**Two axes per output:**
- Coverage: 20-point rubric (each point = one required SKILL.md element).
- Dense-and-complete: 0-100, high coverage at low word count.

**Arms.** Control (bare five rules, no Completeness clause) plus ten clause candidates. One task, one run per arm.

## Files

| File | Content |
|------|---------|
| `README.md` | This test plan and findings. |
| `scoring-rubric.md` | 20-point coverage rubric + the 0-100 dense-and-complete axis. |
| `clause-race-cases.md` | The skill-creation task and the 11 arms. |
