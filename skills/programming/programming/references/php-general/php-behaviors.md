# PHP Behaviors, Tooling, and Output Format

## After Every `.php` Edit

Run these on each edited `.php` file:

1. **Format:** `./vendor/bin/pint <file>` or `php-cs-fixer fix <file>`.
2. **Analyse:** `./vendor/bin/phpstan analyse <file>` or `./vendor/bin/psalm --show-info=true`.
3. **Debug output:** `grep -nE 'var_dump\s*\(|dd\s*\(|dump\s*\(|die\s*\(' <file>`. Remove every `var_dump`/`dd`/`dump`/`die()` hit before committing.
4. **Raw SQL interpolation:** `grep -nE '(query|exec|prepare)\s*\(\s*["\x27]\s*(SELECT|INSERT|UPDATE|DELETE).*\$' <file>`. Any hit is a security warning: use PDO prepared statements, Doctrine QueryBuilder, or the Eloquent query builder.
5. **CSRF/session bypass:** `grep -nE 'VerifyCsrfToken|withoutMiddleware.*csrf|csrf.*except|session_regenerate_id.*false' <file>`. Confirm each CSRF exclusion and `session_regenerate_id(true)` change is intentional and documented.

## Version, Framework, and Tooling Assumptions

- Default target: **PHP 8.2+**. Check `composer.json` `require.php` before using any version-specific feature; use only features available in the project's target version.

| Framework | Key Idioms |
|-----------|-----------|
| Laravel | Eloquent, form requests for validation, policies for authorization, Queues for deferred work, Artisan commands for CLI |
| Symfony | Dependency injection container, EventDispatcher, Security component, Messenger for async, Twig templates |
| Plain PHP | PSR-11 containers (PHP-DI, Pimple), PSR-7/15 middleware stacks |

| Tool | Preferred Configuration |
|------|------------------------|
| PHPStan | Level 8+ (`phpstan.neon`), Larastan for Laravel projects |
| Psalm | Strict mode (`psalm.xml`), errorLevel 1 |
| PHP-CS-Fixer | PSR-12 rule set, or Laravel Pint for Laravel projects |

## Hardcoded Behaviors (Always Apply)

- **STOP. Read the file before editing.** Editing requires a prior read this session; about to Edit/Write an unread file → STOP and read it first.
- **STOP. Run tests/analysis before reporting completion.** Execute `./vendor/bin/phpunit` (or `./vendor/bin/pest`) and `./vendor/bin/phpstan analyse` and show their actual output rather than a "tests pass" summary.
- **Create a feature branch for all code changes.** On main → branch first, then commit.
- **Verify dependencies exist before importing them.** Check `composer.json` for the package before adding a `use` statement.
- **CLAUDE.md compliance.** Read and follow repository CLAUDE.md files before any implementation; project instructions override these defaults.
- **Over-engineering prevention.** Only changes directly requested or clearly necessary; reuse existing abstractions over creating new ones.
- **`declare(strict_types=1)` on new files.** Every new PHP application file opens with `<?php` + `declare(strict_types=1);`. Non-negotiable.
- **Format after every edit.** `./vendor/bin/pint` (Laravel) or `php-cs-fixer fix` before committing.
- **Prepared statements only.** PDO prepared statements, Doctrine QueryBuilder, or Eloquent query builder for all SQL.
- **Constructor injection.** Dependencies enter through constructors; service-locator lookups (`app()->make()`, `container->get()`) stay out of business services.

## Default Behaviors (ON unless disabled)

- **Communication style**: fact-based progress ("Fixed 3 issues", zero self-congratulation); concise summaries; show commands and outputs rather than describing them.
- **Temporary file cleanup** at task completion.
- **Run tests before completion**: `./vendor/bin/phpunit --colors=always` or `./vendor/bin/pest`, full output.
- **Run static analysis** after edits, show any issues.
- **Add docblocks** on all public methods — `@param`, `@return`, `@throws` where applicable.
- **Check for N+1 queries**: review eager loading (`with()`, `load()`) when implementing Eloquent relationships.

## Optional Behaviors (OFF unless enabled)

Aggressive refactoring; adding Composer dependencies; performance optimization before profiling confirms the bottleneck; async/fiber patterns (explicit request only).

## Related Skills

| Skill | When to Use |
|-------|---------------|
| `debugging` | Multi-hypothesis debugging when root cause is unknown |
| `testing` | Final verification gate before marking implementation complete |
| `review` | Structured multi-pass code review for PRs |

> **Roadmap**: Planned companion skills `php-testing` (force-routed on PHPUnit/Pest) and `php-error-handling` (exception hierarchy patterns) will mirror the Go `programming`/`go-testing` pair. These will be force-routed once created.

**Rule**: If a companion skill exists for what you're about to do manually, use the skill instead.

## Scope and Output Format

This reference provides patterns, commands, and code; running them, live connectivity, infrastructure, and profiling results sit outside its scope. Focus is modern PHP 8.2+.

```markdown
## Summary
[1-2 sentence overview of what was implemented]

## Implementation
[Description of approach and key decisions]

## Files Changed
| File | Change | Lines |
|------|--------|-------|
| `path/File.php:42` | [description] | +N/-M |

## Testing
- [x] Tests pass: `./vendor/bin/phpunit` output
- [x] Static analysis: `./vendor/bin/phpstan analyse` output
- [x] Format: `./vendor/bin/pint` output

## Next Steps
- [ ] [Follow-up if any]
```
