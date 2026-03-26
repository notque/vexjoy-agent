# Compaction Reference

Guidance for agents on when to compact and what state survives compaction.

Companion hook: `hooks/suggest-compact.py` — emits `/compact` suggestions at
configurable thresholds during active implementation sessions.

---

## What Survives Compaction

| Survives Compaction | Lost in Compaction |
|--------------------|--------------------|
| CLAUDE.md instructions | Intermediate reasoning and analysis |
| TodoWrite task list | File contents previously read (must re-read) |
| Memory files (`~/.claude/memory/`) | Multi-step conversation context |
| Git state (commits, branches, working tree) | Tool call history and counts |
| All files written to disk (including `.adr-session.json`) | Nuanced user preferences stated verbally |
| | Error resolution context not yet archived |

**Practical implication:** Before compacting, write any important state to disk
(task plans, ADR session files, TodoWrite) so it survives. After compacting,
re-read any files that were previously loaded into context.

---

## Phase-Transition Decision Guide

| Phase Transition | Compact? | Rationale |
|-----------------|----------|-----------|
| Research → Planning | Yes | Research context is bulky; plan is the distilled output |
| Planning → Implementation | Yes | Plan is in TodoWrite or a file; free up context for code |
| Implementation → Testing | Maybe | Keep if tests reference recent code; compact if switching focus |
| Debugging → Next feature | Yes | Debug traces pollute context for unrelated work |
| Mid-implementation | No | Losing variable names, file paths, and partial state is costly |
| After a failed approach | Yes | Clear dead-end reasoning before trying a new approach |

---

## Integration with Hooks

Two hooks collaborate on compaction management:

| Hook | Event | Role |
|------|-------|------|
| `hooks/suggest-compact.py` | `PreToolUse` | Counts Edit/Write calls; suggests `/compact` at threshold |
| `hooks/precompact-archive.py` | `PreCompact` | Archives error patterns and ADR state when compaction fires |

`suggest-compact.py` manages **when** to compact.
`precompact-archive.py` manages **what to preserve** when compaction occurs.
The two hooks are complementary and do not overlap.

---

## Counter Behavior

The `suggest-compact.py` hook emits suggestions at the following points:

- **At threshold** (default 50 Edit/Write calls): one-time suggestion to compact
  if transitioning phases.
- **Every 25 calls after threshold**: periodic reminder that context may be
  growing stale.

Threshold is configurable via the `COMPACT_THRESHOLD` environment variable
(clamped to 1–10000). The counter resets on session restart (state file is
session-keyed in `/tmp`).

The counter tracks only Edit and Write calls. Bash-heavy sessions accumulate
context faster than the counter reflects — use judgment in those cases.
