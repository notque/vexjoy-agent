# Quality Tools Reference

> **Scope**: PHP code quality tool configuration and usage: PHP-CS-Fixer, PHPStan, Psalm, Rector. Covers CI integration commands, config files, and recommended strictness levels. Does NOT cover language features or framework patterns.
> **Version range**: PHP-CS-Fixer 3.x, PHPStan 1.x, Psalm 5.x, Rector 1.x
> **Generated**: 2026-04-16

---

## CI Commands

Run these tools in CI:

```bash
# PHP-CS-Fixer — auto-fix PSR-12 violations
./vendor/bin/php-cs-fixer fix --dry-run --diff

# PHPStan — static analysis (level 0-9, aim for 6+)
./vendor/bin/phpstan analyse src --level=6

# Psalm — alternative static analysis
./vendor/bin/psalm --show-info=true

# Rector — automated refactoring and upgrades
./vendor/bin/rector process src --dry-run
```

---

## Tool Reference

| Tool | Purpose | Config File |
|------|---------|-------------|
| PHP-CS-Fixer | Code style enforcement | `.php-cs-fixer.dist.php` |
| PHPStan | Static analysis, type checking | `phpstan.neon` |
| Psalm | Static analysis, taint analysis | `psalm.xml` |
| Rector | Automated refactoring | `rector.php` |

### PHP-CS-Fixer

Enforces PSR-12 and custom code style rules. Config file `.php-cs-fixer.dist.php` defines rulesets. Use `--dry-run --diff` in CI to detect violations without modifying files. Run `fix` locally to auto-correct.

### PHPStan

Static analysis with levels 0 through 9. Level 6 is the recommended minimum for production code: it covers method return types, property types, and dead code detection. Higher levels add strictness around mixed types and dynamic property access.

### Psalm

Alternative to PHPStan with taint analysis for security-sensitive code paths. Shows data flow from user input to dangerous sinks (SQL queries, shell commands, file operations). Use `--show-info=true` to surface non-error findings like unused variables.

### Rector

Automated refactoring engine. Upgrades PHP syntax to target version (e.g., converting `switch` to `match`, adding property promotion). Always run with `--dry-run` first in CI to preview changes.
