# Commit Workflow Examples

Integration examples and advanced patterns for the git-commit-flow skill.

## Integration with PR Commands

### Using in /pr-sync

When local changes exist during PR sync:

```bash
skill: git-commit-flow
```

The skill validates, stages, commits, and verifies. After completion:

```bash
git pull --rebase origin $(git branch --show-current)
git push origin $(git branch --show-current)
```

### Using in /pr-fix

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

Install git-commit-flow validation as a pre-commit hook:

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
python3 /path/to/scripts/validate_state.py --check all --staged-only
if [ $? -ne 0 ]; then
  echo "Commit blocked by git-commit-flow validation"
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
            message=$(git log -1 --format=%B $commit)
            echo "$message" | python3 scripts/validate_message.py --stdin
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
python3 scripts/validate_message.py --file "$1"
```

## Validation Script Usage

### validate_state.py

```bash
# Check all validations
python3 scripts/validate_state.py --check all

# Check specific validation
python3 scripts/validate_state.py --check sensitive-files

# Check only staged files
python3 scripts/validate_state.py --check sensitive-files --staged-only
```

Exit codes: 0 = clean, 1 = issues found, 2 = critical error.

### validate_message.py

```bash
# Validate message from string
python3 scripts/validate_message.py --message "feat: add feature"

# Validate message from file
python3 scripts/validate_message.py --file commit-msg.txt

# Skip conventional commit check
python3 scripts/validate_message.py --message "message" --no-conventional
```

Exit codes: 0 = valid, 1 = warnings, 2 = errors.
