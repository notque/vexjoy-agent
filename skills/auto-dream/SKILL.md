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
- Cron job at 2 AM nightly (headless, via `claude -p "$(cat skills/auto-dream/dream-prompt.md)"`)
- Manual trigger for testing: `CLAUDE_DREAM_DRY_RUN=1 claude -p "$(cat skills/auto-dream/dream-prompt.md)"`

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
# Dry run (read-only, no filesystem changes)
CLAUDE_DREAM_DRY_RUN=1 claude -p "$(cat skills/auto-dream/dream-prompt.md)" --model sonnet

# Full run
claude -p "$(cat skills/auto-dream/dream-prompt.md)" --model sonnet

# Check output
cat ~/.claude/state/last-dream.md

# Verify cron registration
crontab -l | grep dream
```

## Cost estimate

~$0.09 per nightly run with 50 memory files (~20-30K input tokens at Sonnet pricing). ~$33/year for automated overnight operation.

## Cron setup

```cron
# Auto-Dream: nightly memory consolidation at 2 AM
0 2 * * * claude -p "$(cat skills/auto-dream/dream-prompt.md)" --model sonnet 2>>/tmp/claude-dream.log
```

Add via `crontab -e`. Verify prompt file exists at `~/.claude/skills/auto-dream/dream-prompt.md` before activating.
