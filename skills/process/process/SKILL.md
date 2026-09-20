---
name: process
description: "Run retrospectives, package or resume session state, pair in gated micro-steps, execute plans with fresh subagents, or design bounded waits."
user-invocable: true
argument-hint: "[retro|handoff|pair|subagent|wait]"
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Task, Agent]
routing:
  not_for: "multi-phase feature design (use workflow), code review (use review)"
  triggers: [what didn't work, route health, review roi, hand off this session, session pickup, pair program, micro-steps, subagent per task, execute plan with agents, exponential backoff, poll until ready, retry until success, retro]
  category: process
  pairs_with: [workflow, testing, pr-workflow]
---

# Process

Choose from the request: `retro`, `handoff`, `pair`, `subagent`, or `wait`. Default to retro only when invoked without a discernible mode.

## Retro

Read-only. For negative results, read `docs/what-didnt-work.md`, group by date, and lead with each Decision verdict. For routing telemetry, run `python3 ~/.claude/scripts/learning-db.py route-health` then `route-stats --by <dimension>`. For review ROI, run `review-roi` and `review-fps`, presenting outcome basis, cost, findings, and false positives together. Compare periods with `route-delta --from <sha-or-date> --to <sha-or-date>`.

## Handoff and pickup

A handoff records: scope/status, `git status -sb`, worktree, unpushed commits, branch/PR/CI, relevant live processes with copyable attach or tail commands, checks with revision/log paths, ordered next actions, and risks or approvals. Redact secrets.

On pickup, read the package and current repository instructions, then re-observe branch/worktree, PR/CI, and live processes. Observed state overrides inherited claims. Rerun only invalidated or missing checks, state the next 2–3 actions, then continue within existing authorization.

## Pair

Remain in the main session. Propose a numbered plan and wait for acknowledgment. For each logical step: announce why, show a reviewable proposed diff, wait, apply only after `ok`/`yes`/`y`, then verify. `no` proposes an alternative; `faster`/`slower` change step size; `skip`, `plan`, and `done` control the session. “Just do it” switches the remaining authorized work to autonomous execution.

## Subagent plan execution

Planning owns the plan; this mode owns dispatch and integration.

1. Extract each task’s full text, owned paths, dependencies, and verification. Capture `BASE_SHA`; run `python3 scripts/check-scope-overlap.py --tasks '<json>'`. Serialize overlapping writes and parallelize only independent groups.
2. Dispatch an implementer with the full task and [implementer prompt](implementer-prompt.md). Review requirement/ADR compliance before code quality, using the two compact reviewer prompts. Fix Critical and Important findings; Minor is optional. Stop after three failed review rounds at either stage.
3. Inspect `BASE_SHA..HEAD` as a combined change, resolve cross-task integration issues, run required checks, then follow the already-authorized completion path.

## Wait

Use the repository’s existing primitive where possible. Every wait has a deadline, nonzero interval, useful terminal error, and both success and timeout/exhaustion tests. Retry only transient failures; honor `Retry-After`; add jitter and a delay cap to distributed retries. Use a monotonic clock for elapsed time. Never disguise a permanent error as retryable or hold a worker forever.

Load [references/wait-contracts.md](references/wait-contracts.md) when implementing or reviewing polling, retry, rate-limit, health-check, or circuit-breaker code.
