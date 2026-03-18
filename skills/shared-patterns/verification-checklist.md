# Verification Checklist

Universal checklist for verifying work before marking complete.

## Pre-Completion Checklist (MANDATORY)

Before marking ANY task complete:

| Check | Verified? | Evidence |
|-------|-----------|----------|
| All stated requirements addressed | [ ] | List each requirement + how addressed |
| Tests pass (if applicable) | [ ] | Test output |
| No regressions introduced | [ ] | Existing test output |
| Error handling in place | [ ] | Error paths tested |
| Code compiles/lints | [ ] | Build/lint output |
| Documentation updated (if behavior changed) | [ ] | Doc changes listed |
| Anti-rationalization table reviewed | [ ] | Self-check completed |
| User can verify the change works | [ ] | Steps to verify |

## Evidence Requirements

"Done" requires PROOF, not claims:

| Task Type | Required Evidence |
|-----------|------------------|
| Bug fix | Before/after behavior demonstrated |
| New feature | Feature working + tests passing |
| Refactor | Tests pass + behavior unchanged |
| Configuration | System accepts config + expected effect |
| Documentation | Content matches code behavior |
| Deletion | Removed code not referenced anywhere |

## Verification Methods

### Code Changes

```bash
# Minimum verification for code changes
1. Run tests: [test command]
2. Run linter: [lint command]
3. Run type checker: [type command]
4. Manual verification: [steps]
```

### Configuration Changes

```bash
# Minimum verification for config changes
1. Config syntax valid: [validation command]
2. System starts: [start command]
3. Feature works: [verification steps]
4. No side effects: [check other features]
```

### Documentation Changes

```markdown
1. Technical accuracy: Does it match code?
2. Completeness: Are all cases covered?
3. Examples work: Can examples be run?
4. Links valid: Do all links work?
```

## What "Complete" Actually Means

| NOT Complete | Complete |
|--------------|----------|
| "Code written" | Code written + tested + verified |
| "Tests pass locally" | Tests pass locally + in CI |
| "Looks good" | Verified through testing |
| "Should work" | Demonstrated to work |
| "PR submitted" | PR reviewed + approved + merged |

## Incomplete Work Protocol

If you cannot complete verification:

1. Document what IS complete
2. Document what IS NOT complete
3. List specific blockers
4. Do NOT mark as complete
5. Ask user how to proceed

Example:
```markdown
## Status: INCOMPLETE

Completed:
- Implementation done
- Unit tests written

Not completed:
- Integration tests (database not available)
- Manual verification (blocked on #2)

Blocker: Cannot run integration tests without database connection.

How would you like to proceed?
```

## The "Would I Bet Money?" Test

Before marking complete, ask:

> "Would I bet $100 that this works correctly?"

If hesitant, you're not done.
