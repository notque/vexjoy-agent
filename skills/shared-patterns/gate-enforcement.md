# Gate Enforcement Patterns

Rules for phase transitions in workflows. Gates are checkpoints that MUST be passed before proceeding.

## Core Principle

Gates exist because each phase depends on the previous phase being complete. Skipping gates causes:
- Building the wrong thing (skipped UNDERSTAND)
- Wasted work (skipped PLAN approval)
- Broken code (skipped VERIFY)

## Universal Gate Model

```
UNDERSTAND → PLAN → IMPLEMENT → VERIFY → COMPLETE
     │          │          │          │
     ▼          ▼          ▼          ▼
   Gate 1    Gate 2     Gate 3     Gate 4
```

## Gate Definitions

### Gate 1: UNDERSTAND → PLAN

| Exit Criteria | Evidence Required |
|---------------|-------------------|
| Requirements are clear | Written statement of what to build |
| Scope is defined | List of in-scope and out-of-scope items |
| Success criteria exist | How will we know it works? |
| Ambiguities resolved | Questions answered or documented |

**Cannot proceed if:** Requirements are unclear or ambiguous

### Gate 2: PLAN → IMPLEMENT

| Exit Criteria | Evidence Required |
|---------------|-------------------|
| Approach is defined | Written implementation plan |
| Files identified | List of files to create/modify |
| Dependencies known | External requirements identified |
| User approved | Explicit approval to proceed |

**Cannot proceed if:** No plan exists or plan not approved

### Gate 3: IMPLEMENT → VERIFY

| Exit Criteria | Evidence Required |
|---------------|-------------------|
| Code complete | All planned changes made |
| Tests written | Tests exist for new code |
| Code compiles/lints | No syntax or type errors |
| Self-review done | Author reviewed own code |

**Cannot proceed if:** Implementation incomplete or broken

### Gate 4: VERIFY → COMPLETE

| Exit Criteria | Evidence Required |
|---------------|-------------------|
| Tests pass | Test output showing success |
| Manual verification | Evidence code works as intended |
| No regressions | Existing tests still pass |
| Documentation updated | If behavior changed |

**Cannot proceed if:** Any verification fails

## Gate Violation Handling

When a gate check fails:

1. **STOP** - Do not proceed to next phase
2. **REPORT** - Clearly state what failed
3. **RESOLVE** - Fix the issue in current phase
4. **RE-CHECK** - Verify gate criteria again

Example:
```
Gate 3 FAILED: Tests not written for new function

Cannot proceed to VERIFY phase.

Required: Write tests for `calculateTotal()` function.

Returning to IMPLEMENT phase.
```

## Anti-Patterns

| Anti-Pattern | Why It's Wrong | Correct Behavior |
|--------------|----------------|------------------|
| "Quick test at end" | Tests should guide implementation | Tests before/during implementation |
| "Verify later" | Bugs compound over time | Verify immediately |
| "Plan in my head" | Can't verify unwritten plans | Write the plan |
| "User will catch issues" | Users shouldn't be QA | Verify before delivery |
| "Similar to last time" | Context differs | Re-verify for this case |

## Phase Completion Checklist

Use before transitioning:

```markdown
## Phase Transition: [FROM] → [TO]

Gate check:
- [ ] All exit criteria met
- [ ] Evidence documented
- [ ] No blockers remaining
- [ ] Ready for next phase

Proceeding to [TO] phase.
```

## Blocker Handling

When blocked at a gate:

| Blocker Type | Action |
|--------------|--------|
| Missing information | Ask user for clarification |
| Technical issue | Investigate and resolve |
| Dependency not available | Document and wait or workaround |
| Scope unclear | Return to UNDERSTAND phase |
| Conflicting requirements | Escalate to user |

**NEVER work around blockers by skipping gates.**
