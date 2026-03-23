---
name: github-profile-rules
description: |
  Extract programming rules and coding conventions from a GitHub user's public
  profile via API. Analyzes repos, code files, commit messages, and PR reviews
  to produce confidence-scored rules formatted for CLAUDE.md or JSON output.
  Use for "github rules", "profile analysis", "coding style extraction",
  "github conventions", or "programming rules extraction".
version: 1.0.0
user-invocable: true
agent: github-profile-rules-engineer
model: opus
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - WebFetch
---

# GitHub Profile Rules Extraction

## Operator Context

This skill operates as the main orchestration pipeline for extracting programming rules from a GitHub user's public profile. It implements a 7-phase pipeline that fetches data exclusively via the GitHub API (no git clone), analyzes code patterns across repos, extracts PR review comments for preference signals, compiles findings into deduplicated confidence-scored rules, and outputs actionable CLAUDE.md-compatible entries.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before execution.
- **API-Only Data Fetching**: All GitHub data must be fetched via `scripts/github-api-fetcher.py`. No git clone, no subprocess git calls. This is a non-negotiable constraint.
- **Rate Limit Awareness**: Before each batch of API calls, check remaining quota. If `--token` is not provided, the unauthenticated limit is 60 req/hr.
- **Evidence-Based Rules Only**: Every generated rule must cite at least one repo or review where the pattern was observed. No generic advice.
- **Confidence Scoring**: Every rule gets a confidence level: high (3+ repos), medium (2 repos), low (1 repo).

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report progress by phase with counts (repos fetched, files sampled, patterns found, rules generated).
- **Top-N Repos**: Analyze the top 10 repos by stars/recent activity unless overridden by `--max-repos`.
- **Review Priority**: PR reviews given carry 2x weight vs code authored for preference signals.
- **Output Dual Format**: Always produce both CLAUDE.md markdown and JSON with confidence scores.

### Optional Behaviors (OFF unless enabled)
- **Verbose Mode**: Show each API call and response
- **Raw Data Preservation**: Keep intermediate files alongside final output
- **Org-Wide Analysis**: Extend analysis to all repos in a GitHub organization

## What This Skill CAN Do
- Fetch public repos, file contents, commit messages, and PR reviews via GitHub API (rest endpoints)
- Sample N files per repo across a user's top repositories
- Identify naming conventions, code style patterns, architectural preferences, and testing habits
- Deduplicate and rank patterns by frequency across repos
- Output actionable rules in CLAUDE.md-compatible markdown and structured JSON
- Handle API rate limiting with backoff and user notification

## What This Skill CANNOT Do
- **Clone repositories**: All analysis is API-based
- **Access private data**: Only public repos and reviews are analyzed
- **Run code**: Patterns are extracted from source text, not by executing code
- **Guarantee exhaustive coverage**: API rate limits and sampling mean not every file is analyzed

---

## Instructions

### Phase 0: ADR

**Goal**: Create a persistent reference document before work begins.

**Step 1**: Create `adr/github-profile-rules-{username}.md` with:
- Context: Why rules are being extracted for this user
- Decision: API-only approach, sampling strategy, target repos
- Constraints: Rate limits, public data only
- Test Plan: How generated rules will be validated

**Step 2**: Re-read the ADR before every major decision.

**Gate**: ADR file exists. Username validated via GitHub API. Proceed to Phase 1.

---

### Phase 1: FETCH

**Goal**: Fetch the user's repo list, language statistics, and README samples via GitHub API.

**Step 1**: Run the API fetcher to get repo metadata:
```bash
python3 scripts/github-api-fetcher.py repos \
  --username {username} \
  --max-repos {N} \
  --output-dir /tmp/github-rules-{username}
```

**Step 2**: Review the output. Identify:
- Top repos by stars and recent activity
- Primary languages used
- Repository naming patterns
- README presence and quality signals

**Step 3**: Save profile summary to `/tmp/github-rules-{username}/profile-summary.md` with:
- Total public repos count
- Top 10 repos with stars, language, and description
- Language distribution
- README patterns observed

**Gate**: Repo list fetched. At least 1 repo with accessible content. Profile summary saved. Proceed to Phase 2.

---

### Phase 2: RESEARCH (Parallel Multi-Agent)

**Goal**: Sample code files from top repos to extract coding patterns.

**Step 1**: Prepare shared context block from Phase 1 profile summary.

**Step 2**: Dispatch 4 parallel research agents, each analyzing a different aspect:

- **Agent 1: Naming Conventions** -- variable names, function names, file names, class names across sampled files
- **Agent 2: Code Structure** -- file organization, import patterns, module structure, error handling patterns
- **Agent 3: Commit Messages** -- commit message format, conventional commits usage, message length and detail
- **Agent 4: Documentation Patterns** -- README structure, inline comments, docstring style, documentation quality

Each agent:
- Uses `python3 scripts/github-api-fetcher.py sample-files` to fetch file contents
- Saves findings to `/tmp/github-rules-{username}/research-{aspect}.md`
- Has a 5-minute timeout
- Operates independently

**Step 3**: Collect and merge research artifacts after all agents complete.

**Gate**: All 4 research agents completed. At least 10 files sampled across repos. Findings saved. Proceed to Phase 3.

---

### Phase 3: SAMPLE

**Goal**: Fetch PR reviews the user has given to extract preference signals.

**Step 1**: Run the API fetcher to get PR reviews:
```bash
python3 scripts/github-api-fetcher.py pr-reviews \
  --username {username} \
  --output-dir /tmp/github-rules-{username}
```

**Step 2**: Analyze review comments for recurring themes:
- What patterns do they request changes for?
- What do they approve without comment?
- What feedback do they give most frequently?
- What style/convention issues do they flag?

**Step 3**: Categorize review signals by rule category (naming, style, architecture, testing, error handling, documentation).

**Step 4**: Save review analysis to `/tmp/github-rules-{username}/review-analysis.md`.

**Gate**: PR review data fetched (or documented that user has no public reviews). Review themes categorized. Proceed to Phase 4.

---

### Phase 4: COMPILE

**Goal**: Compile patterns from code analysis and review data, score confidence, and deduplicate.

**Step 1**: Load all research artifacts from Phase 2 and review analysis from Phase 3.

**Step 2**: For each identified pattern:
- Count how many repos it appears in
- Check if it's reinforced by review comments
- Assign confidence: high (3+ repos OR 2+ repos + review signal), medium (2 repos), low (1 repo)
- Categorize using the taxonomy from `references/rule-categories.md`

**Step 3**: Deduplicate similar patterns:
- Merge "uses camelCase for variables" and "prefers camelCase naming" into one rule
- Keep the most specific version
- Combine evidence from all sources

**Step 4**: Run the rules compiler for structured output:
```bash
python3 scripts/rules-compiler.py \
  --input-dir /tmp/github-rules-{username} \
  --output /tmp/github-rules-{username}/compiled-rules.json
```

**Step 5**: Save synthesis results to `/tmp/github-rules-{username}/synthesis.md`.

**Gate**: Patterns compiled and deduplicated. Confidence scores assigned. At least 5 rules identified. Proceed to Phase 5.

---

### Phase 5: GENERATE

**Goal**: Format compiled patterns as CLAUDE.md-compatible rule entries.

**Step 1**: For each rule, generate a CLAUDE.md entry following this format:
```markdown
## [Category]: [Rule Name]

**Confidence**: [high/medium/low] (seen in N repos, M review comments)

[Actionable rule description]

**Evidence**:
- Repo: {repo_name} -- {specific example}
- Review: {pr_url} -- "{comment excerpt}"
```

**Step 2**: Group rules by category (naming, style, architecture, testing, error handling, documentation).

**Step 3**: Order rules within each category by confidence (high first).

**Step 4**: Generate the JSON output with full metadata:
```json
{
  "username": "{username}",
  "generated_at": "{timestamp}",
  "total_rules": N,
  "rules": [
    {
      "category": "naming",
      "rule": "...",
      "confidence": "high",
      "repos_observed": ["repo1", "repo2", "repo3"],
      "review_signals": 2,
      "examples": ["..."]
    }
  ]
}
```

**Gate**: CLAUDE.md entries generated. JSON output generated. Both formats contain the same rules. Proceed to Phase 6.

---

### Phase 6: VALIDATE

**Goal**: Verify rules are actionable, non-contradictory, and properly scoped.

**Step 1**: Check each rule for actionability:
- Can a developer follow this rule without additional context? If not, add specifics.
- Does the rule include a concrete example? If not, add one from evidence.

**Step 2**: Check for contradictions:
- Scan for rules that conflict (e.g., "use camelCase" vs "use snake_case")
- If contradictions found: check if they apply to different languages/contexts
- Resolve by scoping (e.g., "use camelCase in JavaScript, snake_case in Python")

**Step 3**: Check scoping:
- Are language-specific rules properly scoped?
- Are project-type-specific rules properly scoped?
- Remove rules that are too broad to be actionable

**Step 4**: Run the rules compiler in validation mode:
```bash
python3 scripts/rules-compiler.py \
  --input-dir /tmp/github-rules-{username} \
  --output /tmp/github-rules-{username}/validated-rules.json \
  --validate
```

**Gate**: All rules pass actionability check. No unresolved contradictions. Rules properly scoped. Proceed to Phase 7.

---

### Phase 7: OUTPUT

**Goal**: Save final rules to `rules/{username}/rules-output.md` and `rules/{username}/rules.json`.

**Step 1**: Create output directory:
```bash
mkdir -p rules/{username}
```

**Step 2**: Write `rules/{username}/rules-output.md` with:
- Header: "Programming Rules for {username}"
- Generation metadata: date, repos analyzed, files sampled, reviews mined
- Rules grouped by category, ordered by confidence
- Each rule in CLAUDE.md-compatible format

**Step 3**: Write `rules/{username}/rules.json` with:
- Full structured output including confidence scores, evidence, and metadata

**Step 4**: Generate summary report:
- Total rules by confidence level
- Rules by category distribution
- Top 5 highest-confidence rules
- Data coverage (repos analyzed, files sampled, reviews mined)

**Gate**: Output files exist. Both formats contain consistent data. Summary report delivered.

---

## Error Handling

### Error: API Rate Limit Exceeded
**Cause**: Too many requests without authentication token.
**Solution**: Check `X-RateLimit-Remaining`. Suggest `--token` flag. For unauthenticated: 60/hr. With token: 5000/hr.

### Error: No Public Repos or Reviews
**Cause**: User has no public GitHub activity.
**Solution**: Report that no data is available for analysis. Suggest checking username or noting the user may have only private activity.

### Error: Insufficient Data for Confident Rules
**Cause**: Too few repos or files to establish patterns.
**Solution**: Lower confidence thresholds and flag all rules as preliminary. Report data limitations.

## Anti-Patterns

### Anti-Pattern 1: Cloning Repos
**What it looks like**: Using git clone to access code.
**Why wrong**: Violates API-only constraint. Unnecessary for pattern extraction.
**Do instead**: Use `scripts/github-api-fetcher.py sample-files` for file content.

### Anti-Pattern 2: Generic Rules
**What it looks like**: "Follow clean code principles" without specific evidence.
**Why wrong**: Adds no value over generic best practices.
**Do instead**: Extract only patterns with specific evidence from the user's code.

### Anti-Pattern 3: Single-Repo Overfitting
**What it looks like**: 20 rules from one project.
**Why wrong**: May reflect project conventions, not personal preferences.
**Do instead**: Cross-reference across 3+ repos for high confidence.

## References

- [Rule Categories](references/rule-categories.md) -- taxonomy of programming rule types
- ADR: `adr/github-profile-rules.md` -- pipeline architecture decisions
