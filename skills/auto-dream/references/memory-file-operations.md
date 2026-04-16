# Memory File Operations Reference

> **Scope**: Patterns for reading, writing, merging, archiving, and indexing memory files in the toolkit's persistent memory system. Covers YAML frontmatter structure, atomic writes, MEMORY.md index management, and staleness/duplicate detection criteria. Does NOT cover the SQLite learning database.
> **Version range**: All toolkit versions using the `~/.claude/projects/.../memory/` layout
> **Generated**: 2026-04-15 — verify frontmatter field names against current memory files

---

## Overview

Memory files are the toolkit's persistent cross-session knowledge store. Each file carries a YAML frontmatter header and markdown body. The `MEMORY.md` file is a mandatory index — every memory file must have a pointer there. The auto-dream cycle reads, consolidates, and archives these files under strict rules: never delete (only archive), write MEMORY.md atomically, and flag conflicts for human review rather than auto-resolving them.

---

## Pattern Table

| Operation | Pattern | Notes |
|-----------|---------|-------|
| Create memory file | Write frontmatter + body to `memory/{type}_{slug}.md` | Add pointer to MEMORY.md immediately |
| Update MEMORY.md | Write to `.tmp`, then rename | Never write MEMORY.md directly — partial writes corrupt index |
| Archive stale file | `mv memory/file.md memory/archive/file.md` | Never `rm` — archiving is reversible, deletion is not |
| Merge duplicates | Combine into new file, archive both sources | Add `merged_from` field to merged file's frontmatter |
| Detect staleness | Check ALL THREE signals (see Stale Detection) | One or two signals is insufficient — all three required |

---

## YAML Frontmatter Structure

Every memory file must start with a YAML block:

```markdown
---
name: descriptive-memory-name
description: One-line description — used to decide relevance at session start, be specific
type: user | feedback | project | reference | insight
---
```

**Required fields**: `name`, `description`, `type`.

**Optional fields used by consolidation**:
```yaml
---
name: merged-absolute-paths
description: Use absolute paths for bash scripts and cron commands
type: feedback
merged_from:
  - feedback_absolute_paths_a.md
  - feedback_absolute_paths_b.md
---
```

**Why**: The `description` field is what gets injected into session context via MEMORY.md. Vague descriptions ("some notes about bash") produce useless injection payloads. The `merged_from` list preserves audit trail when consolidating duplicates.

---

## Correct Patterns

### Atomic MEMORY.md update

Never write `MEMORY.md` directly. Always write to a `.tmp` file, then rename:

```bash
# Write new index content to temp file
python3 - <<'EOF'
content = build_new_memory_index()  # your index generation logic
with open("memory/MEMORY.md.tmp", "w") as f:
    f.write(content)
EOF

# Atomic rename — this is the only filesystem operation that can fail atomically
mv memory/MEMORY.md.tmp memory/MEMORY.md
```

**Why**: If the process is interrupted while writing `MEMORY.md` directly, the index is partially written and unreadable. The rename (`mv`) is atomic on POSIX filesystems — the index either fully updates or stays unchanged.

---

### Archive-not-delete for stale files

```bash
# Create archive directory if needed
mkdir -p memory/archive/

# Move (never rm) stale memory to archive
mv memory/stale-project-memory.md memory/archive/stale-project-memory.md

# Remove from MEMORY.md (via atomic tmp pattern above)
```

**Why**: Deleted memories are unrecoverable if the staleness assessment was wrong. Archived files in `memory/archive/` are out of the active rotation but available for manual review. Archive is reversible; deletion is not.

---

### Merge with provenance

When two memories cover substantially the same ground, merge into a single file:

```markdown
---
name: absolute-path-preference
description: Always use absolute paths in bash scripts, cron commands, and file operations
type: feedback
merged_from:
  - feedback_bash_absolute_paths.md
  - feedback_cron_path_issues.md
---

Use absolute paths everywhere in bash and cron scripts. Relative paths break when
the working directory changes (e.g., cron runs from `/`, not the project root).

**Why:** Two separate incidents: one from a cron script silently doing nothing because
it couldn't find the config file, one from a hook script failing because `./scripts/`
resolved to the wrong location.
```

After writing the merged file, archive both sources and update MEMORY.md.

---

## Stale Detection Criteria

A memory is stale only when ALL THREE signals are present. One or two is insufficient.

| Signal | How to check | What counts |
|--------|-------------|-------------|
| No recent git activity | `git log --oneline -20 \| grep -i {topic}` | Topic appears in 0 of last 20 commits |
| No recent session refs | SQLite: sessions last 7 days mention topic | Topic in 0 session summaries in last 7 days |
| File age > 30 days | `stat memory/{file}.md` or file mtime | Last modified > 30 days ago |

**Example**: A project memory about "mobile release freeze ends 2026-01-15" with no matching git commits, no matching recent sessions, and file age 45 days → all three signals → candidate for archiving.

**Counter-example**: A feedback memory about "never use --no-verify" with no recent git commits about it → only ONE signal (no recent refs). Still active guidance — do NOT archive.

---

## Duplicate Detection

Two memories are duplicates when a reader could replace one with the other without losing information. Match on semantic content similarity, not filenames.

```bash
# Detection: look for memory files with overlapping descriptions in MEMORY.md
grep -n '—' memory/MEMORY.md | sort -k3  # sort by description to spot semantic overlap
```

**Examples of duplicates**:
- `feedback_use_absolute_paths.md`: "Always use absolute paths in bash"
- `feedback_bash_paths.md`: "Use absolute paths in shell scripts, not relative"

**Examples that are NOT duplicates** (different scope):
- `feedback_no_verify_hooks.md`: "Never skip pre-commit hooks"
- `feedback_test_before_commit.md`: "Run tests before committing"

---

## Anti-Pattern Catalog

### ❌ Writing MEMORY.md directly (non-atomic)

**Detection**:
```bash
# Find code that writes MEMORY.md without going through a .tmp file
grep -rn 'MEMORY\.md' hooks/ scripts/ | grep -v '\.tmp' | grep -v 'read\|cat\|grep\|open.*r'
rg 'write.*MEMORY\.md(?!\.tmp)' --type py
```

**What it looks like**:
```python
with open("memory/MEMORY.md", "w") as f:
    f.write(new_index_content)
# If interrupted here, MEMORY.md is partially written
```

**Why wrong**: A partial write leaves MEMORY.md in an invalid state. The session-start hook reads this file to load context — a corrupted index means no memory injection at all until manually repaired.

**Fix**:
```python
with open("memory/MEMORY.md.tmp", "w") as f:
    f.write(new_index_content)
os.rename("memory/MEMORY.md.tmp", "memory/MEMORY.md")
```

---

### ❌ Deleting memory files instead of archiving

**Detection**:
```bash
# Find any rm operations on memory files
grep -rn 'rm.*memory/' scripts/ hooks/
rg 'os\.remove|os\.unlink|Path.*unlink' --type py | grep -i 'memory'
```

**What it looks like**:
```bash
rm memory/stale-project-memory.md  # Unrecoverable if assessment was wrong
```

**Why wrong**: Staleness assessment can be wrong. A memory that looks inactive (no recent git refs, no session refs) might still be valid ongoing guidance. Archive preserves reversibility; deletion does not. Dream cycle design rule: "Never delete files."

**Fix**:
```bash
mkdir -p memory/archive/
mv memory/stale-project-memory.md memory/archive/stale-project-memory.md
```

---

### ❌ Auto-resolving conflicts between contradictory memories

**Detection**:
```bash
# No automated detection — this is a process violation, not a code pattern
# Review: does the consolidation code ever rewrite one memory based on another?
grep -rn 'conflict\|contradict' scripts/ | grep -v 'flag\|report\|human'
```

**What it looks like**:
```
Memory A: "Use ruff for Python linting"
Memory B: "Use flake8 for Python linting"
→ Auto-consolidation picks A because it's newer and deletes B
```

**Why wrong**: The conflict may reflect a real, unresolved project decision. Auto-resolution buries the disagreement. The human reviewer needs to see both to make the call.

**Fix**: Leave both files untouched. Record in the dream report under "Conflicts Requiring Review" with the specific contradiction described. Do not modify either file.

---

### ❌ Exceeding 200-line MEMORY.md index

**Detection**:
```bash
wc -l memory/MEMORY.md
# Should be under 200 lines; every line after 200 is truncated in context injection
```

**What it looks like**:
An index that grows unbounded as new memories are added without old ones being consolidated or archived, eventually exceeding the 200-line truncation limit.

**Why wrong**: The session-start hook injects MEMORY.md contents. Context injection is truncated at 200 lines — memories after that line are silently excluded from session context, defeating the purpose of writing them.

**Fix**: Each dream cycle should consolidate at least as many memories as it adds. If MEMORY.md approaches 150 lines, prioritize archiving stale project memories in the next cycle.

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| Session starts with no memory context | MEMORY.md corrupted (partial write) | Restore from `memory/archive/` or `MEMORY.md.tmp` if it exists |
| Memory file missing frontmatter | Written without YAML block | Add `---\nname: ...\ndescription: ...\ntype: ...\n---\n` header |
| Merged memory loses original context | `merged_from` field not set | Add `merged_from: [source_a.md, source_b.md]` to merged frontmatter |
| Memory pointer in MEMORY.md has no corresponding file | File was deleted rather than archived | Check `memory/archive/` for the file; restore if needed |
| Stale memory archived that should have stayed | Only 1-2 staleness signals, not all 3 | Restore from archive; require all 3 signals before archiving |
| MEMORY.md index entries missing | MEMORY.md.tmp rename failed | Check for `.tmp` file and rename manually; re-run with corrected atomic write |

---

## Detection Commands Reference

```bash
# Check MEMORY.md line count (should be under 200)
wc -l memory/MEMORY.md

# Find non-atomic MEMORY.md writes
grep -rn 'MEMORY\.md' scripts/ hooks/ | grep -v '\.tmp\|read\|cat\|grep'

# Find rm operations on memory files
grep -rn 'rm.*memory/' scripts/ hooks/

# Verify all MEMORY.md pointers have corresponding files
python3 -c "
import re, os
content = open('memory/MEMORY.md').read()
links = re.findall(r'\[.*?\]\((.*?\.md)\)', content)
missing = [l for l in links if not os.path.exists(f'memory/{l}')]
print('Missing:', missing or 'none')
"

# Find memory files without YAML frontmatter
grep -rL '^---' memory/*.md 2>/dev/null | grep -v 'MEMORY\|archive'

# Count memories by type
grep -h '^type:' memory/*.md 2>/dev/null | sort | uniq -c
```

---

## See Also

- `skills/auto-dream/references/headless-cron-patterns.md` — wrapper script and cron invocation patterns
- `skills/auto-dream/dream-prompt.md` — Phase 3 CONSOLIDATE and Phase 4 SYNTHESIZE instructions
- Memory system design: `skills/auto-dream/SKILL.md` — Safety constraints section
