# Python Error Handling

Common Python errors. See `python-errors.md` for comprehensive catalog.

### Async Deadlock / Hanging
**Cause**: Missing await, awaiting non-awaitable, circular async dependencies, event loop blocking
**Solution**: Use `asyncio.TaskGroup` for structured concurrency, verify all async functions use `await`, debug with `asyncio.create_task()` and task names.

### Type Errors (mypy)
**Cause**: Incorrect type hints, missing types, or actual type bugs
**Solution**: Fix the underlying issue — use TypedDict for dicts, proper Union types. Do not add `# type: ignore`.

### Mutable Default Arguments (B006)
**Cause**: `def func(items=[]):` creates shared state
**Solution**: `def func(items=None):` then `items = items or []`

### Import Errors
**Cause**: Circular imports, missing dependencies, wrong import paths
**Solution**: Use TYPE_CHECKING for type-only imports, check venv activation, verify package installation.

### AttributeError in Tests
**Cause**: Mock objects missing attributes or methods
**Solution**: Configure mocks with `return_value`, `side_effect`, or `spec=` parameter.
