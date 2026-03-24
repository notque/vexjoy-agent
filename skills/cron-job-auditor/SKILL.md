---
name: cron-job-auditor
description: |
  Deterministic audit of cron/scheduled job scripts for reliability,
  error handling, logging, cleanup, and concurrency safety. Use when
  user says "audit cron", "check cron script", "cron best practices",
  "scheduled job review", or "bash script audit". Do NOT use for
  crontab scheduling syntax, systemd timers, or general shell linting
  without a cron/scheduled-job context.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "audit cron jobs"
    - "review scheduled scripts"
    - "cron safety"
  category: infrastructure
---

# Cron Job Auditor Skill

## Operator Context

This skill operates as an operator for cron script auditing workflows, configuring Claude's behavior for deterministic, checklist-driven static analysis. It implements the **Systematic Inspection** architectural pattern -- discover scripts, audit against best practices, report findings -- with **Domain Intelligence** embedded in cron-specific reliability patterns.

### Hardcoded Behaviors (Always Apply)
- **Read-Only**: Only read and analyze script files; never execute them
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before auditing
- **Pattern-Based Detection**: Use regex for reliable, reproducible checks
- **Structured Output**: Produce machine-parseable PASS/FAIL/WARN results
- **Severity Classification**: Every finding gets CRITICAL, HIGH, MEDIUM, or LOW
- **No Auto-Fix**: Report problems with recommendations; do not modify scripts

### Default Behaviors (ON unless disabled)
- **Full Checklist**: Run all 9 best-practice checks on every script
- **Actionable Recommendations**: Provide specific code fixes for every failure
- **Score Calculation**: Report pass/total as percentage
- **Recursive Discovery**: Search `scripts/`, `cron/`, `jobs/` directories for `.sh` files
- **Shebang Validation**: Verify scripts start with `#!/bin/bash` or equivalent

### Optional Behaviors (OFF unless enabled)
- **Strict Mode**: Treat MEDIUM/LOW findings as failures (raise exit code)
- **Custom Patterns**: Add project-specific checks beyond the standard 9
- **Crontab Schedule Analysis**: Parse crontab entries for scheduling conflicts
- **JSON Output**: Emit results as JSON instead of human-readable report

## What This Skill CAN Do
- Detect missing error handling, logging, lock files, and cleanup traps
- Check for explicit PATH/environment setup (cron has minimal defaults)
- Identify scripts vulnerable to concurrent execution
- Verify log rotation prevents unbounded disk growth
- Provide copy-paste code snippets to fix every finding
- Audit multiple scripts in a single pass with aggregate scoring

## What This Skill CANNOT Do
- Execute scripts or validate runtime behavior
- Parse crontab scheduling syntax (focus is script content)
- Check external dependencies or verify services are running
- Test notification delivery (email, webhook, Slack)
- Analyze complex control flow beyond pattern matching
- Replace a full shell linter (shellcheck) for syntax issues

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Locate all cron/scheduled scripts to audit.

**Step 1: Identify target scripts**

If the user provides specific paths, use those. Otherwise search:
```
scripts/*.sh, cron/*.sh, jobs/*.sh, bin/*.sh
```

Also check for scripts referenced in crontab files, Makefiles, or CI configs.

**Step 2: Validate targets**

For each discovered file:
- Confirm it exists and is readable
- Check it has a shell shebang (`#!/bin/bash`, `#!/bin/sh`, `#!/usr/bin/env bash`)
- Skip non-shell files (Python cron jobs, etc.) with a note

**Step 3: Log discovery results**

```markdown
## Scripts Found
1. scripts/daily_backup.sh (bash, 45 lines)
2. cron/cleanup.sh (bash, 22 lines)
3. jobs/sync_data.sh (SKIPPED: Python script)
```

**Gate**: At least one auditable shell script identified. Proceed only when gate passes.

### Phase 2: AUDIT

**Goal**: Run every check against every script. No shortcuts.

**Step 1: Read each script fully**

Read the entire file content. Do not sample or skip sections.

**Step 2: Run the 9-point checklist**

| # | Check | Patterns | Severity |
|---|-------|----------|----------|
| 1 | Error handling | `set -e`, `set -o errexit`, `\|\| exit` | CRITICAL |
| 2 | Exit code checking | `$?`, `if [ $? -eq`, `&& ... \|\|` | HIGH |
| 3 | Logging with timestamps | `>> *.log`, `$(date)`, `date +` | HIGH |
| 4 | Log rotation | `find -mtime -delete`, `logrotate`, `tail -n` | MEDIUM |
| 5 | Working directory | `cd "$(dirname"`, `SCRIPT_DIR=`, absolute paths | HIGH |
| 6 | PATH environment | `PATH=`, `export PATH`, `source *env` | MEDIUM |
| 7 | Lock file / concurrency | `.lock`, `flock`, `.pid`, lock file check | HIGH |
| 8 | Cleanup on exit | `trap ... EXIT`, `trap ... cleanup`, `rm -rf *tmp` | MEDIUM |
| 9 | Failure notification | `mail -s`, `curl *webhook`, `notify`, `alert` | LOW |

For each check, record:
- PASS with line number where pattern found, OR
- FAIL/WARN with specific recommendation

**Step 3: Calculate score**

```
Score = passed / total_checks * 100
```

Classify scripts: 90-100% Excellent, 70-89% Good, 50-69% Needs Work, <50% Critical.

**Gate**: All 9 checks run against every script. No checks skipped. Proceed only when gate passes.

### Phase 3: REPORT

**Goal**: Produce structured, actionable audit output.

**Step 1: Format per-script results**

```
CRON JOB AUDIT: scripts/daily_backup.sh
==================================================
  [PASS] Error handling (line 3)
  [PASS] Logging with timestamps (line 12)
  [FAIL] Lock file: No concurrent run prevention
  [WARN] PATH environment: PATH not explicitly set

SCORE: 7/9 (78%) - Good
```

**Step 2: Provide recommendations**

For every FAIL and WARN, provide a specific code snippet the user can paste:

```bash
# Recommendation: Add lock file
LOCK_FILE="/tmp/daily_backup.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Already running"; exit 0; }
trap "rm -f $LOCK_FILE" EXIT
```

**Step 3: Produce aggregate summary**

If auditing multiple scripts:

```
AGGREGATE SUMMARY
=================
Scripts audited: 4
Average score: 72%
Critical issues: 2 (missing error handling)
Most common gap: Lock files (3/4 scripts missing)
```

**Gate**: Every finding has a recommendation. Report is complete. Audit is done.

---

## Examples

### Example 1: Single Script Audit
User says: "Audit the backup cron script"
Actions:
1. Read `scripts/backup.sh`, verify shebang (DISCOVER)
2. Run 9-point checklist, record PASS/FAIL per check (AUDIT)
3. Format report with score and recommendations (REPORT)
Result: Structured report with actionable fixes

### Example 2: Repository-Wide Audit
User says: "Check all our cron jobs for best practices"
Actions:
1. Glob for `.sh` files in `scripts/`, `cron/`, `jobs/` (DISCOVER)
2. Audit each script against full checklist (AUDIT)
3. Per-script reports plus aggregate summary (REPORT)
Result: Comprehensive audit with prioritized remediation list

---

## Error Handling

### Error: "No Shell Scripts Found"
Cause: Scripts in unexpected locations, or cron jobs written in Python/Ruby
Solution:
1. Ask user for explicit paths
2. Search broader: `**/*.sh` across the entire repository
3. Check crontab entries for referenced file paths

### Error: "Script Has No Shebang"
Cause: Script relies on default shell interpreter
Solution:
1. Still audit the script (treat as bash)
2. Add finding: "Missing shebang line" as MEDIUM severity
3. Recommend adding `#!/bin/bash` or `#!/usr/bin/env bash`

### Error: "Regex Produces False Positive"
Cause: Pattern matches in comments, strings, or unrelated context
Solution:
1. Verify match by reading surrounding lines for context
2. Check if match is inside a comment (`# ...`) and exclude
3. Report the finding but note reduced confidence

### Error: "Script Uses Non-Standard Patterns"
Cause: Custom error handling, logging frameworks, or wrapper functions
Solution:
1. Check if script sources a common library file
2. Read the sourced file for the missing patterns
3. If patterns exist in sourced libraries, mark as PASS with note

---

## Anti-Patterns

### Anti-Pattern 1: Executing Scripts to Test Them
**What it looks like**: Running the cron script to see if it "works"
**Why wrong**: Cron scripts may delete data, send emails, or modify production state
**Do instead**: Static analysis only. Read the file, match patterns, report.

### Anti-Pattern 2: Skipping Checks Because Script Is "Simple"
**What it looks like**: "This is just a 5-line script, no need for lock files"
**Why wrong**: Simple scripts grow. Missing basics cause production incidents.
**Do instead**: Run all 9 checks regardless of script size.

### Anti-Pattern 3: Recommending Over-Engineering
**What it looks like**: Suggesting Prometheus alerting for a log cleanup script
**Why wrong**: Recommendations should match script scope and complexity
**Do instead**: Provide proportional fixes. Lock file yes, monitoring framework no.

### Anti-Pattern 4: Ignoring Sourced Dependencies
**What it looks like**: Marking FAIL because `set -e` is in a sourced common.sh
**Why wrong**: Many teams use shared library files sourced at script start
**Do instead**: Check `source` and `.` commands, read sourced files for patterns.

### Anti-Pattern 5: Reporting Without Recommendations
**What it looks like**: "FAIL: No error handling" with no suggested fix
**Why wrong**: Findings without fixes create work without guidance
**Do instead**: Every FAIL/WARN must include a paste-ready code snippet.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Script is too simple to audit" | Simple scripts cause outages too | Run full 9-point checklist |
| "It works in production already" | Working ≠ reliable under failure | Audit for failure-mode handling |
| "Lock files are overkill" | Concurrent cron runs cause data corruption | Always check for concurrency safety |
| "Logging slows things down" | Debugging blind cron failures wastes hours | Verify logging with timestamps |

### Best Practices Reference

```bash
#!/bin/bash
set -euo pipefail                              # Error handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"                                # Working directory
PATH=/usr/local/bin:/usr/bin:/bin               # Explicit PATH
LOCK="/tmp/$(basename "$0").lock"               # Lock file
exec 200>"$LOCK"
flock -n 200 || { echo "Already running"; exit 0; }
LOG="logs/$(basename "$0" .sh)_$(date +%Y%m%d).log"
exec > >(tee -a "$LOG") 2>&1                   # Logging
echo "$(date): Starting"
trap 'rm -f "$LOCK" /tmp/mytmp_*' EXIT         # Cleanup
find logs -name "*.log" -mtime +30 -delete      # Log rotation

# ... actual work ...

if [ $? -ne 0 ]; then                          # Failure notification
    echo "FAILED" | mail -s "Cron Alert" admin@example.com
fi
```
