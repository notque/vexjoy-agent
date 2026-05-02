---
name: headless-cron-creator
description: "Generate headless Claude Code cron jobs with safety."
user-invocable: false
argument-hint: "<name> <schedule> <prompt>"
agent: python-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
  - Glob
  - Grep
routing:
  triggers:
    - "create cron job"
    - "scheduled task"
    - "headless agent"
    - "background automation"
    - "recurring agent"
  category: process
  pairs_with:
    - cron-job-auditor
    - shell-process-patterns
---

# Headless Cron Creator Skill

Generate headless Claude Code cron jobs with safety mechanisms (lockfile, budget cap, dry-run default, logging) and install crontab entries. All crontab mutations go through `scripts/crontab-manager.py`, which writes to temp files and creates timestamped backups in `~/.claude/crontab-backups/` before every change — never pipe directly to `crontab -`.

## Instructions

### Phase 1: PARSE

Extract job parameters from the user's request.

**Required**: name (kebab-case), prompt (natural language), schedule (cron expression or human-readable).

**Optional** (with defaults): workdir (repo root), budget ($2.00), allowed-tools (`Bash Read`), logdir (`{workdir}/cron-logs/{name}`).

**Human-readable schedule conversion** — use off-minutes (7, 23, 47) instead of `:00`/`:30` to avoid load spikes:

| Human Input | Cron Expression |
|-------------|----------------|
| every 12 hours | `7 */12 * * *` |
| twice daily | `7 8,20 * * *` |
| hourly | `23 * * * *` |
| daily at 6am | `7 6 * * *` |
| weekly on sunday | `7 9 * * 0` |
| every 30 minutes | `*/30 * * * *` |

**Gate**: All required parameters extracted.

### Phase 2: GENERATE

Create wrapper script via `crontab-manager.py generate-wrapper`:

```bash
python3 ~/.claude/scripts/crontab-manager.py generate-wrapper \
  --name "{name}" \
  --prompt "{prompt}" \
  --schedule "{schedule}" \
  --workdir "{workdir}" \
  --budget "{budget}" \
  --allowed-tools "{allowed_tools}"
```

Verify the generated script contains:
- [ ] `set -euo pipefail`
- [ ] `flock` lockfile
- [ ] `--permission-mode auto` — never use `--dangerously-skip-permissions` or `--bare` (breaks OAuth/keychain auth)
- [ ] `--max-budget-usd`
- [ ] `--no-session-persistence`
- [ ] `--allowedTools`
- [ ] `tee` to per-run timestamped log file
- [ ] Dry-run/execute toggle — nothing destructive without `--execute`
- [ ] Exit code propagation via `PIPESTATUS[0]`

Do not use the `CronCreate` tool — it is session-scoped (dies when session ends, auto-expires after 7 days). Use system `crontab` via `crontab-manager.py`.

**Gate**: Script generated and reviewed.

### Phase 3: VALIDATE

1. Syntax check: `bash -n scripts/{name}-cron.sh`
2. `cron-job-auditor` checks:
   - [ ] Error handling (`set -e`)
   - [ ] Lock file (`flock`)
   - [ ] Logging (`tee`, `LOG_DIR`)
   - [ ] Working directory (absolute `cd`)
   - [ ] PATH awareness (absolute path to `claude` — cron has minimal PATH)
   - [ ] Cleanup on exit (lock release)

**Gate**: All checks pass.

### Phase 4: INSTALL

Every entry gets a `# claude-cron: <tag>` marker so `crontab-manager.py` manages only its own entries. All paths must be absolute.

1. Show proposed entry:
   ```bash
   python3 ~/.claude/scripts/crontab-manager.py add \
     --tag "{name}" \
     --schedule "{schedule}" \
     --command "{absolute_script_path} --execute >> {logdir}/cron.log 2>&1" \
     --dry-run
   ```

2. **Ask the user for confirmation.** Never install without explicit approval.

3. If confirmed:
   ```bash
   python3 ~/.claude/scripts/crontab-manager.py add \
     --tag "{name}" \
     --schedule "{schedule}" \
     --command "{absolute_script_path} --execute >> {logdir}/cron.log 2>&1"
   ```

4. Verify:
   ```bash
   python3 ~/.claude/scripts/crontab-manager.py verify --tag "{name}"
   ```

**Gate**: Entry installed and verified.

### Phase 5: REPORT

Output: script path, cron schedule (human-readable + expression), log directory, budget per run, tag for management, and management commands:

```
python3 ~/.claude/scripts/crontab-manager.py list          # see all claude cron jobs
python3 ~/.claude/scripts/crontab-manager.py verify --tag {name}  # health check
python3 ~/.claude/scripts/crontab-manager.py remove --tag {name}   # uninstall
```

To modify an existing wrapper, regenerate with `--force`.

## Error Handling

### Error: "tag already exists"
Either `remove --tag {name}` first, or choose a different name.

### Error: "claude: command not found" in cron
Cron has minimal PATH. `generate-wrapper` resolves the absolute path at generation time. If the path changes, regenerate with `--force`.

### Error: "crontab install failed"
Check `crontab -l` manually. Restore from `~/.claude/crontab-backups/`.

## References

- `scripts/crontab-manager.py` — all crontab mutations (add, remove, list, verify, generate-wrapper)
- `skills/cron-job-auditor/SKILL.md` — validation checks for generated scripts
