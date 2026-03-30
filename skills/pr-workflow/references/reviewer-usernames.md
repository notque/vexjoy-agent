# Known GitHub Reviewer Usernames

## Overview

When mining PR review patterns, you need to know the correct GitHub usernames of reviewers. This file documents how to discover and verify reviewer usernames.

## Common Reviewers

### Special Accounts
- **github-advanced-security** - Dependabot and security scanning
- **dependabot** - Automated dependency updates
- **codecov** - Code coverage bot

## Usage Patterns

### Mining Senior Reviewer Patterns
For senior reviewers, use `--all-comments` flag:
```bash
--reviewer username --all-comments
```

**Why**: Senior reviewers often use questions and explanations instead of direct imperative language:
- "Maybe use errors.Is() here?" (question form)
- "I would prefer X because Y" (suggestion with rationale)
- "Consider using Z for performance" (recommendation)

### Mining Team Standards
For broad team standards, omit `--reviewer` to capture all perspectives:
```bash
# No --reviewer flag = all reviewers
./venv/bin/python3 scripts/miner.py your-org/your-repo mined_data/output.json
```

## Verifying Reviewer Usernames

### Method 1: Mine Without Filter
```bash
./venv/bin/python3 scripts/miner.py \
  your-org/your-repo \
  mined_data/check.json \
  --limit 50 --summary
```

Check the summary output for top reviewers list.

### Method 2: GitHub API Directly
```bash
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/your-org/your-repo/pulls/comments | \
  jq -r '.[].user.login' | sort | uniq -c | sort -rn
```

## Common Username Mistakes

### Capitalization
- GitHub usernames are case-insensitive for API queries
- But display names may differ from login names
- Always verify the exact login format

## Updating This List

When you discover new reviewer usernames:
1. Add to your `.local/` overlay (not this file)
2. Include comment count from discovery
3. Note which repos they review
4. Document any special patterns (e.g., "uses questions instead of imperatives")
