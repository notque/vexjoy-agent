---
name: with-anti-rationalization
description: "Anti-rationalization enforcement for maximum-rigor task execution."
user-invocable: false
argument-hint: "<task>"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - "maximum rigor"
    - "anti-rationalization"
    - "strict verification"
    - "strict mode"
    - "no shortcuts"
  category: process
  pairs_with:
    - verification-before-completion
---

# Anti-Rationalization Enforcement Skill

## Overview

Composable modifier that wraps any task with anti-rationalization enforcement. Every phase transition requires evidence, every completion claim requires proof. Embeds pressure resistance to prevent quality erosion under time or social pressure.

Not a substitute for domain-specific skills (debugging, refactoring, testing have their own). Layers anti-rationalization checks on top of whatever task you execute.

---

## Instructions

### Phase 1: LOAD PATTERNS

**Goal**: Load all relevant anti-rationalization patterns before starting work. Full pattern loading is mandatory because domain-specific patterns catch rationalizations the core set misses.

**Step 1: Identify task domain**

| Domain | Pattern to Load |
|--------|----------------|
| Any task | `anti-rationalization-core.md` |
| Code review | `anti-rationalization-review.md` |
| Testing | `anti-rationalization-testing.md` |
| Security | `anti-rationalization-security.md` |
| Multi-phase work | `gate-enforcement.md` |
| User pressure detected | `pressure-resistance.md` |
| Pre-completion | `verification-checklist.md` |

**Step 2: Load and acknowledge patterns**

Read identified shared-pattern files. State explicitly which patterns were loaded and why — this creates accountability.

**Gate**: All relevant patterns loaded and acknowledged. You must articulate why each applies. Rubber-stamp checks fail the skill's purpose.

### Phase 2: EXECUTE WITH ENFORCEMENT

**Goal**: Run the underlying task with anti-rationalization checks at every transition.

**Step 1: Delegate to appropriate methodology**

If the task fits an existing methodology (debugging, refactoring, testing, review), use that skill. Anti-rationalization amplifies; it does not replace.

**Step 2: At each phase transition, run gate check**

Verify:
1. All exit criteria met
2. Evidence documented (not just claimed)
3. Anti-rationalization table reviewed
4. No rationalization detected

**Pressure Resistance**: If user requests skipping a step:
1. Acknowledge the request
2. Explain why the step matters (one sentence)
3. Proceed with the step
4. If user insists on non-security matter, note risk and comply
5. **Never skip security-sensitive steps** — document refusal and reasoning

Then run rationalization scan:
- Am I assuming without verifying?
- Skipping because it "looks right"?
- Rushing from perceived pressure?
- Calling something "not applicable" when really skipping?
- Treating "basically passes" as "passes"?

If any YES: STOP and address before proceeding.

**Proportionate Rigor**: Scale check depth to task risk. Critical production changes get full ceremony. Three-file refactor gets lighter gates. Never zero.

**Gate**: Task phases executed with all gate checks passing.

### Phase 3: VERIFY WITH FULL CHECKLIST

**Goal**: Verify completion with full checklist and self-check.

**Step 1: Verification checklist**

| Check | Verified? | Evidence |
|-------|-----------|----------|
| All stated requirements addressed | [ ] | [specific evidence] |
| Tests pass (if applicable) | [ ] | [test output] |
| No regressions introduced | [ ] | [existing test output] |
| Error handling in place | [ ] | [error paths tested] |
| Code compiles/lints | [ ] | [build output] |
| Anti-rationalization table reviewed | [ ] | [self-check completed] |

Every check requires actual evidence. "Code looks right" is not evidence. Test output is evidence.

**Step 2: Completion self-check**

```markdown
## Completion Self-Check

1. [ ] Did I verify or just assume?
2. [ ] Did I run tests or just check code visually?
3. [ ] Did I complete everything or just the "important" parts?
4. [ ] Would I bet $100 this works correctly?
5. [ ] Can I show evidence (output, test results)?
```

If ANY answer uncertain, return to Phase 2 and close the gap.

**Step 3: Document completion evidence**

Summarize: task description, patterns loaded, gate checks passed, rationalizations detected and addressed, final evidence.

**Gate**: All verification passes. Self-check clean. Evidence documented.

---

## Reference Material: Anti-Rationalization Patterns

### Domain-Specific Anti-Rationalization

| Rationalization | Why Wrong | Required Action |
|-----------------|-----------|-----------------|
| "I loaded the patterns, that's enough" | Loading is not applying | Check against patterns at each gate |
| "This task is simple, full rigor is overkill" | Simplicity assessment is itself a rationalization risk | Proportionate rigor, but never zero |
| "User seems frustrated, I'll ease up" | Frustration does not change correctness requirements | Acknowledge frustration, maintain standards |
| "The gate basically passes" | Basically is not actually | Passes with evidence or does not |

### Pattern Checklist

**Signal 1: Performative Checking** — Running gate checks but rubber-stamping all as PASS without reading evidence. Read the evidence. If you cannot articulate why it passes, it does not.

**Signal 2: Rationalization Laundering** — Reframing skipped steps as "not applicable". For every "N/A" judgment, state why. If the reason is weak, do the step.

**Signal 3: Selective Pattern Loading** — Loading only core and skipping domain-specific patterns. Classify the domain in Phase 1 and load all matching patterns.

**Signal 4: Pressure Capitulation** — Dropping verification when user says "just do it". Follow pressure resistance: acknowledge, explain, proceed. Comply only after explaining risk.

**Signal 5: Anti-Rationalization Theater** — More time on checking framework than actual task. Scale check depth to task risk.

---

## Error Handling

### Error: "Pattern File Not Found"
Cause: Shared pattern file missing or path changed.
Solution: Check `skills/shared-patterns/` for available files. If renamed, use new name. If deleted, apply core patterns from CLAUDE.md as fallback. Document which pattern could not be loaded.

### Error: "Gate Check Fails Repeatedly"
Cause: Requirements unclear or task fundamentally blocked.
Solution: Re-read gate criteria. If requirements unclear, escalate to user. If blocked, document blocker and ask user. Keep gate criteria intact.

### Error: "User Insists on Skipping Verification"
Cause: Time pressure, frustration, or scope reduction.
Solution: Distinguish quality skip (resist) from scope preference (respect). If quality: explain risk once, note in output, comply if user insists again. If security: refuse. Document that verification was skipped at user request.

---

## References

This skill composes these shared patterns:
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md) - Universal rationalization detection
- [Anti-Rationalization Review](../shared-patterns/anti-rationalization-review.md) - Review-specific patterns
- [Anti-Rationalization Testing](../shared-patterns/anti-rationalization-testing.md) - Testing-specific patterns
- [Anti-Rationalization Security](../shared-patterns/anti-rationalization-security.md) - Security-specific patterns
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition enforcement
- [Pressure Resistance](../shared-patterns/pressure-resistance.md) - Handling pushback professionally
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion verification
