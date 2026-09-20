---
name: quick
description: "Tracked execution for a contained change, with strict trivial-mode limits and optional discussion, research, or full verification."
user-invocable: true
argument-hint: "[--trivial] [--discuss] [--interview] [--research] [--full] [--no-branch] [--no-commit] <task>"
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Skill, Task]
routing:
  force_route: true
  triggers: [quick task, small change, ad hoc task, add a flag, small refactor, targeted fix, quick fix, typo fix, fix typo, fix the typo, one-line change, trivial fix, rename variable, rename this variable, update value, fix import, small mistake, small mistake in, mistake in spelling, spelling mistake, spelling fix, fix the spelling, typo in, small fix in, small fix, tiny fix]
  not_for: "'quick' as a speed preference, investigation-heavy diagnosis, architectural or multi-component work"
  complexity: Simple
  category: process
---

# Quick

Use one execution thread and an inline plan; never create `task_plan.md`. Preserve unrelated changes and repository rules.

## Flags and boundaries

- `--trivial`: mechanical, at most 3 edits across at most 3 files; no task ID or displayed plan.
- `--discuss`: batch independent ambiguities before planning.
- `--interview`: resolve dependent decisions one at a time, with a recommendation.
- `--research`: inspect unfamiliar code, tests, and configuration before planning.
- `--full`: verify the plan, then run affected tests, configured lint, and diff review.
- `--no-branch`: stay on the current branch only when repository rules permit.
- `--no-commit`: leave all edits uncommitted and report that explicitly.

Use `/do` when work becomes architectural, parallel, or multi-component. In standard mode, warn at 10 actual edits and reassess at 15; these thresholds are advisory when the work remains contained. Trivial mode’s limits are strict: preserve its edits and continue as standard quick if exceeded. New dependencies or dependency-file changes also require standard mode.

## Repository workflow

Read current repository instructions and check the branch before editing. Neither `--trivial` nor `--no-branch` bypasses branch safety.

Standard tasks receive `YYMMDD-xxx`, where the daily Base36 suffix progresses `001`…`009`, `00a`…`00z`, `010`. Find today’s highest ID in root `STATE.md`; if corrupt or absent, recover from git log entries containing `Quick task YYMMDD-`. Increment again on a branch collision.

Unless the current branch is allowed, create:

- trivial: `quick/<brief-description>`;
- standard: `quick/<task-id>-<brief-kebab-description>`.

Show a compact plan with intended edits, paths, rationale, and estimate. Research findings need only state current behavior and their effect on that plan. Recommend `--full` for security, payments, and data migrations.

## Completion contract

Run the narrowest meaningful syntax/build check plus repository-required checks. `--full` additionally requires affected tests, configured lint, and review of the resulting diff. Do not call unrelated failures successful.

Unless `--no-commit`, stage only intended paths and commit conventionally with `Quick task <task-id>` in the body (trivial tasks may omit an ID). Verify the commit. Append a row to root `STATE.md` using [references/templates.md](references/templates.md); use tier `trivial->quick` after escalation and record skipped commits literally.

Report changed paths, checks, commit/skipped status, branch, flags, and STATE.md update. Continue already-authorized delivery steps.
