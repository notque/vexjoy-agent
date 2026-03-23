---
name: comprehensive-review
description: |
  Unified 3-wave code review: Wave 0 auto-discovers packages/modules and
  dispatches one language-specialist agent per package for deep per-package
  analysis. Wave 1 dispatches 11 foundation reviewers in parallel (with Wave 0
  context). Wave 2 dispatches 10 deep-dive reviewers that receive Wave 0+1
  findings as context for targeted analysis. Aggregates all findings by severity,
  then auto-fixes ALL issues. Covers per-package deep review, security, business
  logic, architecture, error handling, test coverage, type design, code quality,
  comment analysis, language idioms, docs validation, performance, concurrency,
  API contracts, dependencies, error messages, dead code, naming, observability,
  config safety, and migration safety.
  Use for "comprehensive review", "full review", "review everything", "review
  and fix", or "thorough code review".
  Do NOT use for single-concern reviews (use individual agents instead).
version: 3.2.0
user-invocable: true
command: /comprehensive-review
model: opus
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - TaskCreate
  - TaskUpdate
  - TaskList
  - EnterWorktree
routing:
  triggers:
    - comprehensive review
    - full review
    - review everything
    - review and fix
    - thorough review
    - multi-agent review
    - complete code review
    - 20-agent review
    - per-package review
    - 3-wave review
  pairs_with:
    - systematic-code-review
    - parallel-code-review
    - systematic-code-review
  force_routing: false
  complexity: Complex
  category: review
---

# Comprehensive Code Review v3 — Three-Wave Hybrid Architecture

Three-wave review with per-package deep analysis. Wave 0 auto-discovers packages/modules and dispatches one language-specialist agent per package to read ALL code in that package. Wave 1 (11 foundation agents) runs in parallel with Wave 0 context. Wave 2 (10 deep-dive agents) receives Wave 0+1 findings for targeted analysis. All findings are aggregated, deduplicated, and auto-fixed.

**How this differs from existing skills**:
- `/parallel-code-review`: 3 agents (security, business, arch) — report only
- `/comprehensive-review`: **20+ agents in 3 waves** — per-package + cross-cutting review AND fix everything

---

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before dispatching reviewers
- **Three-Wave Parallelism**: Wave 0 agents dispatched in batches of 10. Wave 1 agents MUST be dispatched in a SINGLE message. Wave 2 agents MUST be dispatched in a SINGLE message after Wave 1 completes.
- **Context Cascading**: Wave 1 receives Wave 0 per-package findings. Wave 2 receives Wave 0+1 findings.
- **Fix Everything, Defer Nothing**: After all waves complete, fix EVERY finding. No deferrals. No "out of scope." No "will fix later." The only exception is BLOCKED (fix + alternative both break tests, <10% of total).
- **Worktree Isolation**: Fixes happen on a new branch, never on the current working branch directly
- **Severity Aggregation**: Combine findings by severity before fixing
- **Phase Gates Enforced**: Each phase must complete before the next begins
- **No Skipping Agents**: All agents run even for "simple" changes

### Default Behaviors (ON unless disabled)
- **Wave 0 Per-Package Review**: Auto-discover packages/modules and dispatch one agent per package. Adds deep per-package context that cross-cutting agents miss.
- **Smart Agent Selection**: Detect file types and PR context to choose relevant agents
- **Deduplication**: Merge overlapping findings from multiple agents, keep highest severity
- **Fix Verification**: Run tests/linters after each fix batch to catch regressions
- **Report Generation**: Write `comprehensive-review-report.md` to repo root
- **Quick Wins First**: Fix lowest-risk issues first to build momentum

### Optional Behaviors (OFF unless enabled)
- **--review-only**: Skip fix phase, report only (like parallel-code-review)
- **--skip-wave0**: Skip Wave 0 per-package review (faster, less thorough)
- **--wave1-only**: Run only Wave 1 (11 agents), skip Wave 0 and Wave 2
- **--focus [files]**: Review only specified files instead of full diff
- **--severity [critical|high|medium|all]**: Only report/fix findings at or above severity
- **--org-conventions**: Pass organization-specific convention flags to reviewer-language-specialist. Configure organization detection in `scripts/classify-repo.py`.

---

## Instructions

### Phase 1: SCOPE

**Goal**: Determine what to review and which agents to dispatch.

**Step 1: Identify changed files**

```bash
# For unstaged changes:
git diff --name-only

# For staged changes:
git diff --cached --name-only

# For PR context:
gh pr view --json files -q '.files[].path' 2>/dev/null

# Fallback: recent commits
git diff --name-only HEAD~1
```

**Step 2: Detect organization conventions**

```bash
# Auto-detect repo type (deterministic — no LLM judgment needed)
REPO_TYPE=$(python3 scripts/classify-repo.py --type-only 2>/dev/null || echo "personal")
```

If the repo belongs to a protected organization with custom conventions:
- Set convention flags for the rest of this review
- Wave 1 Agent 9 (`reviewer-language-specialist`) gets organization-specific flags appended
- Log: "Organization conventions detected — reviewer-language-specialist will check org-specific patterns"

**Step 3: Understand the three-wave agent roster**

#### Wave 0: Per-Package Deep Review (Auto-Discovered)

One language-specialist agent per discovered package reads ALL code in that package. This wave discovers issues that cross-cutting agents miss because they have full package context.

| Language | Discovery Command | Agent Type | Min Package Size |
|----------|-------------------|------------|-----------------|
| Go | `find . -name "*.go" -path "*/internal/*" \| xargs dirname \| sort -u` | `golang-general-engineer-compact` | 1 file |
| Go (also) | `find . -name "*.go" -not -path "*/internal/*" -not -path "*/vendor/*" \| xargs dirname \| sort -u` | `golang-general-engineer-compact` | 1 file |
| Python | `find . -name "__init__.py" \| xargs dirname \| sort -u` | `python-general-engineer` | 1 file |
| TypeScript | `find . -name "index.ts" -o -name "index.tsx" \| xargs dirname \| sort -u` | `typescript-frontend-engineer` | 1 file |

**Wave 0 produces**: Per-package findings with full context (every file in the package was read). These findings inform Wave 1+2 about package-level patterns, internal APIs, and local code quality.

#### Wave 1: Foundation Agents (Independent Analysis)

These agents run in parallel with Wave 0 per-package findings as context. They perform cross-cutting analysis that spans packages and establish the foundation for Wave 2.

| # | Agent | Focus Area | Key Catches |
|---|-------|------------|-------------|
| 1 | `reviewer-security` | Security | OWASP Top 10, auth, injection, secrets |
| 2 | `reviewer-business-logic` | Domain | Edge cases, state transitions, requirement gaps |
| 3 | Architecture reviewer* | Architecture | Patterns, naming, structure, idioms |
| 4 | `reviewer-silent-failures` | Error Handling | Swallowed errors, empty catches, bad fallbacks |
| 5 | `reviewer-test-analyzer` | Test Coverage | Coverage gaps, fragile tests, missing negative cases |
| 6 | `reviewer-type-design` | Type Design | Weak invariants, leaky encapsulation |
| 7 | `reviewer-code-quality` | Quality/Style | CLAUDE.md violations, convention drift |
| 8 | `reviewer-comment-analyzer` | Documentation | Comment rot, misleading docs, stale TODOs |
| 9 | `reviewer-language-specialist` | Language Idioms | Modern stdlib, concurrency, LLM tells, org-specific rules |
| 10 | `reviewer-docs-validator` | Project Health | README, CLAUDE.md, deps, CI, build system |
| 11 | `reviewer-adr-compliance` | ADR Compliance | Implementation matches ADR decisions, no scope creep |

*Architecture reviewer selection by language:

| File Types | Agent |
|-----------|-------|
| `.go` files | `golang-general-engineer` or `golang-general-engineer-compact` |
| `.py` files | `python-general-engineer` |
| `.ts`/`.tsx` files | `typescript-frontend-engineer` |
| Mixed or other | `Explore` |

#### Wave 2: Deep-Dive Agents (Context-Aware Analysis)

These agents receive Wave 0+1 aggregated findings as input. They perform targeted deep-dives informed by per-package analysis (Wave 0) and cross-cutting analysis (Wave 1).

| # | Agent | Focus Area | Wave 1 Context Used |
|---|-------|------------|---------------------|
| 11 | `reviewer-performance` | Performance | Architecture findings → focus on hot paths |
| 12 | `reviewer-concurrency` | Concurrency | Silent-failure + architecture findings → concurrent paths |
| 13 | `reviewer-api-contract` | API Contracts | Business-logic + type-design findings → contract-sensitive code |
| 14 | `reviewer-dependency-audit` | Dependencies | Docs-validator findings → dependency documentation gaps |
| 15 | `reviewer-error-messages` | Error Messages | Silent-failure + code-quality findings → error paths |
| 16 | `reviewer-dead-code` | Dead Code | Code-quality + docs-validator findings → abandoned artifacts |
| 17 | `reviewer-naming-consistency` | Naming | Code-quality + language-specialist findings → convention baselines |
| 18 | `reviewer-observability` | Observability | Silent-failure findings → observability gaps at failure points |
| 19 | `reviewer-config-safety` | Config Safety | Security + docs-validator findings → config security gaps |
| 20 | `reviewer-migration-safety` | Migration Safety | API-contract + business-logic findings → migration-sensitive changes |

**Step 3: Initialize findings directory**

Create a temporary directory to persist findings across waves. This is critical — without it, context compaction between waves loses all prior findings.

```bash
REVIEW_DIR="/tmp/claude-review/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$REVIEW_DIR"
echo "Review findings directory: $REVIEW_DIR"
```

All subsequent phases MUST write their findings to `$REVIEW_DIR/` and read prior wave findings from there. This ensures findings survive context compaction between waves.

| File | Written By | Read By |
|------|-----------|---------|
| `$REVIEW_DIR/wave0-findings.md` | Phase 1c | Phase 2a, 2b |
| `$REVIEW_DIR/wave1-findings.md` | Phase 2b | Phase 3a |
| `$REVIEW_DIR/wave01-summary.md` | Phase 2b | Phase 3a |
| `$REVIEW_DIR/wave2-findings.md` | Phase 3b | Phase 4 |
| `$REVIEW_DIR/final-report.md` | Phase 3b | Phase 4, Phase 5 |

**Step 4: Create task_plan.md**

```markdown
# Task Plan: Comprehensive Review v3

## Goal
Three-wave review and auto-fix of [N] changed files across [N] packages.

## Phases
- [ ] Phase 1: Scope (identify files, discover packages)
- [ ] Phase 1b: Wave 0 Dispatch (per-package deep review)
- [ ] Phase 1c: Wave 0 Aggregate (per-package findings)
- [ ] Phase 2a: Wave 1 Dispatch (11 foundation agents + Wave 0 context)
- [ ] Phase 2b: Wave 1 Aggregate (collect and summarize Wave 0+1 findings)
- [ ] Phase 3a: Wave 2 Dispatch (10 deep-dive agents with Wave 0+1 context)
- [ ] Phase 3b: Wave 2 Aggregate (merge all agents' findings)
- [ ] Phase 4: Fix (auto-fix on branch)
- [ ] Phase 5: Report (write report, verify)

## Review Profile
- Files: [list]
- Packages discovered: [N]
- Wave 0 agents: [N] (one per package)
- Wave 1 agents: 11
- Wave 2 agents: 10
- Org conventions: [detected org or none]
- Mode: [review+fix | review-only]

## Findings Directory
$REVIEW_DIR = [path from Step 3]

## Status
**Currently in Phase 1** - Discovering packages
```

**Gate**: Files identified, packages discovered, findings directory created, plan created. Proceed to Phase 1b.

---

### Phase 1b: WAVE 0 DISPATCH — Per-Package Deep Review

**Goal**: Dispatch one language-specialist agent per discovered package. Each agent reads ALL files in its package for deep, contextual review.

**Skip if**: `--skip-wave0` flag is set or `--wave1-only` flag is set.

**Step 1: Discover packages**

```bash
# Go packages (internal/ and top-level)
find . -name "*.go" -not -path "*/vendor/*" -not -path "*/.git/*" | xargs dirname | sort -u

# Python packages
find . -name "__init__.py" -not -path "*/venv/*" -not -path "*/.git/*" | xargs dirname | sort -u

# TypeScript modules (directories with index.ts/tsx)
find . -name "index.ts" -o -name "index.tsx" | grep -v node_modules | xargs dirname | sort -u
```

**Step 2: Select agent type per language**

| Language | Agent |
|----------|-------|
| Go | `golang-general-engineer-compact` |
| Python | `python-general-engineer` |
| TypeScript | `typescript-frontend-engineer` |
| Mixed | Use language of majority files in that package |

**Step 3: Dispatch agents in batches of 10**

Each per-package agent gets this prompt:

```
PER-PACKAGE DEEP REVIEW — Wave 0

PACKAGE: [package path]
LANGUAGE: [Go/Python/TypeScript]

MCP TOOL DISCOVERY (do this FIRST, before reading package files):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if this is a Go package, loads type-aware analysis
     tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools
- If gopls tools are available AND LANGUAGE is Go:
  * Use go_file_context after reading each .go file for intra-package dependency context
  * Use go_diagnostics on the package to detect build/analysis errors
  * Use go_symbol_references to check for unused or misused exported symbols
- If Context7 tools are available:
  * Use resolve-library-id + query-docs for unfamiliar library APIs in this package

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Read EVERY file in this package directory: [package path]/
4. Understand the package's purpose, internal APIs, and relationships
5. Review ALL code for issues — you have full package context
6. Use MCP tools (gopls, Context7) as you review for type-aware precision
7. Focus on issues that require understanding the WHOLE package:
   - Internal API misuse between files in this package
   - Inconsistent error handling patterns within the package
   - Missing or redundant functionality
   - Package-level design issues (cohesion, coupling)
   - Test coverage relative to package complexity
8. Use structured output format with severity classification
9. Include file:line references for every finding

CONTEXT: This is Wave 0 of a comprehensive review. Your per-package findings
will be passed to 20 cross-cutting review agents in Waves 1 and 2. Focus on
issues that require full package context to detect — cross-cutting agents will
handle file-level and project-level concerns.

OUTPUT FORMAT:
### PACKAGE: [package path]
**Files reviewed**: [list all files read]
**Package purpose**: [1-sentence summary]
**Package health**: [HEALTHY | MINOR_ISSUES | NEEDS_ATTENTION | CRITICAL]

Findings:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Requires package context**: [Why a single-file reviewer would miss this]
---
```

**CRITICAL**: Dispatch up to 10 agents per message. If more than 10 packages are discovered, use multiple batches:
- Batch 1: packages 1-10 (dispatch in ONE message)
- Batch 2: packages 11-20 (dispatch in ONE message after batch 1 completes)
- Continue until all packages are covered

Use `model: sonnet` for ALL per-package agents. Never use haiku for code review. The orchestrator runs on Opus; dispatched agents run on Sonnet for cost efficiency (40% savings, minimal quality tradeoff).

**Gate**: All per-package agents dispatched and completed. Proceed to Phase 1c.

---

### Phase 1c: WAVE 0 AGGREGATE — Per-Package Summary

**Goal**: Collect Wave 0 findings into a per-package summary for Wave 1+2 context injection.

**Step 1: Collect all Wave 0 findings**

Read each per-package agent's output. Extract: package path, health rating, findings with severity.

**Step 2: Build Wave 0 Summary**

```markdown
## Wave 0 Per-Package Findings Summary (for Wave 1+2 context)

### Packages Reviewed: [N]
### Packages Healthy: [N] | Minor Issues: [N] | Needs Attention: [N] | Critical: [N]

### Per-Package Results

#### [package/path1] — [HEALTHY|MINOR_ISSUES|NEEDS_ATTENTION|CRITICAL]
- Purpose: [1-sentence]
- Files: [N]
- Findings: [N] (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)
- Key issues:
  - [SEVERITY]: [summary] at [file:line]
  - ...

#### [package/path2] — [STATUS]
- ...

### Cross-Package Patterns Detected
- [Pattern 1]: Seen in packages [list] — suggests systemic issue
- [Pattern 2]: ...

### Wave 0 Hotspots (packages with most findings)
1. [package] — [N findings, N critical]
2. [package] — [N findings, N high]
3. ...
```

**Step 3: Identify cross-package patterns**

Look across all per-package results for recurring themes (e.g., "5 packages have inconsistent error handling" or "3 packages missing test files"). These cross-package patterns are especially valuable for Wave 1+2 agents.

**Step 4: Save Wave 0 findings to disk**

Write the complete Wave 0 summary to disk so it survives context compaction:

```bash
# Write Wave 0 findings — this is the source of truth for Wave 1+2
cat > "$REVIEW_DIR/wave0-findings.md" << 'WAVE0_EOF'
[Paste the complete Wave 0 Per-Package Findings Summary here]
WAVE0_EOF
echo "Saved Wave 0 findings: $(wc -l < "$REVIEW_DIR/wave0-findings.md") lines"
```

**CRITICAL**: Do NOT skip this step. If compaction fires before Wave 1 dispatch, Wave 0 findings are gone forever without this file.

**Gate**: Wave 0 summary built, saved to `$REVIEW_DIR/wave0-findings.md`. Proceed to Phase 2a.

---

### Phase 2a: WAVE 1 DISPATCH

**Goal**: Launch all foundation review agents in a SINGLE message for true parallel execution, with Wave 0 per-package context. This dispatches 11 agents.

**CRITICAL**: ALL Wave 1 agent dispatches MUST be in ONE message. Sequential dispatch defeats parallelism.

**Step 0: Load Wave 0 findings from disk**

Before constructing agent prompts, read Wave 0 findings from disk (in case context compaction has occurred):

```bash
WAVE0_CONTEXT=$(cat "$REVIEW_DIR/wave0-findings.md" 2>/dev/null || echo "Wave 0 skipped — no per-package context available")
```

Use `$WAVE0_CONTEXT` in each agent prompt below.

**Model**: Use `model: sonnet` for all Wave 1 agents. The orchestrator (this skill) runs on Opus; dispatched review agents run on Sonnet.

Each agent prompt should include:

```
REVIEW SCOPE:
- Files to review: [list of changed files]
- Change context: [what was changed and why, if known]
- Repository: [current directory]

WAVE 0 PER-PACKAGE CONTEXT (deep per-package review results):
[Insert $WAVE0_CONTEXT — loaded from $REVIEW_DIR/wave0-findings.md]

MCP TOOL DISCOVERY (do this FIRST, before any file reads):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if Go files are in scope, this loads type-aware
     analysis tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools for
     verifying dependency usage and API correctness
- If gopls tools are available AND this is a Go repository:
  * Use go_file_context after reading any .go file to understand intra-package dependencies
  * Use go_symbol_references before flagging unused or misused symbols
  * Use go_diagnostics on files you flag to confirm real vs false-positive issues
- If Context7 tools are available:
  * Use resolve-library-id + query-docs to verify library API usage in flagged code

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Review the Wave 0 per-package context to understand package-level findings
4. Review the specified files for issues in your domain
5. Use Wave 0 findings to AVOID duplicating per-package issues already found
6. Focus on CROSS-CUTTING concerns that span multiple packages
7. Use MCP tools (gopls, Context7) during analysis where they add precision
8. Use structured output format with severity classification
9. Include file:line references for every finding
10. For each finding, provide a concrete fix recommendation

OUTPUT FORMAT:
Return findings as:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Wave 0 Cross-Ref**: [Which Wave 0 package finding this relates to, if any]
---
```

**Agent-specific prompt additions:**

| Agent | Extra Instructions |
|-------|-------------------|
| `reviewer-security` | Focus on OWASP Top 10, auth, input validation, secrets. **MCP**: For Go, use gopls `go_symbol_references` to trace tainted input flows. **CALLER TRACING (mandatory)**: When the diff modifies functions with security-sensitive parameters (auth tokens, filter flags, sentinel values like `"*"`), grep for ALL callers across the repo and verify each validates the parameter. Do NOT trust PR descriptions — verify independently. |
| `reviewer-business-logic` | Focus on requirements coverage, edge cases, state transitions. **CALLER TRACING (mandatory)**: When the diff changes interface semantics or introduces sentinel values, grep for ALL callers (`.MethodName(`) across the repo and verify each honors the contract. Do NOT claim "no caller passes X" without searching. |
| Architecture reviewer | Focus on patterns, naming, structure, maintainability. **MCP**: For Go, use gopls `go_file_context` to understand cross-file dependencies |
| `reviewer-silent-failures` | Focus on catch blocks, error swallowing, fallback behavior. **MCP**: For Go, use gopls `go_diagnostics` to verify error handling correctness |
| `reviewer-test-analyzer` | Focus on coverage gaps, missing edge case tests, test quality. **ASSERTION DEPTH CHECK (mandatory)**: For security-sensitive code, flag presence-only assertions (NotEmpty, NotNil, hasKey). Tests MUST verify actual values, not just existence. |
| `reviewer-type-design` | Focus on invariants, encapsulation, type safety. **MCP**: For Go, use gopls `go_package_api` to understand type surface area |
| `reviewer-code-quality` | Focus on CLAUDE.md compliance, conventions, style |
| `reviewer-comment-analyzer` | Focus on comment accuracy, rot, misleading docs |
| `reviewer-language-specialist` | Detect language from files, check modern stdlib, idioms, concurrency, LLM tells. **MCP**: For Go files, use gopls `go_file_context` and `go_diagnostics` to detect non-idiomatic patterns with type awareness. If org conventions detected, append org-specific flags to prompt. |
| `reviewer-docs-validator` | Check README.md, CLAUDE.md, deps, CI config, build system, LICENSE. Review the project, not the code. **MCP**: Use Context7 to verify documented library versions/APIs match actual usage |
| `reviewer-adr-compliance` | Auto-discover ADRs from `adr/` and `.adr-session.json`. Check every decision point has implementation, no contradictions, no scope creep. Output ADR COMPLIANT or NOT ADR COMPLIANT. |

**Gate**: All Wave 1 agents dispatched in a single message (11 agents). Wait for all to complete. Proceed to Phase 2b.

---

### Phase 2b: WAVE 0+1 AGGREGATE

**Goal**: Collect Wave 0 and Wave 1 findings into a structured summary that becomes Wave 2's input context.

**Step 1: Collect all Wave 1 findings**

Read each Wave 1 agent's output. Extract findings with severity, file, description, and fix.

**Step 2: Build Wave 0+1 Summary**

Create a condensed summary combining Wave 0 per-package findings and Wave 1 cross-cutting findings. This combined summary becomes the context injected into every Wave 2 agent.

```markdown
## Wave 0+1 Findings Summary (for Wave 2 context)

### Wave 0 Per-Package Summary: [N packages reviewed]
- Packages with issues: [list with health status]
- Cross-package patterns: [list]
- Hotspot packages: [top 3 by finding count]
- Key per-package findings:
  - [package]: [SEVERITY] [summary]
  - ...

### Security (Agent 1): [N findings]
- CRITICAL: [list if any]
- HIGH: [list]
- Files with security issues: [list]

### Business Logic (Agent 2): [N findings]
- State transitions identified: [list]
- Edge cases flagged: [list]
- Files with domain issues: [list]

### Architecture (Agent 3): [N findings]
- Architectural patterns noted: [list]
- Hot paths identified: [list]
- Files with structural issues: [list]

### Silent Failures (Agent 4): [N findings]
- Swallowed errors at: [file:line list]
- Error paths without handling: [list]
- Files with error handling gaps: [list]

### Test Coverage (Agent 5): [N findings]
- Coverage gaps: [list]
- Untested paths: [list]

### Type Design (Agent 6): [N findings]
- Weak types identified: [list]
- Type safety issues at: [file:line list]

### Code Quality (Agent 7): [N findings]
- Convention baseline established: [patterns]
- Convention violations: [list]
- CLAUDE.md compliance issues: [list]

### Comments (Agent 8): [N findings]
- Comment rot at: [file:line list]
- Stale TODOs: [list]

### Language Specialist (Agent 9): [N findings]
- Language-specific issues: [list]
- Modern stdlib opportunities: [list]
- LLM code tells: [list]

### Docs & Config (Agent 10): [N findings]
- Documentation gaps: [list]
- Dependency issues: [list]
- CI/build issues: [list]

### ADR Compliance (Agent 11): [N findings]
- ADR decisions not implemented: [list]
- ADR contradictions: [list]
- Scope creep: [list]

```

**Step 3: Quick-deduplicate Wave 0+1**

Identify overlapping findings between Wave 0 per-package agents and Wave 1 cross-cutting agents. Note duplicates for final aggregation but keep all findings in the context — Wave 2 agents benefit from seeing the raw data. Wave 0 findings that were also caught by Wave 1 validate both agents' analysis.

**Step 4: Save Wave 1 findings and combined summary to disk**

Write both raw Wave 1 findings AND the combined Wave 0+1 summary to disk:

```bash
# Save raw Wave 1 findings (individual agent outputs)
cat > "$REVIEW_DIR/wave1-findings.md" << 'WAVE1_EOF'
[Paste ALL Wave 1 agent outputs — the raw findings from each of the 11 agents]
WAVE1_EOF

# Save the combined Wave 0+1 summary (the structured context for Wave 2)
cat > "$REVIEW_DIR/wave01-summary.md" << 'WAVE01_EOF'
[Paste the Wave 0+1 Findings Summary built in Step 2 above]
WAVE01_EOF

echo "Saved Wave 1 findings: $(wc -l < "$REVIEW_DIR/wave1-findings.md") lines"
echo "Saved Wave 0+1 summary: $(wc -l < "$REVIEW_DIR/wave01-summary.md") lines"
```

**CRITICAL**: Do NOT skip this step. Wave 2 agents need the combined summary, and context compaction WILL fire between Wave 1 aggregate and Wave 2 dispatch on large reviews.

**Gate**: Wave 0+1 summary built, saved to `$REVIEW_DIR/wave01-summary.md`. Proceed to Phase 3a.

---

### Phase 3a: WAVE 2 DISPATCH

**Goal**: Launch all 10 deep-dive agents in a SINGLE message, each receiving Wave 0+1 findings summary as context.

**CRITICAL**: ALL 10 Wave 2 agent dispatches MUST be in ONE message.

**Step 0: Load Wave 0+1 findings from disk**

Before constructing agent prompts, reload the combined summary from disk (in case context compaction has occurred since Phase 2b):

```bash
WAVE01_SUMMARY=$(cat "$REVIEW_DIR/wave01-summary.md" 2>/dev/null || echo "ERROR: Wave 0+1 summary not found at $REVIEW_DIR/wave01-summary.md — cannot proceed with Wave 2")
```

If the file is missing, something went wrong in Phase 2b. Re-read `$REVIEW_DIR/wave0-findings.md` and `$REVIEW_DIR/wave1-findings.md` and rebuild the summary before proceeding.

**Model**: Use `model: sonnet` for all Wave 2 agents. The orchestrator (this skill) runs on Opus; dispatched review agents run on Sonnet.

Each Wave 2 agent prompt should include the standard review scope PLUS the Wave 0+1 context:

```
REVIEW SCOPE:
- Files to review: [list of changed files]
- Change context: [what was changed and why, if known]
- Repository: [current directory]

WAVE 0+1 CONTEXT (use this to focus your analysis):
[Insert $WAVE01_SUMMARY — loaded from $REVIEW_DIR/wave01-summary.md]

MCP TOOL DISCOVERY (do this FIRST, before any file reads):
- Use ToolSearch to check for available MCP tools that can enhance your analysis:
  a. Run ToolSearch("gopls") — if Go files are in scope, this loads type-aware
     analysis tools (go_file_context, go_diagnostics, go_symbol_references, etc.)
  b. Run ToolSearch("context7") — loads library documentation lookup tools for
     verifying dependency usage and API correctness
- If gopls tools are available AND this is a Go repository:
  * Use go_file_context after reading any .go file to understand intra-package dependencies
  * Use go_symbol_references before flagging unused or misused symbols
  * Use go_diagnostics on files you flag to confirm real vs false-positive issues
- If Context7 tools are available:
  * Use resolve-library-id + query-docs to verify library API usage in flagged code

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Run MCP TOOL DISCOVERY steps above
3. Review the Wave 0 per-package context for package-level issues already found
4. Review the Wave 1 cross-cutting context for foundation issues already found
5. Use Wave 0+1 findings to FOCUS your deep-dive analysis:
   - Prioritize packages flagged as NEEDS_ATTENTION or CRITICAL by Wave 0
   - Prioritize files and paths flagged by Wave 1
   - Look for issues in YOUR domain that neither Wave 0 nor Wave 1 would catch
   - Cross-reference your findings with both waves to add depth
6. Do NOT simply repeat Wave 0 or Wave 1 findings — add NEW insights
7. Use MCP tools (gopls, Context7) during analysis where they add precision
8. Use structured output format with severity classification
9. Include file:line references for every finding

OUTPUT FORMAT:
Return findings as:
### [CRITICAL|HIGH|MEDIUM|LOW]: [One-line summary]
**File**: `path/to/file:LINE`
**Issue**: [Description]
**Impact**: [Why this matters]
**Fix**: [Concrete code fix]
**Wave 0+1 Cross-Ref**: [Which earlier finding this relates to, if any]
---
```

**Wave 2 agent-specific prompt additions:**

| Agent | Extra Context Instructions |
|-------|--------------------------|
| `reviewer-performance` | Use Wave 0 per-package findings to identify packages with complexity issues. Use Wave 1 architecture findings to identify hot paths. Focus on algorithmic complexity, N+1 queries, allocation waste. **MCP**: For Go, use gopls `go_symbol_references` to trace hot path call chains |
| `reviewer-concurrency` | Use Wave 0 per-package findings for concurrent patterns within packages. Use Wave 1 silent-failure + architecture findings for cross-package concurrent paths. Focus on races, goroutine leaks, deadlocks. **MCP**: For Go, use gopls `go_diagnostics` to detect race condition warnings |
| `reviewer-api-contract` | Use Wave 0 per-package findings to understand internal API surfaces. Use Wave 1 business-logic + type-design findings for contract-sensitive endpoints. Focus on breaking changes, status codes. **MCP**: Use Context7 to verify API contract claims against library docs |
| `reviewer-dependency-audit` | Use Wave 1 docs-validator findings to cross-reference documented vs actual dependencies. Run govulncheck/npm audit/pip-audit. Focus on CVEs, licenses, deprecated packages. **MCP**: Use Context7 `resolve-library-id` + `query-docs` to verify dependency API usage. For Go, use gopls `go_vulncheck` for vulnerability scanning |
| `reviewer-error-messages` | Use Wave 0 per-package error handling patterns. Use Wave 1 silent-failure + code-quality findings. Focus on error message quality, actionability, consistency. |
| `reviewer-dead-code` | Use Wave 0 per-package findings to identify unused internal APIs between files. Use Wave 1 code-quality + docs-validator findings. Focus on unreachable code, unused exports. |
| `reviewer-naming-consistency` | Use Wave 0 per-package naming patterns to detect intra-package drift. Use Wave 1 code-quality + language-specialist findings. Focus on cross-package naming consistency. |
| `reviewer-observability` | Use Wave 0 per-package findings for packages missing instrumentation. Use Wave 1 silent-failure findings for error paths missing observability. Focus on RED metrics gaps. |
| `reviewer-config-safety` | Use Wave 0 per-package findings for hardcoded values within packages. Use Wave 1 security + docs-validator findings. Focus on secrets, missing env var validation. |
| `reviewer-migration-safety` | Use Wave 1 api-contract + business-logic findings to identify migration-sensitive changes. Focus on reversible migrations, deprecation paths, rollback safety. |

**Gate**: All 10 Wave 2 agents dispatched in a single message. Wait for all to complete. Proceed to Phase 3b.

---

### Phase 3b: FULL AGGREGATE

**Goal**: Merge ALL agents' findings (Wave 0 + Wave 1 + Wave 2) into a unified, severity-classified, deduplicated report.

**Step 0: Load all prior wave findings from disk**

Reload all wave findings from disk before aggregating (context compaction may have fired):

```bash
# Reload all wave findings from disk
WAVE0=$(cat "$REVIEW_DIR/wave0-findings.md" 2>/dev/null || echo "")
WAVE1=$(cat "$REVIEW_DIR/wave1-findings.md" 2>/dev/null || echo "")
echo "Loaded Wave 0: $(echo "$WAVE0" | wc -l) lines, Wave 1: $(echo "$WAVE1" | wc -l) lines"
```

**Step 1: Collect all findings**

Combine Wave 0 per-package (from `$REVIEW_DIR/wave0-findings.md`), Wave 1 cross-cutting (from `$REVIEW_DIR/wave1-findings.md`), and Wave 2 deep-dive findings (just returned from agents) into a single list.

**Step 2: Deduplicate across all agents**

If two or more agents flagged the same file:line:
- Keep the highest severity classification
- Merge fix recommendations (later waves may have more targeted fixes)
- Note which agents found it (reinforces importance)
- Prefer Wave 2 fixes when they add Wave 0+1 context (deepest understanding)
- Wave 0 per-package findings confirmed by Wave 1+2 are high-confidence

**Step 3: Classify by severity**

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Security vulnerability, data loss risk, breaking change | Fix immediately |
| HIGH | Significant bug, logic error, silent failure, data race | Fix before merge |
| MEDIUM | Quality issue, missing test, comment rot, naming drift | Fix (auto) |
| LOW | Style preference, minor simplification, documentation | Fix (auto) |

**Step 4: Build full summary matrix**

```
| Agent                    | Wave | CRITICAL | HIGH | MEDIUM | LOW |
|--------------------------|------|----------|------|--------|-----|
| Per-Package: [pkg1]      | 0    | N        | N    | N      | N   |
| Per-Package: [pkg2]      | 0    | N        | N    | N      | N   |
| Per-Package: [...]       | 0    | N        | N    | N      | N   |
| **Wave 0 Subtotal**      | **0**| **N**    | **N**| **N**  | **N**|
| Security                 | 1    | N        | N    | N      | N   |
| Business Logic           | 1    | N        | N    | N      | N   |
| Architecture             | 1    | N        | N    | N      | N   |
| Silent Failures          | 1    | N        | N    | N      | N   |
| Test Coverage            | 1    | N        | N    | N      | N   |
| Type Design              | 1    | N        | N    | N      | N   |
| Code Quality             | 1    | N        | N    | N      | N   |
| Comment Analyzer         | 1    | N        | N    | N      | N   |
| Language Specialist      | 1    | N        | N    | N      | N   |
| Docs & Config            | 1    | N        | N    | N      | N   |
| ADR Compliance           | 1    | N        | N    | N      | N   |
| **Wave 1 Subtotal**      | **1**| **N**    | **N**| **N**  | **N**|
| Performance              | 2    | N        | N    | N      | N   |
| Concurrency              | 2    | N        | N    | N      | N   |
| API Contract             | 2    | N        | N    | N      | N   |
| Dependency Audit         | 2    | N        | N    | N      | N   |
| Error Messages           | 2    | N        | N    | N      | N   |
| Dead Code                | 2    | N        | N    | N      | N   |
| Naming Consistency       | 2    | N        | N    | N      | N   |
| Observability            | 2    | N        | N    | N      | N   |
| Config Safety            | 2    | N        | N    | N      | N   |
| Migration Safety         | 2    | N        | N    | N      | N   |
| **Wave 2 Subtotal**      | **2**| **N**    | **N**| **N**  | **N**|
| **TOTAL**                |      | **N**    | **N**| **N**  | **N**|
```

**Step 5: Save all findings to disk**

Write Wave 2 findings and the final aggregated report to disk:

```bash
# Save Wave 2 raw findings
cat > "$REVIEW_DIR/wave2-findings.md" << 'WAVE2_EOF'
[Paste ALL Wave 2 agent outputs]
WAVE2_EOF

# Save the final deduplicated, severity-classified report
cat > "$REVIEW_DIR/final-report.md" << 'REPORT_EOF'
[Paste the full summary matrix + all classified findings from Steps 3-4]
REPORT_EOF

echo "Saved final report: $(wc -l < "$REVIEW_DIR/final-report.md") lines"
echo "All findings persisted at: $REVIEW_DIR/"
ls -la "$REVIEW_DIR/"
```

**Step 6: Present summary to user**

Show the matrix and full findings list BEFORE proceeding to fixes. If `--review-only`, stop here.

**Gate**: All 20+ agents' findings classified, deduplicated, saved to `$REVIEW_DIR/final-report.md`, matrix built. User informed. Proceed to Phase 4.

---

### Phase 4: FIX

**Goal**: Fix EVERY finding. Zero deferred. Zero "out of scope." Zero "will fix later."

**Step 0: Load findings from disk**

Reload the final report from disk before fixing (context compaction almost certainly fired during the 20+ agent dispatch/aggregate cycle):

```bash
# This is your source of truth for what to fix
cat "$REVIEW_DIR/final-report.md"
```

If the file is missing, rebuild from individual wave files:
```bash
cat "$REVIEW_DIR/wave0-findings.md" "$REVIEW_DIR/wave1-findings.md" "$REVIEW_DIR/wave2-findings.md"
```

**CRITICAL RULE: NO DEFERRED FIXES.** Every finding from every wave MUST be fixed. The only acceptable reason to not fix a finding is if applying it breaks tests — and even then, try an alternative fix before giving up. "Deferred" is not a valid status. "Out of scope" is not a valid reason. If an agent found it, fix it.

**Common deferral rationalizations to REJECT:**

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Pre-existing, not modified by this PR" | The review found it. It's a real issue. Fix it. | Fix it in the same branch — pre-existing bugs are still bugs |
| "Needs follow-up PR" | Follow-up PRs don't happen. Fix it now. | Fix it now — one PR with all fixes |
| "Architectural change required" | If you can describe the fix, you can implement it | Implement the fix, even if it touches multiple files |
| "Needs design decision" | The agent already suggested a fix — use it | Apply the suggested fix or a reasonable alternative |
| "Acceptable risk / low impact" | If it was worth reporting, it's worth fixing | Fix it — the agent wouldn't flag it if it didn't matter |
| "Test-only code, doesn't matter" | Test code quality affects reliability | Fix test code to the same standard as production code |
| "Documentation task / maintenance task" | Docs and maintenance are code. Fix them. | Update the docs, bump the dependency, fix the README |
| "Standard pattern / convention choice" | If an agent flagged it as an issue, the pattern is wrong here | Fix it or explicitly justify in a code comment why it's intentional |
| "Optimization, not a bug" | Performance issues ARE bugs to your users | Apply the optimization |

**Step 1: Create branch**

```bash
# Create fix branch from current HEAD
git checkout -b review-fixes/$(date +%Y%m%d-%H%M%S)
```

Or use `EnterWorktree` for full isolation.

**Step 2: Fix ALL findings by severity (CRITICAL first)**

Order:
1. CRITICAL — fix immediately, test after each
2. HIGH — fix in batch, test after batch
3. MEDIUM — fix in batch, test after batch
4. LOW — fix in batch, test after batch

**Every severity level gets fixed.** LOW findings are not optional. MEDIUM findings are not "nice to have." Fix them all.

For each fix:
1. State which finding is being addressed (wave, agent, severity, file:line)
2. Apply the fix
3. Verify the fix compiles/parses
4. Run relevant tests

```bash
# After each fix batch:
# Go:
go build ./... && go vet ./... && go test ./...
# Python:
python -m py_compile file.py && python -m pytest
# TypeScript:
npx tsc --noEmit && npx vitest run
# Generic:
make check 2>/dev/null || make test 2>/dev/null
```

**Step 3: Apply simplifications and docs fixes LAST**

Run `reviewer-code-simplifier` on already-fixed files (final code polish). Apply `reviewer-docs-validator` fixes after code is finalized (docs should reflect final state). Simplification and docs should be the last changes.

**Step 4: If a fix breaks tests**

1. Revert the specific fix
2. Try an ALTERNATIVE fix that addresses the same finding differently
3. If the alternative also breaks tests, note as "BLOCKED — breaks tests, alternative also failed"
4. Continue with remaining fixes
5. "BLOCKED" items must be fewer than 10% of total findings. If more than 10% are blocked, something is wrong with the fix approach — reassess.

**Step 5: Commit**

```bash
git add -A
git commit -m "fix: apply comprehensive review findings (N fixes across M files)"
```

**Gate**: ALL findings fixed. Tests pass. Zero deferred. Commit created on branch.

---

### Phase 5: REPORT

**Goal**: Generate comprehensive report documenting everything.

Write `comprehensive-review-report.md`:

```markdown
# Comprehensive Code Review Report v3

**Date**: [date]
**Files reviewed**: [N]
**Packages discovered**: [N]
**Agents dispatched**: [N] (Wave 0: [N per-package], Wave 1: 11, Wave 2: 10)
**Total findings**: [N]
**Findings fixed**: [N]
**Findings blocked**: [N] (ONLY if fix breaks tests after alternative attempt — must be <10%)

---

## Verdict: [CLEAN | ALL_FIXED | BLOCKED_ITEMS]

- CLEAN: No findings (rare)
- ALL_FIXED: Every finding was fixed (expected outcome)
- BLOCKED_ITEMS: Some fixes break tests even after alternative attempts (<10%)

[2-3 sentences: Overall assessment. What systemic patterns emerged?
Is the codebase better after fixes?]

## Wave Summary

| Wave | Agents | Findings | Fixed | Unique to Wave |
|------|--------|----------|-------|----------------|
| Wave 0 (Per-Package) | N | N | N | N |
| Wave 1 (Foundation) | 11 | N | N | N |
| Wave 2 (Deep-Dive) | 10 | N | N | N |
| **TOTAL** | **N** | **N** | **N** | |

## Wave 0: Per-Package Results

| Package | Health | Files | Findings | Key Issue |
|---------|--------|-------|----------|-----------|
| [pkg/path1] | HEALTHY | N | N | — |
| [pkg/path2] | NEEDS_ATTENTION | N | N | [biggest] |
| ... | ... | ... | ... | ... |

**Cross-Package Patterns**: [List of patterns seen across multiple packages]

## Agent Summary

| Agent | Wave | Findings | Fixed | Blocked | Key Issue |
|-------|------|----------|-------|---------|-----------|
| Per-Package (total) | 0 | N | N | N | [biggest] |
| Security | 1 | N | N | N | [biggest] |
| Business Logic | 1 | N | N | N | [biggest] |
| Architecture | 1 | N | N | N | [biggest] |
| Silent Failures | 1 | N | N | N | [biggest] |
| Test Coverage | 1 | N | N | N | [biggest] |
| Type Design | 1 | N | N | N | [biggest] |
| Code Quality | 1 | N | N | N | [biggest] |
| Comment Analyzer | 1 | N | N | N | [biggest] |
| Language Specialist | 1 | N | N | N | [biggest] |
| Docs & Config | 1 | N | N | N | [biggest] |
| ADR Compliance | 1 | N | N | N | [biggest] |
| Performance | 2 | N | N | N | [biggest] |
| Concurrency | 2 | N | N | N | [biggest] |
| API Contract | 2 | N | N | N | [biggest] |
| Dependency Audit | 2 | N | N | N | [biggest] |
| Error Messages | 2 | N | N | N | [biggest] |
| Dead Code | 2 | N | N | N | [biggest] |
| Naming Consistency | 2 | N | N | N | [biggest] |
| Observability | 2 | N | N | N | [biggest] |
| Config Safety | 2 | N | N | N | [biggest] |
| Migration Safety | 2 | N | N | N | [biggest] |
| **TOTAL** | | **N** | **N** | **N** | |

## Context Cascade Effectiveness

How each wave's context helped later waves find deeper issues:

| Wave 2 Agent | Wave 0 Context Used | Wave 1 Context Used | Additional Findings Due to Context |
|-------------|--------------------|--------------------|-------------------------------------|
| Performance | Package complexity hotspots | Architecture hot paths | [N findings] |
| Concurrency | Intra-package concurrent patterns | Silent failures + arch | [N findings] |
| ... | ... | ... | ... |

## Findings by Severity

### CRITICAL
[Each finding with before/after code]

### HIGH
[Each finding with before/after code]

### MEDIUM
[Summary with file references]

### LOW
[Brief list]

## Quick Wins Applied
[List of easy fixes that improved quality]

## Blocked Items (if any — must be <10% of total)
[List of findings where fix AND alternative fix both break tests]
[Each must include: what was tried, why it failed, suggested manual approach]

## What's Done Well
[Genuine positives found during review]

## Systemic Recommendations
[2-3 big-picture patterns observed across findings]
```

**Step 2: Note findings location**

Display the findings directory path so the user knows where raw data lives:

```
Review findings persisted at: $REVIEW_DIR/
  wave0-findings.md  — Per-package deep review results
  wave1-findings.md  — Foundation agent results
  wave01-summary.md  — Combined Wave 0+1 context for Wave 2
  wave2-findings.md  — Deep-dive agent results
  final-report.md    — Aggregated, deduplicated, severity-classified
```

These files persist in `/tmp/` until next reboot. They can be re-read in future sessions if needed.

**Gate**: Report written, findings persisted to disk. Display summary to user. Review complete.

---

## Combining with Existing Skills

### When to use which

| Situation | Use This |
|-----------|----------|
| Any PR, any language, full review+fix | `/comprehensive-review` (3 waves) |
| Fast review, skip per-package | `/comprehensive-review --skip-wave0` (2 waves) |
| Quick review, 11 agents only | `/comprehensive-review --wave1-only` |
| Quick 3-reviewer check, no fix | `/parallel-code-review` |
| PR comment validation | `/pr-review-address-feedback` |
| Sequential deep dive | `systematic-code-review` skill |

---

## Error Handling

### Error: "Agent Times Out"
Cause: One or more agents exceed execution time.
Solution:
1. Report findings from completed agents immediately
2. Note which agent(s) timed out
3. Offer to re-run failed agent separately
4. Proceed with partial results — do not block the entire wave

### Error: "Fix Breaks Tests"
Cause: Applied fix introduces a regression.
Solution:
1. Revert the specific fix immediately
2. Try an ALTERNATIVE fix approach for the same finding
3. If alternative also fails, mark as "BLOCKED — both approaches break tests"
4. Continue with remaining fixes
5. Blocked items must be <10% of total — if higher, reassess fix strategy

### Error: "Conflicting Fixes"
Cause: Two agents suggest contradictory fixes for same code.
Solution:
1. Prefer security fix over style fix (security wins)
2. Prefer correctness over simplification
3. Wave 2 fixes with Wave 0+1 context generally have better understanding
4. If genuinely ambiguous, apply the higher-severity agent's fix — never skip

### Error: "No Changed Files Found"
Cause: No git diff, no PR context, no changes to review.
Solution:
1. Ask user: "Which files would you like reviewed?"
2. If user says "everything", scan all source files
3. Warn about review scope and time for large repos

### Error: "No Packages Discovered"
Cause: Wave 0 package discovery finds no packages (no internal/ dirs, no __init__.py, no index.ts).
Solution:
1. Skip Wave 0 entirely — this is not an error
2. Proceed to Wave 1 with note: "Wave 0 skipped — no package structure detected"
3. Wave 1 and Wave 2 still run normally without Wave 0 context

### Error: "Too Many Packages (>30)"
Cause: Large monorepo with many packages discovered.
Solution:
1. Report: "Discovered [N] packages. Wave 0 will require [ceil(N/10)] batches."
2. Proceed with batching — quality matters more than speed
3. Consider filtering to packages containing changed files if reviewing a PR

### Error: "Wave 0/1 Produces No Findings"
Cause: A wave finds nothing to report.
Solution:
1. This is good news — code passed that wave's review
2. Still dispatch subsequent waves with note: "Wave [N] found no issues. Perform independent analysis."
3. Empty findings from early waves are still useful context — they confirm code quality

---

## Anti-Patterns

### AP-1: Sequential Agent Dispatch
**What it looks like**: Sending one Agent call, waiting, then sending the next.
**Why wrong**: Multiplies review time. Agents within a wave are independent.
**Do instead**: ALL Agent dispatches within a wave in ONE message.

### AP-2: Fixing Without Full Review
**What it looks like**: Fixing Wave 1 findings while Wave 2 is still running.
**Why wrong**: Wave 2 may find conflicting or deeper issues. Deduplication requires all results.
**Do instead**: Complete Phase 3b full aggregation before ANY fixes.

### AP-3: Skipping "Trivial" Agents
**What it looks like**: "No new types, skip type-design-analyzer"
**Why wrong**: Existing types in changed files may have issues. Let agents find nothing.
**Do instead**: Run all agents. Empty results are fast and confirm quality.

### AP-4: Fixing on Main Branch
**What it looks like**: Applying fixes directly on the user's current branch.
**Why wrong**: Review fixes should be isolated for easy revert.
**Do instead**: Always create a fix branch or use worktree.

### AP-5: Deferring Fixes
**What it looks like**: Marking findings as "deferred", "out of scope", or "will fix later."
**Why wrong**: Deferred fixes never get fixed. The whole point of comprehensive review is fixing everything now.
**Do instead**: Fix every finding. If a fix breaks tests, try an alternative approach. Only "BLOCKED" (fix + alternative both break tests) is acceptable, and must be <10%.

### AP-6: Skipping Wave 2
**What it looks like**: "Wave 1 found enough, no need for Wave 2."
**Why wrong**: Wave 2 agents find categories of issues Wave 1 cannot (performance, concurrency, naming, etc.).
**Do instead**: Always run all waves unless `--wave1-only` or `--skip-wave0` is explicitly passed.

### AP-7: Not Passing Context Between Waves
**What it looks like**: Dispatching Wave 1 without Wave 0 context, or Wave 2 without Wave 0+1 context.
**Why wrong**: The entire value of multi-wave architecture is context-aware analysis. Each wave enriches the next.
**Do instead**: Always include prior wave findings summaries in every subsequent wave agent prompt.

### AP-8: Dispatching Too Many Per-Package Agents at Once
**What it looks like**: Sending 25 per-package agents in one message.
**Why wrong**: Max 10 agents per message. Exceeding this causes failures.
**Do instead**: Batch Wave 0 agents in groups of 10. Wait for each batch before sending the next.

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Small PR, skip comprehensive" | Small PRs hide big bugs | Run all 3 waves |
| "Tests pass, no review needed" | Tests don't catch all issues | Tests are necessary but not sufficient |
| "Just a style fix" | Style issues compound into tech debt | Fix every finding |
| "Fix phase takes too long" | Finding bugs in prod takes longer | Fix now or fix later at 10x cost |
| "Agent found nothing, wasted" | Confirming quality is valuable | No finding = confidence |
| "I'll fix the LOWs manually later" | Later never comes | Auto-fix everything now |
| "This finding is out of scope" | If an agent found it, it's in scope | Fix it — scope is everything agents report |
| "32 findings deferred" | Deferred = not fixed = failed review | Fix all 32. Zero deferred. |
| "Only actionable findings fixed" | ALL findings are actionable — agents don't report non-actionable things | Fix every finding |
| "Wave 1 is enough" | Wave 2 finds performance, concurrency, naming issues Wave 1 misses | Run all waves |
| "Wave 0 is slow, skip it" | Per-package context catches issues cross-cutting agents miss | Run Wave 0 unless explicitly skipped |
| "Too many packages, batch overhead" | Batching costs tokens, not accuracy | Batch all packages, even if it takes 3+ batches |

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md)
- [Anti-Rationalization Review](../shared-patterns/anti-rationalization-review.md)
- [Severity Classification](../shared-patterns/severity-classification.md)
- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Verification Checklist](../shared-patterns/verification-checklist.md)

### Related Skills & Agents

**Wave 1 Agents:**
- `reviewer-security` — OWASP Top 10, auth, injection, secrets
- `reviewer-business-logic` — Edge cases, state transitions, requirements
- Architecture reviewer — Patterns, structure (language-specific agent)
- `reviewer-silent-failures` — Swallowed errors, empty catches
- `reviewer-test-analyzer` — Coverage gaps, test quality
- `reviewer-type-design` — Invariants, encapsulation
- `reviewer-code-quality` — CLAUDE.md compliance, conventions
- `reviewer-comment-analyzer` — Comment accuracy, rot
- `reviewer-language-specialist` — Modern stdlib, idioms, LLM tells
- `reviewer-docs-validator` — README, CLAUDE.md, deps, CI
- `reviewer-adr-compliance` — ADR compliance, decision mapping, scope creep

**Wave 2 Agents:**
- `reviewer-performance` — Hot paths, N+1, allocations, caching
- `reviewer-concurrency` — Races, goroutine leaks, deadlocks
- `reviewer-api-contract` — Breaking changes, status codes, schemas
- `reviewer-dependency-audit` — CVEs, licenses, deprecated packages
- `reviewer-error-messages` — Actionable errors, context, consistency
- `reviewer-dead-code` — Unreachable code, unused exports, stale flags
- `reviewer-naming-consistency` — Convention drift, acronym casing
- `reviewer-observability` — Metrics, logging, traces, health checks
- `reviewer-config-safety` — Hardcoded values, env vars, secrets
- `reviewer-migration-safety` — Reversible migrations, deprecation paths

**Related Skills:**
- `parallel-code-review` — 3-agent subset (security, business, arch) without fix
- `systematic-code-review` — Sequential 4-phase methodology
- `pr-review-address-feedback` — PR comment validation and triage
