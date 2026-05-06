# Depth-First Interview Reference

## Purpose

Resolve ambiguity by walking a decision tree one branch at a time, with a recommended answer alongside each question. Use this when the topic is broad and uncertain — when "help me get clarity" is the request. Contrast with `pre-plan.md` (breadth-first scope clarification) and `socratic-debugging/SKILL.md` (bug-finding via questions).

## When to use vs when not

Use when:
- User signals uncertainty: "not sure", "i'm not sure", "where do i start", "want clarity on X", "interview me", "grill me", "depth-first review".
- `/do` Phase 3 detected an ambiguity signal (vague verb + ambiguous object + no concrete file/symbol named).
- `/quick --interview` was passed.
- Decisions are interdependent — answer A constrains valid options for B, so batch-asking would force premature commitments.

Use `pre-plan.md` instead when:
- Scope is unclear and you need to surface all gray areas at once for batch decisions.
- Brownfield codebase where assumptions need to be made explicit before planning.

Use `socratic-debugging` instead when:
- The task is finding a specific bug.

## Phase 0: PRIME (1-2 turns)

1. Load CLAUDE.md (root and any subdirectory matching the topic).
2. Establish a one-sentence scope boundary (what is in vs out).
3. **Classify the trigger source**:
   - **Explicit**: user typed "interview me", "grill me", "depth-first review", or invoked `/quick --interview`.
   - **Implicit**: trigger was an uncertainty phrase ("not sure", "where do i start") or `/do` Phase 3 auto-injection.
4. **Ask the opt-out question only for implicit triggers**:
   > "Before I start asking — want me to interview you depth-first, or just dive in?"

   Skip this question for explicit triggers — the user already opted in by typing the trigger. Asking again is friction.

   For implicit triggers, if the user responds with `"just build it"`, `"just go"`, `"skip questions"`, `"don't grill me"`, or any clear pass: abort the interview, proceed to direct execution, and record `Mode Used: Interview (skipped — user opted out)` in Phase 3 output.

**GATE**: Trigger classified. For explicit triggers, proceed directly to Phase 1. For implicit triggers, user opted in. Otherwise stop.

## Phase 1: ENUMERATE BRANCHES (1 turn)

1. List candidate decisions discovered from the request plus a quick code exploration.
2. Rank by load-bearing weight — which answer constrains the most downstream choices?
3. Output the ranked list inline (3-7 items). Branches below the cap of 5 questions get deferred to a "Carried Forward" section in Phase 3.

**GATE**: Ranked branch list visible to user.

## Phase 2: TRAVERSE (one branch at a time, max 5 total questions)

For each branch in priority order:

**Step 1**: Pick the highest-leverage unresolved branch.

**Step 2: Read code FIRST.** Use Read/Grep/Glob to answer the question if the codebase contains the answer. Only ask the human for things the codebase cannot tell you: preferences, priorities, intent, scope, taste. Asking the human for facts the code already states wastes a question budget slot and erodes trust.

**Step 3: Ask one question, with a recommendation.** Format:
> Question: [the decision]?
> Recommended: [your answer], because [reason grounded in code or stated constraint].
> Sound right, or different direction?

The recommendation is non-negotiable — turning "design this" into "ratify-or-correct" is the whole point. A bare question without a recommendation puts the design burden back on the user.

**Step 4: Recurse.** If the user's answer opens sub-branches, resolve those before returning to the next top-level branch. Track depth — do not exceed 3 levels of recursion in any one branch. At depth 3, force-stop and mark the deeper sub-branch as `[carried forward]`.

**Step 5: Loop guard.** Hard cap: 5 total questions across the entire interview. After 5, force-stop and emit Phase 3 output even if branches remain unresolved (mark them `[carried forward]`). This is a hard limit, not advisory — caps that get rationalized past stop being caps.

**GATE**: User signals "ok go", "build it", "that's enough", or the 5-question cap is hit.

## Phase 3: COMPILE OUTPUT

Emit the SAME schema as `pre-plan.md` (no fork — downstream consumers must work on either artifact):

```markdown
## Resolved Decisions
- [Decision 1]: [answer] — [one-line rationale]
- [Decision 2]: [answer] — [one-line rationale]

## Carried Forward
- [Branch deferred]: [why deferred, when to revisit]

## Scope Boundary
[One sentence on what is in vs out]

## Mode Used
Interview (depth-first, N questions asked)
```

**GATE**: Output structurally identical to `pre-plan.md` output. Pass to downstream agent or save to `task_plan.md` context alongside any existing plan.

## Error Handling

### Error: User defers every question
**Cause**: User replies "your call" or "you decide" to every question.
**Solution**: After 2 consecutive defers, switch from interview to direct execution using your recommended answers. Note the switch in Phase 3 output: `Mode Used: Interview (defaulted)`.

### Error: Branch explodes into more than 3 sub-questions
**Cause**: A question reveals ambiguity larger than expected.
**Solution**: Stop recursing. Emit current state to Phase 3, mark the exploded branch as `[carried forward — needs separate interview]`, and recommend the user invoke a fresh interview targeted at that branch.

### Error: User invokes interview but request is fully specified
**Cause**: Misclassification — request had concrete file/symbol/test specified but the trigger fired anyway.
**Solution**: In Phase 0 PRIME, when scope boundary is trivially clear and no gray areas surface in a quick code scan, output `## No interview needed` with a one-line justification and skip directly to Phase 3 with `Mode Used: Interview (skipped — no ambiguity)`.

### Error: 5-question cap hit with branches unresolved
**Cause**: Topic genuinely larger than one interview session can resolve.
**Solution**: Emit Phase 3 with all unresolved branches in Carried Forward. Recommend the user run a follow-up interview after the first batch of decisions is implemented — answers narrow the remaining decision space.

## References

- ADR-209 (this design)
- ADR-072 (pre-plan breadth-first contract — sibling, not superseded)
- `pre-plan.md` (sibling reference, breadth-first counterpart)
- `docs/PHILOSOPHY.md` (umbrella pattern, progressive disclosure, anti-rationalization caps)
