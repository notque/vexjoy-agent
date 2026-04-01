# AFK Mode

AFK Mode injects autonomous behavioral context into every Claude Code prompt, telling the model to work proactively without asking for confirmation. It replicates Claude Code's internal `PROACTIVE` feature (which is off in external builds) via the hook system.

## Current Configuration

**AFK Mode is set to `always` on by default.** Every session gets the autonomous posture regardless of whether you're on SSH, tmux, or a local terminal.

## Turning It Off

Set the `CLAUDE_AFK_MODE` environment variable:

```bash
# Disable for a single session
CLAUDE_AFK_MODE=never claude

# Disable permanently (add to your shell profile)
echo 'export CLAUDE_AFK_MODE=never' >> ~/.bashrc

# Auto-detect mode: active on SSH/tmux, inactive on local terminal
CLAUDE_AFK_MODE=auto claude
```

| Value | Behavior |
|-------|----------|
| `always` (default) | AFK mode active on every session |
| `auto` | Active on SSH/tmux/screen sessions only |
| `never` | Disabled entirely |

## What It Injects

When active, the hook injects this block into every prompt's system context:

```
<afk-mode>
The terminal is unfocused — the user is not actively watching.
Work proactively. Complete multi-step tasks without asking for confirmation.
If you can determine the next logical step, take it.
Produce concise task-completion summaries when finishing long-running work.
</afk-mode>
```

This text is the same behavioral trigger that Claude Code's internal `PROACTIVE` mode uses (`REPL.tsx:2776-2778`).

## How It Works

- **Hook**: `hooks/afk-mode.py` (UserPromptSubmit)
- **Registration**: `.claude/settings.json`, fires after datetime inject, before plan detector
- **Performance**: ~95ms (Python startup + hook_utils import; own logic is sub-ms)
- **Cache stable**: Injected text is identical on every prompt within a session
- **Token cost**: ~150 tokens per prompt when active

## Auto-Detection (when `CLAUDE_AFK_MODE=auto`)

| Signal | Detection |
|--------|-----------|
| SSH | `SSH_CONNECTION`, `SSH_TTY`, or `SSH_CLIENT` env var set |
| tmux | `TMUX` env var set |
| GNU screen | `STY` env var set |

## Design Reference

Full design rationale: `adr/143-ssh-session-awareness.md` (ADR-143: AFK Mode)
