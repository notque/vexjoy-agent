# Shell Error Handling Reference

> **Scope**: bash/sh error handling patterns for cron scripts — errexit, pipefail, trap, exit codes
> **Version range**: bash 4.0+, sh (POSIX)
> **Generated**: 2026-04-16

---

## Overview

Cron scripts run unattended. Without strict error handling, a failing command is silently ignored and subsequent commands run against corrupt or missing state. The most common production incident pattern: a cron script fails partway through, leaves partial state, and the next run compounds the damage. `set -euo pipefail` is the single highest-ROI addition to any cron script.

---

## Pattern Table

| Pattern | Shell | Use When | Avoid When |
|---------|-------|----------|------------|
| `set -euo pipefail` | bash 4.0+ | Default for all bash cron scripts | Using `sh` (no pipefail) |
| `set -e` | POSIX sh | Script must be sh-compatible | Bash available (use full form) |
| `|| exit 1` | Both | Single-command guard when errexit disabled | errexit already set |
| `trap 'handler' ERR` | bash | Need context on which line failed | sh (not POSIX) |
| `trap 'cleanup' EXIT` | Both | Always need cleanup on exit | Never — always use for lock files |

---

## Correct Patterns

### Full bash header (use this as the default)

Every cron bash script should start with this block.

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
```

**Why**: `set -e` exits on error, `set -u` catches undefined variable references (typos like `$PAHT`), `set -o pipefail` catches failures inside pipes like `cat file | process`. Without `pipefail`, `failing_command | grep something` returns 0 because grep succeeds.

---

### ERR trap for diagnostic context

```bash
trap 'echo "ERROR: line $LINENO, exit code $?" >&2' ERR
```

**Why**: When `set -e` triggers an exit, the ERR trap fires before exit, logging which line failed. Without this, you only know the script exited — not where.

---

### EXIT trap for guaranteed cleanup

```bash
LOCK_FILE="/tmp/$(basename "$0").lock"
TMPDIR="/tmp/$(basename "$0" .sh)_$$"

trap 'rm -f "$LOCK_FILE"; rm -rf "$TMPDIR"' EXIT
```

**Why**: EXIT fires even on normal exit, `set -e` exit, and signal kills (except SIGKILL). Lock files and temp dirs are cleaned even when the script exits from an error.

---

### Checking exit codes explicitly

```bash
# When you need the exit code of a command that might fail
if ! rsync -avz source/ dest/; then
    echo "rsync failed" >&2
    exit 1
fi

# Or capture for conditional logic
rsync -avz source/ dest/ && echo "sync OK" || { echo "sync FAILED" >&2; exit 1; }
```

**Why**: With `set -e`, any non-zero exit aborts the script. When you want to handle failure specifically, use `if !` or `|| { ... }` — both prevent `set -e` from triggering while still handling the error.

---

<!-- no-pair-required: section heading; individual anti-patterns below carry Do-instead blocks -->
## Anti-Pattern Catalog

### ❌ Missing set -e / no error handling

**Detection**:
```bash
grep -rL "set -e" --include="*.sh" scripts/ cron/ jobs/ bin/
rg -L "set -e" --type sh
```

**What it looks like**:
```bash
#!/bin/bash
cd /var/data
rm -rf old_files/
process_data.py input.csv > output.csv
mv output.csv /var/reports/
```

**Why wrong**: If `process_data.py` fails (non-zero exit), `mv` still runs, overwriting `/var/reports/` with an empty or corrupt file. The failure is invisible — cron marks the job as succeeded.

**Fix**:
```bash
#!/bin/bash
set -euo pipefail
```

---

### ❌ Piped commands ignoring pipeline failures

**Detection**:
```bash
grep -rl "\|" --include="*.sh" scripts/ cron/ | xargs grep -L "pipefail"
rg '\|\s+\w+' --type sh -l | xargs rg -L 'pipefail'
```

**What it looks like**:
```bash
#!/bin/bash
set -e  # but no pipefail!
pg_dump mydb | gzip > backup.sql.gz    # if pg_dump fails, gzip writes a 0-byte gz file
find /data -name "*.log" | xargs gzip  # if find fails, gzip still runs on partial list
```

**Why wrong**: Without `pipefail`, the exit code of a pipeline is the exit code of the last command. A failed `pg_dump` followed by a successful `gzip` returns 0, so the backup appears to succeed but contains no data.

**Do instead:**
```bash
#!/bin/bash
set -euo pipefail
pg_dump mydb | gzip > backup.sql.gz   # now fails if pg_dump fails
```

**Version note**: `pipefail` is bash-specific. If the script must be POSIX `sh`, use intermediate files: `pg_dump mydb > dump.sql && gzip dump.sql && mv dump.sql.gz backup.sql.gz`.

---

### ❌ Undefined variable silently expanding to empty string

**Detection**:
```bash
grep -rL "set -u\|set -euo\|nounset" --include="*.sh" scripts/ cron/
grep -rn 'rm -rf.*\$' --include="*.sh" scripts/
```

**What it looks like**:
```bash
#!/bin/bash
set -e
rm -rf "$BACKUP_DIR/"    # if BACKUP_DIR is unset, expands to "rm -rf /"
rsync -avz "$SRC_PATH/" "$DEST/"   # silently copies nothing if SRC_PATH unset
```

**Why wrong**: Without `set -u`, unset variables expand to empty string. `rm -rf "$BACKUP_DIR/"` becomes `rm -rf "/"` when `BACKUP_DIR` is unset. Catastrophic and silent.

**Do instead:**
```bash
set -u   # or set -euo pipefail
  # Also enforce with parameter expansion:
BACKUP_DIR="${BACKUP_DIR:?BACKUP_DIR must be set}"
```

---

### ❌ Swallowing errors with bare || true

**Detection**:
```bash
grep -rn "|| true" --include="*.sh" scripts/ cron/ jobs/
rg '\|\|\s*true' --type sh
```

**What it looks like**:
```bash
create_schema.sql || true    # if schema creation fails, continue anyway
validate_data.py || true     # silently ignores validation failures
```

**Why wrong**: `|| true` converts any failure into success. Combined with `set -e`, it suppresses the exit but also suppresses the failure signal. The script then continues into a state it was never designed to handle.

**Do instead:**
```bash
  # If failure is truly acceptable, log it explicitly:
create_schema.sql || echo "WARNING: schema creation failed, may already exist" >&2
  # If failure means something: remove || true and let set -e handle it
```

---

## Error-Fix Mappings

| Symptom / Error | Root Cause | Fix |
|-----------------|------------|-----|
| Script exits with code 0 but produced no output | Pipe failure masked without pipefail | Add `set -o pipefail` |
| `rm -rf /` or similar catastrophic expansion | Undefined variable with `rm -rf "$VAR/"` | Add `set -u` or `${VAR:?msg}` |
| Script continues after database/API failure | Missing `set -e` or `|| true` swallowing errors | Add `set -euo pipefail`, remove `|| true` |
| `unbound variable` error on bash run | `set -u` catching an undefined var | Set the variable or provide default: `${VAR:-default}` |
| Cron reports success but data is wrong | Pipeline failure not caught | Add `pipefail`, check each pipe stage |
| `bad substitution` in sh | Using bash syntax in a `#!/bin/sh` script | Change shebang to `#!/bin/bash` |

---

## Detection Commands Reference

```bash
# Missing set -e (all shell scripts without error handling)
grep -rL "set -e" --include="*.sh" scripts/ cron/ jobs/ bin/

# Missing pipefail (scripts with pipes but no pipefail)
grep -rl "\|" --include="*.sh" scripts/ | xargs grep -L "pipefail"

# Dangerous || true usage
grep -rn "|| true" --include="*.sh" scripts/ cron/

# Risky rm -rf with variable
grep -rn 'rm -rf.*\$' --include="*.sh" scripts/

# Missing set -u
grep -rL "set -u\|nounset" --include="*.sh" scripts/ cron/
```
