---
name: headless-cron-creator
description: |
  Generate headless Claude Code cron jobs from a task description and schedule.
  Creates a wrapper script with safety mechanisms (lockfile, budget cap, dry-run
  default, logging) and installs crontab entries via deterministic Python script.
  Use when user says "schedule", "run every", "cron job", "run twice daily",
  "run hourly", "run daily", "run weekly", or "schedule task".
version: 1.0.0
user-invocable: true
argument-hint: "<name> <schedule> <prompt>"
agent: python-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Edit
  - Glob
  - Grep
---

# Headless Cron Creator Skill

## Operator Context

This skill operates as an operator for creating headless Claude Code cron jobs,
configuring Claude's behavior for safe, templated cron job generation. It
implements the **Scaffold → Validate → Install** pattern with deterministic
Python scripts handling all crontab mutations.

### Hardcoded Behaviors (Always Apply)
- **Never pipe to `crontab -`** — all crontab mutations go through `scripts/crontab-manager.py`
- **Backup before mutate** — every crontab change creates a timestamped backup in `~/.claude/crontab-backups/`
- **Dry-run default** — generated scripts do nothing destructive without `--execute`
- **Budget cap** — every generated script has `--max-budget-usd` (default $2.00)
- **Lockfile** — every generated script uses `flock` to prevent concurrent runs
- **No `--bare`** — breaks OAuth/keychain auth
- **No `--dangerously-skip-permissions`** — `--permission-mode auto` is sufficient
- **No `CronCreate` tool** — session-scoped, not persistent
- **Off-minute scheduling** — never use `:00` or `:30` minutes; spread load with odd minutes (7, 23, 47)
- **Tag all entries** — every crontab entry gets a `# claude-cron: <tag>` marker for safe identification
- **Full absolute paths in crontab** — cron has minimal PATH; all commands use absolute paths

### Default Behaviors (ON unless disabled)
- **Auto-validate with cron-job-auditor** — run the auditor on every generated script
- **Show next-steps** — print the exact commands to test and install
- **Heredoc prompts** — embed prompt text via bash heredoc to avoid escaping issues
- **Per-run log files** — `tee` output to timestamped log files

### Optional Behaviors (OFF unless enabled)
- **Auto-install** — install the crontab entry (requires explicit user confirmation)
- **Custom allowed-tools** — override the default `Bash Read` tool set
- **Custom budget** — override the default $2.00 per-run budget

## What This Skill CAN Do
- Generate wrapper scripts from task descriptions
- Install/remove/verify crontab entries safely
- List all Claude Code cron jobs
- Validate generated scripts against cron best practices

## What This Skill CANNOT Do
- Execute the generated cron jobs (that's cron's job)
- Modify existing wrapper scripts (regenerate with `--force` instead)
- Manage non-Claude crontab entries (only touches `# claude-cron:` tagged entries)
- Install crontab entries without user confirmation

---

## Instructions

### Phase 1: PARSE

**Goal**: Extract job parameters from the user's request.

**Required parameters**:
- **name** — short kebab-case identifier (e.g., `reddit-automod`, `feed-health-check`)
- **prompt** — what Claude should do each run (natural language)
- **schedule** — cron expression or human-readable interval

**Optional parameters** (with defaults):
- **workdir** — where to `cd` before running (default: current repo root)
- **budget** — max USD per run (default: `2.00`)
- **allowed-tools** — which tools the headless session can use (default: `Bash Read`)
- **logdir** — where to store logs (default: `{workdir}/cron-logs/{name}`)

**Human-readable schedule conversion**:

| Human Input | Cron Expression |
|-------------|----------------|
| every 12 hours | `7 */12 * * *` |
| twice daily | `7 8,20 * * *` |
| hourly | `23 * * * *` |
| daily at 6am | `7 6 * * *` |
| weekly on sunday | `7 9 * * 0` |
| every 30 minutes | `*/30 * * * *` |

Always use off-minutes (7, 23, 47) instead of :00/:30 to spread load.

**Gate**: All required parameters extracted. Proceed to Phase 2.

### Phase 2: GENERATE

**Goal**: Create the wrapper script using `crontab-manager.py generate-wrapper`.

```bash
python3 ~/.claude/scripts/crontab-manager.py generate-wrapper \
  --name "{name}" \
  --prompt "{prompt}" \
  --schedule "{schedule}" \
  --workdir "{workdir}" \
  --budget "{budget}" \
  --allowed-tools "{allowed_tools}"
```

Review the generated script. Verify it contains:
- [ ] `set -euo pipefail`
- [ ] `flock` lockfile
- [ ] `--permission-mode auto`
- [ ] `--max-budget-usd`
- [ ] `--no-session-persistence`
- [ ] `--allowedTools`
- [ ] `tee` to per-run log file
- [ ] Dry-run/execute toggle
- [ ] Exit code propagation via `PIPESTATUS[0]`

**Gate**: Script generated and reviewed. Proceed to Phase 3.

### Phase 3: VALIDATE

**Goal**: Verify the generated script meets cron best practices.

1. Run the script in dry-run mode:
   ```bash
   bash -n scripts/{name}-cron.sh  # syntax check
   ```

2. Run `cron-job-auditor` checks manually:
   - [ ] Error handling (`set -e`)
   - [ ] Lock file (`flock`)
   - [ ] Logging (`tee`, `LOG_DIR`)
   - [ ] Working directory (absolute `cd`)
   - [ ] PATH awareness (absolute `claude` path)
   - [ ] Cleanup on exit (lock release)

**Gate**: All checks pass. Proceed to Phase 4.

### Phase 4: INSTALL

**Goal**: Install the crontab entry with user confirmation.

1. Show the proposed entry:
   ```bash
   python3 ~/.claude/scripts/crontab-manager.py add \
     --tag "{name}" \
     --schedule "{schedule}" \
     --command "{absolute_script_path} --execute >> {logdir}/cron.log 2>&1" \
     --dry-run
   ```

2. **Ask the user for confirmation** before installing.

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

**Gate**: Entry installed and verified. Proceed to Phase 5.

### Phase 5: REPORT

**Goal**: Summarize the created cron job.

Output:
- Script path
- Cron schedule (human-readable + expression)
- Log directory
- Budget per run
- Tag for management
- Commands for future management:
  ```
  python3 ~/.claude/scripts/crontab-manager.py list          # see all claude cron jobs
  python3 ~/.claude/scripts/crontab-manager.py verify --tag {name}  # health check
  python3 ~/.claude/scripts/crontab-manager.py remove --tag {name}   # uninstall
  ```

---

## Error Handling

### Error: "tag already exists"
Cause: A cron entry with this tag is already installed.
Solution: Either `remove --tag {name}` first, or choose a different name.

### Error: "claude: command not found" in cron
Cause: Cron has minimal PATH; `claude` isn't in it.
Solution: `generate-wrapper` resolves the absolute path to `claude` at generation time.
If the path changes, regenerate the wrapper with `--force`.

### Error: "crontab install failed"
Cause: System crontab service issue.
Solution: Check `crontab -l` manually. Restore from `~/.claude/crontab-backups/`.

---

## Anti-Patterns

### Anti-Pattern 1: Piping to crontab
**What it looks like**: `crontab -l | { cat; echo "new entry"; } | crontab -`
**Why wrong**: If the pipe fails mid-stream, the entire crontab is wiped.
**Do instead**: Always use `crontab-manager.py` which writes to temp files.

### Anti-Pattern 2: Using CronCreate tool
**What it looks like**: Calling the `CronCreate` tool to schedule jobs.
**Why wrong**: Session-scoped only — dies when session ends, auto-expires after 7 days.
**Do instead**: Use system `crontab` via `crontab-manager.py`.

### Anti-Pattern 3: Round-number scheduling
**What it looks like**: `0 */6 * * *` or `30 * * * *`
**Why wrong**: Every cron job on the system fires at :00/:30, creating load spikes.
**Do instead**: Use off-minutes like `7`, `23`, `47`.
