---
description: "Routing and review telemetry from learning.db: route health, per-skill route stats, route errors, recent evidence, review false positives."
argument-hint: "[health|routing|errors|evidence|review-fps]"
allowed-tools: ["Bash", "Read"]
---

# /retro

Reports over the learning database the hooks write (`$CLAUDE_LEARNING_DIR/learning.db`, else
`~/.claude/learning/learning.db`). The learning-capture loop behind the old `status`, `list`,
`search` and `graduate` subcommands was retired; its rows stay, and these reports read them.

## Usage

```
/retro              # Route health: is the routing feedback loop recording outcomes? (default)
/retro routing      # Success and failure counts per skill route
/retro errors       # Routes that end in errors
/retro evidence     # Recent agent evidence events
/retro review-fps   # Review false positives, grouped by reviewer
```

## Instructions for Claude

Run exactly one command for the argument, then summarize what it printed:

- No argument or `health` → `python3 ~/.claude/scripts/learning-db.py route-health`
- `routing` → `python3 ~/.claude/scripts/learning-db.py route-stats --by skill`
- `errors` → `python3 ~/.claude/scripts/learning-db.py route-stats --by errors`
- `evidence` → `python3 ~/.claude/scripts/learning-db.py evidence-recent`
- `review-fps` → `python3 ~/.claude/scripts/learning-db.py review-fps`
- Anything else → list the five arguments above and stop.

These are reports. Never run a subcommand that records or backfills (`record-routing-outcome`,
`route-failure`, `record-review-fp`, `backfill-*`) from /retro.

## Related

- `scripts/learning-db.py`: the CLI; its docstring lists every subcommand
- `agents/hook-development-engineer/references/telemetry-database.md`: what each report means
