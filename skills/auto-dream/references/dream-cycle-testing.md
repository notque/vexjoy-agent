# Dream Cycle Testing Reference

> **Scope**: Patterns for safely testing the auto-dream cycle — dry-run validation, output verification, phase isolation, and graduation candidate inspection. Does NOT cover production execution or memory file authoring.
> **Version range**: All toolkit versions with `scripts/auto-dream-cron.sh` and the 7-phase dream prompt
> **Generated**: 2026-04-16 — verify script flags against `./scripts/auto-dream-cron.sh --help`

---

## Overview

Testing the dream cycle is high-stakes: a mis-run writes to real memory files, archives active memories, and commits graduation branches. The safe testing model is dry-run first, inspect outputs in `~/.claude/state/`, then run a live cycle against a snapshot copy of your memory directory. Never run `--execute` against your live memory directory without reading the dry-run report first.

---

## Pattern Table

| Test Goal | Command | Safe? |
|-----------|---------|-------|
| Full dry-run (no mutations) | `./scripts/auto-dream-cron.sh` | Yes — default mode |
| Read what would be consolidated | `cat ~/.claude/state/last-dream.md` | Yes |
| Inspect graduation candidates without graduating | SQLite query (see below) | Yes |
| Live cycle against a snapshot | `DREAM_MEMORY_DIR=/tmp/test-memory ./scripts/auto-dream-cron.sh --execute` | Yes, safe |
| Live cycle against real memory | `./scripts/auto-dream-cron.sh --execute` | Use with caution |
| Check cron registration | `python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream` | Yes |

---

## Correct Patterns

### Dry-run validation — verifying scan and analysis

The default invocation is always read-only:

```bash
# Run dry-run (no --execute = no filesystem mutations to memory files)
./scripts/auto-dream-cron.sh

# Verify the scan document was written
ls -la ~/.claude/state/dream-scan-*.md | tail -1

# Verify the analysis document was written
ls -la ~/.claude/state/dream-analysis-*.md | tail -1

# Read the consolidated report (written in all modes)
cat ~/.claude/state/last-dream.md
```

**Why**: Dry-run still executes SCAN and ANALYZE phases fully — reading memory files, querying SQLite, reading git log — but CONSOLIDATE and SYNTHESIZE only describe proposed changes without writing them. The report file (`last-dream.md`) is always written, so you see exactly what a live run would do.

---

### Inspecting graduation candidates before GRADUATE runs

```bash
# Query graduation candidates directly — no dream cycle needed
python3 -c "
import sys; sys.path.insert(0, 'hooks/lib')
from learning_db_v2 import query_graduation_candidates
import json
candidates = query_graduation_candidates()
print(json.dumps(candidates, indent=2))
"

# Count graduation-ready entries (confidence >= 0.9, 3+ observations)
sqlite3 ~/.claude/learning.db "
  SELECT pattern_key, confidence, observation_count
  FROM patterns
  WHERE confidence >= 0.9 AND observation_count >= 3
  ORDER BY confidence DESC LIMIT 10;
"

# Check if any graduation branches already exist from a prior run
git branch --list 'dream/graduate-*'
```

**Why**: The GRADUATE phase only runs when entries meet both thresholds (confidence >= 0.9 AND 3+ observations). Checking first prevents surprises and lets you inspect what would be promoted before the dream cycle touches agent files. If a graduation branch already exists, the new cycle skips GRADUATE to avoid duplicate branches.

---

### Safe live testing with a memory snapshot

To test CONSOLIDATE and SYNTHESIZE without risk to real memories:

```bash
# 1. Copy your real memory directory to a temp location
SNAP="/tmp/test-dream-memory-$(date +%Y%m%d)"
cp -r ~/.claude/projects/-home-feedgen-claude-code-toolkit/memory/ "${SNAP}/"

# 2. Run a live cycle against the snapshot only
DREAM_MEMORY_DIR="${SNAP}" ./scripts/auto-dream-cron.sh --execute

# 3. Inspect what changed in the snapshot
diff -r ~/.claude/projects/-home-feedgen-claude-code-toolkit/memory/ "${SNAP}/"

# 4. Read the report (always written to ~/.claude/state/)
cat ~/.claude/state/last-dream.md
```

**Why**: `DREAM_MEMORY_DIR` overrides the default memory path set by the wrapper script via `envsubst`. All CONSOLIDATE and SYNTHESIZE operations happen in the snapshot, leaving real memories untouched. The state directory (`~/.claude/state/`) still receives report files — this is expected and safe.

---

### Verifying output file structure after a run

```bash
DATE=$(date +%Y-%m-%d)
STATE_DIR="${HOME}/.claude/state"

# Scan document (SCAN phase, all modes)
[ -f "${STATE_DIR}/dream-scan-${DATE}.md" ] && echo "PASS: scan doc" || echo "FAIL: scan doc missing"

# Analysis document (ANALYZE phase, all modes)
[ -f "${STATE_DIR}/dream-analysis-${DATE}.md" ] && echo "PASS: analysis doc" || echo "FAIL: analysis doc missing"

# Report (REPORT phase, all modes)
[ -f "${STATE_DIR}/last-dream.md" ] && echo "PASS: report" || echo "FAIL: report missing"

# Injection payload (SELECT phase, all modes — read-only)
HASH=$(echo "/home/feedgen/claude-code-toolkit" | md5sum | cut -c1-8)
[ -f "${STATE_DIR}/dream-injection-${HASH}.md" ] && echo "PASS: injection payload" || echo "FAIL: injection payload missing"
```

**Why**: A dry-run that produces no output files means something failed silently. SCAN and ANALYZE always produce their dated documents. A missing `last-dream.md` means REPORT did not complete — check the cron log for the error. A missing injection payload means SELECT failed, and the next session will start without memory context.

---

## Anti-Pattern Catalog
<!-- no-pair-required: section heading only, paired Do instead blocks appear in each sub-entry below -->

### ❌ Running `--execute` without reading the dry-run report first

**Detection**:
```bash
# Look for --execute runs in cron logs without a preceding dry-run same day
grep -l 'execute' cron-logs/auto-dream/run-*.log | while read f; do
  date=$(basename "$f" | grep -oP '\d{4}-\d{2}-\d{2}')
  grep -l "dry" cron-logs/auto-dream/run-*${date}*.log 2>/dev/null || echo "No dry-run: $f"
done
```

**What it looks like**:
```bash
./scripts/auto-dream-cron.sh --execute  # What will it consolidate? Unknown.
```

**Why wrong**: The dream cycle can archive active memories if it mis-classifies them as stale. Without reading the dry-run report, you don't know which memories are flagged for archiving until they're already moved. New memory files that haven't appeared in recent sessions yet may have all three staleness signals trip at once.

**Do instead**: Always run the cron script without `--execute` first and read `~/.claude/state/last-dream.md` to confirm which memories would be consolidated or archived. Only pass `--execute` once the report shows the expected operations.

**Fix**:
```bash
./scripts/auto-dream-cron.sh              # Step 1: dry run
cat ~/.claude/state/last-dream.md         # Step 2: read what would happen
./scripts/auto-dream-cron.sh --execute    # Step 3: proceed if report looks correct
```

---

### ❌ Testing with learning.db missing

**Detection**:
```bash
ls -la ~/.claude/learning.db 2>/dev/null || echo "MISSING: learning.db"

# Check if the last dream report noted a SQLite failure
grep -i 'sqlite\|database\|learning.db\|failed' ~/.claude/state/last-dream.md | head -5
```

**What it looks like**:
<!-- no-pair-required: this is the detection sub-block inside a code fence; Do instead appears in the enclosing anti-pattern entry -->
```
## Dream Report: 2026-04-16

SCAN: Read 28 memory files.
SQLite query failed: unable to open database file
ANALYZE: Cross-session patterns: none (no session data available)
```

**Why wrong**: When learning.db is missing, SCAN notes the failure and continues — the cycle does not abort. But ANALYZE then lacks session data, so SYNTHESIZE produces low-quality or no cross-session insights. A silent SQLite failure looks like a successful run when it's actually missing half its input.

**Do instead**: Before running any test cycle, verify `~/.claude/learning.db` exists and contains at least one week of sessions. If the database is absent, run a normal Claude Code session with hooks enabled to seed it before testing the dream cycle.

**Fix**:
```bash
# Verify learning.db exists before testing
[ -f ~/.claude/learning.db ] || echo "Run at least one Claude Code session with hooks enabled"

# Count sessions available to dream
sqlite3 ~/.claude/learning.db \
  "SELECT COUNT(*) FROM sessions WHERE start_time > datetime('now', '-7 days');"
```

---

### ❌ Wrapping cron script output and losing the exit code

**Detection**:
```bash
# In any custom test scripts that pipe auto-dream-cron.sh output:
grep -n '\$?' test*.sh 2>/dev/null | grep -v 'PIPESTATUS'
```

**What it looks like**:
```bash
./scripts/auto-dream-cron.sh --execute | tee test-output.log
echo "Exit: $?"  # Always 0 — tee's exit code, not claude's
```

**Why wrong**: The wrapper script handles `PIPESTATUS[0]` internally, but a custom test wrapper that pipes the cron script inherits the same problem. `$?` after a pipe reflects the last command (`tee`), not the cron script. A Claude session that errors mid-run silently appears as success.

**Do instead**: Capture `${PIPESTATUS[0]}` immediately after any pipe from the cron script. Treat any non-zero exit code as a test failure regardless of what the log file contains.

**Fix**:
```bash
./scripts/auto-dream-cron.sh --execute 2>&1 | tee test-output.log
CRON_EXIT="${PIPESTATUS[0]}"
echo "Dream exit code: ${CRON_EXIT}"
[ "${CRON_EXIT}" -eq 0 ] && echo "PASS" || echo "FAIL"
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| No scan document after dry-run | SCAN phase failed; check cron log | `ls -t cron-logs/auto-dream/run-*.log \| head -1 \| xargs tail -50` |
| No injection payload file | SELECT phase skipped or DREAM_PROJECT_HASH wrong | Verify `DREAM_PROJECT_HASH`; check state dir path |
| `last-dream.md` unchanged from prior run | Lockfile blocked the run (prior run still active) | `rm /tmp/auto-dream.lock` then retry |
| Dry-run shows 0 memories scanned | `DREAM_MEMORY_DIR` path wrong | Check envsubst output; verify memory dir exists with `ls` |
| `query_graduation_candidates` ImportError | `hooks/lib` not on `sys.path` | Add `sys.path.insert(0, 'hooks/lib')` before import |
| Graduation branch already exists | Prior GRADUATE phase left the branch | Review branch then `git branch -d dream/graduate-YYYY-MM-DD` |

---

## Detection Commands Reference

```bash
# Check all expected output files exist after a run
ls ~/.claude/state/dream-{scan,analysis}-$(date +%Y-%m-%d).md 2>/dev/null

# Read the last dream report
cat ~/.claude/state/last-dream.md

# Count active graduation candidates
sqlite3 ~/.claude/learning.db \
  "SELECT COUNT(*) FROM patterns WHERE confidence >= 0.9 AND observation_count >= 3;"

# Check for graduation branches
git branch --list 'dream/graduate-*'

# Read the most recent cron run log
ls -t cron-logs/auto-dream/run-*.log | head -1 | xargs tail -50

# Verify cron is registered
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

---

## See Also

- `skills/auto-dream/references/headless-cron-patterns.md` — wrapper script, lockfile, budget cap, dry-run toggle
- `skills/auto-dream/references/memory-file-operations.md` — what CONSOLIDATE and SYNTHESIZE write
- `skills/auto-dream/dream-prompt.md` — the full 7-phase prompt with safety constraints
