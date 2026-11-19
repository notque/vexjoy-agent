# GitHub profile rules

Load this reference when you extract coding conventions and style rules from a GitHub user's public profile through the API. The `github-profile-rules` workflow pipeline (`~/.claude/skills/workflow/references/github-profile-rules.md`) runs the phases; this reference holds the domain rules.

Covers:
- **GitHub REST API**: endpoints for repos, file trees, raw content, commits, pull requests, and reviews
- **Code pattern recognition**: naming, style, architecture, and testing habits from code samples
- **Rule confidence scoring**: frequency-based (high = 3+ repos, medium = 2, low = 1) with cross-signal validation
- **CLAUDE.md rule formatting**: specific, actionable rules for Claude Code workflows

Practices:
- API-only data fetching (no git clone, no subprocess git)
- Rate limit awareness (check X-RateLimit-Remaining)
- PR reviews given > code authored for preference signals
- Confidence scoring prevents over-fitting to single-repo quirks

Priorities, in order: (1) actionability — every rule specific enough to follow; (2) evidence — every rule cites the repos or reviews where the pattern appears; (3) non-contradiction; (4) scoping — each rule says when it applies (language, context, project type). Extract what the developer actually does, not theoretical best practice.

## Rules

### Hardcoded Behaviors (Always Apply)
- **API-Only Constraint**: All GitHub data fetching via REST API. Never use git clone, git commands, or subprocess calls to git.
- **Rate Limit Respect**: Always check X-RateLimit-Remaining before making API calls. Back off when remaining < 10.
- **Privacy Boundary**: Only access public data. Never attempt to access private repos or authenticated-only endpoints without an explicit user token.

### Verification STOP Block
- **Before emitting any rule**: STOP. Verify the rule cites at least one repo and file where the pattern was observed. A rule without evidence is a guess, not an extraction. If you cannot point to a concrete code example, drop the rule.

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report findings with evidence counts. Show rule categories and confidence levels rather than raw data.
- **Top-Repos-First**: Analyze repos sorted by stars/activity, not alphabetically. Most active repos reveal strongest patterns.
- **Review-Priority**: Weight PR review comments higher than authored code for preference signals.

### Optional Behaviors (OFF unless enabled)
- **Verbose API Logging**: Show each API call and response status
- **Raw Data Export**: Save intermediate API responses alongside final rules
- **Cross-Profile Comparison**: Compare extracted rules across multiple GitHub users

## Capabilities & Limitations

### What It Covers
- Fetch and analyze public repos, files, commits, and PR reviews via GitHub REST API
- Sample code files across multiple repos to identify cross-repo patterns
- Extract and categorize programming rules (naming, style, architecture, testing, error handling, documentation)
- Score rule confidence based on frequency across repos and reviews
- Output rules in CLAUDE.md-compatible markdown and structured JSON formats

### Out of Scope
- **Clone repositories**: All data comes via API. For local repo analysis, call the Skill tool with `assessment`.
- **Access private repos**: Without an explicit user-provided token, only public data is available.
- **Guarantee completeness**: API rate limits and sampling constraints mean not all code is analyzed.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Rule taxonomy, confidence scoring, CLAUDE.md output format | `github-profile-rules/rule-categories.md` | Category taxonomy, confidence model, evidence requirements |
| API rate limits, pagination, file tree fetching, auth patterns | `github-profile-rules/github-api-patterns.md` | Efficient endpoint sequence, decode patterns, error-fix mappings |

GitHub REST API docs: https://docs.github.com/en/rest

## Error Handling

### Error: GitHub API Rate Limit Exceeded
**Cause**: Too many API requests without authentication or within the rate window.
**Solution**: Check `X-RateLimit-Remaining` header. If near zero, wait until `X-RateLimit-Reset` timestamp. Suggest user provides `--token` for higher limits (5000 req/hr vs 60 req/hr).

### Error: User Not Found or No Public Repos
**Cause**: Invalid username or user has no public repositories.
**Solution**: Verify username via `GET /users/{username}`. If 404, report the user doesn't exist. If 200 but `public_repos` is 0, report no public data available.

### Error: Insufficient Data for Rule Extraction
**Cause**: User has very few repos (< 3) or very little code, making pattern detection unreliable.
**Solution**: Report that confidence scoring is limited. Lower thresholds: high = 2+ repos, medium = 1 repo with multiple files. Flag all rules as low confidence.

## Patterns to Detect and Fix

### Pattern 1: API-Based Repository Analysis
**What it looks like**: Using `git clone` or subprocess git commands to fetch code.
**Why wrong**: Violates the API-only constraint. Cloning is slow, disk-heavy, and unnecessary when the API provides file content endpoints.
**Do instead**: Use `GET /repos/{owner}/{repo}/contents/{path}` for file content, `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1` for file trees.

### Pattern 2: Cross-Repository Validation
**What it looks like**: Extracting 20 rules from one large repo without checking other repos.
**Why wrong**: Project-specific conventions (e.g., a framework's naming) don't represent the developer's general preferences.
**Do instead**: Always cross-reference patterns across 3+ repos before marking as high confidence.

### Pattern 3: Evidence-Backed Rules
**What it looks like**: Producing rules like "Use meaningful variable names" without citing specific examples from the profile.
**Why wrong**: Generic advice is not personalized. The value is in specific, evidence-backed patterns unique to this developer.
**Do instead**: Every rule must cite at least one repo + file where the pattern was observed.

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "One repo is enough to establish a pattern" | Single-repo patterns may be project-specific | Cross-reference across 3+ repos for high confidence |
| "This generic rule probably applies" | Generic rules add no value over existing best practices | Only extract rules with profile-specific evidence |
| "Rate limits make full analysis impossible" | Sampling + prioritization works within limits | Sample strategically, analyze top repos first |

## Blocker Criteria

Resolve routine issues from repository evidence and existing authorization. When you are sure, decide, record the assumption in your report, and continue; ask Jev when genuinely unsure. Ask only when these situations leave a material decision uncovered:

Rows marked **(owner)** guard production, destructive, credential, public-exposure, or persistence actions; stop and get explicit owner confirmation before acting on those.

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Username returns 404 | Cannot proceed without valid target | "User '{username}' not found. Check spelling?" |
| Rate limit exhausted with no token **(owner)** | Cannot fetch more data | "Rate limit hit. Provide a GitHub token for 5000 req/hr?" |
| Conflicting patterns detected | User may have context on intent | "Found conflicting patterns: X in repos A,B vs Y in repo C. Which reflects current preference?" |
