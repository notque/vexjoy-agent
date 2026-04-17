# Pause-Work Write Templates

Verbatim Phase 4 (WRITE) templates for HANDOFF.json and .continue-here.md, plus WIP commit guidance.

## Step 1: Write HANDOFF.json

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

## Step 2: Write .continue-here.md

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

## Step 3: Suggest WIP commit if needed

If there are uncommitted changes (from Phase 1 Step 3), display a warning because uncommitted work can be lost if the worktree is cleaned up. However, let the user decide whether to commit because auto-committing removes the user's ability to decide — changes may be experimental, broken, or intentionally staged for review.

```
WARNING: Uncommitted changes detected in N file(s):
  - file1
  - file2

Consider a WIP commit before ending the session:
  git add <files> && git commit -m "wip: <description>"

Uncommitted work can be lost if the worktree is cleaned up.
```

## Step 4: Optional commit of handoff files

If `--commit` flag was provided:
```bash
git add HANDOFF.json .continue-here.md
git commit -m "chore: session handoff artifacts"
```
