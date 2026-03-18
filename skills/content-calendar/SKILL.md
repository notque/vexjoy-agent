---
name: content-calendar
description: |
  Manage editorial content pipeline through 6 stages: Ideas, Outlined, Drafted,
  Editing, Ready, Published. Use when user wants to view pipeline status, add
  ideas, move content between stages, schedule posts, or archive published
  content. Use for "content calendar", "pipeline status", "add idea", "schedule
  post", or "move to drafted". Do NOT use for creating Hugo content files,
  deploying posts, or modifying site configuration.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
---

# Content Calendar Skill

## Operator Context

This skill operates as an operator for editorial content pipeline management, configuring Claude's behavior for tracking blog posts through ideation, drafting, editing, and publication stages. It implements the **State Machine** architectural pattern -- content moves through defined stages with recorded transitions -- with **Pipeline Intelligence** embedded in the stage enforcement.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any pipeline operation
- **Over-Engineering Prevention**: Only perform the requested pipeline operation. No speculative reorganization, no "while I'm here" reformatting of unrelated sections
- **Single Source of Truth**: All pipeline state lives in a single `content-calendar.md` file -- never store state elsewhere
- **Stage Integrity**: Content moves forward through defined stages only; no skipping stages
- **Date Tracking**: Every stage transition records a timestamp in YYYY-MM-DD format
- **File Preservation**: Read the full calendar file before writing; never truncate or lose existing entries

### Default Behaviors (ON unless disabled)
- **Visual Dashboard**: Show pipeline overview with progress indicators on view
- **Upcoming Awareness**: Highlight scheduled content in next 14 days
- **In-Progress Focus**: Emphasize content actively being worked on (Outlined, Drafted, Editing)
- **Recent History**: Show publications from last 30 days
- **Duplicate Warning**: Warn when adding topics with titles matching existing entries

### Optional Behaviors (OFF unless enabled)
- **Stale Detection**: Flag content stuck in a stage for 14+ days
- **Velocity Metrics**: Show publishing rate and stage throughput statistics
- **Auto-Archive**: Move published content older than current month to Historical section

## What This Skill CAN Do
- View current pipeline state across all stages with dashboard formatting
- Add new ideas to the pipeline with duplicate detection
- Move content between adjacent stages with timestamp recording
- Schedule ready content for publication dates
- Archive published content to monthly historical sections
- Parse and update the content-calendar.md file structure

## What This Skill CANNOT Do
- Create or modify actual Hugo content files (use content creation skills)
- Publish or deploy posts (use deploy skill)
- Skip stages when moving content forward
- Send notifications or reminders about scheduled content

---

## Instructions

### Phase 1: READ PIPELINE

**Goal**: Load and validate the current calendar state before any mutation.

**Step 1**: Read the content calendar file from the project root

**Step 2**: Parse pipeline sections -- extract entries from Ideas, Outlined, Drafted, Editing, Ready, Published, and Historical sections.

**Step 3**: Validate file structure -- all required sections exist, counts match actual entries.

**Gate**: Calendar file loaded and parsed successfully. All sections accounted for. Proceed only when gate passes.

### Phase 2: EXECUTE OPERATION

**Goal**: Perform the requested pipeline operation with proper validation.

#### Operation: View Pipeline

1. Count entries in each stage
2. Identify upcoming scheduled content (next 14 days)
3. Identify in-progress content (Outlined, Drafted, Editing)
4. Gather recent publications (last 30 days)
5. Display dashboard with progress indicators

#### Operation: Add Idea

1. Validate topic name is non-empty
2. Search all sections for duplicate titles; warn if found
3. Append `- [ ] [Topic name]` to Ideas section
4. Update pipeline count in overview table

#### Operation: Move Content

1. Find topic in its current section (search all sections)
2. Validate target stage is the next sequential stage:
   - Ideas -> Outlined -> Drafted -> Editing -> Ready -> Published
3. Remove entry from current section
4. Add to target section with timestamp metadata:
   - outlined: `(outline: YYYY-MM-DD)`
   - drafted: `(draft: YYYY-MM-DD)`
   - editing: `(editing: YYYY-MM-DD)`
   - ready: `(ready: YYYY-MM-DD)` -- requires scheduled publication date
   - published: `(published: YYYY-MM-DD)`
5. Update pipeline counts

#### Operation: Schedule Content

1. Find topic (must be in Ready section)
2. Validate date is today or future
3. Update or add `Scheduled: YYYY-MM-DD` to entry
4. Update file

#### Operation: Archive Published

1. Find Published entries older than current month
2. Move to appropriate `### YYYY-MM` section in Historical
3. Update pipeline counts

**Gate**: Operation executed with all validations passing. Proceed only when gate passes.

### Phase 3: WRITE AND CONFIRM

**Goal**: Persist changes and verify the write succeeded.

**Step 1**: Write the updated calendar file back to disk.

**Step 2**: Re-read the file and verify the change is present.

**Step 3**: Display confirmation with relevant dashboard section showing the change.

**Gate**: File written, re-read confirms changes persisted. Operation complete.

---

## Error Handling

### Error: "Calendar file not found"
Cause: `content-calendar.md` does not exist in the project
Solution:
1. Create initial calendar file with all empty sections and overview table
2. Confirm file creation to user
3. Proceed with requested operation

### Error: "Topic not found in pipeline"
Cause: User referenced a topic name that does not match any entry
Solution:
1. Search all sections for partial matches (case-insensitive)
2. Suggest closest matches if available
3. Show current pipeline state so user can identify the correct title

### Error: "Invalid stage transition"
Cause: User attempted to skip a stage (e.g., Ideas directly to Ready)
Solution:
1. Explain the required stage sequence
2. Show the topic's current stage and the next valid stage
3. Ask user to confirm sequential move or move to adjacent stage

---

## Anti-Patterns

### Anti-Pattern 1: Skipping Stages
**What it looks like**: Moving content directly from Ideas to Ready or Drafted to Published
**Why wrong**: Skips essential phases of work; stage transitions represent real editorial progress
**Do instead**: Move through each stage sequentially; each transition records that actual work occurred

### Anti-Pattern 2: No Scheduled Dates on Ready Content
**What it looks like**: Content sits in Ready indefinitely without a publication date
**Why wrong**: Pipeline clogs with "ready" items that never publish; content goes stale
**Do instead**: Always prompt for a scheduled date when moving to Ready

### Anti-Pattern 3: Ignoring Historical Archive
**What it looks like**: Published section grows unbounded month after month
**Why wrong**: Makes pipeline overview cluttered and dashboard counts misleading
**Do instead**: Archive published content monthly to Historical section

### Anti-Pattern 4: Mutating Without Reading First
**What it looks like**: Writing calendar file based on assumed state rather than reading first
**Why wrong**: Overwrites changes made by other processes or manual edits
**Do instead**: Always read the full file before any write operation (Phase 1 is mandatory)

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know the current state" | Memory of state ≠ actual file state | Read the calendar file first |
| "Skipping one stage is fine" | Stage transitions track real work | Enforce sequential movement |
| "The file format looks right" | Looking ≠ verifying | Re-read after write to confirm |
| "No one will notice stale entries" | Stale content degrades pipeline trust | Flag or archive old entries |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/pipeline-stages.md`: Detailed stage definitions and transition criteria
- `${CLAUDE_SKILL_DIR}/references/calendar-format.md`: Complete file format specification with examples
- `${CLAUDE_SKILL_DIR}/references/operations.md`: Detailed command reference with edge cases
