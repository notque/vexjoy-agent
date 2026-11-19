---
description: "General PHP development: features, debugging, code quality, security. PSR-12, modern PHP 8.2+, Laravel/Symfony/plain PHP, gates and testing conventions."
type: reference
---

# General PHP Development

Rules for idiomatic, production-ready PHP following PSR-12, modern PHP 8.2+
patterns, and framework best practices. Use for writing and debugging PHP
features. For running or configuring PHP quality or test tooling in isolation,
the `php/` references and the PHP section of `SKILL.md` are enough.

Not for: Go SAP Converged Cloud (sapcc) patterns (load `go/sapcc-conventions.md`);
Python pip/packaging (load `python-general.md`).

## Expertise areas

- **Modern PHP 8.2+:** typed properties, readonly properties and classes, enums,
  fibers, first-class callable syntax, intersection types, `never` return type,
  named arguments, match expressions.
- **PSR standards:** PSR-12 style, PSR-4 autoloading, PSR-7 HTTP messages,
  PSR-11 container, PSR-15 middleware, PSR-3 logging.
- **Frameworks:** Laravel (Eloquent, Artisan, Blade, Queues, Policies), Symfony
  (Console, Security, Messenger, Twig), plain PHP.
- **Architecture:** thin controllers, application/domain services, DTOs for
  commands and API payloads, value objects for money/identifiers/constrained
  types, constructor DI, interface segregation.
- **ORM and database:** Doctrine (entities, repositories, QueryBuilder,
  migrations), Eloquent (query builder, factories, observers), PDO prepared
  statements.
- **Static analysis:** PHPStan level 8+, Psalm strict mode, PHP-CS-Fixer,
  Laravel Pint.
- **Testing:** PHPUnit 10+, Pest 2, factory/builder fixtures, integration vs
  unit separation, coverage reporting.
- **Security:** prepared statements, mass-assignment allowlists, CSRF
  enforcement, session management, `password_hash`/`password_verify`,
  `composer audit`, secrets from environment.

## Baseline practices

- `declare(strict_types=1)` in every new application file.
- Scalar type hints and return types on all functions and methods.
- Readonly properties and classes for immutable data.
- Enums instead of class constants for constrained value sets.
- Constructor injection; never service-locator lookups in business logic.
- Depend on interfaces, not concrete implementations or framework globals.
- `match` instead of `switch` where possible.
- Named arguments for clarity in constructor and factory calls.

## Review priorities

1. Correctness and edge cases
2. Security (SQL injection, mass assignment, CSRF bypass, exposed secrets)
3. Architecture (thin controllers, DI, service layer)
4. PSR-12 style and strict types
5. Type safety (scalar hints, return types, nullable handling)
6. Resource and error safety (exceptions vs return codes, transactions)
7. Test coverage and fixture quality (factories over hand-written arrays)
8. Performance (N+1 queries, missing eager loading, unnecessary hydration)

## Where the rules live

- [php-behaviors.md](php-general/php-behaviors.md): post-edit checks (format,
  analyse, debug-output, raw-SQL, and CSRF/session greps), PHP version
  assumptions and feature gating, framework variants, static-analysis tier,
  always-apply rules (read before edit, tests and analysis before completion,
  feature branch only, strict types, prepared statements, constructor
  injection, version-aware code), defaults, off-unless-requested behaviors,
  related skills, and the Implementation Schema output format.
- [php-conventions.md](php-general/php-conventions.md): hard-gate table with
  fixes, per-repo detection commands, SQL/session/dependency rules, and testing
  conventions.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| pint, phpstan, psalm, composer.json php version, strict_types, feature branch, debug output, var_dump, post-edit checks, Implementation Schema | [php-behaviors.md](php-general/php-behaviors.md) | Post-edit checks, always-apply/default/optional behaviors, tooling tier, framework variants, output schema |
| prepared statements, PDO, $fillable, $guarded, mass assignment, session_regenerate_id, csrf except, mysql_, preg_replace /e, extract, unserialize, composer audit, PHPUnit vs Pest, factories, coverage | [php-conventions.md](php-general/php-conventions.md) | Hard-gate table with fixes, per-repo detection commands, SQL/session/dependency rules, testing conventions |
| Union/intersection types, enums, readonly, match | [modern-php-features.md](php/modern-php-features.md) | Modern PHP feature reference |
| PHPUnit, data providers, mocks, stubs | [testing-patterns.md](php/testing-patterns.md) | PHP testing deep reference |

## Related skills

- `workflow` for multi-phase tasks, feature builds, and planning.
- `testing` for TDD, E2E, and verification.
- `review` for code review.
