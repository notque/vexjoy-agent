# Implementation Plan Quality Rubric

Rate the plan 1-10 on each dimension:

## 1. Task Decomposition (1-10)
- Are tasks atomic (one thing each)?
- Are tasks scoped to 2-5 minutes?
- Do tasks have specific operations (not vague)?
- Are all design components covered?

## 2. Wave Ordering (1-10)
- Are tasks grouped by dependency waves?
- Do wave dependencies make sense?
- Are independent tasks in the same wave?
- Would executing in wave order produce correct results?

## 3. Agent Assignment (1-10)
- Does every task specify a domain agent?
- Are agent assignments appropriate for the task?
- Would the assigned agent have the right expertise?

## 4. Verifiability (1-10)
- Does every task have a verification command?
- Are verification commands executable?
- Would passing verification mean the task succeeded?
- Are file paths absolute?

## 5. Parallel Safety (1-10)
- Are parallel-safe flags present?
- Is file conflict analysis performed?
- Could parallel-safe tasks actually run simultaneously?

## Scoring
- 8-10: Ready for automated execution
- 6-7: Executable with minor clarifications
- 4-5: Needs revision before execution
- 1-3: Not actionable
