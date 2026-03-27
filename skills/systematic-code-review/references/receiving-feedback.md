# Receiving Review Feedback

When YOU are the one receiving code review feedback (not giving it), apply these patterns:

## The Reception Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## No Performative Agreement

**NEVER:**
- "You're absolutely right!"
- "Great point!" / "Excellent feedback!"
- "Thanks for catching that!"

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

**When feedback IS correct:**
```
"Fixed. [Brief description of what changed]"
"Good catch - [specific issue]. Fixed in [location]."
[Just fix it and show in the code]
```

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
Reviewer: "Fix items 1-6"
You understand 1,2,3,6. Unclear on 4,5.

WRONG: Implement 1,2,3,6 now, ask about 4,5 later
RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## When to Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code

**Example:**
```
Reviewer: "Remove legacy code"
WRONG: "You're absolutely right! Let me remove that..."
RIGHT: "Checking... build target is 10.15+, this API needs 13+. Need legacy for backward compat. Fix bundle ID or drop pre-13 support?"
```

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions
```

## External vs Internal Reviewers

**From external reviewers:**
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I investigate/proceed?"
```
