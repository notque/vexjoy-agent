---
name: auto-dream
version: "1.0.0"
description: Background consolidation of this repository's Claude memory files, including the nightly cron wrapper and injection payload.
user-invocable: true
command: dream
context: fork
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
routing:
  triggers: [dream, consolidate memories, clean up memories, memory maintenance, deduplicate memories]
  category: meta-tooling
  pairs_with: []
---

# Auto-Dream

For an interactive run, read and execute `dream-prompt.md`. The same prompt is passed to a headless `claude -p` process by `scripts/auto-dream-cron.sh`; it therefore cannot depend on CLAUDE.md, hooks, or conversation context.

The local execution order is deliberately non-numeric:

`SCAN -> ANALYZE -> REPORT(plan) -> CONSOLIDATE -> SYNTHESIZE -> SELECT -> REPORT(actual)`

The first report is the recovery/audit record and must exist before any memory mutation.

## Local contracts

- Dry-run is the wrapper default. Only `scripts/auto-dream-cron.sh --execute` may apply consolidation and synthesis.
- Never delete memories. Move retired and merged sources to `memory/archive/`.
- At most five memory changes and two new insight memories per cycle; report overflow as deferred.
- Never auto-resolve conflicting memories.
- A merge keeps the newer source's YAML and adds `merged_from` provenance.
- Rewrite `MEMORY.md` and the injection payload through a same-directory `.tmp` rename.
- The cycle may write only memory files and `${DREAM_STATE_DIR}` artifacts. Moving knowledge into skills or agents requires human review.
- The injection file must remain a `<retro-knowledge>` block at `dream-injection-${DREAM_PROJECT_HASH}.md`; the session-start consumer depends on both.

## Operations

```bash
./scripts/auto-dream-cron.sh             # dry run
./scripts/auto-dream-cron.sh --execute   # live run
cat ~/.claude/state/last-dream.md
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```

Install cron through `crontab-manager.py`, not `crontab -e`. Preserve the shipped wrapper contract in `references/headless-cron-patterns.md`.

## Conditional references

- `references/memory-file-operations.md`: memory schema, stale/duplicate rules, merge and archive invariants.
- `references/headless-cron-patterns.md`: wrapper and cron failures.
- `references/dream-cycle-testing.md`: safe dry/live verification.
- `references/logging-patterns.md`: artifacts, phase completion, and rotation.
- `references/concurrency.md`: lock and interrupted atomic-write recovery.
