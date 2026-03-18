# Branch Naming Conventions

Repository standards for Git branch names following conventional commit integration and kebab-case formatting.

## Format

```
<prefix>/<subject>
```

- **Prefix**: Conventional commit type + `/` (e.g., `feature/`, `fix/`)
- **Subject**: Kebab-case description (lowercase, hyphens, a-z0-9)

## Rules

### 1. Prefix Requirements
- **MUST** include valid prefix from: `feature/`, `fix/`, `docs/`, `style/`, `refactor/`, `perf/`, `test/`, `build/`, `ci/`, `chore/`, `revert/`
- **MUST** end with forward slash
- **MUST** be lowercase

### 2. Subject Requirements
- **MUST** be kebab-case (lowercase with hyphens)
- **MUST** contain only: `a-z`, `0-9`, `-`
- **MUST NOT** contain: uppercase, underscores, spaces, special chars
- **MUST NOT** have leading/trailing hyphens
- **MUST NOT** have multiple consecutive hyphens

### 3. Length Limits
- **Total branch name**: 50 characters maximum
- **Prefix**: Typically 6-10 characters
- **Subject**: ~40-44 characters available

## Valid Examples

```
feature/add-user-authentication          (31 chars) ✓
fix/resolve-login-timeout-error          (31 chars) ✓
docs/update-api-reference-guide          (31 chars) ✓
refactor/simplify-validation-logic       (34 chars) ✓
test/add-integration-test-suite          (31 chars) ✓
chore/update-dependencies                (25 chars) ✓
ci/add-deployment-workflow               (26 chars) ✓
```

## Invalid Examples

```
AddUserAuth                               ✗ (missing prefix)
feature/Add_User_Auth                     ✗ (uppercase, underscores)
feature/add user auth                     ✗ (spaces)
bugfix/login-error                        ✗ (invalid prefix "bugfix/")
feature/-add-auth                         ✗ (leading hyphen)
feature/add-auth-                         ✗ (trailing hyphen)
feature/add---auth                        ✗ (multiple hyphens)
feature/add@auth                          ✗ (special character)
```

## Character Whitelist

**Allowed**:
- Lowercase letters: `a-z`
- Numbers: `0-9`
- Hyphens: `-`
- Forward slash: `/` (only in prefix)

**Banned**:
- Uppercase: `A-Z`
- Underscores: `_`
- Spaces: ` `
- Special chars: `@#$%^&*()[]{}.,;:'"`

## Repository Config

Override defaults in `.branch-naming.json`:

```json
{
  "allowed_prefixes": ["feature/", "fix/", "hotfix/"],
  "max_length": 50,
  "case": "kebab"
}
```

## Integration with Conventional Commits

Branch names align with commit message types:

| Commit Type | Branch Prefix | Example Commit → Branch |
|-------------|---------------|-------------------------|
| `feat:` | `feature/` | `feat: add auth` → `feature/add-auth` |
| `fix:` | `fix/` | `fix: login bug` → `fix/login-bug` |
| `docs:` | `docs/` | `docs: update guide` → `docs/update-guide` |

## Best Practices

1. **Be Descriptive**: `feature/add-oauth2-login` > `feature/auth`
2. **Be Concise**: Keep under 50 chars, use abbreviations if needed
3. **Be Consistent**: Match branch type to commit type
4. **Be Specific**: Include context - `fix/login-timeout-30s` > `fix/timeout`
5. **Check Duplicates**: Ensure branch name doesn't exist before creating

## Common Patterns

### Feature Branches
```
feature/add-<functionality>
feature/implement-<feature>
feature/<feature-name>
```

### Bug Fixes
```
fix/<bug-description>
fix/resolve-<issue>
fix/<component>-<problem>
```

### Documentation
```
docs/update-<document>
docs/add-<guide>
docs/<section>-<change>
```

### Refactoring
```
refactor/<component>
refactor/simplify-<logic>
refactor/extract-<module>
```
