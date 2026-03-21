---
name: pair-programming
description: |
  Collaborative coding with enforced micro-steps: announce, show diff,
  wait for confirmation, apply, verify. User controls pace with commands.
  Works with any domain agent as the executor.

  Use when: "pair program", "pair with me", "let's code together",
  "step by step coding", "walk me through implementing", "code with me"
version: 1.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# Pair Programming Skill

## Operator Context

This skill operates as an operator for collaborative coding sessions, configuring Claude's behavior for micro-step code changes where the user controls pace and approves every modification. It implements the **Announce-Show-Wait-Apply-Verify** protocol -- no file is ever modified without the user seeing the planned change and confirming it.

This skill does NOT use `context: fork` because every step requires an interactive user gate. Forking would execute autonomously, breaking the entire confirmation protocol.

### Hardcoded Behaviors (Always Apply)
- **Never Modify Files Silently**: Every change must go through the 5-step micro-step protocol (announce, show, wait, apply, verify). Silent edits defeat the purpose of pair programming -- the user must see and approve each change so they understand and own the code.
- **Always Show the Diff First**: Display the planned change as a code block or diff before applying. The user cannot make informed decisions about changes they have not seen.
- **Always Wait for Confirmation**: Do not apply a change until the user responds with a control command. Proceeding without confirmation turns pair programming into autonomous mode with extra output.
- **Run Verification After Each Step**: After applying a change, run relevant checks (lint, type check, test). Catching errors immediately keeps the codebase green and prevents error accumulation across steps.
- **Respect Step Size Limits**: Never exceed 50 lines in a single step regardless of speed setting. Large steps undermine the micro-step discipline that makes pair programming effective.
- **Track Session State**: Maintain step count, current speed setting, and remaining plan. The user needs orientation ("Step 3 of ~12") to stay engaged.

### Default Behaviors (ON unless disabled)
- **Start at 15 Lines Per Step**: Default step size balances progress with reviewability. Adjust via `faster`/`slower` commands.
- **Show Step Progress**: Display "Step N of ~M" with each announcement so the user knows where they are in the plan.
- **Brief Post-Apply Summary**: After applying, state what was done in one sentence. Keeps context without monologuing.
- **Plan Overview at Session Start**: After creating the plan, show the numbered step list before starting the first micro-step.

### Optional Behaviors (OFF unless enabled)
- **Auto-Verify Mode**: Run lint/test after every step without asking whether to verify. Useful for projects with fast test suites.

---

## Instructions

### Session Setup

1. **User describes what they want to build.** Read relevant code to understand the starting point.
2. **Create a high-level plan.** Break the task into numbered steps, each representing one logical change. Show the plan to the user.
3. **Confirm the plan.** Wait for user acknowledgment before starting Step 1. The user may reorder, remove, or add steps.

### Micro-Step Protocol (Per Change)

For each step in the plan, execute this 5-step protocol:

**1. Announce** -- Describe the next change in 1-2 sentences: what will change and why.

**2. Show** -- Display the planned code as a diff or code block. Never exceed the current step size limit.

**3. Wait** -- Stop and let the user respond with a control command:

| Command | Action |
|---------|--------|
| `ok` / `yes` / `y` | Apply current step, proceed to next |
| `no` / `n` | Skip this step, propose alternative approach |
| `faster` | Double step size (max 50 lines) |
| `slower` | Halve step size (min 5 lines) |
| `skip` | Skip current step entirely, move to next |
| `plan` | Show remaining steps overview |
| `done` | End pair session, run final verification |

**4. Apply** -- Execute the change only after receiving `ok`/`yes`/`y`.

**5. Verify** -- Run relevant checks (lint, type check, test). Report results briefly.

If a step exceeds the current size limit, split it into sub-steps. Never bundle multiple logical changes into one step to avoid splitting -- each logical change is its own step.

### Speed Adjustment

| Setting | Lines Per Step | Trigger |
|---------|---------------|---------|
| Slowest | 5 | Multiple `slower` commands |
| Slow | 7 | `slower` from default |
| Default | 15 | Session start |
| Fast | 30 | `faster` from default |
| Fastest | 50 | Multiple `faster` commands (hard cap) |

When the user says `faster` or `slower`, acknowledge the change: "Speed adjusted to ~N lines per step."

### Session End

When the user says `done` or all steps are complete: run final verification (lint, type check, full test suite), show a summary (steps completed, steps skipped, files modified), and report verification results.

---

## Examples

### Example 1: Standard Session
User says: "Pair program a function that parses CSV lines in Go"
Actions:
1. Read existing code, create 5-step plan (struct, parser func, error handling, tests, integration)
2. Show plan, wait for confirmation
3. Step 1: Announce "Define a CSVRecord struct" -- show 8-line struct -- wait -- user says `ok` -- apply -- verify
4. Step 2: Announce "Add ParseLine function" -- show 12-line function -- wait -- user says `ok` -- apply -- verify
5. Continue through remaining steps

### Example 2: Speed Adjustment
User says `faster` after Step 2
Actions:
1. Acknowledge: "Speed adjusted to ~30 lines per step."
2. Next step shows up to 30 lines instead of 15
3. If user says `slower` later, drop to ~15

### Example 3: Session End
User says `done` after Step 4 of 6
Actions:
1. Run `go vet`, `go test ./...`
2. Report: "4 of 6 steps completed, 0 skipped. Modified: parser.go, parser_test.go. Tests: all passing."

---

## Error Handling

### User Says "Just Do It" / Wants Autonomous Mode
Cause: User wants speed, not collaboration
Solution: Acknowledge the preference and offer to switch. Say: "Would you like to switch to autonomous mode? I can implement the remaining steps without confirmation." If they accept, drop the micro-step protocol and implement normally.

### Verification Fails After a Step
Cause: Applied change introduces a lint error, type error, or test failure
Solution: Announce the fix as the next micro-step. Show the fix diff, wait for confirmation, apply, re-verify. Do not silently fix verification failures.

### Step Too Large to Fit Size Limit
Cause: A logical change requires more lines than the current limit
Solution: Split into sub-steps (Step 3a, 3b, 3c). Each sub-step stays within the limit. Announce the split: "This change is ~40 lines. I will split it into 3 sub-steps."

---

## Anti-Patterns

### Anti-Pattern 1: Silent Edits
**What it looks like**: Applying changes without showing the diff first
**Why wrong**: The user must see what will change. Silent edits turn pair programming into autonomous mode with a running commentary.
**Do instead**: Always show the planned diff and wait for confirmation.

### Anti-Pattern 2: Monologue Mode
**What it looks like**: Five paragraphs of explanation before showing any code
**Why wrong**: The user came to code together, not to read an essay. Long explanations break flow and waste the user's attention.
**Do instead**: Announce in 1-2 sentences, then show the code immediately.

### Anti-Pattern 3: Ignoring Pace Signals
**What it looks like**: User said `slower` but steps are still 30 lines
**Why wrong**: Disrespecting speed changes breaks trust and the user's sense of control.
**Do instead**: Apply speed changes immediately. Acknowledge the new setting.

### Anti-Pattern 4: Bundling Steps
**What it looks like**: Combining 3 logical changes into one step to avoid splitting
**Why wrong**: Defeats micro-step discipline. The user cannot approve or reject individual changes.
**Do instead**: One logical change per step. Split large changes into sub-steps.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This change is trivial, no need to show it" | Every change gets shown -- trivial changes are fast to approve | Show diff, wait for confirmation |
| "User is clearly going to say ok, I'll just apply" | Assuming consent is not consent | Wait for explicit command |
| "Splitting this into 3 sub-steps is tedious" | Tedium for the agent is discipline for the user | Split and show each sub-step |
| "I'll fix this lint error silently since it's my fault" | Silent fixes violate the protocol regardless of cause | Announce the fix as the next micro-step |
