# Workflow-forensics detectors

Run all five. Confidence belongs to the complete evidence, not a single keyword.

| Detector | Signal | High confidence | Important correction |
|---|---|---|---|
| Stuck loop | same file in consecutive commits plus retry behavior | 5+ adjacent commits with near-identical intent, or 3+ with explicit retry/fix language and oscillating content | Frequency alone is not adjacency. Progressive add/test/refactor passes are normal; near-zero net change across repeated edits is stronger evidence. |
| Missing artifacts | completed plan phase lacks its declared output | phase marked complete, no artifact now or in history | Without a plan-defined artifact contract, record this detector as unavailable. |
| Abandoned work | incomplete active plan and abnormal inactivity | incomplete phase and last commit over 24h old | `>3x` that branch’s average commit interval is Medium; recent work is Low. Without a plan, unmerged branch age is weak evidence only. |
| Scope drift | branch changes fall outside plan scope | multiple unrelated/config/infrastructure changes | Adjacent test utilities may be Low; no plan means no defensible scope baseline. |
| Crash/interruption | unfinished state after abnormal stop | at least 3 of: uncommitted changes, incomplete active plan, prunable worktree, pending `.debug-session.md` next action | Two indicators are Medium; one alone is Low and often normal. |

Useful evidence:

```bash
git log main..HEAD --reverse --format='COMMIT %H %ai %s' --name-only
git status --short
git worktree list --porcelain
git diff <first-suspect-commit> <last-suspect-commit> -- <path>
git log main..HEAD --diff-filter=D --name-only --format=''
```

Common chains worth testing, not assuming:

- loop → context/time exhaustion → missing verification artifacts → interruption;
- interruption mid-phase → stale incomplete plan → apparent abandonment;
- out-of-scope configuration change → new constraint → repeated repair loop.

Before assigning High confidence to a loop, verify the suspect file appears in adjacent commits and inspect its net diff. Before calling work abandoned, compare the gap to that branch’s own cadence. Before calling drift, derive scope from an actual plan or user statement.
