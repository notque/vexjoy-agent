# Python-Specific Anti-Rationalization

See `shared-patterns/anti-rationalization-core.md` for universal patterns.

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Tests pass, code is correct" | Tests can be incomplete, type errors not caught | Run mypy, check coverage, review edge cases |
| "Python's duck typing handles it" | Duck typing doesn't catch wrong types at runtime | Add type hints, run mypy strict |
| "It works in my environment" | Dependencies may differ in production | Test with locked requirements, use venv |
| "The linter didn't complain" | Linters miss semantic and security issues | Manual review + linter + security scan |
| "I'll add type hints later" | They never get added later | Add with implementation |
| "Exception handling can wait" | Errors become harder to debug in production | Handle at implementation time |
| "This is just a small script" | Small scripts become production code | Same quality standards regardless |
