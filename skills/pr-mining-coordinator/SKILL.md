---
name: pr-mining-coordinator
description: "Coordinate PR mining for tribal knowledge and coding standards extraction."
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
  - Skill
routing:
  triggers:
    - "coordinate PR mining"
    - "extract tribal knowledge"
  category: git-workflow
---

# PR Mining Coordinator Skill

## Overview

This skill coordinates PR mining workflows to extract tribal knowledge and coding standards from GitHub PR review history. It implements a five-phase pipeline (Validate, Mine, Verify, Generate, Report) that manages background mining jobs, generates confidence-scored coding rules, and prevents common pitfalls like username errors and API rate limiting.

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm all prerequisites before starting mining.

**Step 1: Check miner script exists**

```bash
fish -c "ls ~/.claude/skills/pr-miner/scripts/miner.py"
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
  cd ~/.claude/skills/pr-miner && \
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
fish -c "cat ~/.claude/skills/pr-miner/mined_data/{output}.json | head -50"
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
fish -c "cat > ~/.claude/skills/pr-miner/rules/{repos}_coding_rules.md"
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

**Constraint - Report Clarity**: Show actual numbers and paths, not generic summaries. Example good report: "Analyzed 150 PRs, extracted 42 interactions. HIGH confidence (12 patterns): Error handling (5), Testing (4), Naming (3). MEDIUM confidence: 18 patterns. LOW confidence: 12 patterns. Rules: ~/.claude/skills/pr-miner/rules/myrepo_coding_rules.md"

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
