---
name: auto-dream
description: Background memory consolidation and learning graduation — overnight knowledge lifecycle.
user-invocable: true
command: dream
context: fork
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
routing:
  triggers:
    - dream
    - consolidate memories
    - clean up memories
    - memory maintenance
    - memory consolidation
    - deduplicate memories
    - graduate learnings
    - promote learnings
  category: meta-tooling
  pairs_with: []
---

Background memory consolidation cycle. Scans memory files, finds stale/duplicate/conflicting entries, consolidates, synthesizes cross-session insights, builds injection-ready payload for next session, writes dated dream report.

## When to invoke

- User says "run dream", "consolidate memories", "clean up memories", "memory maintenance", "deduplicate memories"
- Cron at 2 AM nightly: `scripts/auto-dream-cron.sh --execute`
- Manual test: `./scripts/auto-dream-cron.sh` (dry-run by default)

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Debugging failed cron run, silent failure, empty log, wrong exit code | `headless-cron-patterns.md` | Routes to the matching deep reference |
| Setting up or modifying wrapper script (`flock`, `--permission-mode`, `envsubst`, `PIPESTATUS`) | `headless-cron-patterns.md` | Routes to the matching deep reference |
| Budget cap, `--max-budget-usd`, unattended Claude invocation | `headless-cron-patterns.md` | Routes to the matching deep reference |
| Writing, updating, or archiving memory files | `memory-file-operations.md` | Routes to the matching deep reference |
| Updating `MEMORY.md` index, atomic write, `.tmp` rename | `memory-file-operations.md` | Routes to the matching deep reference |
| Staleness detection, duplicate merging, conflict flagging | `memory-file-operations.md` | Routes to the matching deep reference |
| YAML frontmatter structure, `merged_from`, memory file format | `memory-file-operations.md` | Routes to the matching deep reference |
| Testing the dream cycle safely, dry-run validation, output verification | `dream-cycle-testing.md` | Routes to the matching deep reference |
| Inspecting graduation candidates, snapshot testing, PIPESTATUS in test wrappers | `dream-cycle-testing.md` | Routes to the matching deep reference |
| Reading cron run logs, detecting silent failures | `logging-patterns.md` | Routes to the matching deep reference |
| Log rotation, directory structure, phase completion markers | `logging-patterns.md` | Routes to the matching deep reference |
| `last-dream.md` stale, missing injection payload, cron log empty | `logging-patterns.md` | Routes to the matching deep reference |
| Concurrent dream runs, lockfile already held, duplicate cron invocations | `concurrency.md` | Routes to the matching deep reference |
| `MEMORY.md.tmp` left behind, partial write recovery, atomic rename failure | `concurrency.md` | Routes to the matching deep reference |
| `database is locked`, SQLite WAL mode, `busy_timeout`, concurrent DB access | `concurrency.md` | Routes to the matching deep reference |
| `local changes would be overwritten`, git stash before GRADUATE branch switch | `concurrency.md` | Routes to the matching deep reference |

## Instructions

When invoked interactively, read `skills/auto-dream/dream-prompt.md` and execute its phases directly. The prompt is self-contained.

For cron: the dream prompt is passed to `claude -p` as a standalone headless session with no CLAUDE.md, hooks, or project context.

## Phases

1. **SCAN** — Read all memory files, query learning.db (last 7 days), read recent git log. Write to `~/.claude/state/dream-scan-{date}.md`.
2. **ANALYZE** — Identify stale, duplicate, conflicting memories and cross-session patterns. Write to `~/.claude/state/dream-analysis-{date}.md`.
3. **CONSOLIDATE** — Apply max 5 changes. Archive stale/merged files, update MEMORY.md atomically.
4. **SYNTHESIZE** — Create max 2 insight memories from cross-session patterns.
5. **GRADUATE** — Promote mature learning DB entries (confidence >= 0.9, 3+ observations) into agent/skill files. Commits on `dream/graduate-YYYY-MM-DD` branch for human review. Max 3 per cycle. (ADR-159)
6. **SELECT** — Build injection-ready payload. Write to `~/.claude/state/dream-injection-{project-hash}.md`.
7. **REPORT** — Write summary to `~/.claude/state/last-dream.md`.

## Safety constraints (always enforced)

- Never delete files — archive to `memory/archive/`, never `rm`
- Write REPORT before executing CONSOLIDATE filesystem operations
- Max 5 memory changes per cycle — excess deferred to next cycle
- Flag conflicts for human review, never auto-resolve
- Preserve YAML frontmatter when merging; use `merged_from` for provenance
- Dry-run mode (default): CONSOLIDATE, SYNTHESIZE, GRADUATE describe proposed changes only. Wrapper sets `DREAM_DRY_RUN_MODE=yes` substituted into prompt at runtime.
- GRADUATE commits on feature branch (`dream/graduate-*`), never main
- Max 3 graduations per cycle — only entries with confidence >= 0.9 and 3+ observations

## Testing

```bash
# Dry run (default, read-only)
./scripts/auto-dream-cron.sh

# Full run
./scripts/auto-dream-cron.sh --execute

# Check output
cat ~/.claude/state/last-dream.md

# Check graduation candidates
python3 -c "
import sys; sys.path.insert(0, 'hooks/lib')
from learning_db_v2 import query_graduation_candidates
import json
candidates = query_graduation_candidates()
print(json.dumps(candidates, indent=2))
"

# Check graduation branch
git branch --list 'dream/graduate-*'

# Verify cron registration
python3 ~/.claude/scripts/crontab-manager.py list
```

## Cost estimate

~$0.09/night with 50 memory files (~20-30K input tokens at Sonnet pricing). ~$33/year. Budget capped at $3.00/run.

## Cron setup

Use `crontab-manager.py` (not raw `crontab -e`). Wrapper handles PATH, lockfile, logging, budget cap, dry-run/execute toggle.

```bash
# Preview
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "auto-dream" \
  --schedule "7 2 * * *" \
  --command "/home/feedgen/vexjoy-agent/scripts/auto-dream-cron.sh --execute >> /home/feedgen/vexjoy-agent/cron-logs/auto-dream/cron.log 2>&1" \
  --dry-run

# Install
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "auto-dream" \
  --schedule "7 2 * * *" \
  --command "/home/feedgen/vexjoy-agent/scripts/auto-dream-cron.sh --execute >> /home/feedgen/vexjoy-agent/cron-logs/auto-dream/cron.log 2>&1"

# Verify
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

Schedule uses 2:07 AM (off-minute) to avoid load spikes at :00.

## Wrapper script details

`scripts/auto-dream-cron.sh` follows headless cron pattern (see `scripts/reddit-automod-cron.sh`):
- `flock` lockfile prevents concurrent runs
- `--permission-mode auto` (never `--dangerously-skip-permissions`)
- `--max-budget-usd 3.00`
- `--no-session-persistence` for clean headless operation
- `envsubst` templates `dream-prompt.md` with project paths at runtime
- `tee` to timestamped per-run log
- Dry-run by default, `--execute` for live runs
- Exit code propagation via `PIPESTATUS[0]`

## Reference Loading

| Signal / Task | Reference File |
|---------------|----------------|
| Debugging failed cron run, silent failure, empty log, wrong exit code | `references/headless-cron-patterns.md` |
| Setting up or modifying wrapper script (`flock`, `--permission-mode`, `envsubst`, `PIPESTATUS`) | `references/headless-cron-patterns.md` |
| Budget cap, `--max-budget-usd`, unattended Claude invocation | `references/headless-cron-patterns.md` |
| Writing, updating, or archiving memory files | `references/memory-file-operations.md` |
| Updating `MEMORY.md` index, atomic write, `.tmp` rename | `references/memory-file-operations.md` |
| Staleness detection, duplicate merging, conflict flagging | `references/memory-file-operations.md` |
| YAML frontmatter structure, `merged_from`, memory file format | `references/memory-file-operations.md` |
| Testing dream cycle, dry-run validation, output verification | `references/dream-cycle-testing.md` |
| Inspecting graduation candidates, snapshot testing, PIPESTATUS | `references/dream-cycle-testing.md` |
| Reading cron run logs, detecting silent failures | `references/logging-patterns.md` |
| Log rotation, directory structure, phase markers | `references/logging-patterns.md` |
| `last-dream.md` stale, missing injection payload, cron log empty | `references/logging-patterns.md` |
| Concurrent dream runs, lockfile held, duplicate invocations | `references/concurrency.md` |
| `MEMORY.md.tmp` left behind, partial write recovery | `references/concurrency.md` |
| `database is locked`, SQLite WAL mode, `busy_timeout` | `references/concurrency.md` |
| `local changes would be overwritten`, git stash before GRADUATE | `references/concurrency.md` |
