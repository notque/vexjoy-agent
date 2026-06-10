# model-ab-v1 — VERDICT

**Question.** Is "fable coordinates+reviews, opus builds and fixes per review" worth adopting over "fable plans and builds solo"?

**Answer: NO — keep current defaults. Arm A (fable solo) won 3-0, mean weighted delta 1.43/5, and Arm B DNF'd its own review gate.**

## Pre-registered decision rule (verbatim from PROTOCOL.md §5)

Adopt B only when ALL hold: (1) B wins forced-choice majority ≥2/3; (2) mean Δ ≥ 0.3;
(3) every grader scores B correctness ≥ 4; (4) report carries B's cost multiple.
Result: (1) failed (A 3-0), (2) failed for B (Δ = +1.43 toward A), (3) failed
(B correctness: 3, 3, 3). Rule outcome: keep current defaults.

## Task

Fix the runtime-index replace-semantics bug in `hooks/sync-to-user-claude.py`
(stale `INDEX.local.json` symlink hides tracked skills — PR #778 bug class,
final un-fixed instance). Same frozen TASK.md to both arms, same base SHA
`05554d37`, isolated worktrees, neither arm told of the comparison.

## Arms

- **A**: one fable `hook-development-engineer` authors its workflow, builds end-to-end. 1 dispatch.
- **B**: fable-authored workflow (frozen pre-dispatch) → opus builder → fable review → opus fix → fable re-review. 4 dispatches, max 2 review rounds.

## What happened

- A shipped complete in one pass: merge semantics + two adjacent holes it found
  itself (no-local symlink leak; copy mode never overlaid), 38 tests, committed.
- B's build was strong on the happy path but left the deliverable uncommitted
  (round-1 BLOCKING). The round-1 fix complied with a review finding by removing
  a try/except — introducing an unguarded read of the gitignored
  `skills/INDEX.json` that crashes the whole skills sync on fresh clones.
  Round-2 review caught it: BLOCKING after final round → DNF per protocol.

## Blind grading (3 fable graders, randomized X/Y per grader)

| Grader | W(A) | W(B) | Choice |
|---|---|---|---|
| g1 (X=B,Y=A) | 5.00 | 3.70 | A |
| g2 (X=A,Y=B) | 4.85 | 3.35 | A |
| g3 (X=A,Y=B) | 4.85 | 3.35 | A |

Unanimous. All three independently surfaced the same defect the arm-B re-review
flagged (unguarded tracked-index read + fixture edits masking it) — convergent
validity between the review chain and the blind panel, none of whom saw the
review or each other.

## Cost (B's multiple, per rule clause 4)

| Metric | Arm A | Arm B | B multiple |
|---|---|---|---|
| Dispatches | 1 | 4 | 4.0× |
| Tokens | 85,222 | 315,070 | 3.7× |
| Wall-clock | ~542 s | ~930 s (sequential chain) | 1.7× |
| Outcome | complete | DNF | — |

## Mechanism read (one run, n=1 — directional only)

The coordinate/review split did real work — both review rounds found true
defects — but the builder treated findings as edicts: it "fixed" finding 3 by
deleting error tolerance instead of weighing the finding against fresh-clone
reality. The solo arm, owning design end-to-end, weighed those trade-offs
itself and even widened the fix to two adjacent holes the task didn't name.
Review-chain quality did not compensate for split ownership on this task.
Caveats: n=1, one task class (small Python hook fix), one builder/reviewer
prompt shape; a stronger B3 prompt ("evaluate findings, push back when wrong")
might change the result. Replication needed before any general claim.

## Disposition

- Winner PR: Arm A's branch, merged on merit through normal CI/review.
- Loser branch deleted unpushed. Blindness held: zero experiment traces in
  commits, PRs, or CI (G7 grep clean).
- Toolkit change: none (rule says keep defaults). Candidate follow-up worth
  testing separately: B3-style fixer prompts that license push-back on review
  findings.
