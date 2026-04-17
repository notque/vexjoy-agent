# Python General Engineer Blocker Criteria

## Blocker Criteria

STOP and ask the user (get explicit confirmation) before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Async vs sync architecture | Fundamental design choice | "Need concurrency benefits or simpler sync code?" |
| ORM choice or schema change | Long-term data architecture | "SQLAlchemy vs raw SQL? What's the query complexity?" |
| Framework selection | Maintenance and ecosystem lock-in | "FastAPI vs Flask vs Django? What are the requirements?" |
| Error handling strategy | Consistency across codebase | "Custom exceptions or stdlib? What's the existing pattern?" |
| New dependency | Security and maintenance burden | "Add package X or implement? What's the maintenance posture?" |
| Breaking API change | Downstream consumers affected | "This changes the API. How should we handle migration?" |

### Never Guess On
- Database migrations (schema changes)
- Authentication/authorization changes
- Async vs synchronous design
- Framework or ORM selection
- Public API changes
- Dependency version bumps with breaking changes

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for any operation (tests, linting, type checking)
- Clear failure escalation path: fix root cause, address a different aspect each attempt

### Compilation-First Rule
1. Verify tests pass FIRST before fixing linting issues
2. Fix test failures before addressing type errors
3. Validate types before formatting

### Recovery Protocol
**Detection**: If making repeated similar changes that fail
**Intervention**:
1. Run `pytest -v` to verify tests actually pass
2. Read the ACTUAL error message carefully
3. Check if the fix addresses root cause vs symptom
