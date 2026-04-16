# Headless Cron Patterns Reference

> **Scope**: Operational patterns for running Claude Code as an unattended background process via cron. Covers wrapper script structure, lockfiles, budget capping, prompt templating, and logging. Does NOT cover interactive Claude Code usage.
> **Version range**: Claude Code CLI (all versions supporting `--permission-mode auto`)
> **Generated**: 2026-04-15 — verify flag names against current `claude --help` output

---

## Overview

Auto-dream runs as a headless cron process: `claude -p` receives the dream prompt and executes without any interactive session, CLAUDE.md context, or hooks. The wrapper script (`scripts/auto-dream-cron.sh`) handles safety concerns the Claude session cannot: preventing concurrent runs, capping spend, substituting project-specific paths, and dual-logging output. Getting these patterns wrong causes silent failures, duplicate runs, or runaway costs.

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `flock -n` non-blocking | Cron jobs that must not overlap | One-shot manual invocations |
| `--permission-mode auto` | All headless cron invocations | Never substitute `--dangerously-skip-permissions` |
| `--max-budget-usd 3.00` | Any unattended Claude invocation | Interactive sessions with human oversight |
| `--no-session-persistence` | Headless cron (clean state) | Stateful multi-turn workflows |
| `envsubst` | Runtime path injection into prompt templates | Hardcoded absolute paths in prompts |
| `PIPESTATUS[0]` | Any cron job with pipe to `tee` | Direct invocation without pipe |

---

## Correct Patterns

### Lockfile preventing concurrent runs

Use `flock -n` (non-blocking) so the second instance exits cleanly rather than waiting.

```bash
LOCKFILE="/tmp/auto-dream.lock"
exec 9>"${LOCKFILE}"
if ! flock -n 9; then
    echo "[dream] Already running — lockfile held. Skipping."
    exit 0
fi
```

**Why**: Without a lockfile, if the previous cycle runs long (slow SQLite, large memory scan), the next cron tick spawns a second Claude session. Two sessions simultaneously writing `MEMORY.md` corrupt the index. `flock -n` exits immediately if locked; `flock` without `-n` queues the second instance, creating back-to-back runs rather than skipping the conflicting tick.

---

### Safe permission mode and budget cap

```bash
claude \
    --permission-mode auto \
    --no-session-persistence \
    --max-budget-usd 3.00 \
    -p "${PROMPT_CONTENT}"
```

**Why**: `--permission-mode auto` permits all safe local operations (Read, Write, Edit, Bash) without interactive prompts — appropriate for a trusted local cron job. `--dangerously-skip-permissions` is functionally identical today but signals "I acknowledge this is dangerous" and may diverge in future versions. `--max-budget-usd` is the last line of defense against a prompt bug causing a runaway multi-dollar session.

---

### envsubst for runtime path injection

Template the prompt with `${VARIABLE}` placeholders; substitute at runtime:

```bash
# Export all variables the prompt template needs
export DREAM_MEMORY_DIR="/home/feedgen/.claude/projects/$(echo "$PWD" | tr '/' '-')/memory"
export DREAM_LEARNING_DB="/home/feedgen/.claude/learning.db"
export DREAM_STATE_DIR="/home/feedgen/.claude/state"
export DREAM_REPO_DIR="${SCRIPT_DIR}"
export DREAM_PROJECT_HASH=$(echo "${DREAM_REPO_DIR}" | md5sum | cut -c1-8)
export DREAM_DATE=$(date +%Y-%m-%d)
export DREAM_DRY_RUN_MODE="yes"

# Substitute into prompt template
PROMPT_CONTENT=$(envsubst < "${SCRIPT_DIR}/dream-prompt.md")
```

**Why**: Hardcoding absolute paths in `dream-prompt.md` breaks when the repo moves or when another user clones it. `envsubst` substitutes only `${VAR}` patterns — it does NOT evaluate shell expressions. Syntax like `${var:-default}` in the prompt passes through unchanged (safe). Use simple `${VAR}` names in prompt templates to avoid surprises.

---

### Dual logging with exit code preservation

```bash
LOG_DIR="${SCRIPT_DIR}/cron-logs/auto-dream"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/run-$(date +%Y-%m-%d-%H%M%S).log"

claude --permission-mode auto \
       --no-session-persistence \
       --max-budget-usd 3.00 \
       -p "${PROMPT_CONTENT}" | tee "${RUN_LOG}"

CLAUDE_EXIT="${PIPESTATUS[0]}"
exit "${CLAUDE_EXIT}"
```

**Why**: `|` creates a subshell for `tee`; without `PIPESTATUS[0]`, the script exits with `tee`'s code (always 0), not Claude's. A Claude session that errors mid-run silently looks like success to cron and any monitoring. `PIPESTATUS[0]` must be captured immediately after the pipe — it is overwritten by the next command.

---

### Dry-run/execute toggle via argument

```bash
DRY_RUN="yes"
for arg in "$@"; do
    case "$arg" in
        --execute) DRY_RUN="no" ;;
    esac
done
export DREAM_DRY_RUN_MODE="${DRY_RUN}"
```

**Why**: Default to dry-run (read-only). The cron entry passes `--execute`; manual invocations without the flag are always safe. This prevents accidental filesystem mutations during development and testing without requiring code changes.

---

## Anti-Pattern Catalog

### ❌ Using `--dangerously-skip-permissions` in cron

**Detection**:
```bash
grep -rn 'dangerously-skip-permissions' scripts/
rg 'dangerously.skip' scripts/ --type sh
```

**What it looks like**:
```bash
claude --dangerously-skip-permissions -p "${PROMPT}" | tee "${LOG}"
```

**Why wrong**: Semantically equivalent to `--permission-mode auto` today but communicates "I know this is risky" and may diverge in future Claude Code versions. Cron scripts are long-lived; use the explicit stable flag.

**Fix**:
```bash
claude --permission-mode auto -p "${PROMPT}" | tee "${LOG}"
```

---

### ❌ Ignoring PIPESTATUS — silent Claude failures

**Detection**:
```bash
# Find scripts that pipe to tee but don't capture PIPESTATUS
grep -A3 '| tee' scripts/*.sh | grep -v 'PIPESTATUS'
```

**What it looks like**:
```bash
claude -p "${PROMPT}" | tee "${LOG}"
echo "Done, exit: $?"   # $? is tee's exit code, always 0
```

**Why wrong**: A Claude session that crashes or hits the budget cap exits non-zero, but the script reports success. Cron mail, monitoring alerts, and retry logic all miss the failure.

**Fix**:
```bash
claude -p "${PROMPT}" | tee "${LOG}"
CLAUDE_EXIT="${PIPESTATUS[0]}"
exit "${CLAUDE_EXIT}"
```

---

### ❌ Missing budget cap on unattended invocations

**Detection**:
```bash
# Find cron scripts invoking claude without a budget cap
grep -L 'max-budget-usd' scripts/*cron*.sh
rg 'claude' scripts/ --type sh -l | xargs grep -L 'max-budget-usd'
```

**What it looks like**:
```bash
claude --permission-mode auto --no-session-persistence -p "${LARGE_PROMPT}"
# No --max-budget-usd: a prompt bug or unexpectedly large context can cost $50+
```

**Why wrong**: Budget cap is the last defense against a runaway unattended session. Even with `--no-session-persistence`, a misbehaving prompt can loop reasoning across tools and accumulate large costs before timing out.

**Fix**:
```bash
claude --permission-mode auto \
       --no-session-persistence \
       --max-budget-usd 3.00 \
       -p "${PROMPT}"
```

---

### ❌ Blocking flock — concurrent queuing instead of skip

**Detection**:
```bash
# Find flock calls missing the -n (non-blocking) flag
grep -n 'flock' scripts/*.sh | grep -v '\-n '
```

**What it looks like**:
```bash
exec 9>"${LOCKFILE}"
flock 9                # Blocking — waits indefinitely for the lock
claude -p "${PROMPT}" ...
```

**Why wrong**: If a slow run holds the lock past the next cron tick, the second instance queues rather than skipping. When the first finishes, the second starts immediately — creating back-to-back full cycles and doubling cost and mutations in the same day.

**Fix**:
```bash
if ! flock -n 9; then
    echo "[dream] Previous run still active. Skipping."
    exit 0
fi
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Script exits 0 but Claude log shows failure | `PIPESTATUS` not captured | Add `CLAUDE_EXIT="${PIPESTATUS[0]}"` immediately after pipe |
| Two dream processes running simultaneously | Missing `flock` or blocking `flock` | Use `flock -n` non-blocking lockfile pattern |
| `${DREAM_MEMORY_DIR}` appears literally in prompt | Variable not exported before `envsubst` | Add `export` to all template variables before `envsubst` call |
| `envsubst` collapses `${var:-default}` constructs | `envsubst` processes all `${...}` patterns | Escape as `\${var:-default}` or restrict with `envsubst '$VAR1 $VAR2'` |
| Session exceeds expected cost | No `--max-budget-usd` flag | Add `--max-budget-usd 3.00` to all unattended invocations |
| Cron runs but produces empty log file | Absolute path wrong in crontab | Use absolute paths; verify with `crontab-manager.py verify --tag auto-dream` |
| Dry-run changes not visible in report | `DREAM_DRY_RUN_MODE` not exported | Use `export DREAM_DRY_RUN_MODE=...` before prompt templating |

---

## Detection Commands Reference

```bash
# Missing budget cap in cron scripts
grep -L 'max-budget-usd' scripts/*cron*.sh

# Dangerous permissions flag usage
grep -rn 'dangerously-skip-permissions' scripts/

# Pipes to tee without PIPESTATUS capture
grep -A3 '| tee' scripts/*.sh | grep -v 'PIPESTATUS'

# Blocking flock (missing -n flag)
grep -n 'flock' scripts/*.sh | grep -v '\-n '

# Check for concurrent dream processes
pgrep -af 'auto-dream'

# Verify cron registration
python3 ~/.claude/scripts/crontab-manager.py list
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

---

## See Also

- `skills/auto-dream/dream-prompt.md` — prompt template with all `${VARIABLE}` placeholders
- `skills/auto-dream/references/memory-file-operations.md` — memory file lifecycle patterns
- `scripts/reddit-automod-cron.sh` — reference implementation of this headless cron pattern
