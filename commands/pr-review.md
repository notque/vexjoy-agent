---
description: "Comprehensive PR review using specialized agents, with automatic retro knowledge capture"
argument-hint: "[review-aspects]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Agent"]
---

# Comprehensive PR Review (with Retro Learning)

Comprehensive PR review using specialized agents, with automatic knowledge capture.

This is a local fork of `pr-review-toolkit:review-pr` with a retro learning phase that
records review patterns to the knowledge store.

## Usage

```
/pr-review              # Full review (all aspects)
/pr-review tests errors # Specific aspects only
/pr-review all parallel # All agents in parallel
```

**Related**: `/pr-review-address-feedback` — Process existing GitHub reviewer comments (validate-then-fix workflow)

## Review Aspects

- **comments** - Analyze code comment accuracy and maintainability
- **tests** - Review test coverage quality and completeness
- **errors** - Check error handling for silent failures
- **types** - Analyze type design and invariants (if new types added)
- **code** - General code review for project guidelines
- **simplify** - Simplify code for clarity and maintainability
- **all** - Run all applicable reviews (default)

## Instructions for Claude

**Review Aspects (optional):** "$ARGUMENTS"

### Phase 1: Determine Review Scope

1. Check git status to identify changed files: `git diff --name-only`
2. Parse arguments to see if user requested specific review aspects
3. Default: Run all applicable reviews
4. Check if PR already exists: `gh pr view 2>/dev/null`

### Phase 2: Identify Applicable Reviews

Based on changes:
- **Always applicable**: code-reviewer (general quality)
- **If test files changed**: pr-test-analyzer
- **If comments/docs added**: comment-analyzer
- **If error handling changed**: silent-failure-hunter
- **If types added/modified**: type-design-analyzer
- **If organization Go project** (see Phase 3 detection): organization-specific reviewer for convention compliance
- **After passing review**: code-simplifier (polish and refine)

### Phase 3: Detect Languages and Domain

Before launching agents, detect the primary language(s) of changed files:
- `.go` files → Go domain
- `.py` files → Python domain
- `.ts`/`.tsx` files → TypeScript domain
- `.md` files → Documentation domain

**Organization detection** (run this when Go files are present):
Check if this is an organization-specific Go project using ANY of:
1. Session context contains an org marker (injected by operator-context-detector hook at session start)
2. `go.mod` contains organization-specific imports
3. Module path matches organization patterns

If any check passes → **org domain**: add organization-specific reviewer to the agent list for Phase 4.

This determines which retro topics are relevant in Phase 8.

### Phase 4: Launch Review Agents

Use the pr-review-toolkit plugin agents (they're already available):

**Sequential approach** (default):
- Easier to understand and act on
- Each report is complete before next

**Parallel approach** (when user passes "parallel"):
- Launch all agents simultaneously via Agent tool
- Faster for comprehensive review

Each review agent MUST write its findings to a file (e.g., `pr-review-findings.md`) before returning. This prevents context compaction from losing review output.

### Phase 5: Aggregate Results

After agents complete, summarize:
- **Critical Issues** (must fix before merge)
- **Important Issues** (should fix)
- **Suggestions** (nice to have)
- **Positive Observations** (what's good)

### Phase 6: Provide Action Plan

```markdown
# PR Review Summary

## Critical Issues (X found)
- [agent-name]: Issue description [file:line]

## Important Issues (X found)
- [agent-name]: Issue description [file:line]

## Suggestions (X found)
- [agent-name]: Suggestion [file:line]

## Strengths
- What's well-done in this PR

## Recommended Action
1. Fix critical issues first
2. Address important issues
3. Consider suggestions
4. Re-run review after fixes
```

### Phase 7: Apply Fixes (if requested)

If the user asks to fix issues, apply the fixes using the code-simplifier agent or direct edits.

### Phase 8: Retro Learning (ALWAYS run after review completes)

After the review is complete and results are presented, extract reusable patterns.

**Step 1: Identify what was learned**

Review the findings from all agents and ask:
- Did we discover a recurring code pattern (good or bad) worth remembering?
- Did a specific review agent find something that applies broadly to this language/domain?
- Did we find a project-specific convention violation that should be documented?
- Did we discover a testing gap pattern that recurs across PRs?

If nothing reusable was learned, skip recording. Generic findings like "add more tests" are NOT worth recording.

**Step 2: Record via retro-record-adhoc**

For each reusable finding, call:

```bash
python3 ~/.claude/scripts/feature-state.py retro-record-adhoc TOPIC KEY "VALUE"
```

Where:
- **TOPIC**: Match the domain detected in Phase 3:
  - Go code → `go-patterns`
  - Python code → `python-patterns`
  - TypeScript code → `typescript-patterns`
  - Testing patterns → `testing`
  - Error handling patterns → `debugging`
  - General review patterns → `code-review-patterns`
- **KEY**: Short kebab-case identifier (e.g., `missing-context-cancel-check`, `n-plus-one-in-handler`)
- **VALUE**: 1-2 sentence specific, actionable finding. Not generic advice.

**Step 3: Report what was learned**

After the review summary, add a brief learning section:

```
LEARNED: [key] → [topic]
  [one-line value]
```

**Quality gate for recordings**:

| Record this | Don't record this |
|-------------|-------------------|
| "Missing defer rows.Close() in 3 of 5 SQL handlers" | "Close database resources" |
| "Test assertions check status code but never response body" | "Add more assertions" |
| "Error wrapping loses original context in middleware chain" | "Improve error handling" |
| "Unused exported types in api/ package suggest dead code" | "Remove unused code" |

Only record findings that are specific enough to be actionable guidance for future reviews.

## Agent Descriptions

**comment-analyzer**: Verifies comment accuracy vs code, identifies comment rot, checks documentation completeness.

**pr-test-analyzer**: Reviews behavioral test coverage, identifies critical gaps, evaluates test quality.

**silent-failure-hunter**: Finds silent failures, reviews catch blocks, checks error logging.

**type-design-analyzer**: Analyzes type encapsulation, reviews invariant expression, rates type design quality (4 dimensions, 1-10 each).

**code-reviewer**: Checks CLAUDE.md compliance, detects bugs and issues, reviews general code quality.

**code-simplifier**: Simplifies complex code, improves clarity and readability, applies project standards, preserves functionality.

## Tips

- **Run early**: Before creating PR, not after
- **Focus on changes**: Agents analyze git diff by default
- **Address critical first**: Fix high-priority issues before lower priority
- **Re-run after fixes**: Verify issues are resolved
- **Use specific reviews**: Target specific aspects when you know the concern
- **Learning accumulates**: Each review adds to the retro knowledge store, making future reviews smarter
