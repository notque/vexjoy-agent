# Python Error Handling

Common Python errors and solutions. See `python-errors.md` for comprehensive catalog.

### Async Deadlock / Hanging
**Cause**: Awaiting on non-awaitable, missing await keyword, or deadlock in event loop
**Solution**: Use `asyncio.TaskGroup` for structured concurrency, verify all async functions use `await`, check for circular dependencies in async code. Debug with `asyncio.create_task()` and task names.

### Type Errors (mypy)
**Cause**: Incorrect type hints, missing types, or actual type bugs in logic
**Solution**: Fix the underlying issue instead of adding `# type: ignore` - use TypedDict for dicts, proper Union types, or fix the actual bug mypy found.

### Mutable Default Arguments (B006)
**Cause**: Using mutable defaults like `def func(items=[]):` creates shared state
**Solution**: Use `def func(items=None):` and create instance in function body: `items = items or []` or `items = items if items is not None else []`

### Import Errors
**Cause**: Circular imports, missing dependencies, or incorrect import paths
**Solution**: Reorganize imports, use TYPE_CHECKING for type-only imports, check virtual environment activation, verify package installation.

### AttributeError in Tests
**Cause**: Mock objects missing attributes or methods
**Solution**: Configure mocks properly: `mock_obj.return_value`, `mock_obj.side_effect`, or use `spec=` parameter to validate attributes.
