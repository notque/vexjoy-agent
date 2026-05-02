---
name: content-calendar
description: "Manage editorial content through 6 pipeline stages."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - "content pipeline"
    - "editorial calendar"
    - "publishing schedule"
    - "content schedule"
    - "publication plan"
  category: content-creation
  pairs_with:
    - topic-brainstormer
    - series-planner
    - publish
---

# Content Calendar Skill

Manage editorial content through 6 pipeline stages: Ideas, Outlined, Drafted, Editing, Ready, Published. All state lives in a single `content-calendar.md` file -- the sole source of truth.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `calendar-format.md` | Loads detailed guidance from `calendar-format.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| tasks related to this reference | `metrics.md` | Loads detailed guidance from `metrics.md`. |
| tasks related to this reference | `operations.md` | Loads detailed guidance from `operations.md`. |
| tasks related to this reference | `pipeline-stages.md` | Loads detailed guidance from `pipeline-stages.md`. |

## Instructions

### Phase 1: READ PIPELINE

**Goal**: Load and validate current calendar state before any mutation.

Always read the actual file -- assumed state leads to overwrites of changes made by other processes or manual edits.

1. Read `content-calendar.md` from the project root. Also read the repository CLAUDE.md for project-specific rules.
2. Parse pipeline sections -- extract entries from Ideas, Outlined, Drafted, Editing, Ready, Published, and Historical sections.
3. Validate file structure -- all required sections exist, counts match actual entries.

**Gate**: Calendar file loaded and parsed. All sections accounted for. Proceed only when gate passes.

### Phase 2: EXECUTE OPERATION

**Goal**: Perform the requested operation -- only the operation requested. No speculative reorganization.

#### Operation: View Pipeline

1. Count entries in each stage
2. Identify upcoming scheduled content (next 14 days)
3. Identify in-progress content (Outlined, Drafted, Editing)
4. Gather recent publications (last 30 days)
5. Display dashboard with progress indicators
6. Optionally flag content stuck 14+ days or show velocity metrics if requested

#### Operation: Add Idea

1. Validate topic name is non-empty
2. Search all sections for duplicate titles (case-insensitive); warn if match exists
3. Append `- [ ] [Topic name]` to Ideas section
4. Update pipeline count in overview table

#### Operation: Move Content

Content moves forward through defined stages only -- each transition represents real editorial work completed.

1. Find topic in its current section (search all sections)
2. Validate target stage is the next sequential stage:
   - Ideas -> Outlined -> Drafted -> Editing -> Ready -> Published
3. Remove entry from current section
4. Add to target section with timestamp metadata (every transition records YYYY-MM-DD):
   - outlined: `(outline: YYYY-MM-DD)`
   - drafted: `(draft: YYYY-MM-DD)`
   - editing: `(editing: YYYY-MM-DD)`
   - ready: `(ready: YYYY-MM-DD)` -- prompt for a scheduled publication date
   - published: `(published: YYYY-MM-DD)`
5. Update pipeline counts

#### Operation: Schedule Content

1. Find topic (must be in Ready section)
2. Validate date is today or future
3. Update or add `Scheduled: YYYY-MM-DD` to entry
4. Update file

#### Operation: Archive Published

Archive prevents the Published section from growing unbounded.

1. Find Published entries older than current month
2. Move to appropriate `### YYYY-MM` section in Historical
3. Update pipeline counts

**Gate**: Operation executed with all validations passing. Proceed only when gate passes.

### Phase 3: WRITE AND CONFIRM

**Goal**: Persist changes and verify the write succeeded.

Read the full calendar file before writing -- never truncate or lose existing entries.

1. Write the updated calendar file back to disk.
2. Re-read the file and verify the change is present.
3. Display confirmation with relevant dashboard section showing the change.

**Gate**: File written, re-read confirms changes persisted. Operation complete.

## Error Handling

### Error: "Calendar file not found"
Cause: `content-calendar.md` does not exist
Solution:
1. Create initial calendar file with all empty sections and overview table
2. Confirm file creation to user
3. Proceed with requested operation

### Error: "Topic not found in pipeline"
Cause: Topic name does not match any entry
Solution:
1. Search all sections for partial matches (case-insensitive)
2. Suggest closest matches
3. Show current pipeline state so user can identify the correct title

### Error: "Invalid stage transition"
Cause: User attempted to skip a stage
Solution:
1. Explain the required stage sequence
2. Show current stage and next valid stage
3. Ask user to confirm sequential move

## References

| Task | Load |
|------|------|
| Stage definitions, transition criteria | `${CLAUDE_SKILL_DIR}/references/pipeline-stages.md` |
| File format, section structure, date fields | `${CLAUDE_SKILL_DIR}/references/calendar-format.md` |
| Command reference, edge cases per operation | `${CLAUDE_SKILL_DIR}/references/operations.md` |
| File not found, corrupt sections, count drift, malformed dates | `${CLAUDE_SKILL_DIR}/references/error-handling.md` |
| Velocity metrics, stuck content, pipeline health dashboard | `${CLAUDE_SKILL_DIR}/references/metrics.md` |
