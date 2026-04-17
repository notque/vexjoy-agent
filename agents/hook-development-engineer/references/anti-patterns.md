# Hook Development Anti-Patterns Reference

> Loaded by hook-development-engineer when reviewing hook code for correctness, performance, or registration safety issues.

## ❌ Blocking on Errors
**What it looks like**: Hook exits with code 1 when encountering errors
**Why wrong**: Blocks Claude Code operation, defeats purpose of hooks
**Do instead**: Always exit 0, log errors to debug file

## ❌ Synchronous Heavy Operations
**What it looks like**: Reading entire learning database, complex regex on all patterns
**Why wrong**: Exceeds 50ms performance budget
**Do instead**: Lazy loading, early exit, efficient algorithms

```python
# Bad - parses entire database
patterns = json.load(f)
for p in patterns:
    if p['id'] == target_id:
        return p

# Good - early exit
for line in f:
    pattern = json.loads(line)
    if pattern['id'] == target_id:
        return pattern
```

## ❌ Direct Database Writes
**What it looks like**: `json.dump(data, open(db_path, 'w'))`
**Why wrong**: Can corrupt database if interrupted
**Do instead**: Write to temp file, then atomic rename

```python
temp_path = db_path.with_suffix('.tmp')
with open(temp_path, 'w') as f:
    json.dump(data, f)
temp_path.replace(db_path)  # Atomic on POSIX
```

## ❌ Registering Hooks Before Deploying Files
**What it looks like**: Adding a hook to `settings.json` before the script exists at `~/.claude/hooks/`
**Why wrong**: Python file-not-found = exit code 2 = blocks ALL PreToolUse tools. Total session deadlock.
**Do instead**: Deploy file first, verify it runs, THEN register. Never reverse this order.

## ❌ Unguarded main() — Letting Exceptions Propagate to Exit Code
**What it looks like**: `main()` called at top level with no wrapping try/except, so an unhandled exception (file not found, malformed JSON, import error) exits with Python's default code 2 or 1.
**Why wrong**: Python exit code 2 is the same code Claude Code uses to signal BLOCK. A single unhandled exception in any PreToolUse hook deadlocks ALL tools for the entire session.
**Do instead**: Wrap the entry point unconditionally:
```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        debug_log(f"Fatal error: {e}")
    finally:
        sys.exit(0)  # ALWAYS exit 0 — no exception reaches the OS
```
The `finally` block guarantees exit 0 even if `debug_log` itself raises.

## ❌ Assuming Hook File Exists at Register Time
**What it looks like**: Editing `settings.json` (or running `register-hook.py`) in the same step as writing the hook file, or before confirming the file is present at `~/.claude/hooks/`.
**Why wrong**: If the file isn't at `~/.claude/hooks/` when Claude Code starts, every PreToolUse event triggers a Python "file not found" → exit 2 → tool blocked. The session is deadlocked before you can fix it.
**Do instead**: Strict deployment order: (1) write `hooks/my-hook.py` in the repo, (2) copy/sync to `~/.claude/hooks/`, (3) verify `python3 ~/.claude/hooks/my-hook.py < /dev/null` exits 0, (4) THEN register in `settings.json`. Use `scripts/register-hook.py` which enforces this order programmatically.

## ❌ Injecting Agent Context in a UserPromptSubmit Hook
**What it looks like**: A `UserPromptSubmit` hook that tries to inject agent-scoped context (e.g., "you are the go-engineer agent, apply TDD") into the session context file.
**Why wrong**: `UserPromptSubmit` fires BEFORE `/do` selects an agent. The hook has no knowledge of which agent will be chosen, so any agent-scoped injection is either wrong (targets the wrong agent) or a no-op (overwritten by routing). Timing mismatch makes this pattern unreliable by design.
**Do instead**: Agent-scoped context injection belongs at routing time, inside the skill that the router invokes after selecting the agent. Hooks are for session-wide, agent-agnostic concerns (error detection, performance logging, global context).

## Error Handling Patterns

### Hook Blocking Claude Code
**Cause**: Hook exited with non-zero code or failed to exit
**Solution**: Wrap entire main() in try/except and always exit 0:
```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        debug_log(f"Fatal error: {e}")
    finally:
        sys.exit(0)  # ALWAYS exit 0
```

### Performance > 50ms
**Cause**: Heavy operations (file I/O, JSON parsing) without optimization
**Solution**: Use lazy loading, minimal parsing, efficient data structures

### Learning Database Corruption
**Cause**: Direct file writes without atomic operations
**Solution**: Use write-to-temp-then-rename pattern (see Direct Database Writes above)
