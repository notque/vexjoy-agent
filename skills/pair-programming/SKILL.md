---
name: pair-programming
description: "Collaborative coding with enforced micro-steps and user-paced control."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - "pair program"
    - "collaborative coding"
    - "micro-steps"
    - "step by step coding"
    - "one change at a time"
    - "show each change"
    - "walk me through"
    - "interactive coding"
  category: process
  pairs_with:
    - test-driven-development
    - subagent-driven-development
---

# Pair Programming Skill

Collaborative coding through the **Announce-Show-Wait-Apply-Verify** micro-step protocol. The user controls pace, sees every planned change as a diff, and confirms before any file is modified.

Runs in the main session (not `context: fork`) because every step requires an interactive user gate.

## Instructions

### Session Setup

1. **User describes what they want.** Read relevant code to understand the starting point.
2. **Create a high-level plan.** Break the task into numbered steps, each one logical change. Show the plan before starting.
3. **Confirm the plan.** Wait for acknowledgment. The user may reorder, remove, or add steps.

Maintain step count, current speed, and remaining plan throughout. Display "Step N of ~M" with each announcement.

### Micro-Step Protocol (Per Change)

**1. Announce** -- Describe the next change in 1-2 sentences: what and why. Keep brief before showing code.

**2. Show** -- Display planned code as diff or code block. Default 15-line limit (max 50). Never exceed: split large changes into sub-steps.

**3. Wait** -- Stop and let the user respond. Do not proceed without explicit command.

| Command | Action |
|---------|--------|
| `ok` / `yes` / `y` | Apply current step, proceed to next |
| `no` / `n` | Skip this step, propose alternative |
| `faster` | Double step size (max 50 lines) |
| `slower` | Halve step size (min 5 lines) |
| `skip` | Skip current step, move to next |
| `plan` | Show remaining steps |
| `done` | End pair session, run final verification |

**4. Apply** -- Execute only after `ok`/`yes`/`y`. Never apply without explicit confirmation.

**5. Verify** -- Run relevant checks (lint, type check, test) and report in one sentence.

If a step exceeds size limit, split into sub-steps (Step 3a, 3b, 3c). Announce: "This change is ~40 lines. Splitting into 3 sub-steps."

### Speed Adjustment

Start at 15 lines per step. Apply changes immediately when requested.

| Setting | Lines Per Step | Trigger |
|---------|---------------|---------|
| Slowest | 5 | Multiple `slower` |
| Slow | 7 | `slower` from default |
| Default | 15 | Session start |
| Fast | 30 | `faster` from default |
| Fastest | 50 | Multiple `faster` (hard cap) |

Acknowledge: "Speed adjusted to ~N lines per step."

### Session End

On `done` or all steps complete: run final verification (lint, type check, full test suite), show summary (steps completed/skipped, files modified), report results.

### Examples

**Standard Session** -- "Pair program a CSV parser in Go"
1. Read existing code, create 5-step plan
2. Show plan, wait for confirmation
3. Step 1: Announce "Define CSVRecord struct" -- show 8 lines -- wait -- ok -- apply -- verify
4. Step 2: Announce "Add ParseLine function" -- show 12 lines -- wait -- ok -- apply -- verify
5. Continue through remaining steps

**Speed Adjustment** -- User says `faster` after Step 2
1. Acknowledge: "Speed adjusted to ~30 lines per step."
2. Next steps show up to 30 lines
3. `slower` drops back to ~15

**Session End** -- User says `done` after Step 4 of 6
1. Run `go vet`, `go test ./...`
2. Report: "4 of 6 steps completed, 0 skipped. Modified: parser.go, parser_test.go. Tests: all passing."

## Error Handling

### User Says "Just Do It" / Wants Autonomous Mode
Solution: "Would you like to switch to autonomous mode? I can implement remaining steps without confirmation." If accepted, drop micro-step protocol.

### Verification Fails After a Step
Solution: Announce the fix as the next micro-step. Show fix diff, wait for confirmation, apply, re-verify. Never silently fix failures.

### Step Too Large to Fit Size Limit
Solution: Split into sub-steps (Step 3a, 3b, 3c). Announce the split.

## References

- [Micro-step protocol control commands](#micro-step-protocol-per-change) -- user command table
- [Speed adjustment table](#speed-adjustment) -- lines-per-step settings
