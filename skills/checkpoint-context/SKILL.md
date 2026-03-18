---
name: checkpoint-context
description: |
  Structured session state capture before context compaction: task progress,
  decisions, files, debugging state, and next steps. Use when session needs
  checkpointing, before automatic compacting triggers, during long
  implementation or debugging sessions, or when user says "save context".
  Do NOT use for general note-taking, documentation generation, or as a
  substitute for git commits.
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

# Checkpoint Context Skill

## Operator Context

This skill operates as an operator for session state preservation, configuring Claude's behavior for structured context capture before compaction. It implements a **Gather-Structure-Write-Verify** workflow that produces checkpoint files enabling seamless continuation of complex tasks across compaction boundaries.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before creating checkpoints
- **Over-Engineering Prevention**: Capture only context relevant to task continuation — not everything seen in session
- **No Sensitive Data**: NEVER capture passwords, API keys, tokens, or credentials in checkpoint files
- **Timestamp Required**: Every checkpoint MUST include ISO 8601 timestamp
- **Output Location**: Always write to `plan/checkpoints/{YYYYMMDD-HHMMSS}-{slug}.md`
- **Actionable Next Steps**: Next steps MUST include specific file paths and concrete actions
- **LLM-Optimized Section**: Every checkpoint MUST include structured Raw Context section for machine parsing

### Default Behaviors (ON unless disabled)

- **Concise Reporting**: Report what was captured briefly; show checkpoint file path
- **File Excerpts Over Content**: Capture key insights from files, not full file contents
- **Change Summaries**: Summarize modifications with rationale rather than full diffs
- **Auto-Detect Task State**: Infer current task from recent activity if not explicitly stated
- **Git-Based File Tracking**: Use `git status` and `git diff --stat` to detect modified files
- **Pattern Recording**: Capture discovered coding conventions and repository patterns

### Optional Behaviors (OFF unless enabled)

- **Full File Content**: Include complete file contents in checkpoint (large output)
- **Git Diff Inclusion**: Include actual git diffs for all modified files
- **Environment Dump**: Capture sanitized environment variables

## What This Skill CAN Do

- Capture task state: current task, progress percentage, phase, and blockers
- Track files read during session with key insights from each
- Track files modified with rationale for each change
- Preserve technical decisions and alternatives considered
- Save debugging state: errors, hypotheses tested, current hypothesis
- Record discovered patterns and coding conventions
- Define specific next steps with file paths and expected outcomes
- Generate LLM-optimized structured context for post-compaction restoration

## What This Skill CANNOT Do

- Capture full conversation history — checkpoints are structured summaries, not transcripts
- Auto-restore context after compacting — requires manual loading of checkpoint file
- Prevent or delay automatic compacting — compaction is system behavior
- Capture external state such as browser tabs, terminal history, or clipboard
- Replace git commits — checkpoints track session context, not code snapshots

---

## Instructions

### Phase 1: GATHER Session State

**Goal**: Collect all relevant context from the current session.

**Step 1: Detect task state**

Identify from recent activity:
- Current task description
- Progress (percentage or phase: planning / implementing / testing / reviewing)
- Active blockers or open questions

**Step 2: Collect file context**

```bash
# Detect modified files
git status --short
git diff --stat
```

For each file read during session, note the file path and key insight. For each file modified, note what changed and why.

**Step 3: Collect decisions and debugging state**

Document:
- Technical decisions made with rationale and alternatives rejected
- If debugging: current error, hypotheses tested (confirmed/refuted), current hypothesis
- Patterns or conventions discovered during exploration

**Step 4: Define next steps**

Write 2-5 specific next steps. Each MUST include:
- Concrete action (not "continue working")
- File path(s) involved
- Expected outcome

**Gate**: All relevant context gathered. Next steps are specific and actionable. Proceed only when gate passes.

### Phase 2: STRUCTURE Checkpoint Content

**Goal**: Organize gathered context into the standard checkpoint format.

**Step 1: Ensure output directory exists**

```bash
mkdir -p plan/checkpoints
```

**Step 2: Generate filename**

Format: `{YYYYMMDD-HHMMSS}-{task-summary-slug}.md`

Example: `20260213-143022-implementing-auth-flow.md`

**Step 3: Write checkpoint with this structure**

```markdown
# Context Checkpoint: {brief summary}

**Created**: {ISO 8601 timestamp}
**Trigger**: manual | pre-compact

## Task State

- **Current task**: {description}
- **Progress**: {percentage or phase}
- **Blockers**: {blockers, or "None"}

## Files Context

### Read Files

- `path/to/file.ts` - {why read, key insight}

### Modified Files

- `path/to/file.py` - {what changed, why}

## Decisions Made

1. **{Decision}**: {rationale}. Rejected: {alternatives}

## Debugging State

- **Current error**: {error message or "N/A"}
- **Hypotheses tested**:
  1. {hypothesis} - {CONFIRMED | REFUTED | INCONCLUSIVE}
- **Current hypothesis**: {what exploring now}

## Discovered Patterns

- **{Pattern}**: {description, where it applies}

## Next Steps

1. {specific action} in `{file path}` — expected: {outcome}
2. {specific action} in `{file path}` — expected: {outcome}

## Raw Context (for LLM)

TASK: {one-line description}
PROGRESS: {percentage or phase}
CURRENT_FILE: {file being worked on}
CURRENT_ERROR: {error if debugging, else "none"}
HYPOTHESIS: {current hypothesis if debugging}
FILES_READ:
- {file}: {key insight}
FILES_MODIFIED:
- {file}: {change summary}
DECISIONS:
- {decision}: {rationale}
PATTERNS:
- {pattern}: {description}
NEXT:
1. {action with file path}
2. {action with file path}
```

Omit sections that have no content (e.g., Debugging State when not debugging). Do NOT fill sections with "N/A" placeholders.

**Gate**: Checkpoint content structured with all non-empty sections populated. Raw Context section present. Proceed only when gate passes.

### Phase 3: WRITE and VERIFY

**Goal**: Write checkpoint file and confirm it is valid.

**Step 1: Write checkpoint file**

Write the structured content to `plan/checkpoints/{filename}.md`.

**Step 2: Verify file exists and is readable**

```bash
ls -la plan/checkpoints/{filename}.md
```

**Step 3: Report summary to user**

```
Checkpoint created: plan/checkpoints/{filename}.md

Captured:
- Task State: {task} ({progress})
- Files Read: {count}
- Files Modified: {count}
- Decisions: {count}
- Next Steps: {count}

To restore after compacting:
  Read plan/checkpoints/{filename}.md
```

**Gate**: Checkpoint file exists on disk. Summary reported to user. Task is complete.

---

## Error Handling

### Error: "No clear task state to capture"

Cause: Session has no obvious current task from recent activity
Recovery:
1. Ask user to describe current task in one sentence
2. Create checkpoint with user-provided context
3. Mark progress as "Unknown (mid-session checkpoint)"

### Error: "Checkpoint directory doesn't exist"

Cause: `plan/checkpoints/` has not been created yet
Recovery:
1. Run `mkdir -p plan/checkpoints`
2. Continue with checkpoint creation

### Error: "Git not available or not a repository"

Cause: Cannot detect modified files via git commands
Recovery:
1. Skip git-based file tracking
2. Ask user which files were modified during session
3. Note "Git unavailable — user-reported files" in checkpoint

---

## Anti-Patterns

### Anti-Pattern 1: Capturing Everything

**What it looks like**: Including full file contents, every file ever read, raw command output
**Why wrong**: Creates massive checkpoints that are slow to parse and mostly irrelevant to resumption
**Do instead**: One line per file — path + key insight. Excerpts only when critical.

### Anti-Pattern 2: Vague Next Steps

**What it looks like**: "Continue implementing", "Fix the bug", "Test the code"
**Why wrong**: Cannot resume without re-discovering context. Defeats checkpoint purpose.
**Do instead**: "Add error handling to `src/auth.py:authenticate()` for invalid token case"

### Anti-Pattern 3: Missing Debugging Context

**What it looks like**: "Something is wrong" with no error messages, no hypotheses, no attempts listed
**Why wrong**: Will re-try already-attempted solutions. Loses diagnostic information.
**Do instead**: Exact error message, each hypothesis with CONFIRMED/REFUTED result, what was tried

### Anti-Pattern 4: Omitting Raw Context Section

**What it looks like**: Human-readable narrative only, no structured machine-parseable section
**Why wrong**: LLM parses structured key-value format faster and more accurately on restoration
**Do instead**: ALWAYS include Raw Context (for LLM) section with structured format

### Anti-Pattern 5: Checkpoint as Documentation

**What it looks like**: Writing polished prose, adding background context, explaining architecture
**Why wrong**: Checkpoints are for session resumption, not documentation. Wastes tokens.
**Do instead**: Terse, structured, actionable. Optimize for the next session, not a human reader.

---

## References

This skill uses these shared patterns:

- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Context is fresh, no need to checkpoint" | Compaction is unpredictable and sudden | Checkpoint when session is complex |
| "I'll remember the next steps" | LLM context is ephemeral by design | Write explicit next steps with file paths |
| "Quick checkpoint, skip debugging state" | Debugging state is the hardest to reconstruct | Capture all hypotheses and test results |
| "Full file content is safer" | Bloated checkpoints are slower to restore | Key insights only, one line per file |

### Reference Files

- `${CLAUDE_SKILL_DIR}/references/checkpoint-examples.md`: Real checkpoint examples from various scenarios
