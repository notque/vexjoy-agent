# d-single-loop-v1: /do vs /d routing on the golden set

Tasks: 14 (`scripts/golden_eval/tasks.json`), runs per router: 2, model (both arms): `opus`. Window: 2026-11-17T15:08:20.754274+00:00 to 2026-11-17T15:17:21.335505+00:00.
Model cost: /d $2.208, /do $1.9514. Jev: 28 calls, 14 of them served from the Jev cache, 14255 tokens (/d prepare only).

Routing level only: no task was executed. /do's plan follows /do's rules (Medium and Complex dispatch), so the /d dispatch-rule row is a /d check, shown for /do for reference only.

| Metric | /d | /do |
|---|---|---|
| Route correct per run (of 14) | 12 / 12 | 11 / 11 |
| Route correct in every run (of 14) | 12 | 11 |
| Skill correct per run | 12 / 12 | 11 / 11 |
| Pipeline correct per run | 14 / 14 | 13 / 13 |
| Required skill groups hit per run | 14 / 14 | 14 / 14 |
| Forbidden skill picks | 0 | 0 |
| Pipeline picked (share of rows) | 0.286 | 0.357 |
| Main-loop share of planned parts | 0.812 | 0.344 |
| Dispatch reasons | fan-out 6 | fan-out 6, unstated 15 |
| Plan within /d's dispatch rules per run | 14 / 14 | 6 / 7 |
| Tasks whose pick changed between runs | g05-hook-todo | g06-frontend-flicker |

## Rows not route-correct

| Task | Router | Run | Skill | Pipeline | Missed |
|---|---|---|---|---|---|
| g07-docs-from-source | /d | 1 | workflow | doc-pipeline | skill |
| g07-docs-from-source | /do | 1 | workflow | doc-pipeline | skill |
| g09-trivial-question | /do | 1 | assessment | None | skill |
| g14-project-skill | /d | 1 | game-dev | None | skill |
| g14-project-skill | /do | 1 | game-dev | systematic-debugging | skill pipeline |
| g07-docs-from-source | /d | 2 | workflow | doc-pipeline | skill |
| g07-docs-from-source | /do | 2 | workflow | doc-pipeline | skill |
| g09-trivial-question | /do | 2 | assessment | None | skill |
| g14-project-skill | /d | 2 | game-dev | None | skill |
| g14-project-skill | /do | 2 | game-dev | systematic-debugging | skill pipeline |

## Notes on scoring

- Jev: run 2's prepare calls were served from the Jev answer cache (about 9 ms, no usage), so both runs of /d share the same attachment evidence; 14 live Jev calls.
- g14-project-skill: the expected skill is a private overlay skill and is absent from this checkout's manifest for that request (0 matches), so neither arm could pick it. The row is unscoreable here; labels were not changed after the run.
- g07-docs-from-source: both arms picked `workflow` with `doc-pipeline` in both runs; the frozen label accepts `writing` or `toolkit` as the skill.
- Before the full run, a one-task smoke run (g01, one run per router) cost $0.43 in model calls and one Jev call that failed (gateway bridge dependencies missing in the worktree; fixed by linking them).

Rescore: `python3 scripts/golden_eval/run_routing.py --score <this dir>`. Per-row detail: `summary.json`, raw replies with timestamps: `rows.jsonl`.

## Post-run change to the task set

After this run, g14 (a private project skill, unscorable in a clean checkout) was removed and g08 now expects `research` only, so private skill names stay out of tracked files. The numbers above are from the 14-task run; re-run `scripts/golden_eval/run_routing.py` for 13-task numbers.
