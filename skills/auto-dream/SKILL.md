---
name: auto-dream
description: Background memory consolidation — reviews past sessions and deduplicates memories.
version: 1.0.0
user-invocable: true
command: dream
context: fork
model: sonnet
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
  category: meta-tooling
  pairs_with: []
---

Background memory consolidation cycle. Scans memory files, finds stale/duplicate/conflicting entries, consolidates, synthesizes cross-session insights, builds an injection-ready payload for next session start, and writes a dated dream report.

## When to invoke

- User says "run dream", "consolidate memories", "clean up memories", "memory maintenance", "deduplicate memories"
- Cron job at 2 AM nightly via wrapper script: `scripts/auto-dream-cron.sh --execute`
- Manual trigger for testing: `./scripts/auto-dream-cron.sh` (dry-run by default)

## Instructions

When invoked interactively (not via cron), read `skills/auto-dream/dream-prompt.md` and execute its phases directly. The prompt is self-contained — it describes the full six-phase cycle including safety constraints, file paths, and output formats.

For cron invocation: the dream prompt is passed directly to `claude -p` and runs as a standalone headless session with no CLAUDE.md, no hooks, no project context. All instructions are embedded in the prompt.

## Phases

1. **SCAN** — Read all memory files, query learning.db sessions (last 7 days), read recent git log. Write scan document to `~/.claude/state/dream-scan-{date}.md`.
2. **ANALYZE** — Identify stale, duplicate, conflicting memories and cross-session patterns. Write analysis to `~/.claude/state/dream-analysis-{date}.md`.
3. **CONSOLIDATE** — Apply consolidation actions (max 5 changes). Archive stale/merged files, update MEMORY.md atomically.
4. **SYNTHESIZE** — Create insight memories from cross-session patterns (max 2 new memories per cycle).
5. **SELECT** — Build injection-ready payload for session start. Write to `~/.claude/state/dream-injection-{project-hash}.md`.
6. **REPORT** — Write dream summary to `~/.claude/state/last-dream.md`.

## Safety constraints (always enforced)

- Never delete files — archive to `memory/archive/`, never `rm`
- Write the REPORT before executing any CONSOLIDATE filesystem operations
- Maximum 5 memory changes per cycle — excess items deferred to next cycle
- Flag conflicts for human review, never auto-resolve
- Preserve YAML frontmatter when merging; use `merged_from` field for provenance
- If `CLAUDE_DREAM_DRY_RUN=1`, CONSOLIDATE and SYNTHESIZE describe proposed changes only — no filesystem writes

## Testing

```bash
# Dry run (read-only, no filesystem changes — dry-run is the default)
./scripts/auto-dream-cron.sh

# Full run (execute consolidation)
./scripts/auto-dream-cron.sh --execute

# Check output
cat ~/.claude/state/last-dream.md

# Verify cron registration
python3 ~/.claude/scripts/crontab-manager.py list
```

## Cost estimate

~$0.09 per nightly run with 50 memory files (~20-30K input tokens at Sonnet pricing). ~$33/year for automated overnight operation. Budget capped at $3.00/run via wrapper script.

## Cron setup

Use `crontab-manager.py` (not raw `crontab -e`) to install. The wrapper script handles PATH, lockfile, logging, budget cap, and dry-run/execute toggle.

```bash
# Preview the cron entry
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "auto-dream" \
  --schedule "7 2 * * *" \
  --command "/home/feedgen/claude-code-toolkit/scripts/auto-dream-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/auto-dream/cron.log 2>&1" \
  --dry-run

# Install (after dry-run testing passes)
python3 ~/.claude/scripts/crontab-manager.py add \
  --tag "auto-dream" \
  --schedule "7 2 * * *" \
  --command "/home/feedgen/claude-code-toolkit/scripts/auto-dream-cron.sh --execute >> /home/feedgen/claude-code-toolkit/cron-logs/auto-dream/cron.log 2>&1"

# Verify
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

Note: schedule uses 2:07 AM (off-minute) per cron best practice — avoids load spikes from jobs firing at :00.

## Wrapper script details

`scripts/auto-dream-cron.sh` follows the established headless cron pattern (see `scripts/reddit-automod-cron.sh`):
- `flock` lockfile prevents concurrent runs
- `--permission-mode auto` (never `--dangerously-skip-permissions`)
- `--max-budget-usd 3.00` caps spend per run
- `--no-session-persistence` for clean headless operation
- `envsubst` templates `dream-prompt.md` with project-specific paths at runtime
- `tee` to timestamped per-run log file
- Dry-run by default, `--execute` for live runs
- Exit code propagation via `PIPESTATUS[0]`
