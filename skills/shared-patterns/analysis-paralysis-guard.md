# Analysis Paralysis Guard

Prevents unbounded read-only exploration without action.

## When to Use

Use in any investigation-oriented skill or agent where extended codebase exploration is expected: debugging, research, code review, exploration. Any workflow that involves reading multiple files before taking action benefits from this guard.

## The Pattern

Reading is not progress. Reading that informs a hypothesis which leads to an action is progress. If you've read 5 files and still don't have a hypothesis or an action to take, you are either lost or avoiding commitment. Both failure modes are fixed by the same intervention: stop and articulate what you're looking for and why.

### Counter
Track consecutive read-only tool calls. These tools increment the counter:
- **Read** (file reads)
- **Grep** (content search)
- **Glob** (file search)

### Reset
The counter resets to 0 when any action tool is used:
- **Edit** (file modification)
- **Write** (file creation)
- **Bash** (command execution — including running tests, builds, or any shell command)

### Threshold
When the counter reaches **5**, STOP before making another read-only call.

### Required Explanation
The stop must include a specific statement following this format:

> "I am looking for [X] because I suspect [Y]."

The following are NOT acceptable explanations:
- "I am gathering more context" — too vague, indicates no active hypothesis
- "I need to understand the codebase better" — unbounded, no termination condition
- "Let me check one more file" — no rationale for why that specific file matters

### After Explaining
Choose one of:
1. **Form a hypothesis and act** — write a test, make an edit, run a command. The counter resets.
2. **Justify continued reading** — if genuinely more reading is needed, state the specific reason and record it. The counter resets, but the justification is on record.

### Threshold Adjustment

The default threshold of 5 is appropriate for most investigations. It can be adjusted:

| Situation | Adjusted Threshold | Justification |
|-----------|-------------------|---------------|
| Distributed system debugging (tracing across services) | 8 | Message flows cross many files before a hypothesis is possible |
| Security audit (reviewing attack surface) | 8 | Comprehensive reading is required before action |
| Simple bug in single file | 3 | Hypothesis should form quickly with fewer reads |

To adjust, explicitly note: "Raising analysis paralysis threshold to [N] because [specific reason]."

## Examples

**Good**: After reading 5 files: "I am looking for where the session token is validated because I suspect the middleware is skipping validation for API routes." → Forms hypothesis, reads one more targeted file, then edits the middleware.

**Bad**: After reading 8 files: "I need to understand the codebase better." → No hypothesis, no termination condition, no action plan.

## Patterns to Detect and Fix

| Signal | Why It Matters | Preferred Action |
|--------------|----------------|------------|
| Running a no-op Bash command to reset counter | Defeats the guard; action must be meaningful | Only real actions reset the counter |
| Explaining with "gathering context" then continuing to read | Vague explanation without hypothesis means still lost | Form a specific hypothesis or ask for help |
| Disabling the guard because "this investigation is complex" | Complexity is not an excuse for inaction | Raise threshold to 8 with justification |
| Treating the guard as a hard limit on reads | It's a checkpoint, not a limit | Explain, justify, and proceed if genuinely needed |

## Related Patterns

- [Anti-Rationalization Core](anti-rationalization-core.md) — Both address investigation discipline; anti-rationalization prevents shortcut rationalizations, this prevents unbounded exploration
- [Verification Checklist](verification-checklist.md) — Complements by ensuring action (verification) follows investigation
