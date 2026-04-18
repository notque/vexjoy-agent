---
name: pr-review
description: "Comprehensive PR review using specialized agents, with automatic retro knowledge capture"
version: 1.0.0
user-invocable: true
allowed-tools:
  - Bash
  - Glob
  - Grep
  - Read
  - Agent
routing:
  triggers:
    - pr review
    - review pr
    - review pull request
    - review changes
    - review this pr
    - review my changes
  category: review
  complexity: Complex
---

# Comprehensive PR Review (with Retro Learning)

Comprehensive PR review using specialized agents, with automatic knowledge capture.

This is a local fork of `pr-review-toolkit:review-pr` with a retro learning phase that records review patterns to the knowledge store.

## Scope

This skill accepts either a PR reference or a local branch diff. You do not need an open PR to use it.

| Invocation form | What it reviews |
|----------------|-----------------|
| No argument | Uncommitted and committed local changes against the base branch (`HEAD` vs base) |
| PR number or URL | The diff of the specified open PR |

When no argument is provided, the skill reads `git diff` to determine changed files. When a PR number or URL is provided, it fetches the PR diff via `gh pr view`. All review phases and retro learning apply in both cases.

## Usage

```
/do pr review              # Full review (all aspects)
/do review pr tests errors # Specific aspects only
/do review pr all parallel # All agents in parallel
```

## Review Aspects

- **comments** - Analyze code comment accuracy and maintainability
- **tests** - Review test coverage quality and completeness
- **errors** - Check error handling for silent failures
- **types** - Analyze type design and invariants (if new types added)
- **code** - General code review for project guidelines
- **simplify** - Simplify code for clarity and maintainability
- **all** - Run all applicable reviews (default)

## Instructions

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

**gopls MCP Integration** (MANDATORY when `.go` files are in the diff):

When Go files are detected in the changed files, the review MUST use gopls MCP tools to provide type-aware context to all downstream review agents:

1. Run `ToolSearch("gopls")` to fetch gopls tool schemas
2. Call `go_workspace` to understand module structure, build configuration, and workspace layout
3. Call `go_file_context` on EACH changed `.go` file to get intra-package dependency context
4. Collect all type-aware context and pass it as structured input to every review agent dispatched in Phase 4

If gopls MCP is unavailable (ToolSearch returns no results), fall back to Grep-based analysis but note the limitation in the review output.

### Phase 3.5: Caller Tracing (MANDATORY for Go signature/semantic changes)

**Trigger**: MANDATORY for Go projects when the diff modifies any of:
- Function or method signatures (parameters added/removed/retyped)
- Parameter semantics (e.g., a parameter now accepts sentinel values like `"*"`)
- Exported symbols (new exports, changed interfaces)
- Sentinel or special values introduced (constants, magic strings, wildcard patterns)

**Skip condition**: If the diff only modifies function bodies without changing signatures, skip to Phase 4.

**Steps**:
1. Identify changed symbols from the diff
2. Find ALL callers using gopls `go_symbol_references` or Grep
3. Verify each call site has been updated for the new signature/semantics
4. Trace security-sensitive parameters to their source
5. Document results in structured format

Critical finding rule: Any unvalidated caller passing user-controlled input to a security-sensitive parameter is a **Critical** finding.

### Phase 4: Launch Review Agents

Use the pr-review-toolkit plugin agents (they're already available):

**Sequential approach** (default): Easier to understand and act on

**Parallel approach** (when user passes "parallel"): Launch all agents simultaneously via Agent tool

Each review agent MUST write its findings to a file (e.g., `pr-review-findings.md`) before returning to prevent context compaction from losing review output.

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
## Suggestions (X found)
## Strengths
## Recommended Action
```

### Phase 7: Apply Fixes (if requested)

If the user asks to fix issues, apply the fixes using the code-simplifier agent or direct edits.

### Phase 8: Retro Learning (ALWAYS run after review completes)

After the review is complete, extract reusable patterns.

**Step 1: Identify what was learned**

Review the findings from all agents and ask:
- Did we discover a recurring code pattern (good or bad) worth remembering?
- Did a specific review agent find something that applies broadly to this language/domain?
- Did we find a project-specific convention violation that should be documented?

If nothing reusable was learned, skip recording. Generic findings like "add more tests" are NOT worth recording.

**Step 2: Record via retro-record-adhoc**

For each reusable finding:

```bash
python3 ~/.claude/scripts/feature-state.py retro-record-adhoc TOPIC KEY "VALUE"
```

Where TOPIC matches the domain detected in Phase 3: `go-patterns`, `python-patterns`, `typescript-patterns`, `testing`, `debugging`, or `code-review-patterns`.

**Quality gate for recordings**:

| Record this | Don't record this |
|-------------|-------------------|
| "Missing defer rows.Close() in 3 of 5 SQL handlers" | "Close database resources" |
| "Test assertions check status code but never response body" | "Add more assertions" |

Only record findings that are specific enough to be actionable guidance for future reviews.

## Agent Descriptions

**comment-analyzer**: Verifies comment accuracy vs code, identifies comment rot, checks documentation completeness.

**pr-test-analyzer**: Reviews behavioral test coverage, identifies critical gaps, evaluates test quality.

**silent-failure-hunter**: Finds silent failures, reviews catch blocks, checks error logging.

**type-design-analyzer**: Analyzes type encapsulation, reviews invariant expression, rates type design quality.

**code-reviewer**: Checks CLAUDE.md compliance, detects bugs and issues, reviews general code quality.

**code-simplifier**: Simplifies complex code, improves clarity and readability, applies project standards, preserves functionality.
