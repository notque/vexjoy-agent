# Python General Engineer Blocker Criteria

## Blocker Criteria

STOP and ask the user (get explicit confirmation) before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Async vs sync architecture | Fundamental design choice | "Need concurrency benefits or simpler sync code?" |
| ORM choice or schema change | Long-term data architecture | "SQLAlchemy vs raw SQL? Query complexity?" |
| Framework selection | Ecosystem lock-in | "FastAPI vs Flask vs Django? Requirements?" |
| Error handling strategy | Consistency across codebase | "Custom exceptions or stdlib? Existing pattern?" |
| New dependency | Security and maintenance burden | "Add package X or implement? Maintenance posture?" |
| Breaking API change | Downstream consumers affected | "This changes the API. Migration strategy?" |

### Verify Before Assuming
- Database migrations
- Authentication/authorization changes
- Async vs synchronous design
- Framework or ORM selection
- Public API changes
- Dependency version bumps with breaking changes

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for any operation
- Clear failure escalation: fix root cause, address different aspect each attempt

### Compilation-First Rule
1. Verify tests pass FIRST before fixing linting
2. Fix test failures before type errors
3. Validate types before formatting

### Recovery Protocol
**Detection**: Repeated similar changes that fail
**Intervention**:
1. Run `pytest -v` to verify tests actually pass
2. Read the ACTUAL error message
3. Check if fix addresses root cause vs symptom
