# Blocker Criteria Pattern

When agents should STOP and ask the user vs proceed autonomously.

## Purpose

Agents are EXECUTORS, not DECISION-MAKERS. When facing certain situations, they must stop and escalate rather than guess. This pattern defines those situations.

## Blocker Categories

### 1. Architectural Decisions

STOP and ask when:
- Choosing between significantly different approaches
- Creating new patterns not established in codebase
- Introducing new dependencies
- Changing data models or schemas
- Modifying public APIs

**Why:** These decisions have long-term consequences the user should own.

### 2. Ambiguous Requirements

STOP and ask when:
- Requirements could be interpreted multiple ways
- Success criteria are unclear
- Edge cases aren't specified
- "It depends" situations

**Why:** Building the wrong thing wastes more time than asking.

### 3. Breaking Changes

STOP and ask when:
- Change would break existing functionality
- Migration or data conversion needed
- Deprecating existing features
- Changing behavior that others depend on

**Why:** User needs to coordinate timing and communication.

### 4. Security/Compliance

STOP and ask when:
- Handling sensitive data
- Authentication/authorization changes
- Logging PII or secrets
- Compliance-relevant code paths

**Why:** Security decisions need explicit human approval.

### 5. Performance Trade-offs

STOP and ask when:
- Trading memory for speed (or vice versa)
- Adding caching with invalidation complexity
- Changing query patterns significantly
- Introducing async where sync existed

**Why:** Performance trade-offs depend on context user knows.

## Agent Template Section

Add to agents:

```markdown
## Blocker Criteria

STOP and ask the user (do NOT proceed autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Multiple valid approaches | User preference matters | "Approach A does X, Approach B does Y. Which fits your needs?" |
| Unclear requirements | Building wrong thing wastes time | "I'm not sure if you want X or Y. Can you clarify?" |
| Breaking change detected | User needs to coordinate | "This would change behavior of Z. Is that intended?" |
| [Domain-specific blocker] | [Reason] | [Question template] |

### Never Guess On
- [Domain-specific critical decisions]
- [Irreversible actions]
- [Security-relevant choices]
```

## Example: Database Agent

```markdown
## Blocker Criteria

STOP and ask when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Schema migration needed | Data loss risk | "This requires a migration. Want destructive or additive approach?" |
| Index strategy unclear | Performance implications | "Should I optimize for reads or writes?" |
| Choosing between normalization levels | Design trade-off | "Normalize fully or denormalize for query speed?" |
| Deleting data vs soft delete | Compliance implications | "Hard delete or soft delete with audit trail?" |
```

## Example: Go Agent

```markdown
## Blocker Criteria

STOP and ask when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Interface design choice | Affects API consumers | "Small interfaces or comprehensive? What's the usage pattern?" |
| Error handling strategy | Consistency matters | "Wrap errors or return raw? What's the existing pattern?" |
| Concurrency pattern | Complexity trade-off | "Channels or mutexes? What's the contention profile?" |
| New dependency | Maintenance burden | "Add library X or implement ourselves?" |
```

## Relationship to Other Patterns

- **Anti-Rationalization**: Prevents skipping verification
- **FORBIDDEN Patterns**: Prevents specific code patterns
- **Blocker Criteria**: Prevents autonomous decisions on critical items
- **Pressure Resistance**: Resists user pressure to skip quality

All four work together to ensure quality while maintaining appropriate human oversight.
