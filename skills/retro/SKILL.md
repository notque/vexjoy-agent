---
name: retro
description: |
  Interact with the learning system: show stats, list/search accumulated
  knowledge, and graduate mature entries into agents/skills. Backed by
  learning.db (SQLite + FTS5). Use when user says "retro", "retro list",
  "retro search", "retro graduate", "check knowledge", "what have we learned",
  "knowledge health", "graduate knowledge".
version: 2.0.0
user-invocable: true
argument-hint: "[status|list|search <term>|graduate]"
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
---

# Retro Knowledge Skill

## Operator Context

This skill wraps `scripts/learning-db.py` into a user-friendly interface for the learning system. The learning database is the single source of truth — there are no L1/L2 markdown files.

### Hardcoded Behaviors (Always Apply)
- **DB is the source of truth**: All queries go through `python3 ~/.claude/scripts/learning-db.py`; never maintain a parallel file store
- **Graduate requires confirmation**: Always present proposals and wait for user approval before editing agent/skill files
- **Graduate requires specificity**: Only graduate entries that encode non-obvious, actionable knowledge — never generic advice

### Default Behaviors (ON unless disabled)
- **Formatted Output**: Present results in readable tables/sections, not raw JSON
- **Actionable Suggestions**: When showing stats, suggest next actions (search, graduate)

### Optional Behaviors (OFF unless enabled)
- **Auto-Fix**: Apply graduation without confirmation (only if user passes `--auto`)

## What This Skill CAN Do
- Show learning system stats (entry counts, categories, confidence distribution)
- List all entries with filtering by category/confidence
- Full-text search across all learnings (FTS5)
- Graduate mature entries into specific agents/skills (LLM-driven)
- Mark entries as graduated after embedding

## What This Skill CANNOT Do
- Record new learnings (use `learning-db.py record` directly or let hooks capture)
- Auto-graduate without human approval
- Generate L1/L2 markdown files (legacy system, removed in ADR-006)

---

## Instructions

Parse the user's argument to determine the subcommand. Default to `status` if no argument given.

| Argument | Subcommand |
|----------|------------|
| (none), status | **status** |
| list | **list** |
| search TERM | **search** |
| graduate | **graduate** |

### Subcommand: status

Show learning system health summary.

**Step 1**: Get stats.

```bash
python3 ~/.claude/scripts/learning-db.py stats
```

**Step 2**: Present status report.

```
LEARNING SYSTEM STATUS
======================

Entries:     [total] ([high-conf] high confidence)
Categories:  [breakdown by category]
Graduated:   [N] entries embedded in agents/skills

Injection:
  Hook: retro-knowledge-injector.py (DB-backed, FTS5 search)
  Gate: work-intent + keyword relevance

Next actions:
  /retro list              — see all entries
  /retro search TERM       — find specific knowledge
  /retro graduate          — embed mature entries into agents
```

### Subcommand: list

Display all accumulated knowledge.

**Step 1**: Query all entries.

```bash
python3 ~/.claude/scripts/learning-db.py query
```

**Step 2**: Present grouped by category:

```
LEARNING DATABASE
=================

## [Category] ([N] entries)
- [topic/key] (conf: [N], [Nx] observations): [first line of value]
...
```

Optional flags:
- `--category design` — filter to one category
- `--min-confidence 0.7` — only high-confidence entries

### Subcommand: search

Full-text search across all learnings.

**Step 1**: Run FTS5 search.

```bash
python3 ~/.claude/scripts/learning-db.py search "TERM"
```

**Step 2**: Present results ranked by relevance:

```
SEARCH: "TERM"
==============

[N] results:

1. [topic/key] (conf: [N], category: [cat])
   [value excerpt]

2. ...
```

### Subcommand: graduate

Evaluate learning.db entries and embed mature ones into agents/skills.
This is LLM work — graduation requires judgment about target identification,
edit placement, and phrasing as prescriptive instruction.

**Step 1**: Get graduation candidates from the DB.

```bash
python3 ~/.claude/scripts/learning-db.py query --category design --category gotcha
```

Skip categories `error` and `effectiveness` — those are injection-only (useful
in context but not suitable as permanent agent instructions).

**Step 2**: For each entry, evaluate graduation readiness.

For each candidate, the LLM:
- Reads the learning value
- Searches the repo for the target file (grep for related keywords)
- Determines edit type: add anti-pattern, add to operator context,
  add warning, or "not ready / keep injecting"
- Checks if the target already contains equivalent guidance

| Question | Pass | Fail |
|----------|------|------|
| Is this specific and actionable? | "sync.Mutex for multi-field state machines" | "Use proper concurrency" |
| Is this universally applicable? | Applies across the domain | Only applied in one feature |
| Would it be wrong as a prescriptive rule? | Safe as default | Has important exceptions |
| Does the target already contain this? | Not present | Already equivalent |

**Step 3**: Present graduation plan to user.

```
GRADUATION CANDIDATES (N of M entries)

1. [topic/key] → [target file] (add anti-pattern)
   Proposed: "### AP-N: [title]\n[description]"

ALREADY APPLIED (N entries — mark graduated only)
- [topic/key] — already in [file]

NOT READY (N entries — keep injecting)
- [topic/key] — [reason]

Approve? (y/n/pick numbers)
```

**Step 4**: On user approval, apply changes.

Use the Edit tool to insert graduated content into target agent/skill files.

After embedding, mark the entry as graduated:

```bash
python3 ~/.claude/scripts/learning-db.py graduate TOPIC KEY "target:file/path"
```

Graduated entries stop being injected (the injector filters
`graduated_to IS NULL`).

**Step 5**: Report.

```
GRADUATED:
  [key] → [target file] (section: [section])

Entries marked. They will no longer be injected via the hook
since they are now part of the agent's permanent knowledge.
```

---

## Examples

### Example 1: Quick health check
User says: "/retro"
Actions: Run `learning-db.py stats`, show entry counts, injection health.

### Example 2: See what we know
User says: "/retro list"
Actions: Run `learning-db.py query`, display grouped by category.

### Example 3: Search for specific knowledge
User says: "/retro search routing"
Actions: Run `learning-db.py search "routing"`, display ranked results.

### Example 4: Graduate mature knowledge
User says: "/retro graduate"
Actions: Query design/gotcha entries, evaluate each against graduation criteria, propose edits to target agents/skills, apply approved changes, mark graduated.

---

## Error Handling

### Error: "learning.db not found"
Cause: Database not initialized yet
Solution: Report that no learnings exist yet. Hooks auto-populate during normal work.

### Error: "No graduation candidates"
Cause: No design/gotcha entries, or all already graduated
Solution: Report the stats and suggest recording more learnings via normal work.

---

## Anti-Patterns

### Anti-Pattern 1: Graduating Generic Advice
**What it looks like**: Graduating "use proper error handling" into the Go agent
**Why wrong**: Generic advice adds noise. Agents already know general patterns.
**Do instead**: Only graduate specific, actionable findings that encode something non-obvious.

### Anti-Pattern 2: Graduating Without Checking Target
**What it looks like**: Proposing to add knowledge that's already in the target file
**Why wrong**: Creates duplication and maintenance burden
**Do instead**: Always grep the target file for equivalent guidance before proposing.

### Anti-Pattern 3: Auto-Graduating Without User Approval
**What it looks like**: Embedding knowledge into agents without showing proposals first
**Why wrong**: Graduation permanently changes agent behavior. Human judgment required.
**Do instead**: Always present proposals and wait for explicit approval.
