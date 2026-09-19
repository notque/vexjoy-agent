---
name: process
description: "Process: retrospectives, session handoff, pair programming, subagent-driven development, condition-based waiting."
user-invocable: true
argument-hint: "[retro|handoff|pair|subagent|wait]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Task
  - Agent
routing:
  not_for: "multi-phase feature work (use workflow), code review (use review)"
  triggers:
    - "what didn't work"
    - "negative results"
    - "route health"
    - "routing telemetry"
    - "review roi"
    - "hand off this session"
    - "package session state"
    - "session pickup"
    - "rehydrate session state"
    - "pair program"
    - "collaborative coding"
    - "micro-steps"
    - "step by step coding"
    - "walk me through"
    - "interactive coding"
    - "subagent per task"
    - "fresh context execution"
    - "plan execution"
    - "execute plan with agents"
    - "exponential backoff"
    - "retry pattern"
    - "wait for"
    - "poll until ready"
    - "retry until success"
    - "retro"
  category: process
  pairs_with:
    - workflow
    - testing
    - pr-workflow
---

# Process Skill

Five modes. Parse the request to pick one. Default to **retro** when ambiguous.

| Signal | Mode |
|--------|------|
| Negative results, what didn't work, routing stats, review ROI, retro | **Retro** |
| Hand off, package state, session pickup, rehydrate | **Handoff** |
| Pair program, step by step, walk me through, one change at a time | **Pair** |
| Subagent per task, execute plan, fresh context | **Subagent** |
| Wait for, retry, backoff, poll, health check, circuit breaker | **Wait** |

---

## Mode: Retro

Read-only retrospective. Two stores: `docs/what-didnt-work.md` (negative-results
registry) and `learning.db` (routing/review telemetry via `scripts/learning-db.py`).

### Subcommands

| Argument | Action |
|----------|--------|
| (none), what-didnt-work | Read `docs/what-didnt-work.md`. Group by date. Show each Decision verdict up front. If missing, report no negative results recorded. |
| routing, route health | Run `python3 ~/.claude/scripts/learning-db.py route-health`, then `route-stats --by agent` (or the user's dimension). Present outcome basis before rates. |
| reviews, review ROI | Run `learning-db.py review-roi` and `review-fps`. Present cost, findings, and false positives per agent in one table. |

For comparisons: `learning-db.py route-delta --from SHA_OR_DATE --to SHA_OR_DATE`.

---

## Mode: Handoff

Two submodes sharing one state contract. HANDOFF packages work for the next
session. PICKUP rehydrates from that package.

### Handoff (ending/pausing work)

Produce a bullet package with these sections:

1. **Scope/status** -- task in one line, finished vs. remaining, blockers.
2. **Working tree** -- `git status -sb`; note unpushed commits and worktree path.
3. **Branch/PR** -- branch, PR URL, CI status (`gh pr checks`).
4. **Live processes** -- summarize relevant processes with attach/tail commands. Redact secrets.
5. **Tests/checks** -- commands, results, checked revision, log paths.
6. **Next steps** -- remaining actions in execution order.
7. **Risks/gotchas** -- flaky tests, feature flags, approvals needed.

Gate: every process has a copy-paste command; every pending step is ordered.

### Pickup (starting on existing work)

1. Read the handoff and repository instructions.
2. Confirm branch, local commits, worktree path (`git status -sb`).
3. Check CI/PR (`gh pr view --comments`).
4. Check live processes from the handoff. Attach or tail logs.
5. Rerun only invalidated or missing checks.
6. Write next 2-3 actions as bullets, then execute.

Gate: branch, PR state, and first action confirmed. Observed state wins over handoff.

Constraints: separate observed from inherited results. Redact secrets. Scale detail
to the next action.

---

## Mode: Pair

**Announce-Show-Wait-Apply-Verify** micro-step protocol. Stay in the main
session (forks cannot conduct user gates).

### Setup

Read the request and code. Show a numbered plan (one logical change per step).
Wait for acknowledgment. Track current step, remaining steps, and speed.

### Per-step cycle

1. **Announce** the change and reason (1-2 sentences).
2. **Show** the proposed diff (default 15 lines, cap 50). Split larger changes into sub-steps.
3. **Wait** for a control command.
4. **Apply** only after `ok` / `yes` / `y`.
5. **Verify** with relevant checks. Report result in one sentence.

| Command | Action |
|---------|--------|
| `ok`/`yes`/`y` | Apply current step, propose next |
| `no`/`n` | Skip, propose alternative |
| `faster` | Double step size (cap 50) |
| `slower` | Halve step size (min 5) |
| `skip` | Skip to next step |
| `plan` | Show remaining steps |
| `done` | End pairing, run final verification |

"Just do it" = switch to autonomous mode for remaining authorized work.

---

## Mode: Subagent

Execute a plan with fresh implementer subagents. Planning owns the plan format;
this mode owns dispatch and integration.

### Phase 1: SETUP

1. Read the plan once. Extract tasks with text, files, dependencies, and verify commands.
2. Track tasks as pending/in-progress/complete.
3. Capture `BASE_SHA` (`git rev-parse HEAD`), project conventions, and relevant context.
4. Check scope overlap: `python3 scripts/check-scope-overlap.py --tasks '<json>'`. Serialize overlapping writes; parallelize independent groups.

Gate: tasks, BASE_SHA, context, and scope checks ready.

### Phase 2: EXECUTE (per task)

1. Mark in-progress. Dispatch implementer with full task text and context.
2. Dispatch ADR compliance reviewer. Fix requirement failures before code quality.
3. Dispatch code quality reviewer. Fix Critical and Important findings; Minor optional.
4. Mark complete. After three failed reviews at either stage, stop and report.

Gate: requirements and code quality pass per task.

### Phase 3: FINALIZE

1. Review combined `BASE_SHA..HEAD` diff for cross-task conflicts and integration issues.
2. Follow the authorized completion path (`pr-workflow`).

Gate: combined changes work, required checks pass.

---

## Mode: Wait

Implement condition-based polling and retry patterns with bounded timeouts.

### Pattern selection

| Scenario | Pattern |
|----------|---------|
| Wait for condition to become true | Simple poll (timeout + min interval) |
| Retry failing operation | Exponential backoff (max retries + jitter + delay cap) |
| API returns 429 | Rate limit recovery (Retry-After + fallback) |
| Wait for service(s) to start | Health check (all-pass + per-check status) |
| Prevent cascade failures | Circuit breaker (failure threshold + recovery timeout) |

### Shared rules

- Read CLAUDE.md and search for existing wait/retry patterns first.
- Every loop needs a mandatory timeout. No infinite waits.
- Use `time.monotonic()` for elapsed time, never `time.time()`.
- Minimum poll interval: 10ms in-process, 100ms external services.
- Jitter is mandatory on exponential backoff (prevents thundering herd).
- Classify errors before retrying: 408/429/500/502/503/504 are retryable; 400/401/403/404 are not.
- Log each attempt with failure reason and attempt number.
- Test both success and timeout/exhaustion paths.

### Simple poll core

```python
start = time.monotonic()
while time.monotonic() < start + timeout:
    if condition():
        return result
    time.sleep(interval)
raise TimeoutError(f"Timeout waiting for: {description}")
```

### Exponential backoff core

```python
for attempt in range(max_retries + 1):
    try:
        return operation()
    except retryable_exceptions:
        if attempt >= max_retries: raise
        jitter = 1.0 + random.uniform(-0.5, 0.5)
        time.sleep(min(delay * jitter, max_delay))
        delay = min(delay * backoff_factor, max_delay)
```

For full implementations (rate-limited client, health check waiter, circuit
breaker), detection commands, and test patterns, load the deep references.

---

## Deep References

| Signal | Load | Content |
|---|---|---|
| Writing wait/retry implementations | `references/cbw-implementation-patterns.md` | Complete Python/Bash code for all 5 patterns |
| Reviewing wait/retry code for mistakes | `references/cbw-preferred-patterns.md` | Detection commands and fixes for common mistakes |
| Testing wait/retry code | `references/cbw-testing-patterns.md` | pytest patterns for polling, backoff, circuit breaker |
