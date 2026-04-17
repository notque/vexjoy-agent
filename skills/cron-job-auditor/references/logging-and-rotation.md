# Logging and Log Rotation Reference

> **Scope**: Cron script logging patterns — timestamps, structured output, log rotation, stderr/stdout routing
> **Version range**: bash 4.0+, GNU coreutils date (all versions), logrotate 3.x
> **Generated**: 2026-04-16

---

## Overview

Cron jobs run headless — their output goes to the cron daemon (often emailed to root, often discarded). Without explicit logging to files, there is no record of what happened, when it ran, or why it failed. With logging but no rotation, log files grow unbounded until they fill the disk. The two most common cron logging failures: no timestamps (impossible to correlate with events), and no rotation (disk fills silently over weeks).

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| `exec >> "$LOG" 2>&1` | Logging all output to file (headless cron) | Need terminal output too |
| `exec > >(tee -a "$LOG") 2>&1` | Need output in log file AND terminal | Logging only to file |
| `date '+%Y-%m-%d %H:%M:%S'` | ISO timestamps in log lines | Using `$(date)` alone (locale-dependent) |
| `find logs -mtime +N -delete` | Simple rotation without logrotate | High-volume logs needing compression |
| `logrotate -s STATE CONFIG` | Production services, compressed archives needed | Simple scripts (overkill) |
| `LOG="logs/script_$(date +%Y%m%d).log"` | Daily log files (self-rotating by name) | Logs needed across multiple days in one file |

---

## Correct Patterns

### Full logging setup (recommended default)

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/$(basename "$0" .sh)_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1   # redirect all stdout+stderr to log file

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Starting $(basename "$0") ==="
```

**Why**: `exec >> "$LOG_FILE" 2>&1` redirects all subsequent stdout and stderr to the log file. The daily filename (`_20260416.log`) provides natural rotation — yesterday's log is a separate file. The ISO timestamp in the `echo` line makes log correlation to events straightforward.

---

### Timestamped log function

```bash
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$(basename "$0")] $*"
}

log "Starting backup"
log "ERROR: rsync failed" >&2
```

**Why**: A `log()` function ensures every log line has a consistent timestamp and script name prefix. Easier to grep in a combined log file when multiple cron jobs share a log directory.

---

### Log rotation with find

```bash
# At the end of the script, after work is done
LOG_RETENTION_DAYS=30
find "$LOG_DIR" -name "*.log" -mtime +"$LOG_RETENTION_DAYS" -delete
log "Cleaned logs older than $LOG_RETENTION_DAYS days"
```

**Why**: `find -mtime +N -delete` removes files older than N days in one command. Run at the end of the script so rotation happens after logging the current run. Use a variable for retention days — magic numbers in scripts are hard to maintain.

---

### Separate stdout and stderr log files

```bash
LOG="logs/job_$(date +%Y%m%d).log"
ERR="logs/job_$(date +%Y%m%d).err"
exec >> "$LOG" 2>> "$ERR"
```

**Why**: Separating stdout and stderr makes error detection trivial: `[ -s "$ERR" ]` (true if file is non-empty) can drive failure notification. Useful when success output is verbose and you only want to alert on error output.

---

<!-- no-pair-required: section heading; individual anti-patterns below carry Do-instead blocks -->
## Anti-Pattern Catalog

### ❌ No logging at all (relying on cron email)

**Detection**:
```bash
grep -rL '>> .*log\|tee.*log\|LOG=' --include="*.sh" scripts/ cron/ jobs/
rg -L '>> .*\.log|tee .*\.log|LOG=' --type sh
```

**What it looks like**:
```bash
#!/bin/bash
set -e
cd /var/data
python3 process.py
rsync -avz output/ backup/
```

**Why wrong**: All output goes to cron's mail system (usually `nobody@localhost`, usually discarded). When the job fails, there is no record of what was running, what the error was, or when the last successful run occurred. Post-incident investigation is impossible.

**Do instead:** Add `exec >> "$LOG_FILE" 2>&1` near the top, after defining `LOG_FILE`.

---

### ❌ Timestamps missing or locale-dependent format

**Detection**:
```bash
  # Scripts using bare $(date) without format string
grep -rn '\$(date)[^+]' --include="*.sh" scripts/ cron/
  # Scripts with echo/printf but no date at all
grep -rl "echo\|printf" --include="*.sh" scripts/ | xargs grep -L "date"
```

**What it looks like**:
```bash
echo "Starting job"   # no timestamp at all

  # or locale-dependent:
echo "$(date): Starting"  # Thu Apr 16 20:07:00 UTC 2026 (hard to sort/grep)
```

**Why wrong**: Without timestamps, log lines from different runs blend together. Locale-dependent `date` output sorts lexicographically wrong and is hard to parse programmatically. In a post-incident review, "which run caused this?" becomes guesswork.

**Do instead:**
```bash
echo "$(date '+%Y-%m-%d %H:%M:%S'): Starting job"
  # Output: 2026-04-16 20:07:00 (sorts correctly, easily parsed)
```

---

### ❌ No log rotation (unbounded growth)

**Detection**:
```bash
grep -rl "\.log" --include="*.sh" scripts/ | xargs grep -L "mtime\|logrotate\|rotate"
rg -l '\.log' --type sh | xargs rg -L 'mtime|logrotate|rotate'
```

**What it looks like**:
```bash
LOG="/var/log/myjob.log"
exec >> "$LOG" 2>&1
echo "$(date): Starting"
  # ... no rotation, this file grows forever ...
```

**Why wrong**: A daily cron job writing 1 MB of output fills 365 MB/year into a single file. On a VPS with a small `/var` partition, this causes disk-full failures in other services (nginx, postgres, syslog). The problem is usually noticed at 3am when cron itself fails to write.

**Do instead:**
```bash
  # Option 1: Daily log files (self-rotating by filename)
LOG="/var/log/myjob_$(date +%Y%m%d).log"
  # Add cleanup: find /var/log -name "myjob_*.log" -mtime +30 -delete

  # Option 2: Explicit rotation at end of script
find "$LOG_DIR" -name "*.log" -mtime +30 -delete
```

---

### ❌ Logging to stdout only (lost in cron daemon)

**Detection**:
```bash
grep -rL ">>" --include="*.sh" scripts/ cron/ | xargs grep -l "echo\|printf" 2>/dev/null
rg -L '>>' --type sh | xargs rg -l 'echo|printf' 2>/dev/null
```

**What it looks like**:
```bash
#!/bin/bash
set -e
echo "Starting at $(date)"
do_work
echo "Done"
  # All output captured by cron daemon, usually discarded or emailed to root
```

**Why wrong**: Cron captures stdout/stderr and emails them. Most systems have cron email disabled or pointing to an unread mailbox. Even when email works, you lose historical logs: only the most recent run's output is potentially available.

**Do instead:**
```bash
exec >> "/var/log/myjob_$(date +%Y%m%d).log" 2>&1
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| No log files despite cron running | Output goes to cron mail, not files | Add `exec >> "$LOG" 2>&1` |
| Log file disk usage growing unbounded | No rotation configured | Add `find $LOG_DIR -mtime +30 -delete` |
| Timestamp format is `Thu Apr 16 20:07` | Using bare `$(date)` | Use `$(date '+%Y-%m-%d %H:%M:%S')` |
| Log shows stdout but not error messages | `>> log` without `2>&1` | Change to `>> "$LOG" 2>&1` |
| `/var` disk full, cron stops working | Unbounded single log file | Switch to daily log files with rotation |
| Cannot tell which cron instance wrote what | Multiple jobs sharing one log, no prefix | Add script name to log prefix: `[$(basename "$0")]` |

---

## Detection Commands Reference

```bash
# No log file redirection
grep -rL '>> .*log\|tee.*log' --include="*.sh" scripts/ cron/ jobs/

# No timestamps in log output
grep -rl "echo" --include="*.sh" scripts/ | xargs grep -L "date"

# No log rotation
grep -rl "\.log" --include="*.sh" scripts/ | xargs grep -L "mtime\|logrotate\|rotate"

# Bare $(date) without format (locale-dependent output)
grep -rn '\$(date)[^+]' --include="*.sh" scripts/ cron/

# Stdout only (no file redirection)
grep -rL ">>" --include="*.sh" scripts/ cron/ | xargs grep -l "echo\|printf" 2>/dev/null
```
