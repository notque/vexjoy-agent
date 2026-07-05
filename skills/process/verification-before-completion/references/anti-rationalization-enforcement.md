# Anti-Rationalization Enforcement Patterns

From the demoted `with-anti-rationalization` skill. Use as a composable overlay on any verification task requiring maximum rigor.

## Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I loaded the patterns, that's enough" | Loading is not applying | Actively check against patterns at each gate |
| "This task is simple, full rigor is overkill" | Simplicity assessment is itself a rationalization risk | Apply proportionate rigor, but never zero |
| "User seems frustrated, I'll ease up" | Frustration does not change correctness requirements | Acknowledge frustration, maintain standards |
| "The gate basically passes" | Basically is not actually | Either it passes with evidence or it does not |

## Pattern Checklist: What to Detect and Fix

### Signal 1: Performative Checking
**Signal**: Running gate checks but rubber-stamping them all as PASS without reading evidence
**Why it matters**: Gate checks that always pass provide zero value. The check is the evidence review, not the checkbox.
**Preferred action**: Read the evidence for each criterion. If you cannot articulate why it passes, it does not pass.

### Signal 2: Rationalization Laundering
**Signal**: Reframing a skipped step as "not applicable" rather than "skipped"
**Why it matters**: "Not applicable" is sometimes legitimate, but it is also the most common way to rationalize skipping steps.
**Preferred action**: For every "N/A" judgment, state why it does not apply. If the reason is weak, do the step.

### Signal 3: Selective Pattern Loading
**Signal**: Loading only anti-rationalization-core and skipping domain-specific patterns
**Why it matters**: Domain-specific patterns catch rationalizations that the core misses.
**Preferred action**: Classify the task domain and load all matching patterns.

### Signal 4: Pressure Capitulation
**Signal**: Immediately dropping verification when the user says "just do it"
**Why it matters**: The entire purpose of this skill is to resist shortcuts. Immediate capitulation defeats the purpose.
**Preferred action**: Follow the pressure resistance framework: acknowledge, explain, proceed. Comply only after explaining risk.

### Signal 5: Anti-Rationalization Theater
**Signal**: Spending more time on the checking framework than on the actual task
**Why it matters**: The goal is correct output, not elaborate process documentation. Checks should be proportionate.
**Preferred action**: Scale check depth to task risk. Critical production changes get full ceremony. A three-file refactor gets lighter gates.

## Pressure Resistance Framework

When the user requests skipping a step:
1. Acknowledge the request
2. Explain why the step matters (one sentence)
3. Proceed with the step
4. If user insists on a non-security matter, note the risk and comply
5. Security-sensitive steps are non-negotiable. Document refusal and reasoning.

## Completion Self-Check

1. Did I verify or just assume?
2. Did I run tests or just check code visually?
3. Did I complete everything or just the "important" parts?
4. Would I bet $100 this works correctly?
5. Can I show evidence (output, test results)?

If ANY answer is uncertain, return and address the gap before continuing.

## Shared Pattern Files

These shared-patterns are composed by this enforcement layer:
- `skills/shared-patterns/anti-rationalization-core.md` - Universal rationalization detection
- `skills/shared-patterns/anti-rationalization-review.md` - Review-specific patterns
- `skills/shared-patterns/anti-rationalization-testing.md` - Testing-specific patterns
- `skills/shared-patterns/anti-rationalization-security.md` - Security-specific patterns
- `skills/shared-patterns/gate-enforcement.md` - Phase transition enforcement
- `skills/shared-patterns/pressure-resistance.md` - Handling pushback professionally
- `skills/shared-patterns/verification-checklist.md` - Pre-completion verification
