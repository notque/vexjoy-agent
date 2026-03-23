# PR Miner Usage Examples

## Example 1: Mine Go Repository for Error Handling Patterns

```bash
python3 ~/.claude/scripts/miner.py your-org/your-repo your-project_errors.json --limit 100
```

**What it finds:**
- Error wrapping patterns
- Error comparison methods (errors.Is vs ==)
- Error message formatting
- Logging before return patterns

**Expected output:**
```
⛏️  Mining your-org/your-repo...
  PR #234: 127 interactions found
✓ your-org/your-repo: Analyzed 100 PRs
✅ Mining complete!
   PRs analyzed: 100
   Comments found: 456
   Interactions extracted: 127
   Saved to: your-project_errors.json
```

## Example 2: Multi-Repo Team Standards

```bash
python3 ~/.claude/scripts/miner.py your-org/your-repo,your-org/repo1,your-org/repo2 team_standards.json --limit 50
```

**Use case:** Extract common patterns across the your team repos

**What it reveals:**
- Shared logging standards (your standard libraries)
- Common error handling patterns
- Test structure conventions
- Architecture patterns

## Example 3: Learning from Senior Developer

```bash
python3 ~/.claude/scripts/miner.py your-org/your-repo senior_patterns.json \
  --reviewer senior-developer \
  --limit 200
```

**Use case:** Extract all coding standards from the senior developer's reviews

**What it captures:**
- Function length preferences
- Naming conventions
- Code organization patterns
- Complexity thresholds

## Example 4: Recent Standards (Last 6 Months)

```bash
python3 ~/.claude/scripts/miner.py your-org/your-repo recent_standards.json \
  --since 2024-06-01 \
  --limit 200
```

**Use case:** Get current standards, not historical ones

**What it shows:**
- Recent pattern changes
- New conventions adopted
- Deprecated patterns
- Current team practices

## Example 5: Quick Summary for Exploration

```bash
python3 ~/.claude/scripts/miner.py your-org/your-repo your-project_quick.json \
  --limit 30 \
  --summary
```

**Output includes:**
```
Top Reviewers:
  senior-developer: 45 comments
  tech-lead: 23 comments
  senior-dev: 18 comments

Most Commented Files:
  service/user.go: 12 comments
  handler/api.go: 8 comments
  repository/db.go: 7 comments

Top Keywords:
  'should': 34 occurrences
  'use': 28 occurrences
  'instead': 22 occurrences
  'prefer': 18 occurrences
```

## Example 6: Check Authentication Before Mining

```bash
python3 ~/.claude/scripts/miner.py --check-auth
```

**Output:**
```
✓ Authenticated as: your-username
  API rate limit: 4987/5000
```

## Example Output Structure

```json
{
  "metadata": {
    "repos": ["your-org/your-repo"],
    "mined_at": "2025-11-20T14:30:00Z",
    "pr_count": 50,
    "comment_count": 234,
    "interaction_count": 87
  },
  "interactions": [
    {
      "source": "pr_review",
      "pr_number": 234,
      "pr_title": "Add error wrapping to user service",
      "author": "developer",
      "reviewer": "senior-developer",
      "file": "service/user.go",
      "line": 45,
      "comment_text": "Please use errors.Is() instead of == for error comparison. This handles wrapped errors correctly.",
      "code_before": "if err == ErrNotFound {",
      "code_after": "if errors.Is(err, ErrNotFound) {",
      "resolution": "likely_changed",
      "comment_url": "https://github.com/your-org/your-repo/pull/234#discussion_r123456",
      "created_at": "2025-10-15T10:23:45Z"
    }
  ]
}
```

## Integration with Code Archaeologist

After mining, feed to agent:

```bash
# Step 1: Mine the data
python3 skills/pr-miner/scripts/miner.py your-org/your-repo your-project_mined.json --limit 100

# Step 2: Run Code Archaeologist agent
# (Claude will read your-project_mined.json and generate tribal-rules.md)
```

The agent will:
1. Read the mined JSON
2. Identify patterns (12 instances of "use errors.Is")
3. Calculate confidence (98% - high frequency)
4. Generate rules with examples
5. Create Semgrep enforcement rules

## Tips for Effective Mining

### Start Small
```bash
# First run: 20 PRs to validate output
python3 ~/.claude/scripts/miner.py your-org/your-repo test.json --limit 20
# Review test.json before scaling up
```

### Focus on Quality
```bash
# Target specific high-value reviewer
python3 ~/.claude/scripts/miner.py your-org/your-repo quality.json \
  --reviewer senior-developer \
  --limit 100
```

### Update Regularly
```bash
# Quarterly update
python3 ~/.claude/scripts/miner.py your-org/your-repo q4_2025.json \
  --since 2025-10-01 \
  --limit 100
```

### Multi-Repo Analysis
```bash
# All observability repos
python3 ~/.claude/scripts/miner.py \
  your-org/your-repo,your-org/repo1,your-org/repo2,your-org/repo-d \
  observability_standards.json \
  --limit 50
```

## Common Patterns You'll Find

### Error Handling
- `errors.Is()` vs `==` comparison
- Error wrapping: `fmt.Errorf("while X: %w", err)`
- Logging before return
- Custom error types usage

### Code Structure
- Function length limits (100-150 lines)
- Nesting depth (max 3 levels)
- Helper extraction thresholds
- Context parameter positioning

### Testing
- Table-driven test patterns
- Test naming conventions
- Mock usage patterns
- Coverage expectations

### Architecture
- Import restrictions
- Layer violations
- Dependency direction
- Package organization

### Style
- Naming conventions
- Comment quality expectations
- Variable naming (err vs e)
- Modern Go features (slices.Contains, min/max)

## Troubleshooting

### No interactions found
**Problem:** Limit too low or repo has few comments
**Solution:** Increase --limit to 100-200

### Rate limit exceeded
**Problem:** Too many API calls
**Solution:** Wait for rate limit reset or use different token

### Empty code_before/code_after
**Problem:** Comment on non-code lines (whitespace, comments)
**Solution:** Normal - filter these out in analysis phase

### Too many interactions
**Problem:** Generic comments captured
**Solution:** Let Code Archaeologist filter by frequency (high frequency = real rules)
