---
name: pause-work
description: |
  Create session handoff artifacts (HANDOFF.json + .continue-here.md) that capture
  completed work, remaining tasks, decisions, uncommitted files, and reasoning context
  so the next session can resume without reconstruction overhead. Use for "pause",
  "save progress", "handoff", "stopping for now", "end session", "pick this up later".
  Route to other skills for task planning (use task_plan.md), session summaries (use /retro),
  or committing work (use /commit or git directly).
version: 1.0.0
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
    - pause
    - save progress
    - handoff
    - stopping for now
    - end session
    - pick this up later
    - session handoff
    - wrap up session
  pairs_with:
    - resume-work
  complexity: Simple
  category: process
---

# /pause - Session Handoff

Capture ephemeral session reasoning into durable artifacts so the next session can resume without wasting time on context reconstruction. `task_plan.md` records WHAT tasks exist; this skill captures WHY the current session chose a particular approach, what it rejected, and what it planned to do next.

Two output files serve different audiences because each addresses a distinct use case:
- `HANDOFF.json` — machine-readable, consumed by `/resume-work` for automated state reconstruction. Must always be produced to enable `/resume-work` routing.
- `.continue-here.md` — human-readable, for users who want to understand session state without starting a new session. Must always be produced to support human-only resumption paths.

Skipping either file breaks half the use case: without the JSON, `/resume-work` cannot detect handoff state automatically; without the markdown, users cannot quickly grok where things stand.

## Instructions

### Phase 1: GATHER

**Goal**: Collect all state needed for the handoff.

**Step 1: Read CLAUDE.md**

Read and follow the repository CLAUDE.md before any other operations because it establishes conventions for the current project that may differ from defaults.

**Step 2: Identify project root**

Find the git root directory:
```bash
git rev-parse --show-toplevel
```

All subsequent paths and file writes target this root, not the current working directory because writing to the project root ensures `/resume-work` can find the files reliably across different shell invocation contexts.

**Step 3: Collect git state**

Uncommitted work is the highest-risk information to lose across sessions because a new shell or worktree cleanup can destroy changes the user intended to save. Run these commands to capture the current state:

```bash
# Current branch
git branch --show-current

# Uncommitted files (staged and unstaged)
git status --short

# Summary of uncommitted changes
git diff --stat
git diff --cached --stat

# Recent commits on this branch (for context)
git log --oneline -10
```

**Step 4: Check for false completions**

Search uncommitted/modified files for placeholder markers because they indicate work that looks done but is not — this is the most dangerous handoff failure mode. These markers are easily missed during context loss and become invisible in the next session.

```bash
# Get list of modified files
git diff --name-only
git diff --cached --name-only
```

Use the Grep tool to search those files for these patterns: `TODO`, `FIXME`, `PLACEHOLDER`, `TBD`, `XXX`, `HACK`, `stub`, `not yet implemented`.

Record any findings — these are items that look complete but are not.

**Step 5: Read task_plan.md if present**

If `task_plan.md` exists in the project root, read it and incorporate its phase status into the handoff because the plan captures WHAT phases and tasks exist while the handoff captures WHY and the session's mental model. The handoff supplements the plan (capturing session reasoning), it does not replace it. Extract:
- Which phases are complete (marked `[x]`)
- Which phases remain (marked `[ ]`)
- Current status line
- Decisions and errors logged

**Step 6: Read .adr-session.json if present**

If `.adr-session.json` exists, note the active ADR for context in the handoff because ADRs record architectural decisions that influence remaining work.

**GATE**: Git state collected. Modified file list available. Placeholder scan complete. Ready to synthesize.

### Phase 2: SYNTHESIZE

**Goal**: Combine gathered state with session reasoning into handoff content.

**Step 1: Construct completed_tasks**

List what was accomplished this session with specificity because the next session needs to know what NOT to repeat. Draw from:
- Git commits made during the session
- Phases marked complete in task_plan.md
- Work the session performed (files created, edited, reviewed)

Be specific: "Implemented scoring module in scripts/quality-score.py" not "Did some work on scoring" because vague entries waste the next session's time reconstructing what was done.

**Step 2: Construct remaining_tasks**

List what still needs to be done because this is the primary input to the next session's context. Draw from:
- Unchecked phases in task_plan.md
- Placeholder markers found in Phase 1 Step 4
- Known incomplete work from session context

**Step 3: Construct decisions**

Record key decisions made during the session and WHY because this is the highest-value handoff content. Git log shows WHAT changed but not WHY or what was rejected — decisions fill that gap and prevent the next session from re-exploring dead ends or reconsidering options that were already deliberated.

Format: `{"decision description": "reasoning for the decision"}`

**Step 4: Construct next_action**

Write a specific, actionable description of what the next session should do first because what seems obvious now becomes opaque after context loss. Include:
- The exact action (not vague "continue working")
- Relevant file paths and function names
- Integration points or dependencies
- Why this is the right next step

Example: `"Wire quality-score.py into pr-pipeline Phase 3. The function signature is score_package(path) -> ScoreResult. Integration point is the gate check between STAGE and REVIEW phases."`

**Step 5: Construct context_notes**

Capture the session's mental model — the reasoning context that is NOT captured in code or commits because this information is the most likely to be lost and most expensive to reconstruct. Always include at least: what approach was chosen, what was rejected, and any gotchas discovered. This information prevents thrashing in the next session. Record:
- Approaches tried and rejected (and why)
- Assumptions being made
- Gotchas discovered
- Performance or design trade-offs considered

**GATE**: All handoff fields populated with specific, actionable content. No vague entries like "continue work" or "finish implementation."

### Phase 3: EXTRACT LEARNINGS

**Goal**: Query session learnings from learning.db, filter for architectural decisions that warrant ADRs, and draft ADR skeletons for each candidate. This phase runs before WRITE so that ADR data is available for inclusion in both handoff files — passing extracted data downstream is cheaper than appending to files after the fact.

**Step 1: Query session learnings**

```bash
python3 ~/.claude/scripts/learning-db.py query --format json --limit 20
```

`learning-db.py` has no `--since` flag, so query recent entries and filter by recency. Use the `created_at` field in the JSON output to identify entries recorded during this session — the most recent entries are the ones this session produced.

**Step 2: Filter for ADR candidates**

Apply this heuristic to determine which learnings describe architectural decisions vs. incidental tips:

| Learning pattern | ADR candidate? |
|-----------------|----------------|
| "After X, always do Y" | Yes — process decision |
| "X depends on Y" | Yes — contract/coupling |
| "Use A instead of B because C" | Yes — architectural choice |
| "X is faster than Y" | Maybe — only if it changes approach |
| "Use --flag for better output" | No — tip, not decision |

Keep only entries that describe process changes, tooling contracts, or architectural choices. Tips and incidental observations don't warrant ADRs because they don't reflect decisions that constrain future work — capturing them as ADRs would dilute the ADR corpus and create noise in architecture documentation.

**Step 3: Draft ADR skeletons** (only if candidates found)

Get the next safe ADR number once, then increment for subsequent candidates:
```bash
python3 ~/.claude/scripts/adr-query.py next-number 2>/dev/null || echo "manual"
```

Call `next-number` once for the first candidate. For additional candidates, increment the number manually (e.g., if first returns 132, use 133 for the second) because the script checks existing files on disk and the first skeleton has not been committed yet.

If `adr-query.py` returns "manual", use placeholder numbers and note that the user should assign them before merging.

Draft to `adr/{number}-{slug}.md`:

```markdown
# ADR-{number}: {Title from learning}

**Status**: Proposed
**Date**: {today}
**Source**: Auto-extracted from session learning (confidence: {confidence})

## Context
{Context derived from the learning entry}

## Decision
{Decision derived from the learning pattern}

## Validation Criteria
- [ ] {Criterion derived from the decision}
```

Write the file to disk so it is visible in the next session even if Phase 4 fails.

**Step 4: Pass ADR data to Phase 4**

Construct a `drafted_adrs` list in memory for use during the WRITE phase:
- If candidates were found: list of `{"number": N, "path": "adr/N-slug.md", "title": "..."}` entries
- If no candidates found: empty list — skip silently, no empty sections in output files

**GATE**: learning.db queried. Candidates filtered using the decision-vs-tip heuristic. ADR skeleton files written to disk for any candidates found. `drafted_adrs` data available for Phase 4.

### Phase 4: WRITE

**Goal**: Write both handoff files to the project root. This skill only creates files — it only creates files and leaves existing code and git state untouched because it must be safe to invoke repeatedly without side effects.

**Step 1: Write HANDOFF.json**

Write to `{project_root}/HANDOFF.json` with UTC ISO 8601 timestamps for unambiguous parsing across time zones and system clocks. Include the `drafted_adrs` field from Phase 3 — omit the field entirely (not null, not `[]`) if no ADRs were drafted, so `/resume-work` can detect absence reliably:

```json
{
  "created_at": "<ISO 8601 UTC timestamp>",
  "task_summary": "<Brief description of the overall task>",
  "completed_tasks": [
    "<Specific completed item 1>",
    "<Specific completed item 2>"
  ],
  "remaining_tasks": [
    "<Specific remaining item 1>",
    "<Specific remaining item 2>"
  ],
  "blockers": [
    "<Blocker if any, or empty array>"
  ],
  "decisions": {
    "<Decision 1>": "<Reasoning>",
    "<Decision 2>": "<Reasoning>"
  },
  "uncommitted_files": [
    "<file1>",
    "<file2>"
  ],
  "next_action": "<Specific next action with file paths and integration points>",
  "context_notes": "<Mental model, rejected approaches, gotchas, assumptions>",
  "branch": "<current branch name>",
  "base_branch": "main",
  "false_completions": [
    "<file:line — placeholder marker found, if any>"
  ],
  "drafted_adrs": [
    {"number": "<N>", "path": "adr/<N>-<slug>.md", "title": "<title>"}
  ]
}
```

**Step 2: Write .continue-here.md**

Write to `{project_root}/.continue-here.md` because humans need prose-form state before committing to `/resume-work`. Include the ADR section only if `drafted_adrs` is non-empty — an empty section wastes the reader's attention and signals noise:

```markdown
# Continue Here

## What I was doing
[Prose description of the task, current state, and approach being taken]

## What's done
- [Completed item 1]
- [Completed item 2]

## What's next
[Specific next action — what to do, which files, why this step]

## Key decisions
- [Decision 1]: [Why]
- [Decision 2]: [Why]

## Watch out for
- [Blockers, gotchas, dead ends already explored]
- [False completions found: file:line — marker]

## Uncommitted work
- [file1 — brief description of changes]
- [file2 — brief description of changes]

## ADRs Drafted from Session Learnings
- [ADR-N: Title — adr/N-slug.md]
```

Omit the "ADRs Drafted from Session Learnings" section entirely when `drafted_adrs` is empty.

**Step 3: Suggest WIP commit if needed**

If there are uncommitted changes (from Phase 1 Step 3), display a warning because uncommitted work can be lost if the worktree is cleaned up. However, let the user decide whether to commit because auto-committing removes the user's ability to decide — changes may be experimental, broken, or intentionally staged for review.

```
WARNING: Uncommitted changes detected in N file(s):
  - file1
  - file2

Consider a WIP commit before ending the session:
  git add <files> && git commit -m "wip: <description>"

Uncommitted work can be lost if the worktree is cleaned up.
```

**Step 4: Optional commit of handoff files**

If `--commit` flag was provided:
```bash
git add HANDOFF.json .continue-here.md
git commit -m "chore: session handoff artifacts"
```

**GATE**: Both files written to project root. User notified of uncommitted work if any.

### Phase 5: CONFIRM

**Goal**: Display summary and confirm handoff was captured. Skip this phase if `--quiet` flag was provided (for automated/scripted usage).

Display the handoff summary:

```
===================================================================
 SESSION PAUSED
===================================================================

 Handoff files created:
   - HANDOFF.json (machine-readable)
   - .continue-here.md (human-readable)

 Completed: N task(s)
 Remaining: N task(s)
 Blockers: N
 Uncommitted files: N
 False completions: N placeholder(s) found
 ADRs drafted: N

 Next action: <brief next_action summary>

 Resume with: /resume-work
===================================================================
```

## Error Handling

### Error: Not in a Git Repository
**Cause**: `git rev-parse --show-toplevel` fails — no `.git/` directory found
**Solution**: Handoff files require git context for branch and uncommitted file detection. Navigate to a git repository root and retry.

### Error: Cannot Determine Session Work
**Cause**: No commits on current branch, no task_plan.md, no uncommitted changes — nothing to hand off
**Solution**: If the session genuinely did no work, there is nothing to hand off. Inform the user: "No work detected to hand off. If you made changes that aren't committed or tracked, describe what you were working on and I'll create the handoff manually."

### Error: learning-db.py query fails
**Cause**: `learning-db.py query` exits non-zero — database not initialized, script missing, or corrupted db file
**Solution**: Skip Phase 3 silently and proceed to Phase 4 with an empty `drafted_adrs` list. The handoff files are the primary deliverable; ADR extraction is a best-effort enhancement. Log a single line in context_notes: "learning-db.py unavailable — ADR extraction skipped."

### Error: HANDOFF.json Already Exists
**Cause**: A previous `/pause` created handoff files that were not yet consumed by `/resume-work`
**Solution**: Warn the user that stale handoff files exist. Offer to overwrite (default) or append. Overwriting is almost always correct — stale handoffs from abandoned sessions should not block new ones.

## References

### Related Skills
- `resume-work` — Consumes handoff artifacts to restore session state
- `workflow-orchestrator` — For complex multi-phase tasks that benefit from handoff between phases
