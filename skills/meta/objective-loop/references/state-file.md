# Objective State File

Contract for `.objective/<slug>/state.md`. The state file is the loop's only
memory across wakeups — write it as if the next reader knows nothing else.

## Slug rules

- Kebab-case from the objective statement, 40 chars max: "all PRs merged and CI green" → `prs-merged-ci-green`.
- One directory per objective: `.objective/<slug>/state.md`.
- `.objective/` is session working memory — keep it unstaged (stage repo files by name only).

## Template

```markdown
# Objective: <one-sentence objective statement>

- slug: <slug>
- created: <ISO-8601 timestamp>
- mode: wakeup | inline
- budget: <N> iterations, <k> used
- token-budget note: <from settings, or "default 500000">

## Done-criteria

| # | Check (command) | Expected | Last result |
|---|---|---|---|
| 1 | `pytest -q` | exit 0 | exit 1 (3 failed) @ iter 2 |

## Guardrails (NOT-DONE-YET)

- <verbatim guardrail, e.g. "never weaken a gate to make it pass">

## Iteration log

### Iteration <k> — <ISO-8601 timestamp>

- Dispatched: agent=<name> skill=<name> — <one-line task>
- Verified: criterion #<n> → exit <code>, <decisive output line>
- Unmet: criterion #<n> → exit <code>, <decisive output line>
- Notes: <surprises, blockers, route changes>

## Next planned step

<one concrete step for the next wakeup — specific enough to dispatch without
re-deriving the plan>
```

## Resume protocol (on wakeup)

1. Read the state file top to bottom. Trust the file over conversation memory — the wakeup may arrive with fresh context.
2. Confirm budget remains; when exhausted, write the honest NOT-DONE report and stop.
3. Execute the "Next planned step" as one /do cycle (SKILL.md Phase 3).
4. Verify all criteria (SKILL.md Phase 4), append the iteration log entry, update "Last result" and "Next planned step".
5. Reschedule or stop (SKILL.md Phase 5).

When the state file is missing, report and stop — ask the user to restate the
objective. A re-derived objective silently drifts from the agreed criteria.

## Write discipline

- Update the state file BEFORE calling `ScheduleWakeup` — a wakeup that lands on a stale file repeats work.
- Paste real exit codes and output lines into "Last result"; summaries hide regressions.
- Keep each iteration entry to the facts: dispatched, verified, unmet, next.
