# Pause-Work Synthesize Fields

Verbatim Phase 2 (SYNTHESIZE) detail. Combine gathered state with session reasoning into handoff content.

## Step 1: Construct completed_tasks

List what was accomplished this session with specificity because the next session needs to know what NOT to repeat. Draw from:
- Git commits made during the session
- Phases marked complete in task_plan.md
- Work the session performed (files created, edited, reviewed)

Be specific: "Implemented scoring module in scripts/quality-score.py" not "Did some work on scoring" because vague entries waste the next session's time reconstructing what was done.

## Step 2: Construct remaining_tasks

List what still needs to be done because this is the primary input to the next session's context. Draw from:
- Unchecked phases in task_plan.md
- Placeholder markers found in Phase 1 Step 4
- Known incomplete work from session context

## Step 3: Construct decisions

Record key decisions made during the session and WHY because this is the highest-value handoff content. Git log shows WHAT changed but not WHY or what was rejected — decisions fill that gap and prevent the next session from re-exploring dead ends or reconsidering options that were already deliberated.

Format: `{"decision description": "reasoning for the decision"}`

## Step 4: Construct next_action

Write a specific, actionable description of what the next session should do first because what seems obvious now becomes opaque after context loss. Include:
- The exact action (not vague "continue working")
- Relevant file paths and function names
- Integration points or dependencies
- Why this is the right next step

Example: `"Wire quality-score.py into pr-pipeline Phase 3. The function signature is score_package(path) -> ScoreResult. Integration point is the gate check between STAGE and REVIEW phases."`

## Step 5: Construct context_notes

Capture the session's mental model — the reasoning context that is NOT captured in code or commits because this information is the most likely to be lost and most expensive to reconstruct. Always include at least: what approach was chosen, what was rejected, and any gotchas discovered. This information prevents thrashing in the next session. Record:
- Approaches tried and rejected (and why)
- Assumptions being made
- Gotchas discovered
- Performance or design trade-offs considered
