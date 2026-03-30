# Branch Naming Examples

Real-world examples of branch name generation from this agents repository.

## Good Examples from This Repository

### Feature Branches

```bash
# Commit: feat: add distinctive frontend design skill
Branch: feature/add-distinctive-frontend-design-skill

# Commit: feat: improve routing clarity and integrate UI design
Branch: feature/routing-clarity-and-ui-design-integration
```

### Fix Branches

```bash
# Commit: fix: research coordinator subagent delegation
Branch: fix/research-coordinator-subagent-delegation

# Commit: fix: sanitization rules and error handling
Branch: fix/sanitization-rules-and-error-handling
```

### Documentation Branches

```bash
# Commit: docs: update agents skills routing
Branch: docs/update-agents-skills-routing

# Commit: docs: comprehensive documentation update
Branch: docs/comprehensive-documentation-update
```

## Generation Examples

### Example 1: From Conventional Commit Message

**Input**: `feat: add user authentication with OAuth2`

**Process**:
1. Parse: type=`feat`, subject=`add user authentication with OAuth2`
2. Map type: `feat` → `feature/`
3. Sanitize: `add-user-authentication-with-oauth2`
4. Generate: `feature/add-user-authentication-with-oauth2`

**Output**: `feature/add-user-authentication-with-oauth2` (46 chars) ✓

### Example 2: From Plain Description (Type Inference)

**Input**: `fix login timeout after 30 seconds`

**Process**:
1. Infer type: keyword "fix" → `fix`
2. Map type: `fix` → `fix/`
3. Sanitize: `fix-login-timeout-after-30-seconds`
4. Generate: `fix/fix-login-timeout-after-30-seconds`
5. Deduplicate: Remove repeated "fix" → `fix/login-timeout-after-30-seconds`

**Output**: `fix/login-timeout-after-30-seconds` (35 chars) ✓

### Example 3: Truncation Required

**Input**: `feat: add comprehensive user authentication system with OAuth2 JWT and session management`

**Process**:
1. Parse: type=`feat`, subject=`add comprehensive user authentication system with OAuth2 JWT and session management`
2. Map type: `feat` → `feature/`
3. Sanitize: `add-comprehensive-user-authentication-system-with-oauth2-jwt-and-session-management` (85 chars)
4. Truncate:
   - Remove fillers: `add-comprehensive-user-authentication-system-oauth2-jwt-session-management`
   - Apply abbreviations: `add-comprehensive-user-auth-system-oauth2-jwt-session-management`
   - Truncate at word boundary: `add-comprehensive-user-auth-system-oauth2`
5. Generate: `feature/add-comprehensive-user-auth-system-oauth2`

**Output**: `feature/add-user-auth-oauth2-jwt` (32 chars, intelligently shortened) ✓

### Example 4: With Scope

**Input**: `feat(api): add user authentication endpoint`

**Process**:
1. Parse: type=`feat`, scope=`api`, subject=`add user authentication endpoint`
2. Map type: `feat` → `feature/`
3. Sanitize: `add-user-authentication-endpoint`
4. Generate: `feature/add-user-authentication-endpoint`

**Output**: `feature/add-user-authentication-endpoint` (43 chars) ✓

*Note*: Scope is extracted but not included in branch name (convention varies by repo).

### Example 5: Special Characters Removed

**Input**: `feat: add "super cool" feature!!!`

**Process**:
1. Parse: type=`feat`, subject=`add "super cool" feature!!!`
2. Map type: `feat` → `feature/`
3. Sanitize: `add-super-cool-feature` (quotes and exclamations removed)
4. Generate: `feature/add-super-cool-feature`

**Output**: `feature/add-super-cool-feature` (32 chars) ✓

### Example 6: Underscores to Hyphens

**Input**: `fix: login_timeout_error`

**Process**:
1. Parse: type=`fix`, subject=`login_timeout_error`
2. Map type: `fix` → `fix/`
3. Sanitize: `login-timeout-error` (underscores → hyphens)
4. Generate: `fix/login-timeout-error`

**Output**: `fix/login-timeout-error` (23 chars) ✓

## Bad Examples (with Corrections)

### ❌ Example 1: Missing Prefix

**Input**: `add-user-authentication`

**Issues**:
- No prefix (missing `feature/`)

**Correction**: `feature/add-user-authentication`

### ❌ Example 2: Uppercase Letters

**Input**: `feature/AddUserAuth`

**Issues**:
- Uppercase letters: `A`, `U`, `A`

**Correction**: `feature/add-user-auth`

### ❌ Example 3: Underscores

**Input**: `feature/add_user_auth`

**Issues**:
- Underscores instead of hyphens

**Correction**: `feature/add-user-auth`

### ❌ Example 4: Spaces

**Input**: `feature/add user auth`

**Issues**:
- Spaces instead of hyphens

**Correction**: `feature/add-user-auth`

### ❌ Example 5: Invalid Prefix

**Input**: `bugfix/login-error`

**Issues**:
- Invalid prefix `bugfix/` (should be `fix/`)

**Correction**: `fix/login-error`

### ❌ Example 6: Too Long

**Input**: `feature/add-comprehensive-user-authentication-system-with-oauth2-and-jwt-support` (79 chars)

**Issues**:
- Exceeds 50-character limit

**Correction**: `feature/add-user-auth-oauth2-jwt` (32 chars)

### ❌ Example 7: Special Characters

**Input**: `feature/add-user@auth`

**Issues**:
- Special character `@` not allowed

**Correction**: `feature/add-user-auth`

### ❌ Example 8: Leading/Trailing Hyphens

**Input**: `feature/-add-user-auth-`

**Issues**:
- Leading hyphen after prefix
- Trailing hyphen

**Correction**: `feature/add-user-auth`

## Duplicate Handling Examples

### Example 1: Duplicate Exists Locally

**Generated**: `feature/add-user-auth`

**Check**: Branch exists locally

**Alternatives**:
1. `feature/add-user-auth-v2`
2. `feature/add-user-auth-alt`
3. `feature/add-user-auth-20251206`

**User Choice**: Select or provide custom suffix

### Example 2: Duplicate Exists Remotely

**Generated**: `fix/login-timeout`

**Check**: Branch exists on remote `origin`

**Alternatives**:
1. `fix/login-timeout-v2`
2. `fix/login-timeout-improved`
3. `fix/login-timeout-20251206`

**Suggestion**: Add specificity - `fix/login-timeout-30s`

## Integration with /pr-workflow

### Example: Auto-Generate Branch from Commit

```bash
# User on main branch
$ /pr-workflow

# System prompts for commit message
Commit message: feat: add branch naming skill

# Skill generates branch name
Generated: feature/add-branch-naming-skill

# User confirms
Use this branch name? [Y/n] Y

# System creates branch
Created branch: feature/add-branch-naming-skill
Switched to branch: feature/add-branch-naming-skill
```

## Validation Examples

### Valid Branch Names ✓

```
feature/add-user-auth
fix/login-timeout-error
docs/update-readme
refactor/simplify-validation
test/add-integration-tests
chore/update-dependencies
ci/add-deployment-workflow
perf/optimize-database-query
style/format-code
build/update-webpack-config
```

### Invalid Branch Names ✗

```
AddUserAuth                    (missing prefix)
feature/Add_User_Auth          (uppercase, underscores)
bugfix/login-error             (invalid prefix)
feature/-add-auth              (leading hyphen)
feature/add auth               (spaces)
feature/add@auth               (special character)
FEATURE/add-auth               (uppercase prefix)
feature//add-auth              (double slash)
```

## Real-World Patterns

### Pattern 1: Issue Number in Branch

Some teams include issue numbers:

```
# With issue number
feature/123-add-user-authentication

# Generated from: "feat: add user authentication (closes #123)"
```

*Note*: This requires custom branch naming config.

### Pattern 2: Developer Initials

For shared feature branches:

```
# With developer initials
feature/add-user-auth-jsmith

# Manually added suffix to avoid conflicts
```

### Pattern 3: Environment-Specific

```
# Environment branches (custom config)
staging/deploy-v2.0.0
production/hotfix-security-patch
```

*Note*: Requires custom prefix mapping in `.branch-naming.json`.

## Testing Your Branch Names

Use the validation script to test:

```bash
# Test generation
$ python3 ~/.claude/scripts/generate.py --from-commit-message "feat: add OAuth2"
{
  "branch_name": "feature/add-oauth2",
  "prefix": "feature/",
  "subject": "add-oauth2",
  "length": 19,
  "valid": true
}

# Test validation (scripts/validate.py not yet implemented for branch-naming)
# Manual alternative: check branch name format
$ echo "feature/add-oauth2" | grep -qE '^(feature|fix|docs|chore|refactor|test|ci)/[a-z0-9-]+$' && echo "valid" || echo "invalid"
valid
```

## See Also

- [Naming Conventions](naming-conventions.md) - Full rules
- [Type Mapping](type-mapping.md) - Type → prefix mapping
- [Sanitization Rules](sanitization-rules.md) - Text processing
