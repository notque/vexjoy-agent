# Pipeline Metrics Reference

> **Scope**: Velocity tracking, stuck-content detection, and pipeline health indicators for content-calendar. Does NOT cover format or stage definitions.
> **Version range**: all versions
> **Generated**: 2026-04-16

---

## Overview

Pipeline metrics answer three questions: Is content moving? Where does it stall? What is the publication rate? The most common failure is ignoring the in-progress stages (Outlined, Drafted, Editing) and only counting Ready and Published — which makes a blocked pipeline look healthy.

---

## Pattern Table

| Metric | Formula | Healthy Signal | Warning Signal |
|--------|---------|----------------|----------------|
| Throughput | Published this month / days elapsed | >= 1 post/week | 0 posts for 14+ days |
| Pipeline depth | Sum of all in-progress entries | 3-8 | > 15 (overloaded) or 0 (empty) |
| Stage velocity | Days avg per stage | Outlined: 1-3d, Drafted: 1-5d | Any stage > 14d |
| Idea conversion | Outlined / Ideas | > 20% monthly | < 5% (ideas accumulate, nothing advances) |

---

## Correct Patterns

### Stuck Content Detection

Content stuck in a stage for more than 14 days signals a bottleneck.

```bash
# Find entries with dates more than 14 days ago (ISO comparison)
# Outlined entries older than 14 days
grep -E "\(outline: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md

# Drafted entries older than 14 days  
grep -E "\(draft: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md

# Editing entries older than 14 days
grep -E "\(editing: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md
```

**Why**: The 14-day threshold surfaces real bottlenecks — content that entered a stage and never left is "stuck", not "in progress". Reporting it as in-progress hides the problem.

---

### Publication Rate Calculation

Count published items this calendar month for the view dashboard.

```bash
MONTH=$(date +%Y-%m)
grep -E "\(published: ${MONTH}-[0-9]{2}\)" content-calendar.md | wc -l
```

**Why**: The overview table only stores totals. To show "3 posts this month", you must grep with the current month prefix — the count in the overview table includes all-time published, not just this month.

---

### Days-in-Stage Calculation

To calculate how long a piece of content has been in its current stage:

```bash
# Extract the most recent date metadata from an entry
grep "Hugo build errors" content-calendar.md | grep -oE "(outline|draft|editing|ready|published): [0-9]{4}-[0-9]{2}-[0-9]{2}" | tail -1
# Then compare to today's date to get days elapsed
python3 -c "from datetime import date; print((date.today() - date.fromisoformat('2025-01-14')).days)"
```

**Why**: Users asking "what needs attention?" should see days-in-stage alongside the entry title. A piece that's been in Editing for 12 days is more urgent than one added yesterday.

---

## Anti-Pattern Catalog

### ❌ Reporting "Active" Without Flagging Stuck Items

**Detection**:
```bash
# Find editing entries older than threshold (14 days back)
CUTOFF=$(python3 -c "from datetime import date, timedelta; print((date.today() - timedelta(days=14)).isoformat())")
grep -E "\(editing: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md | \
  awk -F'editing: ' '{print $2}' | tr -d ')' | awk -v c="$CUTOFF" '$1 < c'
```

**What it looks like**:
```
IN PROGRESS:
  -> "Hugo debugging guide" (editing)     ← no age shown
  -> "Image optimization" (drafted)       ← no age shown
```

**Why wrong**: "In progress" with no age hides a piece that's been stuck in editing for 3 weeks. The pipeline view should surface stalls, not mask them.

**Fix**:
```
IN PROGRESS:
  -> "Hugo debugging guide" (editing, 18 days) ⚠ STUCK
  -> "Image optimization" (drafted, 3 days)
```

---

### ❌ Counting Ideas as Pipeline Velocity

**Detection**:
```bash
# If Ideas count dominates the overview table
grep "| Ideas" content-calendar.md
# Compare to sum of active stages
grep -E "^\| (Outlined|Drafted|Editing|Ready)" content-calendar.md
```

**What it looks like**:
```
Pipeline Overview:
| Ideas    | 23 |
| Outlined |  1 |
| Drafted  |  0 |
```

**Why wrong**: 23 ideas with 1 outlined means idea generation is not bottlenecked — advancement is. Reporting a "full" pipeline when Ideas=23 gives false confidence. Ideas are potential, not velocity.

**Fix**: When displaying pipeline health, separate "idea backlog depth" from "active pipeline depth". Flag pipelines where Ideas >> (Outlined + Drafted + Editing) as backlog-heavy.

---

### ❌ Not Prompting for Schedule Date on Move to Ready

**Detection**:
```bash
# Ready entries with no Scheduled line
grep -A 2 "^## Ready" content-calendar.md | grep "\*\*" | while read line; do
  echo "$line"
done
# Then check if each has a Scheduled: line following it
grep -A 1 "(ready:" content-calendar.md | grep -v "Scheduled:"
```

**What it looks like**:
```markdown
## Ready
- [x] **Hugo build errors** (ready: 2025-01-14)
<!-- no Scheduled: line — when does this publish? -->
```

**Why wrong**: Content without a scheduled date clogs the Ready stage indefinitely. A 3-month-old "Ready" item is effectively abandoned, but looks like active work.

**Fix**: Block the move-to-ready operation from completing until a publication date is provided. Show: "When should this be published? (YYYY-MM-DD or 'tbd' to skip)".

---

### ❌ Archive Operation Skips Month Boundary Check

**Detection**:
```bash
# Find Published entries from previous months
CURRENT_MONTH=$(date +%Y-%m)
grep -E "\(published: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md | \
  grep -v "published: ${CURRENT_MONTH}"
```

**What it looks like**:
```
# Running /content-calendar archive in February
# December and January posts remain in Published — not moved to Historical
```

**Why wrong**: The Published section grows unbounded. A 6-month-old pipeline will have dozens of entries in Published, making counts misleading and dashboard output unreadable.

**Fix**: Run archive check on every `view` operation (warn-only) and require explicit user confirmation before moving to Historical on `archive` operation.

---

## Velocity Dashboard Format

When displaying metrics in the view operation:

```
===============================================================
 PIPELINE HEALTH
===============================================================
 Throughput: 2 posts published this month (on pace for 8/mo)
 In progress: 4 items (Outlined: 2, Drafted: 1, Editing: 1)
 Stuck: ⚠ "Hugo debugging guide" stuck in Editing for 18 days
 Backlog: 12 ideas (5.4x current in-progress — healthy depth)
 Next up: "PaperMod customization" scheduled Jan 20
===============================================================
```

---

## Detection Commands Reference

```bash
# Publication rate this month
MONTH=$(date +%Y-%m); grep -c "published: ${MONTH}" content-calendar.md

# Stuck content (editing > 14 days)
CUTOFF=$(python3 -c "from datetime import date,timedelta; print((date.today()-timedelta(14)).isoformat())")
grep -E "\(editing: [0-9]{4}-[0-9]{2}-[0-9]{2}\)" content-calendar.md

# Ready items with no scheduled date
grep -B 0 -A 1 "(ready:" content-calendar.md | grep -v "Scheduled:"

# Published items from previous months (archive candidates)
MONTH=$(date +%Y-%m); grep -E "\(published: " content-calendar.md | grep -v "${MONTH}"

# Ideas-to-active ratio (backlog health)
grep -c "^- \[ \]" content-calendar.md  # rough total unchecked
```

---

## See Also

- `pipeline-stages.md` — stage definitions and typical duration ranges
- `operations.md` — view operation output format
- `error-handling.md` — handling malformed date metadata
