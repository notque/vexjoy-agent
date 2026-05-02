---
name: retro
description: "Learning system interface: stats, search, graduate learnings. Backed by learning.db (SQLite + FTS5)."
user-invocable: true
argument-hint: "[status|list|search <term>|graduate]"
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
routing:
  triggers:
    - "retro stats"
    - "list learnings"
    - "graduate knowledge"
    - "learning stats"
    - "search learnings"
  category: meta-tooling
  pairs_with:
    - learn
    - auto-dream
---

# Retro Knowledge Skill

Wraps `scripts/learning-db.py` into a user-friendly interface. The learning database is the single source of truth -- all queries go through the Python CLI.

---

## Instructions

Parse user's argument to determine subcommand. Default to `status` if none given.

| Argument | Subcommand |
|----------|------------|
| (none), status | **status** |
| list | **list** |
| search TERM | **search** |
| graduate | **graduate** |

### Subcommand: status

Always present results in readable tables/sections, not raw JSON. Suggest next actions.

**Step 1**: Get stats.

```bash
python3 ~/.claude/scripts/learning-db.py stats
```

**Step 2**: Present:

```
LEARNING SYSTEM STATUS
======================

Entries:     [total] ([high-conf] high confidence)
Categories:  [breakdown by category]
Graduated:   [N] entries embedded in agents/skills

Injection:
  Hook: session-context.py (SessionStart, ADR-147 dream system)
  Method: pre-built payload from nightly auto-dream cycle + learning.db high-confidence patterns

Next actions:
  /retro list              -- see all entries
  /retro search TERM       -- find specific knowledge
  /retro graduate          -- embed mature entries into agents
```

### Subcommand: list

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

Optional flags: `--category design` (filter), `--min-confidence 0.7` (high-confidence only).

### Subcommand: search

**Step 1**: Run FTS5 search.

```bash
python3 ~/.claude/scripts/learning-db.py search "TERM"
```

**Step 2**: Present ranked:

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

**Constraints:**
- Only graduate non-obvious, actionable knowledge -- never generic advice
- Present proposals and wait for user approval before editing files
- No auto-graduation without explicit approval
- Skip categories `error` and `effectiveness` -- injection-only (useful in context but not permanent agent instructions)

**Step 1**: Get candidates.

```bash
python3 ~/.claude/scripts/learning-db.py query --category design --category gotcha
```

**Step 2**: Evaluate each candidate. For each:
- Read the learning value
- Search repo for target file (grep for related keywords)
- Determine edit type: add anti-pattern, add to operator context, add warning, or "not ready"
- Check if target already contains equivalent guidance (Grep before proposing)

| Question | Pass | Fail |
|----------|------|------|
| Specific and actionable? | "sync.Mutex for multi-field state machines" | "Use proper concurrency" |
| Universally applicable? | Applies across the domain | Only one feature |
| Safe as prescriptive rule? | Safe as default | Has important exceptions |
| Already in target? | Not present | Already equivalent |

**Step 3**: Present graduation plan:

```
GRADUATION CANDIDATES (N of M entries)

1. [topic/key] -> [target file] (add anti-pattern)
   Proposed: "### AP-N: [title]\n[description]"

ALREADY APPLIED (N entries -- mark graduated only)
- [topic/key] -- already in [file]

NOT READY (N entries -- keep injecting)
- [topic/key] -- [reason]

Approve? (y/n/pick numbers)
```

**Step 4**: On approval, use Edit tool to insert into target files. Mark graduated:

```bash
python3 ~/.claude/scripts/learning-db.py graduate TOPIC KEY "target:file/path"
```

Graduated entries stop being injected (`graduated_to IS NULL` filter).

**Step 5**: Report:

```
GRADUATED:
  [key] -> [target file] (section: [section])

Entries marked. No longer injected via hook -- now permanent agent knowledge.
```

---

## Error Handling

### Error: "learning.db not found"
**Cause**: Database not initialized.
**Solution**: Report no learnings exist yet. Hooks auto-populate during normal work.

### Error: "No graduation candidates"
**Cause**: No design/gotcha entries, or all graduated.
**Solution**: Report stats, suggest recording more learnings via normal work.

### Common Graduation Mistakes
- **Graduating generic advice** ("use proper error handling"): Creates noise. Only graduate specific, non-obvious findings.
- **Proposing without target verification**: Always grep target for equivalent guidance before proposing.
- **Proceeding without approval**: Graduation permanently changes agent behavior. Always wait for explicit approval.

---

## References

- `~/.claude/scripts/learning-db.py` -- Python CLI for all database operations
- `hooks/session-context.py` -- Injects pre-built dream payload and high-confidence patterns at session start (ADR-147)
- `scripts/learning.db` -- SQLite database with FTS5 search index
