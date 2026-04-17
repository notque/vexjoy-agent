# Concurrency and Lock File Reference

> **Scope**: Preventing concurrent cron job execution — flock, PID files, lock file patterns
> **Version range**: Linux (flock via util-linux 2.20+), macOS (flock via brew), all bash versions
> **Generated**: 2026-04-16

---

## Overview

Cron jobs fire on a schedule with no built-in awareness of whether a previous run is still executing. If a job runs longer than its interval (a slow backup, a stalled network call), two instances run simultaneously — both writing the same output files, both modifying the same database rows, both sending duplicate notifications. Lock files are the standard mitigation. `flock` is preferred over manual PID files because the kernel releases the lock automatically on process death, even on crash.

---

## Pattern Table

| Mechanism | Reliability | Use When | Avoid When |
|-----------|-------------|----------|------------|
| `flock -n FD` | High — kernel-managed | bash scripts, Linux | macOS without util-linux |
| `flock -n LOCKFILE CMD` | High — single-shot | Wrapping an external command | Script needs lock for full duration |
| PID file + `kill -0` | Medium — race window | Must be sh-compatible | Can use flock |
| `mkdir` atomic lock | Low — no auto-cleanup | Absolute POSIX sh only | Any other case |
| `lockrun` wrapper | High | Wrapping a command externally | Not installed |

---

## Correct Patterns

### flock with file descriptor (preferred)

```bash
#!/bin/bash
set -euo pipefail

LOCK_FILE="/tmp/$(basename "$0").lock"
exec 200>"$LOCK_FILE"

# -n: non-blocking (fail immediately if locked)
flock -n 200 || { echo "$(date): Another instance is running, exiting." >&2; exit 0; }

trap 'rm -f "$LOCK_FILE"' EXIT

# ... rest of script ...
```

**Why**: File descriptor 200 holds the lock for the script's lifetime. The kernel automatically releases it when the process exits, even on crash or SIGKILL. `exit 0` (not `exit 1`) on conflict — cron sees success, not failure; this prevents alert fatigue from overlapping runs.

---

### flock wrapping a command (single-shot)

```bash
flock -n /tmp/my-job.lock -c '/usr/local/bin/my-job.py'
```

**Why**: Simpler form when the entire job is a single command. No cleanup needed — lock releases when the command exits.

---

### PID file fallback (sh-compatible)

```bash
#!/bin/sh
PID_FILE="/var/run/$(basename "$0").pid"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Already running (PID $OLD_PID)" >&2
        exit 0
    fi
    # Stale PID file — process is gone
    rm -f "$PID_FILE"
fi

echo $$ > "$PID_FILE"
trap 'rm -f "$PID_FILE"' EXIT
```

**Why**: `kill -0 PID` checks if the process exists without sending a signal. Stale PID files (from crashes) are cleaned up. Race window: two instances can pass the `[ -f ]` check simultaneously on fast systems — use `flock` when available.

---

<!-- no-pair-required: section heading; individual anti-patterns below carry Do-instead blocks -->
## Anti-Pattern Catalog

### ❌ No concurrency protection at all

**Detection**:
```bash
grep -rL "flock\|\.lock\|\.pid\|lockrun" --include="*.sh" scripts/ cron/ jobs/
rg -L 'flock|\.lock|\.pid' --type sh
```

**What it looks like**:
```bash
#!/bin/bash
set -euo pipefail
cd /var/data
python3 process_all_records.py   # runs for 45 min, cron fires again at minute 0
```

**Why wrong**: If the job takes longer than its interval, two instances run simultaneously. Both read the same input, both write to the same output, both update the same DB rows — producing duplicates, data corruption, or deadlocks.

**Do instead:** Add `flock` at the top of the script (see correct pattern above).

---

### ❌ Testing lock file existence without flock (TOCTOU race)

**Detection**:
```bash
grep -rn "if \[ -f.*lock\|test -f.*lock" --include="*.sh" scripts/ cron/
rg 'if \[ -f.*lock' --type sh
```

**What it looks like**:
```bash
LOCK="/tmp/myjob.lock"
if [ -f "$LOCK" ]; then
    echo "Running, exit"
    exit 0
fi
touch "$LOCK"    # race window between [ -f ] check and touch
trap 'rm -f $LOCK' EXIT
```

**Why wrong**: There is a TOCTOU race: two instances can both pass `[ -f "$LOCK" ]` before either creates the file. On a loaded system or slow filesystem, this happens. Result: both instances run concurrently despite the "protection."

**Do instead:** Use `flock -n` — the kernel makes the lock acquisition atomic.

```bash
exec 200>"/tmp/myjob.lock"
flock -n 200 || exit 0
```

---

### ❌ Using sleep-retry as a "lock"

**Detection**:
```bash
grep -rn "while.*lock\|sleep.*lock" --include="*.sh" scripts/ cron/
rg 'while.*lock' --type sh
```

**What it looks like**:
```bash
while [ -f /tmp/myjob.lock ]; do
    sleep 5
done
touch /tmp/myjob.lock
  # ... work ...
rm /tmp/myjob.lock
```

**Why wrong**: Busy-waits waste CPU, has the same TOCTOU race as file existence checks, and if the script crashes before `rm`, subsequent runs loop forever.

**Do instead:** Use `flock -w TIMEOUT` for waiting with a timeout, or `flock -n` to exit immediately.

```bash
  # Wait up to 5 minutes for the lock, then give up
flock -w 300 /tmp/myjob.lock -c 'your_command'
```

---

### ❌ Not removing the lock on abnormal exit

**Detection**:
```bash
  # Files that mention lock but not trap
grep -rl "lock\|\.pid" --include="*.sh" scripts/ cron/ | xargs grep -L "trap"
rg -l 'lock|\.pid' --type sh | xargs rg -L 'trap'
```

**What it looks like**:
```bash
touch /tmp/myjob.lock
do_work
rm /tmp/myjob.lock   # only runs on success; if set -e fires, lock is never removed
```

**Why wrong**: With `set -e`, any failure exits the script immediately — `rm` never runs. The lock file persists. All future runs think a job is still running and exit immediately, silently. The job never runs again until someone manually removes the lock.

**Do instead:** Always use `trap 'rm -f "$LOCK_FILE"' EXIT` instead of relying on explicit cleanup at the end.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Job never runs after a crash | Stale lock file from crashed previous run | Use `flock` (auto-released on death) or add PID validation to PID file check |
| Duplicate records / double-processing | No concurrency protection, job ran twice | Add `flock -n` at script start |
| Lock file stays after job fails | Missing `trap EXIT` | Replace end-of-script `rm` with `trap 'rm -f "$LOCK"' EXIT` |
| `flock: command not found` | macOS default shell / minimal container | Install `util-linux` or use PID file fallback |
| Two instances both acquired "lock" | File existence check instead of flock | Replace `[ -f $LOCK ]` pattern with `flock -n FD` |

---

## Detection Commands Reference

```bash
# No lock mechanism at all
grep -rL "flock\|\.lock\|\.pid\|lockrun" --include="*.sh" scripts/ cron/ jobs/

# File existence lock (TOCTOU risk)
grep -rn "if \[ -f.*\.lock\|test -f.*\.lock" --include="*.sh" scripts/

# Lock without trap (stale lock risk)
grep -rl "lock\|\.pid" --include="*.sh" scripts/ | xargs grep -L "trap"

# Sleep-retry lock pattern
grep -rn "while.*lock\|sleep.*lock" --include="*.sh" scripts/

# flock usage (positive check — these are doing it right)
grep -rn "flock" --include="*.sh" scripts/ cron/
```
