# Manus-Style Planning

The `pretool-plan-gate` hook (PreToolUse) blocks Write/Edit to `agents/` and `skills/` when `task_plan.md` is missing, enforcing plan-first development.

## When Plans Are Required

| Complexity | Indicators | Action |
|------------|------------|--------|
| Trivial | Pure lookup, single read | No plan needed |
| Simple+ | Routes to agent, code change | **Create task_plan.md** |

## Plan File Template

```markdown
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Phases
- [ ] Phase 1: Understand/research
- [ ] Phase 2: Plan approach
- [ ] Phase 3: Implement
- [ ] Phase 4: Verify and deliver

## Key Questions
1. [Question to answer]

## Decisions Made
- [Decision]: [Rationale]

## Errors Encountered
- [Error]: [Resolution]

## Status
**Currently in Phase X** - [What I'm doing now]
```

## Critical Rules

1. **ALWAYS create plan first** - Never start complex work without `task_plan.md`
2. **Read before decide** - Re-read plan before major decisions (combats context drift)
3. **Update after act** - Mark [x] and update status after each phase
4. **Store, don't stuff** - Large outputs go to files, not context
5. **Log all errors** - Every error goes in "Errors Encountered" section
