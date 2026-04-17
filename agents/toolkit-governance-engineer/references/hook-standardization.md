# Hook Standardization Reference

> **Scope**: Hook event types, settings.json registration format, exit code conventions, output protocols, timeout configuration, and common hook anti-patterns. Does not cover frontmatter compliance (see frontmatter-compliance.md).
> **Version range**: Claude Code hooks system (all current versions)
> **Generated**: 2026-04-15

---

## Overview

Hooks are shell commands registered in `settings.json` that execute in response to Claude Code lifecycle events. The most common failure modes are: wrong exit code (non-zero blocks Claude unexpectedly), missing `timeout` (hooks that hang stall the session indefinitely), and using `sys.stdin.isatty()` to detect TTY state (always False in hook context — hooks run with piped stdin).

---

## Event Type Reference

| Event | When Fires | `once` Default | Typical Timeout |
|-------|------------|---------------|-----------------|
| `SessionStart` | Session begins | `true` | 1000–5000ms |
| `UserPromptSubmit` | Before prompt is processed | — | 500–2000ms |
| `PreToolUse` | Before a tool executes | — | 500ms |
| `PostToolUse` | After a tool returns | — | 500–2000ms |
| `PreCompact` | Before context compression | `true` | 2000ms |
| `PostCompact` | After context compression | — | 1000ms |
| `TaskCompleted` | After task completion | — | 1000ms |
| `SubagentStop` | After subagent finishes | — | 500ms |
| `StopFailure` | Session ends with error | — | 1000ms |
| `Stop` | Session ends cleanly | — | 2000ms |

---

## settings.json Registration Format

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/my-hook.py\"",
            "description": "One-line description of what the hook does",
            "timeout": 2000,
            "once": true
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/posttool-lint-hint.py\"",
            "description": "Emit lint hints after file edits",
            "timeout": 1000
          }
        ]
      }
    ]
  }
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `type` | yes | `"command"` | Only `"command"` is currently supported |
| `command` | yes | string | Shell command; always quote paths with spaces |
| `description` | yes | string | Shown in session startup output |
| `timeout` | recommended | integer (ms) | Omitting allows hooks to hang indefinitely |
| `once` | no | boolean | `true` = run only once per session (SessionStart default) |

---

## Correct Patterns

### Always Exit 0

All hooks must exit 0. Non-zero exit codes block Claude from proceeding.

```python
#!/usr/bin/env python3
"""Hook docstring explaining purpose and advisory/blocking intent."""

import sys

def main():
    # ... hook logic ...
    pass

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never let exceptions propagate as non-zero exit
    sys.exit(0)  # Explicit exit 0
```

**Why**: Hooks that exit non-zero act as blockers — Claude cannot continue until the user resolves the exit. Advisory hooks (the vast majority) must always exit 0, even on internal error, to avoid stalling the session.

---

### Read Event JSON from stdin

Hooks receive the triggering event as JSON on stdin.

```python
import json
import sys

def read_event() -> dict:
    """Read hook event from stdin. Returns empty dict on parse failure."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {}

event = read_event()
tool_name = event.get("tool_name", "")
tool_result = event.get("tool_result", {})
```

**Why**: Hooks that skip stdin reading miss the event context. For `PostToolUse`, the tool name and result are in the event — without reading them, the hook cannot inspect what just happened.

---

### Inject Context via stdout

Hooks inject context into Claude's prompt by printing structured output to stdout.

```python
# Inject a context block (appears as system-reminder in Claude's context)
print(json.dumps({"type": "context", "content": "Important context here"}))

# Print a plain string (simpler, appears as hook output)
print("[hook-name] Action suggested: fix the broken reference")

# Silent hook — print nothing when there's nothing to report
# (preferred: hooks should be silent when they have no signal)
```

**Why**: Hooks that always print output — even when silent — add noise to every interaction. Hooks should only print when they have a signal to communicate.

---

### Timeout Configuration by Event Type

```json
"SessionStart": { "timeout": 5000 }   // Sync operations, file reads: allow up to 5s
"UserPromptSubmit": { "timeout": 500 } // Must be fast — blocks prompt processing
"PreToolUse": { "timeout": 500 }       // Blocks tool execution — keep under 500ms
"PostToolUse": { "timeout": 2000 }     // Can be slower; runs after tool completes
"Stop": { "timeout": 3000 }            // Session ending — can afford more time
```

**Why**: `UserPromptSubmit` and `PreToolUse` hooks are on the critical path — they block user interaction. Slow hooks here cause noticeable latency. `Stop` and `SessionStart` hooks can afford longer timeouts since they don't block active work.

---

## Anti-Pattern Catalog
<!-- no-pair-required: section header with no content -->

### ❌ Missing Timeout (Hook Can Hang Indefinitely)

**Detection**:
```bash
# Find hooks registered without timeout field
python3 -c "
import json
settings = json.load(open('$HOME/.claude/settings.json'))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            if 'timeout' not in hook:
                print(f'NO TIMEOUT: [{event}] {hook.get(\"description\", hook.get(\"command\", \"?\"))}')
"
```

**What it looks like**:
```json
{
  "type": "command",
  "command": "python3 \"$HOME/.claude/hooks/my-hook.py\"",
  "description": "Does something"
}
```

**Why wrong**: Without `timeout`, a hook that hangs (network call, waiting for input) stalls the session indefinitely. Claude cannot proceed until the hook exits or the user kills it.

**Do instead:**

Always add `"timeout"` to every hook entry in `settings.json`. Use 1000ms for informational hooks, 500ms for `PreToolUse` and `UserPromptSubmit` hooks, and up to 5000ms for `SessionStart` hooks doing file reads. Run the detection script above to find any hooks currently missing this field.

**Fix**: Always set `"timeout"` in milliseconds. Use 1000ms as a safe default for informational hooks; 500ms for `PreToolUse`/`UserPromptSubmit`.

---

### ❌ Using `sys.stdin.isatty()` to Detect Session Type

**Detection**:
```bash
grep -rn "stdin.isatty\|stdout.isatty" ~/.claude/hooks/*.py
```

**What it looks like**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
```python
# In a hook — WRONG
if sys.stdin.isatty():
    print("Interactive session")
else:
    print("Non-interactive — activating AFK mode")
```

**Why wrong**: Claude Code pipes stdin (the event JSON) into hooks and captures stdout (the hook output). Both are always non-TTY in hook context, so `isatty()` always returns False — every session is classified as non-interactive regardless of actual session type.

**Do instead:**

Detect session type using environment variables: check `SSH_CONNECTION` or `SSH_TTY` for SSH sessions, `TMUX` for tmux sessions, and `TERM_PROGRAM` for terminal type. Replace any `isatty()` call with an environment variable check as shown in the Fix code below.

**Fix**: Detect session type via environment variables instead.
```python
import os
is_ssh = bool(os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"))
is_tmux = bool(os.environ.get("TMUX"))
is_afk = is_ssh or is_tmux
```

---

### ❌ Non-Zero Exit Code in Advisory Hook

**Detection**:
```bash
# Find hooks that call sys.exit with non-zero values
grep -rn "sys.exit([^0)]" ~/.claude/hooks/*.py
grep -rn "exit(1\|exit(2\|exit(-" ~/.claude/hooks/*.py
```

**What it looks like**:
```python
def main():
    if not validate_something():
        print("Validation failed")
        sys.exit(1)  # WRONG for advisory hook
```

**Why wrong**: Exit code 1 signals Claude to block and surface the error to the user. For advisory hooks (lint hints, context injection, learning), this is almost always wrong — the hook should report its finding and exit 0 so Claude can continue.

**Do instead:**

Wrap all hook logic in a `try/except` block and call `sys.exit(0)` unconditionally at the end. Only use non-zero exit codes in deliberately blocking hooks (e.g., branch safety gates, ADR creation guards) where preventing Claude from proceeding is the intended behavior.

**Fix**: Wrap all hook logic in try/except and always exit 0. Only use non-zero exit for deliberately blocking hooks (branch safety gates, ADR creation guards).
```python
try:
    main()
except Exception:
    pass
sys.exit(0)
```

---

### ❌ Hook File Registered Before Being Deployed to `~/.claude/hooks/`

**Detection**:
```bash
# Check that all registered hook commands reference files that exist
python3 -c "
import json, os, re
settings = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            cmd = hook.get('command', '')
            m = re.search(r'[\"\047]([^\"\047]+\.py)[\"\047]', cmd)
            if m:
                path = os.path.expandvars(m.group(1))
                if not os.path.exists(path):
                    print(f'MISSING: [{event}] {path}')
"
```

**Why wrong**: Registering a hook before deploying the file causes a startup error on every session. The hook runs, finds no file, and exits non-zero — blocking or noising every session until fixed.

**Do instead:**

Deploy the hook Python file to `~/.claude/hooks/` first, verify it exists with `ls ~/.claude/hooks/my-hook.py`, and only then add its entry to `settings.json`. Use `scripts/register-hook.py` to enforce this ordering mechanically rather than relying on memory.

**Fix**: Always deploy the hook file to `~/.claude/hooks/` BEFORE adding its entry to `settings.json`.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Session startup fails or hangs | Hook missing `timeout` and hangs | Add `"timeout": 2000` to the hook config |
| Every session classified as AFK | `sys.stdin.isatty()` check in hook | Replace with `os.environ.get("SSH_CONNECTION")` check |
| Hook blocks Claude from proceeding | Advisory hook exits non-zero | Wrap in try/except, call `sys.exit(0)` unconditionally |
| Hook registered but errors on startup | Hook file not deployed to `~/.claude/hooks/` | Deploy file first, then register in settings.json |
| Hook runs multiple times per session | Missing `"once": true` on SessionStart hook | Add `"once": true` for one-time session initialization hooks |
| Hook output appears as noise every turn | Hook prints even when no signal | Add early-return guard: only print when there's something to report |

---

## Detection Commands Reference

```bash
# List all registered hooks with their events and descriptions
python3 -c "
import json, os
settings = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for event, groups in settings.get('hooks', {}).items():
    for group in groups:
        for hook in group.get('hooks', []):
            timeout = hook.get('timeout', 'MISSING')
            once = hook.get('once', False)
            desc = hook.get('description', '?')
            print(f'[{event}] timeout={timeout} once={once} — {desc}')
"

# Find hooks with missing timeout
python3 -c "
import json, os
s = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for ev, groups in s.get('hooks', {}).items():
    for g in groups:
        for h in g.get('hooks', []):
            if 'timeout' not in h: print(f'NO TIMEOUT [{ev}]: {h.get(\"description\",\"?\")}')
"

# Find hook files with sys.exit non-zero
grep -rn "sys.exit([^0)]" ~/.claude/hooks/*.py

# Find hook files using isatty (TTY detection anti-pattern) <!-- no-pair-required: detection command label, not an anti-pattern block -->
grep -rn "isatty" ~/.claude/hooks/*.py

# Verify all registered hook files exist on disk
python3 -c "
import json, os, re
s = json.load(open(os.path.expanduser('~/.claude/settings.json')))
for ev, groups in s.get('hooks', {}).items():
    for g in groups:
        for h in g.get('hooks', []):
            m = re.search(r'[\"\047]([^\"\047]+\.py)[\"\047]', h.get('command',''))
            if m:
                p = os.path.expandvars(m.group(1))
                if not os.path.exists(p): print(f'MISSING [{ev}]: {p}')
"
```

---

## See Also

- `frontmatter-compliance.md` — agent/skill YAML field standards
- `routing-table-patterns.md` — routing entry validation
- `skills/do/references/hooks-guide.md` — hook event types overview
- `~/.claude/hooks/` — deployed hook files
