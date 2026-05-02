---
name: php-testing
description: "PHP testing patterns: PHPUnit, test doubles, database testing."
user-invocable: false
context: fork
agent: php-general-engineer
routing:
  triggers:
    - "php testing"
    - "phpunit"
    - "pest php"
    - "php mock"
  category: php
  pairs_with:
    - php-quality
    - test-driven-development
---

# PHP Testing Skill

PHPUnit testing patterns: unit tests, data providers, test doubles, database testing (Laravel/Symfony), HTTP testing, coverage. See `references/patterns.md` for code examples, anti-patterns, and commands.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `patterns.md` | Loads detailed guidance from `patterns.md`. |

## Instructions

### Phase 1: IDENTIFY

Determine what needs testing:
- Unit logic: PHPUnit `TestCase` with `test` prefix or `@test`
- Table-driven cases: `@dataProvider` static methods
- Collaborator behavior: stubs (return values) or mocks (assert interactions)
- Database state: `DatabaseTransactions` (Laravel) or `KernelTestCase` (Symfony)
- HTTP endpoints: Laravel HTTP helpers or Symfony `WebTestCase`

### Phase 2: WRITE

Rules:
- Call `parent::setUp()` first in every `setUp()` method
- Use `assertSame()` over `assertTrue($a === $b)` for meaningful failure messages
- Mock only collaborators, never the class under test
- Keep tests independent -- no `@depends` chains
- Extract repetitive cases to `@dataProvider`

Test doubles: `createStub()` for return values only, `createMock()` for asserting calls, Prophecy (`phpspec/prophecy-phpunit`) for expressive interaction assertions.

Database tests: `DatabaseTransactions` (Laravel) or DoctrineTestBundle (Symfony) to roll back after each test.

### Phase 3: VERIFY

Run the test suite and confirm all tests pass:

```bash
./vendor/bin/phpunit
```

For coverage enforcement:

```bash
XDEBUG_MODE=coverage ./vendor/bin/phpunit --coverage-text --coverage-min=80
```

**GATE**: All tests pass. Coverage threshold met if configured. No anti-patterns from `references/patterns.md` introduced.
