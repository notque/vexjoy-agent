---
name: hook-development-pipeline
description: |
  Formal 5-phase pipeline for creating production-quality hooks with mandatory
  performance gates: SPEC → IMPLEMENT → TEST → REGISTER → DOCUMENT. Enforces
  sub-50ms execution, non-blocking exit-0 pattern, and proper event type selection.
  Use when creating new hooks or upgrading existing ones. Use for
  "create hook pipeline", "new hook formal", "hook with gates".
version: 1.0.0
user-invocable: false
agent: hook-development-engineer
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
routing:
  triggers:
    - create hook pipeline
    - new hook formal
    - hook with gates
  pairs_with:
    - hook-development-engineer
    - systematic-debugging
  complexity: Medium
  category: infrastructure
---

# Hook Development Pipeline

## Operator Context

This skill wraps the `hook-development-engineer` with explicit phase gates that enforce the requirements the engineer cannot enforce alone: a reviewed spec before any code is written, a mandatory sub-50ms timing test before the hook is registered, and a registration step that makes "done" mean "live and documented" rather than just "written."

Hooks fire on every tool use in a live Claude Code session. A slow hook is not an acceptable hook — it degrades every tool call permanently. The performance gate in Phase 3 exists precisely because "should be fast" is not the same as "was measured."

### Hardcoded Behaviors (Always Apply)

- **Spec Before Code**: Phase 1 must produce a written spec with all decisions recorded before Phase 2 begins. Never skip to implementation.
- **ADR Session Awareness**: In Phase 1 (SPEC), check for active ADR session (`.adr-session.json`). If found, read hook requirements from the ADR via `python3 ~/.claude/scripts/adr-query.py context --adr {adr_path} --role script-creator`. Include ADR-specified event types, matchers, and behavioral requirements in the spec. Run `adr-query.py list` to check for related ADRs.
- **Performance Gate is Blocking**: If `time python3 hooks/{name}.py < /dev/null` reads ≥ 50ms, return to Phase 2. Do not proceed to Phase 4. No exceptions, no "close enough."
- **Non-Blocking Gate is Blocking**: If the hook exits non-zero on invalid input, return to Phase 2. A crashing hook is worse than no hook.
- **Registration is Part of Done**: A hook not registered in `settings.json` is not done. Phase 4 is mandatory.
- **Lazy Imports Only**: All non-stdlib imports must be inside functions. Top-level imports add cold-start time and kill the performance budget.
- **Exit 0 Always**: The hook's `__main__` block must end with `sys.exit(0)` inside a `finally` clause. Not optional.

### Default Behaviors (ON unless disabled)

- **Dispatch to hook-development-engineer for Phase 2**: Use the Agent tool to dispatch implementation to `hook-development-engineer`. The pipeline orchestrates; the specialist writes.
- **Timeout field in registration**: Include `timeout` in every settings.json hook registration (default: 5000ms; 10000ms for SessionStart).
- **Learning-db record in Phase 5**: Record the hook in `scripts/learning-db.py` so the retro system can reference it.

### Optional Behaviors (OFF unless enabled)

- **Skip Phase 5 documentation**: Omit learning-db record for throwaway or experimental hooks (enable with "skip docs").
- **Extended timeout**: Use `timeout: 10000` for hooks that need heavier startup (enable explicitly; still test against 50ms).

## What This Skill CAN Do

- Guide the full lifecycle of a new hook from contract definition through live registration
- Enforce the performance and non-blocking gates that the single-pass engineer workflow skips
- Dispatch Phase 2 implementation to `hook-development-engineer` with a precise spec
- Update `settings.json` with the correct event type, timeout, and `once` flag
- Record the hook in the learning database for retro visibility

## What This Skill CANNOT Do

- Guarantee correctness of hook logic — that is the engineer's domain
- Choose an event type for you — the spec phase requires your decision
- Override the performance gate — if it's slow, you go back to Phase 2

---

## Instructions

### Phase 1: SPEC

**Goal**: Define the hook contract before writing any code.

Work through the following decisions and record them in a spec block. Do not proceed to Phase 2 until all decisions are made.

**Decision 1 — Event type** (pick one):

| Event | Fires When | Use For |
|-------|-----------|---------|
| `PreToolUse` | Before Claude executes a tool | Block bad calls, inject pre-context |
| `PostToolUse` | After tool returns | Learn from errors, inject post-context |
| `SessionStart` | Session begins | Load context, sync files (use `once: true`) |
| `UserPromptSubmit` | User submits a prompt | Detect complexity, inject skills |
| `Stop` | Session ends | Generate summary, archive |
| `PreCompact` | Before context compression | Archive learnings |

**Decision 2 — Target tools** (if applicable): Which specific tool names trigger logic? Or does the hook respond to all tools?

**Decision 3 — Action type** (pick one or more):

- `block`: Output JSON with `{"decision": "block", "reason": "..."}` to prevent a tool call (PreToolUse only)
- `inject-context`: Output JSON with `{"additionalContext": "..."}` to prepend context before the next prompt
- `learn`: Update a database or file with observed patterns; no output to Claude
- `observe`: Log or record without any output

**Decision 4 — Performance budget**: Default is 50ms hard limit. Is there any reason to expect this hook needs more? If yes, stop and reconsider the design.

**Decision 5 — Once-per-session?**: Should this hook run only once per session (`once: true`)? Applies mainly to SessionStart hooks that load context.

**Decision 6 — External dependencies**: Does the hook import anything outside the Python standard library? If yes, those imports MUST be lazy (inside functions). List them.

**Output**: A spec block like this:

```
HOOK SPEC: {hook-name}
======================
Event:        PostToolUse
Target tools: Edit, Write (or "all tools")
Action:       inject-context — inject fix suggestion when error matches pattern
Performance:  50ms hard limit
Once:         no
Lazy imports: sqlite3 (stdlib, ok), hooks/lib/learning_db_v2.py (local, lazy)
Output format: {"additionalContext": "..."}
```

**Gate**: Spec block written with all six decisions. Proceed to Phase 2.

---

### Phase 2: IMPLEMENT

**Goal**: Write the hook Python file following established patterns.

Dispatch to `hook-development-engineer` using the Agent tool with the spec from Phase 1. The spec is the brief; the engineer writes the code.

**Required structure** (verify before accepting Phase 2 output):

1. **Shebang + module docstring** — docstring must state: event type, what the hook does, performance characteristics, dependencies.
2. **Stdlib imports at top level only** — `sys`, `json`, `os` are fine at the top. Everything else: inside functions.
3. **Early-exit for non-target tools** — if the hook targets specific tools, check `tool_name` immediately after JSON parse and exit 0 if it doesn't match.
4. **JSON parse with error handling** — wrap `json.loads(sys.stdin.read())` in try/except; on failure, write to debug log and exit 0.
5. **Main logic** — the actual hook behavior.
6. **Exit 0 always**:
```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # write to debug log, never raise
        pass
    finally:
        sys.exit(0)
```

**Import pattern for local libs** (lazy, inside the function that needs them):

```python
def _get_db():
    from hooks.lib import learning_db_v2  # lazy import
    return learning_db_v2.open()
```

**Output helpers from `hooks/lib/hook_utils.py`** (if the file exists, prefer these):
- `context_output(text)` — produces `{"additionalContext": text}`
- `empty_output()` — produces `{}`
- `block_output(reason)` — produces `{"decision": "block", "reason": reason}`

**Output**: `hooks/{name}.py` written to disk.

**Gate**: File exists at `hooks/{name}.py`. Proceed to Phase 3.

---

### Phase 3: TEST

**Goal**: Verify performance and correctness. All three checks are required. Any failure returns to Phase 2.

**Check 1 — Syntax**:
```bash
python3 -m py_compile hooks/{name}.py
```
Must complete with exit 0 and no output.

**Check 2 — Non-blocking** (both must exit 0):
```bash
echo '{}' | python3 hooks/{name}.py
echo 'invalid json' | python3 hooks/{name}.py
```
Check with `echo $?` after each. Both must be 0. If either is non-zero, the hook has an unguarded exit path — return to Phase 2.

**Check 3 — Performance** (MANDATORY hard gate):
```bash
time python3 hooks/{name}.py < /dev/null
```
Read the `real` time from the output. **Must be under 50ms.** This is a cold-start measurement — it includes Python interpreter startup, import resolution, and the hook's own logic.

If performance fails:
- Identify which imports are at the top level and move them inside functions
- Reduce startup logic (defer DB connections, lazy-load config)
- Simplify the early-exit path so non-matching tool calls return immediately
- Re-run `time python3 hooks/{name}.py < /dev/null` after each change

**Do not proceed to Phase 4 until all three checks pass.**

**Gate**: All three checks pass. Record measured performance time for Phase 5 documentation. Proceed to Phase 4.

---

### Phase 4: REGISTER

**Goal**: Wire the hook into Claude Code settings so it actually fires.

**Step 1**: Locate the settings file:
```bash
# Project-level (preferred for project-specific hooks)
cat .claude/settings.json

# User-level (for hooks that apply to all projects)
cat ~/.claude/settings.json
```

**Step 2**: Add the hook registration under the correct event type key. Example structure:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 hooks/{name}.py",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

**Timeout defaults**:
- Most hooks: `5000` (5 seconds — generous ceiling above the 50ms target)
- SessionStart hooks: `10000` (10 seconds — loading context can legitimately take longer)
- UserPromptSubmit hooks: `5000`

**Once flag** (add if applicable):
```json
{
  "type": "command",
  "command": "python3 hooks/{name}.py",
  "timeout": 10000,
  "once": true
}
```

**Step 3**: Write the updated settings file with Edit tool. Verify JSON is valid:
```bash
python3 -m json.tool .claude/settings.json > /dev/null
```

**Output**: Settings file updated and valid.

**Gate**: Hook appears in settings.json under the correct event type. JSON validates. Proceed to Phase 5.

---

### Phase 5: DOCUMENT

**Goal**: Make the hook understandable and findable.

**Step 1**: Verify module-level docstring covers all four elements:
- What event it handles
- What it does (one sentence)
- Performance characteristics (measured time from Phase 3)
- Dependencies (if any, note they are lazy-loaded)

If the docstring is missing any element, add it with Edit tool.

**Step 2**: Check for a hooks README or inventory file:
```bash
ls hooks/README* hooks/HOOKS.md hooks/inventory.md 2>/dev/null
```
If one exists, add a one-line entry for the new hook.

**Step 3**: Record in learning database:
```bash
python3 ~/.claude/scripts/learning-db.py record hooks {name} \
  "what it does and when to use it" \
  --category design
```
If `scripts/learning-db.py` does not exist or fails, skip this step and note the skip.

**Output**: Docstring complete. README updated (if applicable). Learning-db record created (if available).

**Gate**: All documentation steps complete or explicitly skipped with reason.

---

## Completion Summary

After Phase 5, produce this summary:

```
HOOK COMPLETE: {name}
=====================
Event:       {event type}
Registered:  {settings file path}
Performance: {measured time}ms (gate: <50ms) ✓
Exit 0:      verified ✓

Files:
  hooks/{name}.py
  {settings file} (updated)

Docs:
  Module docstring: ✓
  README entry: ✓ / skipped (no README found)
  Learning-db: ✓ / skipped (script not available)
```

---

## Error Handling

### Error: Performance gate fails (≥ 50ms)
**Cause**: Top-level imports, eager DB connections, or too much logic before the early-exit check in Phase 3.
**Solution**: 1) Add `import time; t = time.time()` at the very top, `print(time.time() - t, file=sys.stderr)` just before `sys.exit(0)` to profile. 2) Check for any `import X` at module level where X is not `sys`, `json`, `os`, `re`, or other zero-cost stdlib modules. 3) Check if the hook opens a file or DB connection before checking `tool_name` — move those after the early-exit guard. Return to Phase 2 with specific optimization instructions.

### Error: Non-blocking gate fails (exit non-zero)
**Cause**: An unguarded code path that calls `sys.exit(1)`, raises an uncaught exception, or calls `exit()` directly. Common locations: JSON parse without try/except, file open without try/except, missing `finally: sys.exit(0)` in `__main__`.
**Solution**: Identify the specific failure path by running `echo '{}' | python3 hooks/{name}.py; echo $?` and `echo 'invalid json' | python3 hooks/{name}.py; echo $?`. Wrap the failing code path in try/except and ensure the `finally: sys.exit(0)` block exists in `__main__`. Return to Phase 2 with the failure path identified.

### Error: JSON parse fails on settings.json
**Cause**: Settings file has trailing commas, comments, or other non-standard JSON.
**Solution**: Run `python3 -m json.tool .claude/settings.json` to identify the parse error location. Fix the JSON syntax error before proceeding. Do not write a broken settings file.

### Error: Engineer produces hook without lazy imports
**Cause**: The dispatch to `hook-development-engineer` in Phase 2 produces top-level imports that violate the performance budget. The engineer is not in pipeline mode and may not enforce the lazy-import constraint.
**Solution**: Review the Phase 2 output before accepting it as complete. Move any non-stdlib top-level imports inside the functions that use them. Re-run Phase 3 performance check after refactoring.

---

## Anti-Patterns

### Top-Level Imports That Bloat Startup Time

**What it looks like**:
```python
import sqlite3           # fine (stdlib, near-zero cost)
from hooks.lib import learning_db_v2  # BAD — local module with filesystem lookup
import requests          # BAD — third-party, slow
```

**Why wrong**: Python resolves every top-level import before `main()` runs. A local module import can cost 10–30ms on its own — enough to fail the performance gate before a single line of hook logic executes.

**Do instead**: Move non-stdlib imports inside the functions that need them:
```python
def _check_patterns(tool_output):
    from hooks.lib import learning_db_v2  # imported only when this function is called
    db = learning_db_v2.open()
    ...
```

### Blocking on Error Instead of Exiting 0

**What it looks like**:
```python
data = json.loads(sys.stdin.read())  # raises on invalid JSON → unhandled → exit 1
```

**Why wrong**: Any unhandled exception causes Python to exit with code 1. Claude Code interprets a non-zero hook exit as a hard failure and can stall.

**Do instead**:
```python
try:
    data = json.loads(sys.stdin.read())
except (json.JSONDecodeError, ValueError):
    sys.exit(0)  # not our event format; ignore silently
```

### Skipping the Spec Because "It's Simple"

**What it looks like**: Moving directly to Phase 2 because the hook "obviously" handles PostToolUse and "obviously" injects context.

**Why wrong**: "Obviously" is the source of half of all hook event type mismatches. PreToolUse and PostToolUse are not interchangeable. A hook that fires before a tool runs cannot see the tool's output. A hook that fires after cannot block the call.

**Do instead**: Write the spec, even for a two-line hook. It takes 2 minutes and prevents a wrong-event-type regression.

### Registering Under the Wrong Event Type

**What it looks like**: Registering an error-learning hook under `PreToolUse` instead of `PostToolUse` because both "kind of make sense."

**Why wrong**: The hook will receive the wrong JSON structure and silently do nothing — or worse, fire at the wrong time and inject stale context.

**Do instead**: Match the event type to the action type table in Phase 1's SPEC section. `PostToolUse` = "I need to see the result." `PreToolUse` = "I need to prevent or modify the call."

### Treating Timeout in settings.json as the Performance Budget

**What it looks like**: Setting `"timeout": 5000` and considering the performance question answered.

**Why wrong**: The timeout is a ceiling on how long Claude Code will wait before killing the hook. It says nothing about actual hook performance. A hook that takes 2000ms every tool call degrades the session even if it doesn't time out.

**Do instead**: Treat 50ms as the performance target. Treat 5000ms as the safety net. The Phase 3 `time` test measures actual performance; the timeout field does not.

---

## References

- [Hook Development Engineer](../../agents/hook-development-engineer.md) - Agent dispatched in Phase 2 for implementation
- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks) - Official hooks event types, JSON schemas, and registration format
