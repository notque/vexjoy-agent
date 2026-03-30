# Commit Workflow Examples

Integration examples and advanced patterns for the git-commit-flow skill.

## Integration with PR Commands

### Using in /pr-workflow (sync)

When local changes exist during PR sync:

```bash
skill: git-commit-flow
```

The skill validates, stages, commits, and verifies. After completion:

```bash
git pull --rebase origin $(git branch --show-current)
git push origin $(git branch --show-current)
```

### Using in /pr-workflow (fix)

After applying PR review feedback:

```bash
skill: git-commit-flow --message "fix: apply PR review feedback"
```

### Direct User Invocation

User request: "Commit my changes with message 'Add authentication flow'"

```bash
skill: git-commit-flow --message "feat: add authentication flow"
```

Runs all 4 phases with the provided message.

## Dry Run Mode

Shows what would be committed without modifying repository state:

```bash
skill: git-commit-flow --dry-run
```

Output includes: validation results, staging plan, generated message, and compliance checks.

## Bulk Commits from Staging Groups

For large changesets needing multiple logical commits, the skill creates separate staging groups by file type and presents them for user approval. Each group becomes its own commit with an appropriate conventional commit prefix.

Example flow for mixed changes:

```
Group 1 (docs): README.md, docs/guide.md
  -> "docs: update documentation"

Group 2 (code): src/auth.py, src/middleware.py
  -> "feat: add authentication middleware"

Group 3 (ci): .github/workflows/test.yml
  -> "ci: add automated testing workflow"
```

## Pre-Commit Hook Integration

> **Note**: `scripts/validate_state.py` and `scripts/validate_message.py` are not yet implemented. The examples below show the intended integration patterns. Use manual checks (grep for sensitive files, validate conventional commit format) until the scripts are available.

Install git-commit-flow validation as a pre-commit hook:

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Check for sensitive files in staged changes
if git diff --cached --name-only | grep -iE '\.(env|pem|key)$|credentials|secret|\.npmrc|\.pypirc'; then
  echo "Commit blocked: sensitive files detected in staging area"
  echo "Fix issues and try again, or bypass with: git commit --no-verify"
  exit 1
fi
EOF
chmod +x .git/hooks/pre-commit
```

## CI/CD Validation

Validate commit messages in GitHub Actions:

```yaml
name: Validate Commits
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      - name: Validate commit messages
        run: |
          for commit in $(git log --format=%H origin/main..HEAD); do
            message=$(git log -1 --format=%s $commit)
            # Check conventional commit format
            echo "$message" | grep -qE '^(feat|fix|docs|style|refactor|test|chore|ci|build|perf)(\(.+\))?: .+' \
              || { echo "FAIL: $message"; exit 1; }
          done
```

## Custom Validation Rules

For repositories requiring additional message constraints (e.g., JIRA tickets):

```bash
# .git/hooks/commit-msg
#!/bin/bash
message=$(cat "$1")
if ! echo "$message" | grep -qE '\[PROJ-[0-9]+\]'; then
  echo "ERROR: Commit message must include JIRA ticket [PROJ-XXX]"
  exit 1
fi
# Check for banned patterns
if echo "$message" | grep -iqE 'Generated with Claude Code|Co-Authored-By: Claude'; then
  echo "ERROR: Commit message contains banned pattern"
  exit 1
fi
```

## Validation Script Usage

> **Note**: The scripts below are not yet implemented. Use the manual alternatives shown in the SKILL.md.

### validate_state.py (not yet implemented)

Intended interface:
```bash
# Check all validations
# python3 ~/.claude/scripts/validate_state.py --check all

# Check specific validation
# python3 ~/.claude/scripts/validate_state.py --check sensitive-files

# Check only staged files
# python3 ~/.claude/scripts/validate_state.py --check sensitive-files --staged-only
```

Exit codes: 0 = clean, 1 = issues found, 2 = critical error.

### validate_message.py (not yet implemented)

Intended interface:
```bash
# Validate message from string
# python3 ~/.claude/scripts/validate_message.py --message "feat: add feature"

# Validate message from file
# python3 ~/.claude/scripts/validate_message.py --file commit-msg.txt

# Skip conventional commit check
# python3 ~/.claude/scripts/validate_message.py --message "message" --no-conventional
```

Exit codes: 0 = valid, 1 = warnings, 2 = errors.
