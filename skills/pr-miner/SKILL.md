---
name: pr-miner
description: |
  Deterministic 3-phase GitHub PR review comment extraction: Authenticate,
  Mine, Validate. Use when mining tribal knowledge from PR reviews, extracting
  coding standards from review history, or building datasets for the Code
  Archaeologist agent. Use for "mine PRs", "extract review comments", "tribal
  knowledge", or "PR review history". Do NOT use for analyzing patterns,
  generating rules, or interpreting comments — that is the Code Archaeologist
  agent's responsibility.
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
---

# PR Miner Skill

## Operator Context

This skill operates as an operator for deterministic GitHub data extraction, configuring Claude's behavior for mining PR review comments. It implements the **Pipeline** architectural pattern — authenticate, mine, validate — with strict separation between extraction (this skill) and analysis (Code Archaeologist agent).

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Extract only requested data. No analysis, interpretation, or pattern detection — that is the Code Archaeologist agent's job
- **Deterministic Extraction Only**: Output raw JSON. Never analyze patterns, generate rules, or interpret comments
- **Authenticate First**: Verify GitHub token before starting any mining operation
- **Rate Limit Respect**: Honor GitHub API rate limits with exponential backoff

### Default Behaviors (ON unless disabled)
- **Merged PRs Only**: Focus on merged PRs representing accepted standards
- **Imperative Filtering**: Filter for imperative language keywords (should, must, avoid, prefer)
- **Progress Reporting**: Display mining progress during long operations
- **Temporary File Cleanup**: Remove partial JSON and temp files at completion; keep only final output
- **Summary Output**: Report interaction count and reviewer distribution after mining

### Optional Behaviors (OFF unless enabled)
- **All Comments Mode**: Capture every review comment regardless of language (`--all-comments`)
- **Reviewer Filter**: Focus on comments from particular reviewers (`--reviewer`)
- **Date Range**: Limit mining to specific time periods (`--since`/`--until`)
- **Multi-Repo**: Mine across multiple repositories in single operation

## What This Skill CAN Do
- Extract review comments with code context (before/after) from merged PRs
- Track resolution status per comment (changed, resolved, dismissed, unresolved)
- Filter by imperative language keywords or capture all comments
- Mine multiple repositories in a single operation
- Respect GitHub API rate limits with retry logic
- Generate structured JSON output for downstream analysis
- Validate GitHub authentication before mining

## What This Skill CANNOT Do
- Analyze patterns or generate rules (Code Archaeologist agent's job)
- Interpret comment meaning or intent (pure extraction only)
- Create enforcement rules (no Semgrep/golangci-lint generation)
- Mine private repos without proper token permissions (requires `repo` scope)
- Process non-GitHub platforms (GitHub-specific implementation)
- Monitor PRs in real-time (snapshot-based mining only)

---

## Instructions

### Phase 1: AUTHENTICATE

**Goal**: Verify GitHub access and validate target repositories before mining.

**Step 1: Verify token**

```bash
python3 scripts/miner.py --check-auth
```

Confirm output shows valid authentication with `repo` scope.

**Step 2: Validate target repositories**

Confirm each target repository:
- Exists and is accessible with current token
- Has merged PRs with review comments
- Uses a code review workflow (not just self-merges)

**Step 3: Check rate limits**

```bash
gh api rate_limit --jq '.resources.core | "Remaining: \(.remaining)/\(.limit), Resets: \(.reset)"'
```

Ensure sufficient API calls remain for the planned mining scope (estimate 3-5 calls per PR).

**Gate**: Token is valid, repositories are accessible, rate limits are sufficient. Proceed only when gate passes.

### Phase 2: MINE

**Goal**: Extract raw review comment data with code context.

**Step 1: Determine scope**

Choose mining parameters based on the task:
- **Single repo**: `python3 scripts/miner.py org/repo output.json --limit 50`
- **Multi-repo**: `python3 scripts/miner.py org/repo-a,org/repo-b output.json --limit 50`
- **Filtered**: Add `--reviewer name`, `--since date`, or `--all-comments`

Start with 50 PRs. Expand only after validating output quality.

**Step 2: Execute mining**

```bash
python3 scripts/miner.py <repos> mined_data/<output>.json --limit <N>
```

Monitor progress output. Watch for:
- Rate limit warnings
- Authentication errors
- Empty PR responses (may indicate bot-only reviews)

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
python3 scripts/validate.py
```

**Step 2: Spot-check data quality**

Review 3-5 interactions manually:
- `comment_text` contains actionable review feedback (not just "LGTM")
- `code_before` and `code_after` fields are populated where resolution is "changed"
- `reviewer` and `author` fields are not empty
- URLs resolve to valid GitHub locations

**Step 3: Generate summary statistics**

```bash
python3 scripts/miner.py <repos> <output>.json --summary
```

Verify:
- Reviewer distribution is not dominated by a single person (unless `--reviewer` was used)
- Interaction count is proportional to PR count (expect 2-5 interactions per PR)
- Resolution types include a mix (not all "unknown")

**Step 4: Clean up temporary files**

Remove any partial JSON, debug logs, or temp files created during mining. Keep only the final output in `mined_data/`.

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

## Anti-Patterns

### Anti-Pattern 1: Analyzing During Mining
**What it looks like**: "I mined the data and found 5 key patterns: always use errors.Is()..."
**Why wrong**: This skill extracts raw data. Pattern analysis is the Code Archaeologist agent's job. Mixing extraction with interpretation creates unreliable, non-deterministic output.
**Do instead**: Mine data, validate output, hand off JSON to Code Archaeologist.

### Anti-Pattern 2: Mining Without Authentication Check
**What it looks like**: Running `miner.py` immediately, failing 10 minutes later on "Bad credentials"
**Why wrong**: Wastes time and API rate limits. No early validation of token permissions.
**Do instead**: Complete Phase 1 (AUTHENTICATE) before any mining.

### Anti-Pattern 3: Mining Entire Repository History
**What it looks like**: `--limit 10000` to get "everything"
**Why wrong**: Extremely slow, burns rate limits, old PRs reflect outdated standards, massive output files are hard to process.
**Do instead**: Start with `--limit 50 --since <6-months-ago>`. Expand only after validating output quality.

### Anti-Pattern 4: Skipping Output Validation
**What it looks like**: Mining completes, immediately passing output to Code Archaeologist without checking
**Why wrong**: May contain zero useful interactions, incomplete data from API errors, or bot-generated noise. Garbage in, garbage out.
**Do instead**: Complete Phase 3 (VALIDATE). Spot-check interactions, verify counts, review distribution.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Token worked last time" | Tokens expire, permissions change | Run `--check-auth` every session |
| "50 PRs is enough" | Depends on review density | Validate interaction count before proceeding |
| "I can summarize the patterns" | Extraction skill, not analysis skill | Output raw JSON only |
| "All comments mode wastes time" | Imperative filter may miss valuable feedback | Consider `--all-comments` for first run |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/imperative-keywords.txt`: Full list of detected imperative keywords
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real-world mining examples and expected output
- `${CLAUDE_SKILL_DIR}/scripts/miner.py`: Main mining script (GitHub API extraction)
- `${CLAUDE_SKILL_DIR}/scripts/validate.py`: Output validation script
