# File Staging Rules

Smart staging rules based on file types and change patterns.

## Overview

The git-commit-flow skill uses intelligent staging rules to group files logically and suggest appropriate commit boundaries. This ensures commits are atomic, reviewable, and semantically meaningful.

## File Type Categories

### 1. Documentation Files

**Patterns**: `*.md`, `*.txt`, `*.rst`, `docs/*`, `*.adoc`

**Staging Strategy**:
- Group all documentation changes together
- Separate commit from code changes
- Prefix: `docs:`

**Rationale**: Documentation changes rarely break functionality and can be reviewed independently.

**Example**:
```bash
# Files changed:
README.md
docs/installation.md
docs/api-guide.md
src/main.py

# Staging groups:
Group 1 (docs): README.md, docs/installation.md, docs/api-guide.md
  → Commit: "docs: update installation and API guide"

Group 2 (code): src/main.py
  → Commit: "feat: add new API endpoint"
```

### 2. Source Code Files

**Patterns**: `*.py`, `*.go`, `*.js`, `*.ts`, `*.jsx`, `*.tsx`, `*.java`, `*.c`, `*.cpp`, `*.rs`

**Staging Strategy**:
- Group by directory or logical feature
- Keep related files together
- Prefix: `feat:`, `fix:`, or `refactor:`

**Rationale**: Code changes should be grouped by feature or fix to maintain atomicity.

**Example**:
```bash
# Files changed:
agents/golang-engineer.md
agents/python-engineer.md
skills/linting/SKILL.md

# Staging groups:
Group 1: agents/golang-engineer.md, agents/python-engineer.md
  → Commit: "feat: add golang and python engineer agents"

Group 2: skills/linting/SKILL.md
  → Commit: "feat: add linting skill"
```

### 3. Configuration Files

**Patterns**: `*.yaml`, `*.yml`, `*.json`, `*.toml`, `*.ini`, `*.conf`, `Makefile`, `*.cfg`

**Staging Strategy**:
- **Separate commit** from code changes
- Group related configs together
- Prefix: `chore:` or `build:`

**Rationale**: Config changes can have broad impact and should be isolated for easier rollback.

**Example**:
```bash
# Files changed:
package.json
.eslintrc.json
src/app.js

# Staging groups:
Group 1: package.json, .eslintrc.json
  → Commit: "chore: update dependencies and linter config"

Group 2: src/app.js
  → Commit: "feat: add new feature"
```

**Exception**: Configs tightly coupled to code change can be in same commit:
```bash
# OK to combine:
agents/new-agent.md + agents/new-agent/config.yaml
  → Single commit: "feat: add new agent with configuration"
```

### 4. Test Files

**Patterns**: `*_test.*`, `*.test.*`, `*_spec.*`, `*.spec.*`, `tests/*`, `test/*`

**Staging Strategy**:
- **User choice**: Same commit as code OR separate
- If separate, prefix: `test:`
- If combined, no special prefix

**Rationale**: Team preference varies - some prefer tests with code, others separate.

**Option A - Combined** (preferred for TDD):
```bash
# Files changed:
src/auth.py
tests/test_auth.py

# Single commit:
git add src/auth.py tests/test_auth.py
git commit -m "feat: add user authentication with tests"
```

**Option B - Separate**:
```bash
# Files changed:
src/auth.py
tests/test_auth.py

# Two commits:
git add src/auth.py
git commit -m "feat: add user authentication"

git add tests/test_auth.py
git commit -m "test: add authentication tests"
```

**Interactive prompt**:
```
Test files detected: tests/test_auth.py

Include tests in same commit as code? [Y/n]
  Y = Single commit (feat: add authentication with tests)
  n = Separate commits (feat: add authentication + test: add tests)
```

### 5. Build/CI Files

**Patterns**: `.github/*`, `Dockerfile`, `*.dockerfile`, `.gitlab-ci.yml`, `.travis.yml`, `*.ci.*`, `.circleci/*`

**Staging Strategy**:
- **Always separate commit**
- Prefix: `ci:` or `build:`
- Never combined with code changes

**Rationale**: CI changes should be isolated for debugging pipeline issues.

**Example**:
```bash
# Files changed:
.github/workflows/test.yml
src/app.py

# Staging groups:
Group 1: .github/workflows/test.yml
  → Commit: "ci: add automated testing workflow"

Group 2: src/app.py
  → Commit: "feat: add new feature"
```

### 6. Style/Formatting Files

**Patterns**: `.prettierrc`, `.editorconfig`, `.clang-format`, `.yapfrc`, `.black.toml`

**Staging Strategy**:
- Separate commit from code changes
- Prefix: `style:`
- Note if auto-formatted files included

**Rationale**: Style changes create noisy diffs; isolate for cleaner review.

**Example**:
```bash
# Files changed:
.prettierrc
src/app.js (formatted)
src/utils.js (formatted)

# Staging:
git add .prettierrc src/app.js src/utils.js
git commit -m "style: update prettier config and reformat code"
```

### 7. Dependency Files

**Patterns**: `package.json`, `package-lock.json`, `requirements.txt`, `Pipfile`, `Pipfile.lock`, `go.mod`, `go.sum`, `Cargo.toml`, `Cargo.lock`

**Staging Strategy**:
- Group lock files with their manifests
- Separate commit from feature code
- Prefix: `build:` or `chore:`

**Rationale**: Dependency updates should be atomic and separately reviewable.

**Example**:
```bash
# Files changed:
package.json
package-lock.json
src/app.js

# Staging groups:
Group 1: package.json, package-lock.json
  → Commit: "build: update dependencies to latest versions"

Group 2: src/app.js
  → Commit: "feat: use new API from updated dependency"
```

### 8. Generated Files

**Patterns**: `*.generated.*`, `dist/*`, `build/*`, `*.min.js`, `*.bundle.js`

**Staging Strategy**:
- **Warning**: Should these be committed?
- Usually in .gitignore
- If needed, separate commit

**Rationale**: Generated files bloat repository and create merge conflicts.

**Prompt**:
```
⚠ WARNING: Generated files detected
  - dist/app.min.js
  - build/bundle.js

These files are usually in .gitignore. Commit anyway? [y/N]
  y = Stage and commit
  N = Skip these files, add to .gitignore
```

## Grouping Strategies

### Strategy 1: By File Type (Default)

Groups files by their type (docs, code, config, etc.):

```bash
# Files changed:
README.md
docs/guide.md
src/app.py
tests/test_app.py
.gitignore

# Groups:
Group 1 (docs): README.md, docs/guide.md
Group 2 (code+tests): src/app.py, tests/test_app.py
Group 3 (config): .gitignore
```

### Strategy 2: By Directory

Groups files by directory structure:

```bash
# Files changed:
agents/golang-engineer.md
agents/python-engineer.md
skills/linting/SKILL.md
skills/linting/scripts/lint.py

# Groups:
Group 1 (agents/): golang-engineer.md, python-engineer.md
Group 2 (skills/linting/): SKILL.md, scripts/lint.py
```

### Strategy 3: By Feature (Manual)

User manually groups related files:

```bash
# Files changed:
src/auth.py
src/middleware.py
tests/test_auth.py
docs/auth-guide.md

# Manual grouping:
"Authentication feature": all 4 files in single commit
```

## Auto-Stage Conditions

Files can be auto-staged (no confirmation required) when:

### Condition 1: Documentation-Only Changes

All changed files are documentation (*.md, *.txt):

```bash
# Auto-stage:
README.md
docs/installation.md
docs/api-guide.md

→ Automatically staged, commit message suggested:
   "docs: update installation and API guide"
```

### Condition 2: Single File Change

Only one file changed:

```bash
# Auto-stage:
src/app.py

→ Automatically staged (trivial case)
```

### Condition 3: Tightly Coupled Files

Changes are clearly related and must be committed together:

```bash
# Auto-stage:
package.json (dependency added)
package-lock.json (lockfile updated)

→ Automatically staged together
```

### Condition 4: User Flag

User explicitly requests auto-stage:

```bash
skill: git-commit-flow --auto-stage
```

## Confirmation Requirements

Confirmation is required when:

### Require Confirmation: Mixed File Types

```
STAGING PLAN
════════════════════════════════════════════════════════════════

Group 1: Documentation (2 files)
  ✓ README.md
  ✓ docs/guide.md
  Suggested: "docs: update documentation"

Group 2: Code (1 file)
  ✓ src/app.py
  Suggested: "feat: add new feature"

Total: 3 files in 2 commits

Proceed with this plan? [Y/n/m]
  Y = Yes, proceed
  n = No, cancel
  m = Modify plan (interactive)
```

### Require Confirmation: Large Change Set

More than 10 files changed:

```
⚠ Large change set: 23 files modified

Staging plan:
  Group 1 (docs): 5 files
  Group 2 (code): 12 files
  Group 3 (tests): 6 files

Review plan? [Y/n]
```

### Require Confirmation: Critical Files

Sensitive or critical files detected:

```
⚠ Critical files in staging plan:
  - .github/workflows/deploy.yml (CI/CD)
  - Dockerfile (build)

Review carefully before proceeding? [Y/n]
```

## User Confirmation Responses

### Response: Y (Yes)

Proceed with staging plan as presented.

### Response: n (No)

Cancel staging, return to manual git commands.

### Response: m (Modify)

Enter interactive mode:

```
INTERACTIVE STAGING
════════════════════════════════════════════════════════════════

1. Group all files in single commit
2. Stage only specific files (enter numbers)
3. Adjust grouping strategy
4. Cancel and use manual git commands

Your choice [1-4]:
```

**Option 1**: All files, one commit
**Option 2**: Manual file selection
```
Select files to stage (comma-separated):
  1. README.md
  2. docs/guide.md
  3. src/app.py
  4. tests/test_app.py

Enter numbers (e.g., 1,2): 3,4
```

**Option 3**: Change strategy
```
Select grouping strategy:
  1. By file type (default)
  2. By directory
  3. Manual feature grouping

Your choice [1-3]:
```

## Staging Rules Examples

### Example 1: Documentation Update

```bash
# Files changed:
README.md
docs/installation.md
docs/api-guide.md

# Automatic staging (docs only):
git add README.md docs/installation.md docs/api-guide.md

# Suggested message:
"docs: update installation and API guide"
```

### Example 2: Feature with Tests

```bash
# Files changed:
src/auth.py
tests/test_auth.py

# Interactive prompt:
Include tests in same commit? [Y/n]

# If Y:
git add src/auth.py tests/test_auth.py
# Message: "feat: add user authentication with tests"

# If n:
git add src/auth.py
# Message: "feat: add user authentication"
# (tests staged separately later)
```

### Example 3: Mixed Changes

```bash
# Files changed:
README.md (docs)
src/app.py (code)
.github/workflows/test.yml (CI)
package.json (deps)

# Staging plan:
Group 1: README.md
  → "docs: update README"

Group 2: src/app.py
  → "feat: add new feature"

Group 3: .github/workflows/test.yml
  → "ci: add testing workflow"

Group 4: package.json
  → "build: update dependencies"

# Confirmation required for 4 separate commits
```

### Example 4: Refactoring with Style

```bash
# Files changed:
.prettierrc (style config)
src/app.js (reformatted)
src/utils.js (reformatted + logic change)

# Staging plan:
Group 1: .prettierrc, src/app.js (formatting only)
  → "style: update prettier config and reformat app.js"

Group 2: src/utils.js
  → "refactor: simplify error handling in utils"

# Separates pure formatting from logic changes
```

## Advanced: Dependency Analysis

For advanced staging, analyze file dependencies:

### Tightly Coupled Files (Same Commit)

```python
# Example: Python module and its __init__.py
src/mymodule/feature.py
src/mymodule/__init__.py (imports feature)

→ Stage together (new module export)
```

### Loosely Coupled Files (Separate Commits)

```python
# Example: Independent features
src/auth.py
src/logging.py

→ Separate commits (unrelated features)
```

## Error Handling

### Error: No Files to Stage

```
No changed files detected.

Run: git status

To see current repository state.
```

### Error: Unresolved Merge Conflicts

```
✗ Cannot stage files with unresolved conflicts

Files with conflicts:
  - src/app.py

Resolve conflicts first:
  1. Edit file and resolve <<<<<<< markers
  2. git add src/app.py
  3. Re-run staging
```

### Error: File Deleted

```
File staged for deletion: old-deprecated-file.md

Include in commit? [Y/n]
  Y = Stage deletion
  n = Unstage (keep in working tree)
```

## Integration with git-commit-flow

The staging rules described above are applied manually by the skill during Phase 2 (STAGE).

> **Note**: `scripts/stage_files.py` is not yet implemented. Use `git add <files>` directly, following the grouping strategy outlined above.

## References

- [Git Best Practices](https://git-scm.com/book/en/v2/Distributed-Git-Contributing-to-a-Project)
- [Atomic Commits](https://www.freshconsulting.com/insights/blog/atomic-commits/)
- [Code Review Best Practices](https://google.github.io/eng-practices/review/)
