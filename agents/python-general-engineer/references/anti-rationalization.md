# Python-Specific Anti-Rationalization

See `shared-patterns/anti-rationalization-core.md` for universal patterns.

### Python-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Tests pass, code is correct" | Tests can be incomplete, type errors not caught | Run mypy, check coverage, review edge cases |
| "Python's duck typing handles it" | Duck typing doesn't catch wrong types at runtime | Add type hints, run mypy in strict mode |
| "It works in my environment" | Dependencies may differ in production | Test with locked requirements, use venv |
| "The linter didn't complain" | Linters miss semantic and security issues | Manual review + linter + security scan |
| "I'll add type hints later" | Type hints never get added later | Add type hints with implementation |
| "Exception handling can wait" | Errors become harder to debug in production | Handle exceptions at implementation time |
| "This is just a small script" | Small scripts become production code | Apply same quality standards regardless |
