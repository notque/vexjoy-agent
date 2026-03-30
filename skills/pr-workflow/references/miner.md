# PR Mining

This reference covers both raw PR review data extraction (Miner) and coordinated mining workflows with rule generation (Mining Coordinator).

---

# Part 1: PR Miner (Raw Data Extraction)

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


---

# Part 2: PR Mining Coordinator (Workflow Coordination and Rule Generation)

# PR Mining Coordinator Skill

## Overview

This skill coordinates PR mining workflows to extract tribal knowledge and coding standards from GitHub PR review history. It implements a five-phase pipeline (Validate, Mine, Verify, Generate, Report) that manages background mining jobs, generates confidence-scored coding rules, and prevents common pitfalls like username errors and API rate limiting.

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm all prerequisites before starting mining.

**Step 1: Check miner script exists**

```bash
fish -c "ls ~/.claude/skills/pr-workflow/scripts/miner.py"
```

Expected: File exists at path.

**Constraint**: Always complete this step. Miner script must exist before mining can run.

**Step 2: Verify GitHub token**

```bash
fish -c "security find-internet-password -s github.com -w 2>/dev/null"
```

Expected: Token printed (ghp_...).

**Constraint**: Always extract token from keychain using `security find-internet-password -s github.com -w`. Always extract tokens from keychain. If empty, user must add token with `security add-internet-password`.

**Step 3: Verify reviewer username (if filtering by reviewer)**

```bash
fish -c "gh pr list --repo {org/repo} --search 'reviewed-by:{username}' --limit 5"
```

Expected: PR results confirm username is valid and active.

**Constraint**: Username verification is MANDATORY when user specifies --reviewer flag. Silently wrong usernames cause 0 interactions after 5+ minutes of wasted API quota. Verify before mining, not after. (Pattern #1)

**Gate**: Miner script exists, token available, reviewer verified if applicable. Proceed only when gate passes.

### Phase 2: MINE

**Goal**: Execute mining job in background, track progress, avoid rate limit exhaustion.

**Step 1: Start mining job**

```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-workflow && \
  ./venv/bin/python3 scripts/miner.py {repos} mined_data/{output}.json {flags} --summary" &
```

**Output naming**: `{reviewer}_{repos}_{YYYY-MM-DD}.json` or `{repos}_all_{YYYY-MM-DD}.json`

See `references/mining-commands.md` for full command patterns and flag reference.

**Constraint - Background Execution**: Always run mining with `&` (ampersand suffix) to background the job. Run mining operations in the background. Capture and store the background job PID for tracking.

**Constraint - GitHub Token Source**: Always extract token from keychain inline with `security find-internet-password -s github.com -w`. Export as GITHUB_TOKEN environment variable before calling miner.py. No other token sources are acceptable.

**Step 2: Track progress**

Monitor background job with BashOutput tool. Check every 30-60 seconds. Report progress to user showing: repos scanned, PRs processed, interactions extracted so far.

**Constraint - Progress Reporting**: Show command output, not marketing descriptions. Real numbers (e.g., "150 PRs scanned, 42 interactions extracted") beat "Mining is progressing nicely."

**Step 3: Handle multiple repos**

Run jobs sequentially. Wait for each to complete before starting next. Wait for each job to complete before starting the next.

**Constraint - Sequential by Default**: Running multiple mining jobs in parallel exhausts the 5000 requests/hour API quota faster than you can track which job caused the failure. Sequential mining prevents rate limit cascades and makes attribution clear. (Pattern #2) Only enable concurrency if explicitly requested AND user understands rate limit risk.

**Gate**: Mining job completes with non-zero interaction count. If job exits with 0 interactions, see Error Handling "0 interactions found" section.

### Phase 3: VERIFY

**Goal**: Confirm mining output is valid, contains interactions with usable data, and failed mining exits cleanly.

**Step 1: Check output file exists and has content**

```bash
fish -c "cat ~/.claude/skills/pr-workflow/mined_data/{output}.json | head -50"
```

**Step 2: Validate structure**

Confirm JSON matches expected schema:

```json
{
  "metadata": {
    "repos": ["org/repo"],
    "reviewer": "username",
    "mined_at": "2025-11-29T10:30:00Z",
    "pr_count": 100,
    "interaction_count": 36
  },
  "interactions": [
    {
      "pr_number": 123,
      "pr_title": "Add feature X",
      "comment": "Use errors.Is() instead of comparing error strings",
      "code_before": "if err.Error() == \"not found\" {",
      "code_after": "if errors.Is(err, ErrNotFound) {"
    }
  ]
}
```

**Constraint**: If `interaction_count` is 0, stop and resolve before proceeding to Phase 4. Instead, check Error Handling section "0 interactions found" for diagnosis. Common causes: wrong reviewer username (should have caught in Phase 1), no PR activity in date range, or repo has no review comments (only approvals).

**Step 3: Check interaction quality**

Verify interactions have: pr_number, pr_title, comment text. Code pairs (code_before/code_after) are strongly preferred but not mandatory. Interactions without code pairs can still produce rules but are lower value.

**Constraint - Prevent Flat Dumps**: Confirm `interaction_count > 0` before proceeding to Phase 4. Checking that `interaction_count > 0`. Attempting to generate rules from empty results wastes time and produces nothing usable. Empty results signal a problem to diagnose, not a success to report.

**Gate**: Output JSON is valid, interaction_count > 0, interactions have required fields. Proceed only when gate passes.

### Phase 4: GENERATE

**Goal**: Produce categorized, confidence-scored markdown rules from mined data.

**Step 1: Load and categorize patterns**

Read mined JSON. Group interactions by topic using standard categories from `references/pattern-categories.md`. Example categories: Error Handling, Testing, API Design, Concurrency, Performance, Naming, Documentation, Security, Refactoring, Tooling.

**Constraint - Mandatory Categorization**: Organize patterns by topic with confidence ranking of 50 patterns. Flat lists are overwhelming, unscannable, and lose priority context. Organize by topic, then by confidence within topic. (Pattern #3)

**Step 2: Score confidence**

Calculate confidence from occurrence frequency and reviewer seniority:

| Level | Criteria | Action |
|-------|----------|--------|
| HIGH | 5+ occurrences (especially from senior reviewers) | Include as standard practice |
| MEDIUM | 2-4 occurrences | Include with context caveats |
| LOW | Single occurrence | Place in "Additional Observations" section |

**Step 3: Generate markdown rules document**

Follow this structure for each pattern:

```markdown
## {Category Name}

### {Pattern Name} ({CONFIDENCE} confidence)

**Pattern**: {Brief description of the rule}

**Good**:
\`\`\`{lang}
{good_example_code}
\`\`\`

**Bad**:
\`\`\`{lang}
{bad_example_code}
\`\`\`

**Rationale**: From PR #{number} review by {reviewer}:
"{comment_text}"
```

**Constraint - Ordering for Usability**: Sort categories by pattern count (descending: most patterns first). Within each category, sort patterns HIGH → MEDIUM → LOW confidence. Users scan from top, so high-confidence patterns must come first to maximize scanning efficiency.

**Step 4: Save rules**

```bash
fish -c "cat > ~/.claude/skills/pr-workflow/rules/{repos}_coding_rules.md"
```

**Constraint - Cleanup Behavior**: After saving rules to disk, remove temporary coordination files (PIDs, debug logs, intermediate JSON). Keep ONLY the final mining result JSON (for future reference) and generated rules markdown (for user consumption).

**Gate**: Rules document is categorized, confidence-scored, saved to disk, and temporary files cleaned.

### Phase 5: REPORT

**Goal**: Deliver actionable results with all necessary context.

Provide:
- PRs analyzed count
- Interactions extracted count
- File path to mined data JSON
- File path to generated rules markdown
- List of top 3-5 HIGH confidence patterns with occurrence counts
- Summary of MEDIUM and LOW confidence pattern distribution

**Constraint - Report Clarity**: Show actual numbers and paths, not generic summaries. Example good report: "Analyzed 150 PRs, extracted 42 interactions. HIGH confidence (12 patterns): Error handling (5), Testing (4), Naming (3). MEDIUM confidence: 18 patterns. LOW confidence: 12 patterns. Rules: ~/.claude/skills/pr-workflow/rules/myrepo_coding_rules.md"

**Constraint - Communication Style**: Report facts without self-congratulation. Show what happened and where the output is. Report facts directly: "Mined 42 interactions from 150 PRs" — keep the tone factual.

**Gate**: User has file paths, pattern counts, and top patterns. They can immediately act on the rules markdown.

---

## Error Handling

### Error: "API rate limit exceeded"
Cause: GitHub API 5000 requests/hour exhausted by mining operations
Solution:
1. Report remaining quota and reset time to user
2. Stop current job if rate limit is critically low (<150 remaining)
3. Wait for reset or cancel and retry later
4. For future runs: reduce --limit or mine fewer repos per job

### Error: "Authentication failed"
Cause: GitHub token expired, revoked, or missing from keychain
Solution:
1. Run `fish -c "security find-internet-password -s github.com -w 2>/dev/null"` to check token
2. If empty: token not in keychain. User must add it
3. If present but rejected: token expired or lacks repo scope
4. Guide user to update token with `security add-internet-password`

### Error: "0 interactions found"
Cause: Wrong reviewer username, no PR activity, or date range too narrow
Solution:
1. Verify reviewer username with `gh pr list --search 'reviewed-by:{username}'`
2. Re-run without --reviewer to confirm data exists
3. Widen date range by removing --since/--until
4. Check if repo has PR review comments (not just approvals)

### Error: "Mining job timeout (>5 min)"
Cause: Large repo, many PRs, or slow API responses
Solution:
1. Report current progress to user
2. Continue monitoring -- mining is still running
3. If stuck: check for network issues or API downtime
4. For future runs: reduce --limit to smaller batches

### Error: "Senior reviewer returns 0-2 interactions"
Cause: Missing --all-comments flag when mining senior reviewers
Solution:
1. Senior reviewers often use questions and suggestions instead of imperative statements
2. Default mining mode captures only imperative comments
3. Re-run with `--all-comments` flag to capture all comment types
4. For future runs: always use `--all-comments` when mining experienced reviewers (Pattern #4)

### Error: "Multi-repo mining fails partway through"
Cause: Running 5+ repos in parallel, early jobs exhaust rate limits, later jobs fail
Solution:
1. Check remaining rate quota with `gh rate-limit`
2. If critically low (<150 remaining): wait for reset before retrying
3. For future runs: test with a single repo and `--limit 10` first. Expand incrementally after confirming access works. (Pattern #5)

---

## References

This skill uses these reference files:
- `${CLAUDE_SKILL_DIR}/references/mining-commands.md`: Command patterns, flag reference, output naming conventions
- `${CLAUDE_SKILL_DIR}/references/pattern-categories.md`: Standard categories for coding rules (10 categories with examples)
- `${CLAUDE_SKILL_DIR}/references/reviewer-usernames.md`: Known GitHub usernames and verification methods
