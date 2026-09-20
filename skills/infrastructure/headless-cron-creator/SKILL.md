---
name: headless-cron-creator
promoted_to: deploy
description: "Generate and safely install repository-standard headless Claude cron wrappers through crontab-manager.py."
user-invocable: false
argument-hint: "<name> <schedule> <prompt>"
allowed-tools: [Read, Write, Bash, Edit, Glob, Grep]
routing:
  triggers: ["create cron job", "scheduled task", "headless agent", "recurring agent"]
  category: process
---

# Headless Cron Creator

Collect `name`, `prompt`, and `schedule`; optional defaults are repo root workdir, USD 2.00 budget, tools `Bash Read`, and `{workdir}/cron-logs/{name}`. Prefer off-minutes (7, 23, 47) to avoid host-wide round-minute load spikes.

All mutations must use `~/.claude/scripts/crontab-manager.py`. It stages through temp files and backs up to `~/.claude/crontab-backups/`; never pipe directly to `crontab -`. Do not use session-scoped `CronCreate`.

```bash
python3 ~/.claude/scripts/crontab-manager.py generate-wrapper \
  --name "$name" --prompt "$prompt" --schedule "$schedule" \
  --workdir "$workdir" --budget "$budget" --allowed-tools "$allowed_tools"
```

Review the generated wrapper for `set -euo pipefail`, `flock`, absolute workdir/tool paths, `--permission-mode auto`, `--max-budget-usd`, `--no-session-persistence`, `--allowedTools`, timestamped logs, dry-run-by-default, and `PIPESTATUS[0]` propagation. Never substitute `--dangerously-skip-permissions` or `--bare`; the latter breaks OAuth/keychain authentication.

Syntax-check the wrapper, then show the dry-run entry:

```bash
bash -n scripts/${name}-cron.sh
python3 ~/.claude/scripts/crontab-manager.py add --tag "$name" \
  --schedule "$schedule" --command "$absolute_script --execute >> $logdir/cron.log 2>&1" --dry-run
```

Ask for explicit confirmation immediately before installation. Installed entries use `# claude-cron: <tag>` so the manager changes only owned lines. After confirmation, repeat without `--dry-run`, then run `verify --tag "$name"`.

Use `list`, `verify --tag`, and `remove --tag` for management. Regenerate changed wrappers with `--force`; do not hand-edit them. If the resolved Claude binary moves, regenerate. On install failure, inspect `crontab -l` and the timestamped backup.
