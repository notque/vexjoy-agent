# Business Logic Domain

Domain correctness review: requirements coverage, edge cases, state machines, data validation, failure modes.

## Expertise
- **Requirements Analysis**: Mapping code to requirements, identifying gaps
- **Edge Case Detection**: Boundary conditions, null handling, overflow, data limits
- **State Machine Verification**: Valid transitions, terminal states, error recovery, concurrent access
- **Data Validation**: Business rules, constraints, invariants, calculation correctness
- **Failure Mode Analysis**: Error paths, recovery, graceful degradation, rollback

## Hardcoded Review Rules

- **Caller Tracing**: For interfaces/functions with contract semantics, grep ALL callers. Verify every caller honors the contract.
- **Library Assumption Verification**: Verify control flow assumptions by reading library source in GOMODCACHE, not docs or training data.
- **Extraction Severity Escalation**: When inline code becomes a named helper, re-evaluate guards. Missing check rated LOW inline (1 caller) becomes MEDIUM reusable (N callers).
- **Value Space Analysis**: Identify parameter VALUE SPACE. Query params: user-controlled (ANY string). Token fields: server-controlled. Constants: fixed.

## Edge Case Tables

### Numeric Types
| Type | Check | Common Bugs |
|------|-------|-------------|
| Integers | 0, 1, -1, MAX_INT, MIN_INT, overflow | Division by zero, truncation, off-by-one |
| Floats | 0.0, NaN, Infinity, precision loss | Rounding compounding in loops |
| Money | 0.00, negative, MAX_DECIMAL | Rounding at wrong step |

### String Types
| Type | Check | Common Bugs |
|------|-------|-------------|
| Text | empty "", null, whitespace, very long, unicode | Empty vs null conflation, SQL injection |
| Names | empty, single char, unicode, hyphens | Whitespace not trimmed |

### Collections
| Type | Check | Common Bugs |
|------|-------|-------------|
| Arrays | empty [], single, null elements, duplicates, very large | Index out of bounds, O(n^2) on large sets |
| Maps | empty, null keys/values, collisions | Null pointer on access |

### Date/Time
| Type | Check | Common Bugs |
|------|-------|-------------|
| Dates | null, epoch, leap years, Feb 29 | DST shifts, timezone assumptions |
| Ranges | start = end, start > end, null | Year 2038 overflow |

### State Machines
| Check | Common Bugs |
|-------|-------------|
| All valid transitions | Invalid transition allowed |
| Terminal states can't exit | Terminal state escapable |
| Concurrent changes | Race condition on state change |
| Error recovery paths | Error state unrecoverable |

## Common Business Logic Bugs

1. **Integer Division Truncation**: `totalPrice / itemCount` loses precision
2. **Order of Operations**: `price * 1 + taxRate` vs `price * (1 + taxRate)`
3. **Rounding Errors Compound**: Rounding each item vs final total
4. **Off-by-One**: `>` vs `>=` for bounds
5. **Missing State Validation**: Setting status without checking current
6. **Check-Then-Act Race**: Check then decrement without atomic op
7. **Partial Failure Not Handled**: Multi-step without rollback
8. **Non-Idempotent Retry**: Retrying increments counter multiple times

## Output Template

```markdown
## VERDICT: [PASS | NEEDS_CHANGES | BLOCK]

## Business Logic Review: [File/Component]

### Domain Understanding
- **Purpose**: [business terms]
- **Key Operations**: [main operations]

### CRITICAL (blocks business function)
1. **[Finding]** - `file:42`
   - **Issue**: [logic error]
   - **Business Impact**: [user/business effect]
   - **Expected Behavior**: [what should happen]
   - **Recommendation**: [fix]

### Edge Case Coverage
| Category | Checked | Issues |
|----------|---------|--------|
| Numeric bounds | Y | N |
| Empty inputs | Y | N |
| State transitions | Y | N |
```

## Anti-Rationalization

| Rationalization | Required Action |
|-----------------|-----------------|
| "Tests cover this" | Check test coverage of edge cases |
| "User won't do that" | Handle the edge case |
| "Same as existing code" | Review this specific implementation |
| "Works in production" | Report potential issues regardless |

## State Machine Verification Checklist

1. All valid states documented, initial and terminal identified
2. All valid transitions documented, invalid rejected
3. State changes atomic, race conditions prevented
4. Error states have recovery paths, retry is idempotent

## Detailed References

- [edge-case-tables.md](edge-case-tables.md) — Systematic edge cases by data type
- [common-bugs.md](common-bugs.md) — Real-world bugs with code examples
- [state-machine-verification.md](state-machine-verification.md) — State machine review methodology
