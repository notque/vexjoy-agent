---
name: pr-mining-coordinator
description: |
  Coordinate PR mining to extract tribal knowledge and coding standards from
  GitHub PR history. Use when mining review comments, extracting coding rules,
  tracking mining jobs, or analyzing reviewer patterns across repositories.
  Use for "mine PRs", "extract standards", "coding rules from reviews", or
  "reviewer patterns". Do NOT use for code review, linting, static analysis,
  or writing new coding standards from scratch without PR data.
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
---

# PR Mining Coordinator Skill

## Operator Context

This skill operates as an operator for PR mining coordination workflows, configuring Claude's behavior for background job management and tribal knowledge extraction. It implements the **Pipeline** architectural pattern -- Validate, Mine, Verify, Generate, Report -- with **Domain Intelligence** embedded in the mining methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Only implement what's directly requested. No speculative features
- **Background Execution**: Mining jobs always run in background with `&`
- **GitHub Token from Keychain**: Uses `security find-internet-password -s github.com -w`
- **Process Tracking**: Always store and monitor background job PIDs
- **Sequential by Default**: Run mining jobs one at a time to avoid API rate limits

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output, not descriptions
- **Temporary File Cleanup**: Remove coordination files and debug outputs at completion. Keep only mining results (JSON) and generated rules (markdown)
- **Progress Reporting**: Show mining job progress every 30-60 seconds
- **Auto Rules Generation**: Generate categorized markdown rules after successful mining
- **Error Detection**: Monitor for API rate limits, auth failures, empty results
- **Confidence Scoring**: Calculate HIGH/MEDIUM/LOW confidence for patterns

### Optional Behaviors (OFF unless enabled)
- **Concurrent Mining**: Run multiple repos simultaneously (risk: rate limits)
- **Historical Analysis**: Mine specific date ranges with --since/--until flags
- **All Comments Mode**: Use --all-comments for senior reviewers (default: imperative only)
- **Cross-Repo Merging**: Combine patterns from multiple mining results into unified rules

## What This Skill CAN Do
- Coordinate background PR mining jobs with the pr-miner tool
- Track running jobs and report progress to user
- Generate categorized coding rules documents from mined data
- Calculate pattern confidence from occurrence frequency
- Handle API rate limits, auth failures, and empty result sets

## What This Skill CANNOT Do
- Mine without a valid GitHub token
- Run multiple mining jobs in parallel (sequential by default)
- Perform code review (use code-review skill instead)
- Write coding standards from scratch without PR data
- Skip prerequisite validation or result verification

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm prerequisites before starting any mining operation.

**Step 1: Check miner script exists**

```bash
fish -c "ls ~/.claude/skills/pr-miner/scripts/miner.py"
```

Expected: File exists at path.

**Step 2: Verify GitHub token**

```bash
fish -c "security find-internet-password -s github.com -w 2>/dev/null"
```

Expected: Token printed (ghp_...).

**Step 3: Verify reviewer username (if filtering by reviewer)**

```bash
fish -c "gh pr list --repo {org/repo} --search 'reviewed-by:{username}' --limit 5"
```

Expected: PR results confirm username is valid and active.

**Gate**: Miner script exists, token available, reviewer verified. Proceed only when gate passes.

### Phase 2: MINE

**Goal**: Execute mining job in background and track progress.

**Step 1: Start mining job**

```bash
fish -c "set -x GITHUB_TOKEN (security find-internet-password -s github.com -w 2>/dev/null) && \
  cd ~/.claude/skills/pr-miner && \
  ./venv/bin/python3 scripts/miner.py {repos} mined_data/{output}.json {flags} --summary" &
```

**Output naming**: `{reviewer}_{repos}_{YYYY-MM-DD}.json` or `{repos}_all_{YYYY-MM-DD}.json`

See `references/mining-commands.md` for full command patterns and flag reference.

**Step 2: Track progress**

Monitor background job with BashOutput tool. Check every 30-60 seconds. Report progress to user.

**Step 3: Handle multiple repos**

Run jobs sequentially. Wait for each to complete before starting next.

**Gate**: Mining job completes with non-zero interaction count. Proceed only when gate passes.

### Phase 3: VERIFY

**Goal**: Confirm mining output is valid and contains usable data.

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

If `interaction_count` is 0, do not proceed -- see Error Handling for "0 interactions found".

**Step 3: Check interaction quality**

Verify interactions have: pr_number, pr_title, comment text, and ideally code_before/code_after pairs. Interactions without code pairs can still produce rules but lack concrete examples.

**Gate**: Output JSON is valid, contains interactions with usable data. Proceed only when gate passes.

### Phase 4: GENERATE

**Goal**: Produce categorized coding rules document from mined data.

**Step 1: Load and categorize patterns**

Read mined JSON. Categorize interactions by topic using standard categories from `references/pattern-categories.md`.

**Step 2: Score confidence**

| Level | Criteria | Action |
|-------|----------|--------|
| HIGH | 5+ occurrences from senior reviewers | Include as standard practice |
| MEDIUM | 2-4 occurrences | Include with context caveats |
| LOW | Single occurrence | Place in "Additional Observations" |

**Step 3: Generate markdown rules document**

Follow this structure for each pattern entry:

```markdown
## {Category Name}

### {Pattern Name} ({CONFIDENCE} confidence)

**Pattern**: {Brief description}

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

Order categories by total pattern count (most patterns first). Within each category, sort HIGH before MEDIUM before LOW.

**Step 4: Save rules**

```bash
fish -c "cat > ~/.claude/skills/pr-miner/rules/{repos}_coding_rules.md"
```

**Gate**: Rules document is categorized, confidence-scored, and saved to disk.

### Phase 5: REPORT

**Goal**: Deliver comprehensive results to user.

Provide:
- PRs analyzed count
- Interactions extracted count
- File paths for mined data and generated rules
- Top HIGH confidence patterns with occurrence counts
- Summary of MEDIUM and LOW confidence pattern counts

**Gate**: User has all information needed to act on mining results.

---

## Examples

### Example 1: Mine Specific Reviewer
User says: "Mine senior-reviewer's patterns from go-libs"
Actions:
1. Verify miner, token, and reviewer username (VALIDATE)
2. Run mining with --reviewer and --all-comments flags (MINE)
3. Check output JSON for valid interactions (VERIFY)
4. Categorize patterns and generate rules markdown (GENERATE)
5. Report top patterns and file locations (REPORT)
Result: Categorized coding rules with confidence scores

### Example 2: Team Standards Extraction
User says: "Get coding standards from service-a and service-b"
Actions:
1. Verify miner and token, no reviewer to verify (VALIDATE)
2. Run mining without --reviewer to capture all reviewers (MINE)
3. Confirm output has interactions from multiple reviewers (VERIFY)
4. Generate team-wide rules document (GENERATE)
5. Report findings with reviewer distribution (REPORT)
Result: Team-wide coding rules across both repositories

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

---

## Anti-Patterns

### Anti-Pattern 1: Mining Without Verifying Reviewer Username
**What it looks like**: Running `--reviewer senior-reviewer` without checking the actual GitHub username
**Why wrong**: Job completes successfully with 0 interactions. Wastes API quota and 5-10 minutes. Username errors are silent.
**Do instead**: Verify username with `gh pr list --search 'reviewed-by:{username}'` before mining.

### Anti-Pattern 2: Running Multiple Mining Jobs in Parallel
**What it looks like**: Starting 3+ mining jobs simultaneously to save time
**Why wrong**: Exhausts 5000 requests/hour rate limit across all jobs. Later jobs fail mid-execution. Cannot track which job consumed quota.
**Do instead**: Run jobs sequentially. Wait for each to complete before starting the next.

### Anti-Pattern 3: Generating Flat Rules Without Categorization
**What it looks like**: A numbered list of 50 patterns with no organization or confidence scoring
**Why wrong**: Overwhelming to read. No way to find relevant patterns. Loses priority context.
**Do instead**: Categorize by topic (Error Handling, Testing, API Design, etc.) and sort by confidence level within each category. See `references/pattern-categories.md`.

### Anti-Pattern 4: Skipping --all-comments for Senior Reviewers
**What it looks like**: Mining a senior reviewer without the --all-comments flag and getting 0-2 interactions
**Why wrong**: Senior reviewers use questions ("Why not use errors.Is here?") and suggestions instead of imperatives. Default mode misses the majority of their feedback.
**Do instead**: Always use `--all-comments` when mining senior or experienced reviewers.

### Anti-Pattern 5: Testing Multi-Repo Mining Without Single-Repo Validation
**What it looks like**: Mining 5 repos at once on the first attempt without verifying any individually
**Why wrong**: If any repo has access issues, entire job fails after minutes of wasted time. Cannot determine which repo caused failure.
**Do instead**: Test with a single repo and `--limit 10` first. Expand incrementally after confirming access.

---

## References

This skill uses these reference files:
- `${CLAUDE_SKILL_DIR}/references/mining-commands.md`: Command patterns, flag reference, output naming conventions
- `${CLAUDE_SKILL_DIR}/references/pattern-categories.md`: Standard categories for coding rules (10 categories with examples)
- `${CLAUDE_SKILL_DIR}/references/reviewer-usernames.md`: Known GitHub usernames and verification methods

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Username is probably right" | Probably = 0 interactions after 5 min | Verify with gh pr list first |
| "Parallel mining saves time" | Saves nothing when rate limit kills jobs | Run sequentially |
| "Just dump all patterns" | Flat lists are unusable at 50+ items | Categorize and score confidence |
| "Low limit is enough" | Small samples produce low-confidence rules | Use --limit 100+ for meaningful patterns |
