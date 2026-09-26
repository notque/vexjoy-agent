---
name: accounts
description: "Manage multiple Claude Code accounts: add, list, check, launch, and install shell aliases for 10+ isolated CLAUDE_CONFIG_DIR profiles."
version: 1.0.0
user-invocable: true
argument-hint: "[add <name>|list|check|launch <name>|link [<name>]|install-aliases|remove <name>]"
allowed-tools:
  - Read
  - Bash
  - Edit
routing:
  triggers:
    - "multiple accounts"
    - "multiple claude accounts"
    - "CLAUDE_CONFIG_DIR"
    - "claude account"
    - "switch accounts"
    - "account alias"
    - "claude login"
    - "c1 c2 aliases"
    - "claude max account"
    - "manage accounts"
    - "add claude account"
  pairs_with:
    - deploy
  category: meta
  not_for: "API key rotation (use secrets management), Anthropic billing (use the web console)"
---

# Accounts Skill

Manages multiple Claude Code accounts using isolated `CLAUDE_CONFIG_DIR` directories.
One directory per account keeps auth tokens, session history, and settings separate.
Shell aliases let the user pick an account before Claude Code starts — no `/logout`/`/login` needed.

Script: `scripts/manage-accounts.py`. Registry: `~/.claude-accounts/accounts.json`.

## Quick reference

| Task | Command |
|------|---------|
| Add an account | `python3 scripts/manage-accounts.py add <name>` |
| Add with a named alias | `python3 scripts/manage-accounts.py add work --alias cwork` |
| List all accounts | `python3 scripts/manage-accounts.py list` |
| Validate all accounts | `python3 scripts/manage-accounts.py check` |
| Launch an account | `python3 scripts/manage-accounts.py launch <name>` |
| Share skills, agents, commands from `~/.claude` | `python3 scripts/manage-accounts.py link [<name>]` |
| Install/update aliases | `python3 scripts/manage-accounts.py install-aliases` |
| Preview alias changes | `python3 scripts/manage-accounts.py install-aliases --dry-run` |
| Remove an account | `python3 scripts/manage-accounts.py remove <name>` |

## Setup flow for 10+ accounts

### 1. Add accounts

```bash
python3 scripts/manage-accounts.py add work --alias cwork
python3 scripts/manage-accounts.py add personal --alias cpersonal
python3 scripts/manage-accounts.py add max1 --alias cm1
# … repeat for as many accounts as needed
```

Use named aliases (`cwork`, `cpersonal`) rather than sequential ones (`c1`, `c2`) — named aliases are self-documenting and you won't need `list` to remember which is which.

Each `add` creates `~/.claude-accounts/<name>/`, assigns the alias, installs aliases into your shell config, and links the account's `skills/`, `agents/`, and `commands/` to `~/.claude`.

### How the toolkit reaches every account

`./install.sh` installs once into `~/.claude`. Every account dir holds symlinks to `~/.claude/skills`, `~/.claude/agents`, and `~/.claude/commands`, so each skill exists once and every account sees the same set. Run `link` (no name means all accounts) to repair an account made before this, or one where Claude Code created its own `skills/` dir. `link` moves non-conflicting content, such as `skills/synced/<account-id>/`, into `~/.claude` first. It stops and reports on a real conflict.

### 2. Log in to each account

After `add`, the script prints a login command. Run it once per account:

```bash
CLAUDE_CONFIG_DIR=~/.claude-accounts/work claude
# inside Claude Code: /login
# exit, then repeat for each account
```

### 3. Verify

```bash
python3 scripts/manage-accounts.py list
python3 scripts/manage-accounts.py check
```

`list` shows every account including the default `~/.claude` one. `check` validates that each registered account has credentials and shares the toolkit dirs.

### 4. Use

Reload your shell once, then use aliases from any terminal:

```
cwork            # opens Claude Code with the 'work' account
cpersonal        # opens Claude Code with the 'personal' account
cwork --resume   # resumes the last session for the 'work' account
```

## Shell alias format

**Fish** (`~/.config/fish/config.fish`):
```fish
function cwork
    set -lx CLAUDE_CONFIG_DIR "~/.claude-accounts/work"
    claude --dangerously-skip-permissions --system-prompt="." $argv
end
```

**Bash/Zsh** (`~/.bashrc` / `~/.zshrc`):
```bash
alias cwork='CLAUDE_CONFIG_DIR="~/.claude-accounts/work" claude --dangerously-skip-permissions --system-prompt="."'
```

Every alias and `launch` pass `DEFAULT_CLAUDE_ARGS` from `scripts/manage-accounts.py` before your own arguments. Edit that tuple and re-run `install-aliases` to change them.

The managed block is idempotent — re-run `install-aliases` any time to sync after adding accounts.
Use `--dry-run` to preview changes before writing:

```bash
python3 scripts/manage-accounts.py install-aliases --dry-run --shell fish
```

## Manual alternative (2 accounts only)

If you have exactly two accounts and prefer not to use the script:

```fish
# ~/.config/fish/config.fish
function cwork
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-accounts/work"
    claude $argv
end
function cpersonal
    set -lx CLAUDE_CONFIG_DIR "$HOME/.claude-accounts/personal"
    claude $argv
end
```

Create dirs and log in manually:
```bash
mkdir -p ~/.claude-accounts/work ~/.claude-accounts/personal
CLAUDE_CONFIG_DIR=~/.claude-accounts/work claude   # /login
CLAUDE_CONFIG_DIR=~/.claude-accounts/personal claude  # /login
```

## Notes

- Accounts share the same Claude Code binary and one vexjoy-agent install in `~/.claude`.
- Usage limits are per-subscription — no automatic failover between accounts.
- Session histories are isolated; `--resume` picks up the right history per alias.
- `remove` preserves the config directory so credentials are not accidentally deleted. To fully purge, delete the directory manually after `remove`.
- Shell config mutation note: `install-aliases` writes a managed block between header/footer markers. Do not delete the markers manually; doing so causes the next run to append a second block instead of replacing. Use `--dry-run` to inspect before writing.
- The default `~/.claude` account (no alias, opened by bare `claude`) is always shown in `list` but not managed by this script.
