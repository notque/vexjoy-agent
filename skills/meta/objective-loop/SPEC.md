# SPEC: objective-loop

Maintainer contract. Not runtime context — load only when changing this skill.

## Purpose

Iterate a user-stated objective to verified-done: each iteration is one /do
cycle; done-criteria verify by execution; the loop reschedules via
`ScheduleWakeup` until all criteria pass or the budget stops it.

## Scope

- Objective spec capture (statement, deterministic done-criteria, iteration budget, NOT-DONE-YET guardrails).
- State file at `.objective/<slug>/state.md`; resume from file on every wakeup.
- Planner/verifier role only — all work dispatches through /do.
- Cache-aware wakeup delays; harness fallback to in-session iteration.

## Non-goals

- Executing work inline (route through /do).
- Persistence: cron/CronCreate loops belong to `headless-cron-creator` behind `OWNER-APPROVED-PERSISTENCE`.
- Retry/backoff code inside programs (`condition-based-waiting`).
- Single-condition waits (harness `Monitor`).
- Replacing `feature-lifecycle` (features keep their phase machine).

## Invariants

1. The loop ends by not calling `ScheduleWakeup`; every stop path is explicit.
2. Verification is execution: criterion commands run, exit codes pasted.
3. A criterion is never satisfied by weakening a hook, gate, test, or safety control — conflict stops the loop.
4. Wakeups resume from the state file, never conversation memory.
5. Default mode is session-scoped; persistence requires the owner phrase.
6. Learning capture stays hook-automatic via /do dispatch — no manual rows.
7. `.objective/` stays unstaged.

## Dependencies

- `/do` router (`skills/meta/do/SKILL.md`) — dispatch + learning hooks.
- Harness `ScheduleWakeup` (optional; in-session fallback without it), `Monitor` (optional).
- `references/state-file.md` — state contract.

## Success criteria

- Routes on objective phrasing ("keep working until…"), declines one-off tasks, cron requests, and retry-code requests (`evals.json`).
- A resumed wakeup reconstructs the loop from the state file alone.
- Budget exhaustion produces a per-criterion NOT-DONE report.
