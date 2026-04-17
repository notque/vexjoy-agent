# Error Handling Reference

> **Scope**: Concrete patterns for detecting and recovering from corrupt, malformed, or invalid content-calendar.md state. Does NOT cover normal pipeline operation or stage transitions.
> **Version range**: all versions
> **Generated**: 2026-04-16

---

## Overview

Content-calendar operations fail in two categories: file-level failures (missing file, corrupt sections, count drift) and entry-level failures (invalid dates, duplicate titles, malformed metadata). The most common silent failure is count drift — the overview table says 3 but the section contains 2 — because writes that error mid-update leave the file in a partial state.

---

## Pattern Table

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| Re-read after write | Always — proves the write landed | Never skip, even for "simple" changes |
| Case-insensitive duplicate search | Before adding any idea | After the add (too late) |
| Section-count reconciliation | Before any mutation | Only on view operations (warn, don't block) |
| Partial-match fallback | Topic not found exactly | Multiple items match — list and ask |

---

## Correct Patterns

### Re-Read After Write

Always re-read the file after writing to verify persistence. Write failures can be silent.

```bash
# After writing content-calendar.md, verify the change is present
grep -n "Topic Name" content-calendar.md
```

**Why**: Write tool calls fail silently in some contexts. The re-read is the only proof the mutation landed. "Looked correct before" is not evidence of a successful write.

---

### Section Header Validation on Load

Before any mutation, confirm all 7 required sections are present.

```bash
grep -c "^## " content-calendar.md
# Expected: at least 7 (Ideas, Outlined, Drafted, Editing, Ready, Published, Historical)
```

**Why**: A file with missing sections will silently corrupt counts and lose content during moves. A 6-section file is missing a stage; entries written there disappear.

---

### Count Reconciliation Before Write

Count actual entries per section and compare to overview table before mutating.

```bash
# Count items in Ideas section (lines starting with "- [")
grep -A 100 "^## Ideas" content-calendar.md | grep -B 100 "^## Outlined" | grep -c "^- \["
```

**Why**: If counts drift before a move operation, updating counts after the move produces a wrong number. Reconcile first, then mutate, then update counts.

---

## Anti-Pattern Catalog

### ❌ Assuming Topic Title Matches Exactly

**Detection**:
```bash
# Find entries where title casing may differ from user input
grep -in "topic keyword" content-calendar.md
```

**What it looks like**:
```
User: "move hugo caching to drafted"
# Searching for exact string "hugo caching" — not found
# Error: topic not found
```

**Why wrong**: Users type partial titles or wrong case. "Hugo caching" and "Hugo partial caching issues" — the latter is the real entry. Hard stop wastes user time when a partial match could resolve it.

**Fix**:
```bash
# Step 1: exact match (case-insensitive)
grep -in "^- \[.\] \*\*hugo caching" content-calendar.md
# Step 2: if no match, partial
grep -in "hugo caching" content-calendar.md
# Step 3: if multiple, list all and ask user
```

---

### ❌ Writing Without Reading Current State

**Detection**:
```bash
# Signal: write produces a file shorter than before
wc -l content-calendar.md  # before
# ... write operation ...
wc -l content-calendar.md  # after — should be >= before for add/move
```

**What it looks like**:
```
# Skill reconstructs file from memory instead of reading current state
# Result: other stages' content is overwritten with cached state
```

**Why wrong**: The calendar may have been edited manually or by another process between reads. Writing from cached state silently destroys changes. The file is the source of truth, not the model's memory.

**Fix**: Always `Read content-calendar.md` immediately before any write, even if it was read earlier in the same operation.

---

### ❌ Invalid Stage Transition Goes Unblocked

**Detection**:
```bash
# Unchecked items in Ready or Published (should all be [x])
grep -A 200 "^## Ready" content-calendar.md | grep "^- \[ \]"
grep -A 200 "^## Published" content-calendar.md | grep "^- \[ \]"
```

**What it looks like**:
```markdown
## Ready
- [ ] **Hugo build errors** (ready: 2025-01-14)  <!-- should be [x] -->
```

**Why wrong**: Checkbox state `[x]` must flip at the Editing→Ready transition. If a topic lands in Ready as `- [ ]`, the Published and Historical sections will contain unchecked items, making the file unreadable as a kanban board.

**Fix**: Enforce checkbox flip during move-to-ready. If a topic arrives in Ready with `[ ]`, convert to `[x]` before writing.

---

### ❌ Malformed Date Metadata

**Detection**:
```bash
# Non-ISO dates in stage metadata
grep -E "\((outline|draft|editing|ready|published): [0-9]{1,2}/[0-9]{1,2}" content-calendar.md
# Non-ISO scheduled date
grep -E "Scheduled: [A-Za-z]" content-calendar.md
# Single-digit month/day (should be zero-padded)
grep -E "\((outline|draft|editing|ready|published): [0-9]{4}-[0-9]-" content-calendar.md
```

**What it looks like**:
```markdown
- [ ] **Hugo debugging guide** (outline: Jan 10, 2025)
- [x] **Build errors** (ready: 2025-1-5)
  - Scheduled: January 20
```

**Why wrong**: Date parsing logic expects `YYYY-MM-DD`. Non-ISO dates break velocity calculations, stuck-content detection, and archive operations that compare dates to the current month.

**Fix**: Normalize on read. Detect non-ISO dates and convert before date arithmetic. Reject ambiguous formats (MM/DD vs DD/MM) and prompt user to clarify.

---

### ❌ Duplicate Section Headers

**Detection**:
```bash
grep -n "^## Ideas\|^## Outlined\|^## Drafted\|^## Editing\|^## Ready\|^## Published" content-calendar.md | sort | uniq -d
```

**What it looks like**:
```markdown
## Ideas
- [ ] Topic A

## Outlined
...

## Ideas        <!-- duplicate — botched merge or manual edit -->
- [ ] Topic B
```

**Why wrong**: Only the first `## Ideas` section is parsed. Topic B is silently invisible to all operations and the count table is wrong.

**Fix**: On load, detect duplicate section headers. Merge content from all instances into one section and warn the user before proceeding.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| "Calendar file not found" | `content-calendar.md` missing from project root | Create with full template including empty sections and 0-count overview |
| "Topic not found in pipeline" | Title mismatch (case, partial, typo) | Search all sections case-insensitively; show partial matches as numbered list |
| "Invalid stage transition" | User asked to skip stages (e.g. Ideas → Ready) | Show the full stage chain; confirm move to next sequential stage only |
| "Section count mismatch" | Manual edit or failed write left count table stale | Recount all sections; update overview table; write corrected file |
| "Topic appears in multiple sections" | Botched move left duplicate entries | Show both occurrences; ask user which to keep; remove the other |
| "Scheduled date is in the past" | User set a date that has already passed | Warn with date diff; ask if they want to reschedule or publish immediately |
| "No Scheduled date in Ready" | Moved to Ready without setting publication date | Prompt: "When should this be published? (YYYY-MM-DD)" before completing move |

---

## Detection Commands Reference

```bash
# Section header count (should be >= 7)
grep -c "^## " content-calendar.md

# Duplicate section headers
grep -n "^## Ideas\|^## Outlined\|^## Drafted\|^## Editing\|^## Ready\|^## Published" content-calendar.md | sort | uniq -d

# Unchecked items in Ready or Published (should all be [x])
grep -A 200 "^## Ready" content-calendar.md | grep "^- \[ \]"

# Non-ISO dates
grep -E "\((outline|draft|editing|ready|published): [0-9]{1,2}/[0-9]{1,2}" content-calendar.md

# Overview table count vs actual entries (run both, compare)
grep -c "^- \[" content-calendar.md
```

---

## See Also

- `calendar-format.md` — canonical file format and section structure
- `operations.md` — command reference with full edge-case behavior
- `pipeline-stages.md` — stage entry/exit criteria for validation logic
