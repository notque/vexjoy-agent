# AFK Mode

AFK Mode adds an autonomous working posture to Claude Code at session start. It tells the model to continue obvious next steps without waiting for confirmation. It does not change tool permissions or bypass safety controls.

The default is `always`: every session receives the posture, including local terminals.

## Configure the mode

Set `CLAUDE_AFK_MODE` when starting Claude Code:

```bash
CLAUDE_AFK_MODE=never claude
CLAUDE_AFK_MODE=auto claude
```

| Value | Behavior |
|-------|----------|
| `always` (default) | AFK mode active on every session |
| `auto` | Active when any SSH, tmux, or GNU screen signal listed below is present; otherwise inactive |
| `never` | Disabled entirely |

Any other value currently behaves like `auto`.

To make a choice persistent, add `export CLAUDE_AFK_MODE=never` (or another value) to `~/.zshrc` for zsh or `~/.bashrc` for bash.

## What It Injects

In the default `always` mode the hook injects the block below. Nothing detects whether anyone is watching, so the block states the configured mode, not an observation:

```
<afk-mode>
AFK mode is set to "always" (CLAUDE_AFK_MODE), so work as if the user may not be watching the terminal. This is the configured mode; nothing checked whether anyone is watching.
Work proactively. Complete multi-step tasks without asking for confirmation.
If you can determine the next logical step, take it.
Produce concise task-completion summaries when finishing long-running work.
Actions that CLAUDE.md reserves for owner approval still need that approval.
</afk-mode>
```

In `auto` mode the first line instead says the mode is `auto` and that the session runs over SSH, tmux or screen.

## How It Works

- **Hook:** `hooks/afk-mode.py`
- **Event:** `SessionStart`
- **Registration:** `.claude/settings.json`
- **Failure behavior:** advisory and non-blocking; the hook always exits successfully

### Auto-detection signals

| Signal | Detection |
|--------|-----------|
| SSH | `SSH_CONNECTION`, `SSH_TTY`, or `SSH_CLIENT` env var set |
| tmux | `TMUX` env var set |
| GNU screen | `STY` env var set |
