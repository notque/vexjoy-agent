# Conventional Commit Type → Branch Prefix Mapping

This reference defines the mapping between conventional commit types and Git branch prefixes used in branch name generation.

## Standard Mappings

| Commit Type | Branch Prefix | Description | Example |
|-------------|---------------|-------------|---------|
| `feat` | `feature/` | New features or enhancements | `feature/add-user-authentication` |
| `fix` | `fix/` | Bug fixes | `fix/login-timeout-error` |
| `docs` | `docs/` | Documentation only changes | `docs/update-api-reference` |
| `style` | `style/` | Code style/formatting (no logic change) | `style/format-imports` |
| `refactor` | `refactor/` | Code restructuring (no behavior change) | `refactor/simplify-validation` |
| `perf` | `perf/` | Performance improvements | `perf/optimize-query-speed` |
| `test` | `test/` | Adding or updating tests | `test/add-integration-tests` |
| `build` | `build/` | Build system or dependency changes | `build/update-webpack-config` |
| `ci` | `ci/` | CI/CD configuration changes | `ci/add-deployment-workflow` |
| `chore` | `chore/` | Maintenance tasks, tooling | `chore/update-dependencies` |
| `revert` | `revert/` | Reverting previous commits | `revert/undo-feature-x` |

## Type Selection Guidelines

### feat (feature/)
Use when:
- Adding new functionality
- Implementing new features
- Creating new capabilities
- Introducing new APIs or endpoints

Examples:
- `feat: add OAuth2 login` → `feature/add-oauth2-login`
- `feat: implement user dashboard` → `feature/implement-user-dashboard`
- `feat: create export functionality` → `feature/create-export-functionality`

### fix (fix/)
Use when:
- Fixing bugs
- Resolving errors
- Correcting incorrect behavior
- Patching security issues

Examples:
- `fix: resolve login timeout` → `fix/resolve-login-timeout`
- `fix: correct calculation error` → `fix/correct-calculation-error`
- `fix: patch XSS vulnerability` → `fix/patch-xss-vulnerability`

### docs (docs/)
Use when:
- Updating documentation
- Adding READMEs
- Writing guides or tutorials
- Documenting APIs

Examples:
- `docs: update installation guide` → `docs/update-installation-guide`
- `docs: add API reference` → `docs/add-api-reference`
- `docs: document authentication flow` → `docs/document-authentication-flow`

### refactor (refactor/)
Use when:
- Restructuring code without changing behavior
- Simplifying logic
- Improving code organization
- Extracting functions or modules

Examples:
- `refactor: simplify validation logic` → `refactor/simplify-validation-logic`
- `refactor: extract database utilities` → `refactor/extract-database-utilities`
- `refactor: reorganize file structure` → `refactor/reorganize-file-structure`

### test (test/)
Use when:
- Adding new tests
- Updating existing tests
- Improving test coverage
- Adding test infrastructure

Examples:
- `test: add unit tests for auth` → `test/add-unit-tests-for-auth`
- `test: improve coverage for validators` → `test/improve-coverage-for-validators`
- `test: add integration test suite` → `test/add-integration-test-suite`

### chore (chore/)
Use when:
- Updating dependencies
- Configuring tools
- Performing maintenance
- Cleaning up code

Examples:
- `chore: update npm dependencies` → `chore/update-npm-dependencies`
- `chore: configure linter` → `chore/configure-linter`
- `chore: remove deprecated code` → `chore/remove-deprecated-code`

## Repository-Specific Mappings

Some repositories may define custom type mappings in `.branch-naming.json`:

```json
{
  "type_prefix_map": {
    "feat": "feature/",
    "fix": "fix/",
    "hotfix": "hotfix/",
    "release": "release/",
    "experiment": "experiment/"
  }
}
```

### Custom Type Examples

**hotfix/** (not in conventional commits, but commonly used):
- For critical production fixes that skip normal development flow
- Example: `hotfix/critical-security-patch`

**release/** (version bumps, release preparation):
- For release branch preparation
- Example: `release/v2.0.0`

**experiment/** (experimental features):
- For proof-of-concept or experimental work
- Example: `experiment/new-rendering-engine`

## Type Inference from Description

When commit type is not explicitly provided, the skill infers type based on keywords:

| Keywords | Inferred Type |
|----------|---------------|
| add, implement, create, introduce | `feat` |
| fix, resolve, correct, repair, patch | `fix` |
| document, readme, guide, explain | `docs` |
| refactor, restructure, reorganize, simplify | `refactor` |
| test, spec, coverage | `test` |
| remove, delete, cleanup, update | `chore` |

### Inference Examples

| Description | Inferred Type | Generated Branch Name |
|-------------|---------------|----------------------|
| "add user authentication" | `feat` | `feature/add-user-authentication` |
| "fix login bug" | `fix` | `fix/login-bug` |
| "update README" | `chore` | `chore/update-readme` |
| "refactor validation" | `refactor` | `refactor/validation` |
| "test authentication flow" | `test` | `test/authentication-flow` |

**Default**: If no keywords match, defaults to `feat` (feature/).

## Validation Rules

### Valid Prefix Format
- Must end with forward slash: `feature/` ✓
- No trailing spaces: `feature/ ` ✗
- Lowercase only: `Feature/` ✗

### Prefix Consistency
- One prefix per branch: `feature/fix/bug` ✗
- Prefix must be first component: `bug/feature/fix` ✗

## Common Mistakes

### ❌ Mistake 1: Wrong Prefix for Type
**Wrong**: Using `feat/` for bug fix
```
feat: fix login bug → feat/fix-login-bug
```

**Correct**: Use `fix/` for bug fixes
```
fix: login bug → fix/login-bug
```

### ❌ Mistake 2: Using Non-Standard Prefixes
**Wrong**: Custom prefix not in allowed list
```
bugfix/login-error  (should be fix/)
enhancement/new-ui  (should be feature/)
```

**Correct**: Use standard prefixes
```
fix/login-error
feature/new-ui
```

### ❌ Mistake 3: Multiple Types in One Branch
**Wrong**: Mixing types
```
feature-and-fix/add-auth-and-fix-bug
```

**Correct**: Separate branches for separate types
```
feature/add-auth
fix/auth-bug
```

## Integration with Conventional Commits

This mapping aligns with [Conventional Commits specification](https://www.conventionalcommits.org/):

**Conventional Commit Message**:
```
feat(api): add user authentication endpoint

Implements OAuth2 authentication with JWT tokens.
```

**Generated Branch Name**:
```
feature/add-user-authentication-endpoint
```

**Workflow**:
1. Create branch: `git checkout -b feature/add-user-authentication-endpoint`
2. Commit with conventional format: `git commit -m "feat(api): add user authentication endpoint"`
3. Branch name and commit type are aligned

## Best Practices

1. **Consistency**: Use same type in branch name and commit messages
2. **Specificity**: Choose most specific type (use `fix` not `chore` for bugs)
3. **Scope**: Keep branch name focused on single type of work
4. **Documentation**: Document custom types in repository `.branch-naming.json`
5. **Review**: Validate branch names match commit types in PR reviews

## See Also

- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/) - Types relate to version bumps
- [Repository CLAUDE.md](../../CLAUDE.md) - Repository-specific conventions
