---
name: branch-naming
description: "Generate and validate Git branch names."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - "generate branch name"
    - "validate branch name"
  category: git-workflow
---

# Branch Naming Skill

Generate and validate Git branch names from conventional commit messages or plain descriptions. This skill only handles naming -- it does not create, delete, or manage branches.

## Instructions

### Step 1: Parse Input

Determine the commit type and subject from whatever the user provides.

**If a conventional commit message** (e.g., `feat: add user auth`):
- Extract type, optional scope, and subject
- Pattern: `<type>[optional scope]: <description>`

**If a plain description** (e.g., `add user authentication`):
- Infer type from keywords (see `references/type-mapping.md` for full mapping)
- Keywords: add/implement/create -> feat, fix/resolve/correct -> fix, document/readme -> docs, refactor/restructure -> refactor, test/spec -> test, remove/delete/update -> chore
- Default to `feat` when no keywords match

Strip banned characters (emojis, special chars) from the input. If the input is too vague to determine a type (e.g., "stuff", "things"), prompt the user for a more descriptive input starting with an action verb.

**Gate**: Commit type identified and subject extracted. If not, prompt for clarification before continuing.

### Step 2: Generate Branch Name

**Map type to prefix** using the standard table (or `.branch-naming.json` overrides if present in the repo root):

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

Every branch name must have a prefix from this list -- unprefixed names like `add-user-authentication` break CI/CD automation and make filtering impossible.

**Sanitize the subject to kebab-case** using the 7-step pipeline (see `references/sanitization-rules.md`):
1. Lowercase
2. Strip leading/trailing whitespace
3. Replace spaces with hyphens
4. Replace underscores with hyphens (underscores violate kebab-case convention and create inconsistency with conventional commits)
5. Remove special characters (keep only a-z, 0-9, hyphens)
6. Collapse multiple consecutive hyphens
7. Remove leading/trailing hyphens

Only a-z, 0-9, and hyphens are allowed in the subject. The forward slash appears only once, separating prefix from subject.

**Apply the 50-character length limit** (prefix + subject combined). If exceeded:
1. Remove filler words (the, a, with, and, for, etc.)
2. Apply common abbreviations (authentication -> auth, configuration -> config)
3. Truncate at word boundaries -- never cut mid-word

Long names signal scope creep; move detail to the commit message body rather than cramming it into the branch name.

**Combine prefix + sanitized subject**:

Example: `feat: add user authentication` -> `feature/add-user-authentication`

**Gate**: Generated name has a valid prefix, uses kebab-case, stays within the length limit, and contains only allowed characters.

### Step 3: Validate

Run all checks against the generated (or user-provided) name:

**Format validation**:
- Has a valid prefix from the allowed list
- Subject is kebab-case (no uppercase, no underscores)
- Only allowed characters (a-z, 0-9, hyphens, one forward slash)
- No leading/trailing hyphens in subject
- No consecutive hyphens
- Name is specific enough to convey purpose (`feature/updates` or `fix/stuff` are too vague)

**Length check**: Total length is 50 characters or fewer.

**Duplicate detection**:

```bash
# Check local
git branch --list "<branch-name>"

# Check remote
git ls-remote --heads origin "<branch-name>"
```

If a duplicate is found, generate alternatives:
1. Append `-v2`, `-v3` for versioning
2. Append date `-YYYYMMDD` for uniqueness
3. Ask user for a custom suffix

**Repository convention compliance**: Check `.branch-naming.json` if present for custom prefix restrictions.

**Gate**: All validation checks pass. If any fail, regenerate with adjustments or present alternatives.

### Step 4: Confirm

Present the validated name and wait for user approval before proceeding:

```
Generated Branch Name: feature/add-user-authentication
  Type: feat (feature)
  Length: 31 characters
  Format: Valid
  Duplicates: None found

Use this branch name? [Y/n]
```

Handle the response:
- **Yes**: Output the final name with a `git checkout -b` command
- **No**: Return to Step 1 with new input
- **Customize**: User provides a custom name; run it through Step 3 validation

Skip confirmation only in automated/scripted workflows where the caller has explicitly opted into auto-accept.

**Gate**: User approved name. Workflow complete.

### Examples

**From a conventional commit**:
Input: `feat: add user authentication`
1. Parse: type=feat, subject="add user authentication"
2. Map feat -> feature/, sanitize -> "add-user-authentication"
3. Validate format, length (31 chars), no duplicates
4. Present and confirm
Result: `feature/add-user-authentication`

**From a plain description with truncation**:
Input: `add comprehensive user authentication system with OAuth2 and JWT`
1. Infer type=feat from "add" keyword
2. Sanitize, remove fillers, abbreviate auth -> 32 chars
3. Validate all checks pass
4. Present and confirm
Result: `feature/add-user-auth-oauth2-jwt`

**Validating an existing branch name**:
Input: `feature/User_Authentication`
1. Detect uppercase letters and underscores
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

## References

- `${CLAUDE_SKILL_DIR}/references/type-mapping.md`: Conventional commit type to branch prefix mapping
- `${CLAUDE_SKILL_DIR}/references/naming-conventions.md`: Branch format rules, character whitelist, examples
- `${CLAUDE_SKILL_DIR}/references/sanitization-rules.md`: 7-step text sanitization pipeline and truncation strategies
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Good/bad examples with corrections and integration patterns
