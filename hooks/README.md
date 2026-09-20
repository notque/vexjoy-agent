# Hooks

Hooks are event-driven Python programs that extend Claude Code at lifecycle boundaries. They enforce safety rules, add context, record telemetry, and run maintenance checks. Most remain silent unless they block an action or have useful context to add.

This page explains the hook system. The authoritative inventory is [`.claude/settings.json`](../.claude/settings.json), which records each enabled hook, its event, and any tool matcher. The scripts themselves live in this directory; tests live in [`hooks/tests/`](tests/).

## Lifecycle

```text
session starts -> prompt submitted -> tool selected -> tool runs -> response stops
     |                 |                  |              |
 SessionStart   UserPromptSubmit     PreToolUse      PostToolUse

context compaction: PreCompact -> compact -> PostCompact
subagent lifecycle: SubagentStart -> SubagentStop
session outcomes:   Stop | StopFailure
```

The installed configuration currently uses these events:

| Event | When it runs | Typical use |
| --- | --- | --- |
| `SessionStart` | A session starts or resumes | Sync files and inject environment or project context |
| `UserPromptSubmit` | Before Claude processes a prompt | Add routing, review, or pipeline context |
| `PreToolUse` | Before a matched tool executes | Enforce safety gates or issue advisory warnings |
| `PostToolUse` | After a matched tool completes | Scan changes, record telemetry, or refresh indexes |
| `PreCompact` | Before context compression | Preserve state that must survive compaction |
| `PostCompact` | After context compression | Restore bounded session context |
| `SubagentStart` | Before a subagent begins | Add parent-session context |
| `SubagentStop` | When a subagent finishes | Check completion state and record outcomes |
| `Stop` | After a normal response cycle ends | Persist summaries and resolve pending state |
| `StopFailure` | When a session ends because of an API error | Record failure metadata |

`PreToolUse` hooks may block a tool call; advisory hooks allow it to continue. Other events have event-specific response contracts. Check the corresponding script and tests before changing exit behavior or output fields.

## Organization

Hook filenames describe their position and purpose:

- `pretool-*` and `posttool-*` run around tool calls.
- `precompact-*` and `postcompact-*` run around context compression.
- `session-*` handle session startup, context, or summaries.
- `routing-*` record and resolve request-routing outcomes.
- `*-gate` hooks enforce a condition; advisory scanners report without blocking.
- Files in [`lib/`](lib/) provide shared input handling, output formatting, telemetry, and database access.

Some files remain as compatibility stubs after their behavior moved elsewhere. A stub should say so in its module documentation and should not be inferred to be active merely because the file exists. Registration in [`.claude/settings.json`](../.claude/settings.json) determines whether a hook runs.

## Common capabilities

The active hook set includes four broad kinds of behavior:

| Capability | Examples |
| --- | --- |
| Safety and policy | Branch protection, CI merge checks, configuration protection, ADR and implementation gates |
| Context injection | AFK posture, operator profile, project agents, team configuration, session memory |
| Quality checks | Security scans, prompt-injection scans, documentation drift, index synchronization |
| Telemetry and state | Usage tracking, routing outcomes, subagent state, session summaries, failure records |

Use the registration file rather than this table when you need an exhaustive list. Historical implementation notes are retained in [`docs/legacy.md`](docs/legacy.md); they are background, not the current inventory.

## Development

All hooks receive an event payload as JSON on standard input. Output and exit behavior depend on the event: use the helpers in [`lib/hook_utils.py`](lib/hook_utils.py) and safe input handling in [`lib/stdin_timeout.py`](lib/stdin_timeout.py) instead of creating a new protocol. Hooks on frequent events should target less than 50 ms unless their documented operation necessarily performs external work.

For a new hook:

1. Use the `hook-development-pipeline` (`SPEC -> IMPLEMENT -> TEST -> REGISTER -> DOCUMENT`).
2. Add focused tests under [`hooks/tests/`](tests/).
3. Register the hook under the correct event and matcher in [`.claude/settings.json`](../.claude/settings.json).
4. Run the hook tests and health checks.
5. Benchmark hooks that run on prompts or tool calls.

Useful checks:

```bash
pytest -q hooks/tests
python3 scripts/validate-hook-health.py
python3 scripts/benchmark-hooks.py
```

Treat the tests and the registered command as the contract. In particular, preserve whether a hook is blocking or advisory, keep fail-open behavior where specified, and avoid adding output to hooks that are intentionally silent.
