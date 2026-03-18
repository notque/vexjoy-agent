---
name: branch-naming
description: |
  Generate and validate Git branch names from commit messages or descriptions.
  Use when creating branches, generating names for /pr-sync, validating existing
  branch names, or converting conventional commits to branch prefixes. Triggers:
  "branch name", "create branch", "name this branch", "validate branch". Do NOT
  use for git operations (checkout, merge, delete), branching strategies, or
  branch protection rules.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
---

# Branch Naming Skill

## Operator Context

This skill operates as an operator for Git branch naming workflows, configuring Claude's behavior for deterministic branch name generation and validation with conventional commit integration.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Deterministic Naming**: Type-to-prefix mapping, kebab-case sanitization, 50-char limit
- **Character Whitelist**: Only a-z, 0-9, hyphens in subject; forward slash only in prefix
- **Over-Engineering Prevention**: Only generate/validate names. No branch creation, deletion, or management
- **Reproduce-First Validation**: Always validate generated names before presenting to user
- **No Speculative Features**: No branch templates, cleanup tools, or management beyond naming

### Default Behaviors (ON unless disabled)
- **Interactive Confirmation**: Show generated name and ask for confirmation before use
- **Conventional Commit Inference**: Detect commit type from message and map to prefix
- **Duplicate Detection**: Check if proposed name already exists locally or remotely
- **Suggestion Alternatives**: If name exists, suggest alternatives (-v2, -alt, timestamp)
- **Sanitization Pipeline**: Lowercase, hyphenate, strip special chars, collapse hyphens
- **Intelligent Truncation**: Remove filler words and abbreviate to fit length limit

### Optional Behaviors (OFF unless enabled)
- **Auto-Accept**: Skip confirmation for automated/scripted workflows
- **Custom Prefix Rules**: Override default type-to-prefix mapping via .branch-naming.json
- **Allow Long Names**: Bypass 50-char limit for exceptional cases

## What This Skill CAN Do
- Parse conventional commit messages to extract type and subject
- Map commit types to branch prefixes (feat -> feature/, fix -> fix/, etc.)
- Sanitize text to kebab-case following the 7-step pipeline
- Validate branch name format (prefix, length, characters, duplicates)
- Generate alternative names when duplicates exist

## What This Skill CANNOT Do
- Create, delete, or manage Git branches (use git directly)
- Enforce GitHub branch protection rules (GitHub settings)
- Resolve naming conflicts between competing conventions (human judgment)
- Auto-rename existing branches (risks breaking active work)

---

## Instructions

### Phase 1: ANALYZE

**Goal**: Parse input and determine commit type and subject.

**Step 1: Parse input**

If conventional commit message provided (e.g., `feat: add user auth`):
- Extract type, optional scope, and subject
- Pattern: `<type>[optional scope]: <description>`

If plain description provided (e.g., `add user authentication`):
- Infer type from keywords (see `references/type-mapping.md` for full mapping)
- Keywords: add/implement/create -> feat, fix/resolve/correct -> fix, document/readme -> docs, refactor/restructure -> refactor, test/spec -> test, remove/delete/update -> chore
- Default if no keywords match: feat

**Step 2: Validate input content**
- Strip banned characters (emojis, special chars)
- If input is too vague to determine type, prompt user for specifics

**Gate**: Commit type identified and subject extracted. If FAIL, prompt user for clarification.

### Phase 2: GENERATE

**Goal**: Produce a valid branch name from analyzed input.

**Step 1: Map type to prefix**

Standard mapping (see `references/type-mapping.md` for details):

| Type | Prefix |
|------|--------|
| feat | feature/ |
| fix | fix/ |
| docs | docs/ |
| refactor | refactor/ |
| test | test/ |
| chore | chore/ |
| style | style/ |
| perf | perf/ |
| build | build/ |
| ci | ci/ |
| revert | revert/ |

Check for `.branch-naming.json` in repository root for custom overrides.

**Step 2: Sanitize subject to kebab-case**

Apply the 7-step sanitization pipeline (see `references/sanitization-rules.md`):
1. Lowercase
2. Strip leading/trailing whitespace
3. Replace spaces with hyphens
4. Replace underscores with hyphens
5. Remove special characters (keep only a-z, 0-9, hyphens)
6. Collapse multiple consecutive hyphens
7. Remove leading/trailing hyphens

**Step 3: Apply length limits**

Total branch name (prefix + subject) must be 50 characters or fewer. If exceeded:
1. Remove filler words (the, a, with, and, for, etc.)
2. Apply common abbreviations (authentication -> auth, configuration -> config)
3. Truncate at word boundaries (never cut mid-word)

**Step 4: Combine prefix + sanitized subject**

Example: `feat: add user authentication` -> `feature/add-user-authentication`

**Gate**: Valid branch name generated (correct prefix, kebab-case, within length limit, allowed characters only).

### Phase 3: VALIDATE

**Goal**: Confirm generated name meets all requirements.

**Step 1: Format validation**
- Has valid prefix from allowed list
- Subject is kebab-case
- Only allowed characters (a-z, 0-9, hyphens, one forward slash)
- No leading/trailing hyphens in subject
- No consecutive hyphens

**Step 2: Length check**
- Total length is 50 characters or fewer

**Step 3: Duplicate detection**

```bash
# Check local
git branch --list "<branch-name>"

# Check remote
git ls-remote --heads origin "<branch-name>"
```

If duplicate found, generate alternatives:
1. Append `-v2`, `-v3` for versioning
2. Append date `-YYYYMMDD` for uniqueness
3. Ask user for custom suffix

**Step 4: Repository convention compliance**

Check `.branch-naming.json` if present for custom prefix restrictions.

**Gate**: All validation checks pass. If FAIL, regenerate with adjustments or present alternatives.

### Phase 4: CONFIRM

**Goal**: Present validated name and get user approval.

**Step 1: Display result**

```
Generated Branch Name: feature/add-user-authentication
  Type: feat (feature)
  Length: 31 characters
  Format: Valid
  Duplicates: None found

Use this branch name? [Y/n]
```

**Step 2: Handle response**
- **Yes**: Output final name with git checkout command
- **No**: Return to Phase 1 with new input
- **Customize**: User provides custom name, run through Phase 3 validation

**Gate**: User approved name. Workflow complete.

---

## Examples

### Example 1: From Conventional Commit
Input: `feat: add user authentication`
Actions:
1. Parse: type=feat, subject="add user authentication" (ANALYZE)
2. Map feat -> feature/, sanitize -> "add-user-authentication" (GENERATE)
3. Validate format, length (31 chars), no duplicates (VALIDATE)
4. Present and confirm (CONFIRM)
Result: `feature/add-user-authentication`

### Example 2: From Plain Description with Truncation
Input: `add comprehensive user authentication system with OAuth2 and JWT`
Actions:
1. Infer type=feat from "add" keyword (ANALYZE)
2. Sanitize, remove fillers, abbreviate auth -> 32 chars (GENERATE)
3. Validate all checks pass (VALIDATE)
4. Present and confirm (CONFIRM)
Result: `feature/add-user-auth-oauth2-jwt`

### Example 3: Validation of Existing Branch
Input: `feature/User_Authentication`
Actions:
1. Detect uppercase letters and underscores (VALIDATE)
2. Report issues with corrections
Result: Suggest `feature/user-authentication`

---

## Error Handling

### Error: "Cannot Infer Commit Type"
Cause: Description too vague (e.g., "stuff", "things") to determine type
Solution:
1. Prompt user to start with action verb (add, fix, update, remove)
2. Suggest using `--type` flag to specify explicitly
3. Provide examples of descriptive input

### Error: "Name Exceeds Length Limit"
Cause: Description too long even after truncation
Solution:
1. Remove filler words and apply abbreviations
2. Suggest shorter focused description
3. Move detail to commit message body instead of branch name

### Error: "Duplicate Branch Detected"
Cause: Branch name already exists locally or remotely
Solution:
1. Suggest alternatives with -v2 or date suffix
2. Offer to check out existing branch instead
3. Prompt for custom differentiating suffix

---

## Anti-Patterns

### Anti-Pattern 1: Underscores Instead of Hyphens
**What it looks like**: `feature/add_user_auth`
**Why wrong**: Violates kebab-case convention, inconsistent with conventional commits
**Do instead**: Use hyphens: `feature/add-user-auth`

### Anti-Pattern 2: Vague Branch Names
**What it looks like**: `feature/updates`, `fix/stuff`, `feature/branch-1`
**Why wrong**: Impossible to understand purpose, hard to track, likely duplicates
**Do instead**: Be specific: `feature/add-oauth2-login`, `fix/login-timeout-30s`

### Anti-Pattern 3: Missing Branch Prefix
**What it looks like**: `add-user-authentication` (no prefix)
**Why wrong**: No type indication, breaks CI/CD automation, inconsistent filtering
**Do instead**: Always include conventional commit prefix: `feature/add-user-authentication`

### Anti-Pattern 4: Overly Long Names
**What it looks like**: `feature/add-comprehensive-user-authentication-system-with-oauth2-jwt-and-session-management` (95 chars)
**Why wrong**: Exceeds 50-char limit, hard to read, indicates scope too large
**Do instead**: Abbreviate and move details to commit body: `feature/add-user-auth-oauth2-jwt`

### Anti-Pattern 5: Mixing Naming Conventions
**What it looks like**: Repository has `feat/`, `feature/`, `bugfix/`, `fix/`, `Feature/` branches
**Why wrong**: No standard, hard to filter, CI/CD rules only match some patterns
**Do instead**: Enforce one convention via `.branch-naming.json` and this skill

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Any name is fine" | Inconsistent names break automation and readability | Use skill to generate compliant name |
| "I'll fix the name later" | Branch renames disrupt active work and PRs | Name correctly from the start |
| "50 chars is too restrictive" | Long names indicate scope creep | Abbreviate; move detail to commit body |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/type-mapping.md`: Conventional commit type to branch prefix mapping
- `${CLAUDE_SKILL_DIR}/references/naming-conventions.md`: Branch format rules, character whitelist, examples
- `${CLAUDE_SKILL_DIR}/references/sanitization-rules.md`: 7-step text sanitization pipeline and truncation strategies
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Good/bad examples with corrections and integration patterns
