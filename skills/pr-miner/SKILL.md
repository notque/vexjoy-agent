---
name: pr-miner
description: "GitHub PR review comment extraction: mine tribal knowledge, standards."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
context: fork
routing:
  triggers:
    - "extract PR comments"
    - "mine PR reviews"
  category: git-workflow
---

# PR Miner Skill

## Overview

This skill extracts raw review comment data from GitHub pull requests in three deterministic phases: AUTHENTICATE (verify token and repo access), MINE (extract raw JSON with code context), and VALIDATE (confirm output quality).

The skill operates with strict separation of concerns:
- **This skill**: Extracts raw data only. No analysis, interpretation, or pattern detection.
- **Code Archaeologist agent**: Analyzes patterns, generates rules, interprets comments.

Key principles:
- **Over-engineering prevention**: Extract only what was requested. Do not analyze, interpret, or detect patterns.
- **Deterministic extraction only**: Output raw JSON. No speculation about intent or meaning.
- **Authenticate first**: Verify GitHub token before any mining operation.
- **Rate limit respect**: Honor GitHub API rate limits with exponential backoff and monitoring.

---

## Instructions

### Phase 1: AUTHENTICATE

**Goal**: Verify GitHub access and validate target repositories before mining.

**Step 1: Verify token**

```bash
python3 ~/.claude/scripts/miner.py --check-auth
```

Confirm output shows valid authentication with `repo` scope.

Constraint: This token will be reused across sessions. Verify it every run because tokens expire and permissions change. Do not assume "it worked last time."

**Step 2: Validate target repositories**

Confirm each target repository:
- Exists and is accessible with current token
- Has merged PRs with review comments
- Uses a code review workflow (not just self-merges)

**Step 3: Check rate limits**

```bash
gh api rate_limit --jq '.resources.core | "Remaining: \(.remaining)/\(.limit), Resets: \(.reset)"'
```

Ensure sufficient API calls remain for the planned mining scope (estimate 3-5 calls per PR). If approaching limit, wait for reset or reduce scope.

**Gate**: Token is valid, repositories are accessible, rate limits are sufficient. Proceed only when gate passes.

### Phase 2: MINE

**Goal**: Extract raw review comment data with code context.

**Constraints during mining**:
- Focus on merged PRs only. Merged PRs represent accepted standards; drafts and abandoned work are noise.
- Apply imperative filtering by default. Filter for keywords like "should", "must", "avoid", "prefer" because they signal actionable feedback. This reduces noise from discussion and off-topic comments.
- Display mining progress during long operations so you know the process is running and can estimate completion time.
- Never analyze patterns, generate rules, or interpret comments during mining. Your job is extraction only.

**Step 1: Determine scope**

Choose mining parameters based on the task:
- **Single repo**: `python3 ~/.claude/scripts/miner.py org/repo output.json --limit 50`
- **Multi-repo**: `python3 ~/.claude/scripts/miner.py org/repo-a,org/repo-b output.json --limit 50`
- **Filtered**: Add `--reviewer name`, `--since date`, or `--all-comments`

Start with 50 PRs. Expand only after validating output quality. Large limits (1000+) burn rate limits, return outdated standards, and produce unwieldy files.

**Step 2: Execute mining**

```bash
python3 ~/.claude/scripts/miner.py <repos> mined_data/<output>.json --limit <N>
```

Monitor progress output. Watch for:
- Rate limit warnings (adjust scope if needed)
- Authentication errors (re-verify token)
- Empty PR responses (may indicate bot-only reviews; consider adjusting repo or time range)

**Step 3: Verify extraction**

Check the output file exists and contains data:

```bash
python3 -c "import json; d=json.load(open('mined_data/<output>.json')); print(f'PRs: {d[\"metadata\"][\"pr_count\"]}, Interactions: {d[\"metadata\"][\"interaction_count\"]}')"
```

If interaction count is below 20, consider expanding scope (`--limit`, `--all-comments`, or broader date range).

**Gate**: Mining completed without errors. Output JSON contains meaningful interaction data. Proceed only when gate passes.

### Phase 3: VALIDATE

**Goal**: Confirm output quality and completeness.

**Step 1: Run validation script**

```bash
python3 ~/.claude/scripts/validate.py
```

**Step 2: Spot-check data quality**

Review 3-5 interactions manually:
- `comment_text` contains actionable review feedback (not just "LGTM")
- `code_before` and `code_after` fields are populated where resolution is "changed"
- `reviewer` and `author` fields are not empty
- URLs resolve to valid GitHub locations

**Step 3: Generate summary statistics**

```bash
python3 ~/.claude/scripts/miner.py <repos> <output>.json --summary
```

Verify:
- Reviewer distribution is not dominated by a single person (unless `--reviewer` was used)
- Interaction count is proportional to PR count (expect 2-5 interactions per PR)
- Resolution types include a mix (not all "unknown")

**Step 4: Clean up temporary files**

Remove any partial JSON, debug logs, or temp files created during mining. Keep only the final output in `mined_data/`. This prevents stale data from being accidentally reused.

**Gate**: Validation passes. Data quality is sufficient for downstream analysis. Mining is complete.

---

## Output Format

```json
{
  "metadata": {
    "repo": "org/repo",
    "mined_at": "2025-11-20T14:30:00Z",
    "pr_count": 50,
    "interaction_count": 127
  },
  "interactions": [
    {
      "source": "pr_review",
      "pr_number": 234,
      "pr_title": "Add error wrapping",
      "author": "developer",
      "reviewer": "senior-developer",
      "file": "service/user.go",
      "line": 45,
      "comment_text": "Please use errors.Is() instead of == for error comparison",
      "diff_hunk": "@@ -42,7 +42,7 @@...",
      "code_before": "if err == ErrNotFound {",
      "code_after": "if errors.Is(err, ErrNotFound) {",
      "resolution": "changed",
      "url": "https://github.com/org/repo/pull/234#discussion_r123456",
      "created_at": "2025-10-15T10:23:45Z"
    }
  ]
}
```

### Resolution Types
- **changed**: Comment led to code modification
- **resolved**: Marked resolved without code change
- **dismissed**: Dismissed by author
- **unresolved**: Still open when PR merged
- **unknown**: Cannot determine resolution

### File Naming Conventions

**Raw data** (`mined_data/`): `{reviewer}_{repos}_{date}.json` or `{repos}_all_{date}.json`

**Distilled rules** (`rules/`): `{repos}_coding_rules.md` or `{reviewer}_{repos}_patterns.md`

---

## Examples

### Example 1: Mine Single Repository
User says: "Extract review patterns from our Go service"
Actions:
1. Verify token and repo access (AUTHENTICATE)
2. Mine last 50 merged PRs with imperative filtering (MINE)
3. Validate output has sufficient interactions (VALIDATE)
Result: `mined_data/go-service_all_2026-02-13.json` with 100+ interactions

### Example 2: Mine Specific Reviewer Across Repos
User says: "Get all of Alice's review comments across our backend repos"
Actions:
1. Verify token and all repo access (AUTHENTICATE)
2. Mine with `--reviewer alice` across 3 repos (MINE)
3. Validate reviewer field shows only Alice (VALIDATE)
Result: `mined_data/alice_backend_2026-02-13.json` for Code Archaeologist analysis

### Example 3: Team Standards Extraction
User says: "Build a dataset of our team's coding standards from PRs"
Actions:
1. Verify token for all team repos (AUTHENTICATE)
2. Mine 50 PRs from each of 4 team repos (MINE)
3. Validate cross-repo coverage and interaction quality (VALIDATE)
Result: Multi-repo dataset ready for pattern analysis

---

## Error Handling

### Error: "Bad credentials" or Authentication Failure
Cause: Token expired, revoked, or missing `repo` scope
Solution:
1. Verify `GITHUB_TOKEN` is set: `echo $GITHUB_TOKEN | head -c 10`
2. Check token permissions: `gh auth status`
3. Regenerate token with `repo` scope if needed
4. Retry authentication check before proceeding

### Error: "Rate limit exceeded"
Cause: Too many API calls in the current hour
Solution:
1. Check reset time: `gh api rate_limit --jq '.resources.core.reset'`
2. Wait for reset or reduce mining scope (`--limit`)
3. For large mining operations, split across multiple sessions
4. Consider using a dedicated token with higher rate limits

### Error: "No interactions found"
Cause: Repo has few review comments, or filters too restrictive
Solution:
1. Try `--all-comments` to disable imperative filtering
2. Increase `--limit` to mine more PRs
3. Broaden date range with `--since`
4. Verify the repo uses code review (check for review activity manually)

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/imperative-keywords.txt`: Full list of detected imperative keywords
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world mining examples and expected output
- `${CLAUDE_SKILL_DIR}/scripts/miner.py`: Main mining script (GitHub API extraction)
- `${CLAUDE_SKILL_DIR}/scripts/validate.py`: Output validation script
