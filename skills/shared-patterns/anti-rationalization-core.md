# Anti-Rationalization Core Patterns

Universal patterns to prevent AI from rationalizing skipped requirements, incomplete verification, or "good enough" shortcuts.

## Why This Exists

LLMs naturally want to be helpful and efficient. This can lead to rationalizing shortcuts:
- "The code looks correct, I don't need to verify"
- "This is a simple change, tests aren't needed"
- "The user is in a hurry, I'll skip verification"

These shortcuts cause bugs. This pattern blocks them.

## Anti-Rationalization Table (MANDATORY CHECK)

Before completing ANY task, verify you haven't rationalized:

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Already done/verified" | Assumption ≠ Verification | **Actually verify with evidence** |
| "Code looks correct" | Looking ≠ Being correct | **Run tests, check types** |
| "Trivial change, skip tests" | All changes need verification | **Test anyway** |
| "Time pressure" | Quality > Speed | **Complete all steps** |
| "User said skip it" | CLAUDE.md > user shortcuts | **Follow protocol, explain why** |
| "Partial is good enough" | Partial ≠ Complete | **Finish completely** |
| "Similar to before" | Similar ≠ Same | **Verify this specific case** |
| "Should work" | Should ≠ Does | **Prove it works** |
| "Only changed one line" | One line can break everything | **Full verification** |
| "Tests are slow" | Slow tests > broken code | **Run them anyway** |
| "I'm confident" | Confidence ≠ Correctness | **Verify regardless** |
| "Edge case won't happen" | Edge cases always happen | **Handle it** |
| "Need to un-ignore this path" | `.gitignore` defines safety boundaries | **NEVER modify `.gitignore` to un-ignore paths** |
| "Just force-add this one file" | `git add -f` bypasses safety boundaries | **NEVER use `git add --force`; if git refuses, that's correct** |

## Assertive Language Reference

Use strong language for non-negotiable requirements:

| Category | Words to Use | When |
|----------|--------------|------|
| **Requirements** | MUST, REQUIRED, MANDATORY, SHALL, ALWAYS | Non-negotiable actions |
| **Prohibitions** | CANNOT, NEVER, FORBIDDEN, MUST NOT, PROHIBITED | Actions that would break invariants |
| **Enforcement** | HARD GATE, NON-NEGOTIABLE, NO EXCEPTIONS | Phase transitions |
| **Anti-patterns** | "Assumption ≠ Verification", "Looking ≠ Being" | Counter rationalizations |

## Self-Check Protocol

Before marking ANY task complete:

```markdown
## Completion Self-Check

1. [ ] Did I verify or just assume?
2. [ ] Did I run tests or just check code visually?
3. [ ] Did I complete everything or just the "important" parts?
4. [ ] Would I bet money this works?
5. [ ] Can I show evidence (output, test results)?
```

If any answer is uncertain, you're not done.

## Escalation Triggers

STOP and ask the user when:

| Situation | Why Escalate | Don't |
|-----------|--------------|-------|
| Unclear requirements | Building wrong thing | Guess and proceed |
| Multiple valid approaches | User preference matters | Pick arbitrarily |
| Breaking change detected | User impact | Hide it in PR |
| Tests failing unexpectedly | Root cause unknown | Skip the failing test |
| Security concern | Risk assessment needed | Assume it's fine |

## Evidence Requirements

"Done" means you can show proof:

| Task Type | Required Evidence |
|-----------|------------------|
| Bug fix | Before/after behavior + test output |
| New feature | Tests pass + manual verification |
| Refactor | Tests still pass + no behavior change |
| Configuration | System accepts config + expected effect |
| Documentation | Accurate + matches code |

## Common Rationalization Patterns by Domain

### Code Changes
- "The type system catches this" → Run tests anyway
- "Linter didn't complain" → Linter misses logic errors
- "It compiled" → Compiling ≠ Correct

### Testing
- "Happy path works" → Test error paths
- "Unit tests pass" → Integration might fail
- "Works locally" → CI might differ

### Reviews
- "Author explained it" → Still verify
- "Tests pass" → Tests can be incomplete
- "Small change" → Small changes cause big bugs

## Integration with Skills

Skills reference this pattern and add domain-specific rows:

```markdown
## Anti-Rationalization

See [core patterns](../shared-patterns/anti-rationalization-core.md).

Domain-specific for [skill name]:

| Rationalization | Why Wrong | Action |
|-----------------|-----------|--------|
| [specific to domain] | [reason] | [action] |
```
