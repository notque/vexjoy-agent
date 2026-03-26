---
name: with-anti-rationalization
description: |
  Explicit anti-rationalization enforcement for maximum-rigor task execution.
  Loads all anti-rationalization patterns, gate enforcement, and pressure
  resistance as a composable modifier on any task. Use when executing critical
  production changes, security-sensitive code, complex multi-file refactors,
  or any task where shortcuts could cause harm. Use for "with rigor",
  "carefully", "maximum verification", or "no shortcuts". Do NOT use for
  trivial lookups, documentation-only edits, or simple typo fixes where
  full gate enforcement would be disproportionate overhead.
version: 2.0.0
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
  category: process
---

# Anti-Rationalization Enforcement Skill

## Operator Context

This skill operates as a composable modifier that wraps any task with explicit anti-rationalization enforcement. It implements the **Gate Enforcement** architectural pattern -- every phase transition requires evidence, every completion claim requires proof -- with **Pressure Resistance** embedded to prevent quality erosion under time or social pressure.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before starting any work
- **Full Pattern Loading**: Load ALL anti-rationalization patterns, not just a relevant subset
- **Gate Enforcement**: Every phase transition requires explicit evidence before proceeding
- **Pressure Resistance**: Cannot skip verification even when user pressures for speed
- **Evidence-Based Completion**: "Done" requires proof, not claims or confidence
- **Self-Check Protocol**: Run the anti-rationalization self-check before marking any task complete

### Default Behaviors (ON unless disabled)
- **Verbose Check Output**: Log each gate check and its pass/fail result visibly
- **Domain Pattern Loading**: Load domain-specific anti-rationalization patterns (security, testing, review) when relevant to the task
- **Escalation on Ambiguity**: Stop and ask user when requirements are unclear rather than guessing
- **Rationalization Logging**: Document any detected rationalization attempts during execution
- **Completion Checklist**: Run full verification checklist before declaring done

### Optional Behaviors (OFF unless enabled)
- **Audit Trail**: Write detailed execution log of all gate checks to a file
- **Strict Mode**: Treat warnings as failures at gate checks
- **Regression Verification**: Run full test suite at every phase transition, not just at completion

## What This Skill CAN Do
- Wrap any task with explicit anti-rationalization enforcement
- Load all shared anti-rationalization patterns (core, security, testing, review)
- Enforce phase gates with evidence requirements at every transition
- Resist pressure to skip steps while remaining professional
- Detect and surface rationalization attempts during execution
- Require proof of completion rather than accepting claims

## What This Skill CANNOT Do
- Replace domain-specific skills (debugging, refactoring, testing have their own methodologies)
- Make tasks faster -- this adds overhead deliberately for safety
- Override explicit user decisions about scope or technical approach
- Guarantee zero defects -- rigor reduces risk, it does not eliminate it
- Operate without an underlying task -- this is a modifier, not a standalone workflow

---

## Instructions

### Phase 1: LOAD PATTERNS

**Goal**: Load all anti-rationalization patterns relevant to the task before starting work.

**Step 1: Identify task domain**

Classify the task to determine which domain-specific patterns apply:

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

Read the identified shared-pattern files. Internalize the rationalization tables and enforcement rules. State which patterns were loaded and why -- this creates accountability.

**Gate**: All relevant patterns loaded and acknowledged. Proceed only when gate passes.

### Phase 2: EXECUTE WITH ENFORCEMENT

**Goal**: Run the underlying task with anti-rationalization checks at every transition.

**Step 1: Delegate to appropriate methodology**

This skill wraps other skills. If the task involves debugging, follow systematic-debugging methodology. If refactoring, follow systematic-refactoring. The anti-rationalization layer adds checks on top.

**Step 2: At each phase transition, run gate check**

For each transition, verify: (1) all exit criteria met, (2) evidence documented not just claimed, (3) anti-rationalization table reviewed, (4) no rationalization detected. Then run a rationalization scan -- am I assuming without verifying? Skipping because it "looks right"? Rushing from perceived pressure? If any answer is YES: STOP and address the rationalization before proceeding.

**Step 3: Handle pressure resistance**

If the user requests skipping a step:
1. Acknowledge the request
2. Explain why the step matters (one sentence)
3. Proceed with the step
4. If user insists on a non-security matter, note the risk and comply

**Gate**: Task phases executed with all gate checks passing. Proceed only when gate passes.

### Phase 3: VERIFY WITH FULL CHECKLIST

**Goal**: Verify completion with the full verification checklist and anti-rationalization self-check.

**Step 1: Run verification checklist**

| Check | Verified? | Evidence |
|-------|-----------|----------|
| All stated requirements addressed | [ ] | [specific evidence] |
| Tests pass (if applicable) | [ ] | [test output] |
| No regressions introduced | [ ] | [existing test output] |
| Error handling in place | [ ] | [error paths tested] |
| Code compiles/lints | [ ] | [build output] |
| Anti-rationalization table reviewed | [ ] | [self-check completed] |

**Step 2: Run completion self-check**

```markdown
## Completion Self-Check

1. [ ] Did I verify or just assume?
2. [ ] Did I run tests or just check code visually?
3. [ ] Did I complete everything or just the "important" parts?
4. [ ] Would I bet $100 this works correctly?
5. [ ] Can I show evidence (output, test results)?
```

If ANY answer is uncertain, return to Phase 2 and address the gap.

**Step 3: Document completion evidence**

Summarize: task description, patterns loaded, gate checks passed, rationalizations detected and addressed, and final evidence proving the task is complete.

**Gate**: All verification steps pass. Self-check is clean. Evidence documented. Task is complete.

---

## Examples

### Example 1: Critical Production Change
User says: "/with-anti-rationalization deploy the payment processor update"
Actions:
1. Load core + security anti-rationalization patterns (LOAD)
2. Execute deployment with gate checks at each phase (EXECUTE)
3. Resist any "just ship it" pressure with evidence requirements
4. Full verification checklist before declaring done (VERIFY)
Result: Deployment verified with evidence at every step

### Example 2: Security-Sensitive Code Review
User says: "/with-anti-rationalization review the authentication module"
Actions:
1. Load core + security + review anti-rationalization patterns (LOAD)
2. Review with explicit checks against "internal only" and "low risk" rationalizations (EXECUTE)
3. Every finding documented with evidence, not dismissed
4. Completion self-check confirms no findings were skipped (VERIFY)
Result: Thorough review with no rationalized dismissals

---

## Error Handling

### Error: "Pattern File Not Found"
Cause: Shared pattern file missing or path changed
Solution:
1. Check `skills/shared-patterns/` for available files
2. If file was renamed, use the new name
3. If file was deleted, apply the core patterns from CLAUDE.md as fallback
4. Document which pattern could not be loaded

### Error: "Gate Check Fails Repeatedly"
Cause: Task requirements unclear, or task is fundamentally blocked
Solution:
1. Re-read the gate criteria -- are they appropriate for this task?
2. If requirements are unclear, escalate to user for clarification
3. If technically blocked, document the blocker and ask user how to proceed
4. Do NOT weaken the gate criteria to force a pass

### Error: "User Insists on Skipping Verification"
Cause: Time pressure, frustration, or genuine scope reduction
Solution:
1. Distinguish quality skip (resist) from scope preference (respect)
2. If quality: explain risk once, note risk in output, comply if user insists again
3. If security: refuse and explain -- security shortcuts are non-negotiable
4. Document that verification was skipped at user request

---

## Anti-Patterns

### Anti-Pattern 1: Performative Checking
**What it looks like**: Running gate checks but rubber-stamping them all as PASS without reading evidence
**Why wrong**: Gate checks that always pass provide zero value. The check is the evidence review, not the checkbox.
**Do instead**: Read the evidence for each criterion. If you cannot articulate WHY it passes, it does not pass.

### Anti-Pattern 2: Rationalization Laundering
**What it looks like**: Reframing a skipped step as "not applicable" rather than "skipped"
**Why wrong**: "Not applicable" is sometimes legitimate, but it is also the most common way to rationalize skipping steps.
**Do instead**: For every "N/A" judgment, state WHY it does not apply. If the reason is weak, do the step.

### Anti-Pattern 3: Selective Pattern Loading
**What it looks like**: Loading only anti-rationalization-core and skipping domain-specific patterns
**Why wrong**: Domain-specific patterns catch domain-specific rationalizations that the core misses.
**Do instead**: Classify the task domain in Phase 1 and load ALL matching patterns.

### Anti-Pattern 4: Pressure Capitulation
**What it looks like**: Immediately dropping verification when user says "just do it"
**Why wrong**: The entire purpose of this skill is to resist shortcuts. Immediate capitulation defeats the purpose.
**Do instead**: Follow the pressure resistance framework: acknowledge, explain, proceed. Comply only after explaining risk.

### Anti-Pattern 5: Anti-Rationalization Theater
**What it looks like**: Spending more time on the checking framework than on the actual task
**Why wrong**: The goal is correct output, not elaborate process documentation. Checks should be proportionate.
**Do instead**: Scale check depth to task risk. Critical production changes get full ceremony. A three-file refactor gets lighter gates.

---

## References

This skill composes these shared patterns:
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md) - Universal rationalization detection and prevention
- [Anti-Rationalization Review](../shared-patterns/anti-rationalization-review.md) - Review-specific patterns
- [Anti-Rationalization Testing](../shared-patterns/anti-rationalization-testing.md) - Testing-specific patterns
- [Anti-Rationalization Security](../shared-patterns/anti-rationalization-security.md) - Security-specific patterns
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition enforcement
- [Pressure Resistance](../shared-patterns/pressure-resistance.md) - Handling pushback professionally
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion verification

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I loaded the patterns, that's enough" | Loading is not applying | Actively check against patterns at each gate |
| "This task is simple, full rigor is overkill" | Simplicity assessment is itself a rationalization risk | Apply proportionate rigor, but never zero |
| "User seems frustrated, I'll ease up" | Frustration does not change correctness requirements | Acknowledge frustration, maintain standards |
| "The gate basically passes" | Basically is not actually | Either it passes with evidence or it does not |
