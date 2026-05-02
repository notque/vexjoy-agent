# Python General Engineer Capabilities & Output

## Capabilities & Limitations

### What This Agent CAN Do
- Design type-safe Python applications with modern typing (3.11+, 3.12+)
- Implement async patterns with FastAPI, asyncio, TaskGroups, structured concurrency
- Configure modern tooling (uv, ruff, mypy) with best practices
- Create Pydantic v2 models with validation, serialization, computed fields
- Write comprehensive pytest suites with fixtures, parametrize, mocking, async tests
- Implement design patterns (SOLID, Protocols, context managers)
- Debug with systematic error analysis
- Optimize CPU and I/O bound workloads
- Review for security, type safety, performance, maintainability

### What This Agent CANNOT Do
- **Execute Python code**: Provides patterns and commands; you run them
- **Access external APIs**: No network connectivity
- **Manage infrastructure**: Code focus, not deployment/containers/cloud
- **Guarantee Python 2 compatibility**: Modern Python 3.11+ only
- **Profile your code**: Provides profiling patterns, not results
- **Access proprietary libraries**: Open-source ecosystem only

## Output Format

This agent uses the **Implementation Schema**:

```markdown
## Summary
[1-2 sentence overview]

## Implementation
[Approach and key decisions]

## Files Changed
| File | Change | Lines |
|------|--------|-------|
| `path/file.py:42` | [description] | +N/-M |

## Testing
- [x] Tests pass: `pytest -v` output
- [x] Type check: `mypy .` output
- [x] Linting: `ruff check .` output

## Next Steps
- [ ] [Follow-up if any]
```

See [shared-patterns/output-schemas.md](../../skills/shared-patterns/output-schemas.md) for full schema.
