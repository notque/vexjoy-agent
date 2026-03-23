---
name: explore-pipeline
description: |
  Systematic codebase exploration pipeline with parallel subagents and
  tiered depth. Quick: 1 phase (targeted lookup). Standard: 4 phases
  (Scan, Map, Analyze, Report). Deep: 8 phases (Scan, Map, Analyze,
  Compile, Assess, Synthesize, Refine, Report) for quality evaluation,
  consistency assessment, and pattern analysis across the codebase.
  Use when user asks to "understand codebase", "explore repo", "how does
  X work", "map architecture", "explain this code", "analyze quality of",
  "assess consistency of", or "evaluate patterns in". Do NOT use for code
  changes, debugging, refactoring, or any task that modifies files.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Task
context: fork
command: /explore
routing:
  triggers:
    - understand codebase
    - explore repo
    - how does this work
    - codebase exploration
    - understand this code
    - map architecture
    - analyze quality
    - assess consistency
    - evaluate patterns
    - analyze codebase
  pairs_with:
    - codebase-overview
    - codebase-analyzer
    - technical-documentation-engineer
  complexity: medium
  category: exploration
---

# Exploration Pipeline

## Operator Context

This skill operates as an operator for systematic codebase exploration, configuring Claude's behavior for structured, read-only investigation. It implements the **Pipeline Architecture** pattern — parallel scan, structured mapping, deep analysis, artifact-based reporting — with **Domain Intelligence** embedded in the exploration methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before exploring
- **Over-Engineering Prevention**: Explore what was asked. No speculative scope expansion, no "while I'm here" tangents into unrelated subsystems
- **Read-Only**: This pipeline NEVER modifies source code, configs, or tests
- **Artifacts at Every Phase**: Save findings to files; context is ephemeral
- **Structured Output**: Always produce a structured exploration report
- **Scope Discipline**: Answer the exploration question; do not generate improvement recommendations unless explicitly asked

### Default Behaviors (ON unless disabled)
- **Parallel Scanning**: Launch 3 parallel subagents for initial scan
- **Architecture Mapping**: Map component relationships and data flow
- **Save Report**: Save findings to `exploration-report.md`
- **Entry Point Tracing**: Identify main executables, CLI entry points, API routes
- **Pattern Detection**: Identify naming conventions, directory organization, error handling patterns
- **Dependency Mapping**: Trace component relationships and dependency graphs

### Optional Behaviors (OFF unless enabled)
- **Deep Dive**: Use `--deep` for comprehensive multi-layer analysis
- **Quick Mode**: Use `--quick` for high-level overview only (skip Phase 3)
- **Specific Focus**: Use `--focus [area]` to constrain exploration to a single component
- **Explicit Tier Selection**: Use `--tier quick|standard|deep` to set exploration depth (see Tiered Depth Model below)

## What This Skill CAN Do
- Systematically scan repository structure using parallel subagents
- Map architecture layers, component relationships, and data flow
- Identify patterns, conventions, and key abstractions
- Produce structured, reusable exploration reports saved as artifacts
- Trace entry points and execution paths through the codebase

## What This Skill CANNOT Do
- Modify any files in the repository (read-only)
- Debug or fix bugs (use systematic-debugging instead)
- Refactor code (use systematic-refactoring instead)
- Generate documentation (use technical-documentation-engineer instead)
- Skip phases within the selected tier (Quick: Phase 1; Standard: 1-3,8; Deep: all 8)

---

## Instructions

### Phase 1: SCAN (Parallel Subagents)

**Goal**: Gather broad structural understanding through parallel investigation.

Launch 3 scanners in parallel using Task:

**Structure Scanner:**
- List all top-level directories and their purposes
- Identify language(s) and frameworks used
- Find configuration files (build, CI, linting, env)
- Locate test directories and test infrastructure
- Identify build, deploy, and infrastructure files

**Entry Point Scanner:**
- Find main executables (main.py, main.go, index.ts, etc.)
- Identify CLI entry points and argument parsers
- Locate API route definitions and server startup
- Find worker, background job, or queue entry points
- Return list with file paths and brief descriptions

**Pattern Detector:**
- Detect naming conventions (files, functions, variables)
- Identify directory organization patterns
- Catalog import and dependency patterns
- Analyze error handling approach
- Identify testing patterns and coverage strategy

**Gate**: All 3 scanners have returned results. If a scanner times out after 5 minutes, proceed with available data. Minimum 2 of 3 scanners MUST complete. Proceed only when gate passes.

### Phase 2: MAP

**Goal**: Create an architecture map from scan findings.

**Step 1: Identify layers**

Determine the architectural layers present (presentation, application, domain, infrastructure, or whatever pattern the codebase uses).

**Step 2: Map component relationships**

For each major component discovered in Phase 1:
- What does it depend on?
- What depends on it?
- How does data flow between components?

**Step 3: Save architecture artifact**

Save `architecture-map.md` with layer diagram, component relationships, and data flow.

**Gate**: Architecture map saved as artifact with component relationships documented. Proceed only when gate passes.

### Phase 3: ANALYZE

**Goal**: Deep investigation of key areas identified in Phases 1-2.

**Step 1: Analyze core abstractions**

For each key component identified in the architecture map:
1. What is its single responsibility?
2. What patterns does it implement?
3. How is it configured?
4. How is it tested?

**Step 2: Trace critical paths**

Follow the most important execution paths end-to-end (e.g., request lifecycle, data pipeline, event processing).

**Step 3: Identify conventions**

Document the implicit rules: how errors propagate, how state is managed, how components communicate.

**Gate**: Key components analyzed with evidence from actual code. Critical paths traced. Proceed only when gate passes.

### Phase 4: COMPILE (Deep tier only)

**Goal**: Structure raw findings from Phases 1-3 into a structured corpus for evaluation.

**Step 1: Categorize findings**

Group all Phase 1-3 findings by evaluation dimension:
- **Consistency**: Same pattern used everywhere, or mixed approaches?
- **Quality**: Meets best practices? Error handling complete? Tests adequate?
- **Coverage**: Any gaps? Components without tests, docs, or error handling?
- **Patterns**: What patterns recur? What's the dominant approach?

**Step 2: Build comparison matrix**

Create a structured table comparing components against each dimension. Save as `analysis-compilation.md`.

**Gate**: Findings structured into evaluation dimensions with per-component data. Compilation artifact saved.

### Phase 5: ASSESS (Deep tier only)

**Goal**: Evaluate the compiled findings against quality criteria.

**Step 1: Score each dimension**

For each evaluation dimension from Phase 4:
- Rate compliance as a percentage (X/Y components follow the pattern)
- Identify outliers (components that deviate from the norm)
- Assess severity of deviations (cosmetic vs functional vs safety)

**Step 2: Identify root causes**

For each deviation found:
- Is it intentional (documented exception) or accidental (drift)?
- Is it a one-off or a recurring pattern?
- What's the fix complexity (trivial, moderate, significant)?

**Gate**: All dimensions scored with evidence. Deviations cataloged with root causes.

### Phase 6: SYNTHESIZE (Deep tier only)

**Goal**: Combine assessment findings into actionable recommendations.

**Step 1: Rank findings by impact**

| Severity | Criteria |
|----------|----------|
| Critical | Safety issue, data loss risk, session-blocking |
| High | Functional gap, inconsistency that causes confusion |
| Medium | Quality gap, missing best practice |
| Low | Cosmetic, style preference |

**Step 2: Group by theme**

Cluster related findings into themes (e.g., "error handling consistency", "test coverage gaps", "naming drift").

**Gate**: Findings ranked by severity, grouped by theme.

### Phase 7: REFINE (Deep tier only)

**Goal**: Verify findings against actual code before reporting.

**Step 1: Spot-check top findings**

For the top 5 findings by severity, re-read the actual source code to confirm the finding is accurate. Adjust if the initial analysis was wrong.

**Step 2: Remove false positives**

If spot-checking reveals a finding was incorrect (e.g., the pattern is actually intentional), remove it from the report.

**Gate**: Top findings verified against source. False positives removed.

### Phase 8: REPORT (final phase for all tiers)

**Goal**: Produce a structured, reusable exploration report.

**Standard tier**: This is effectively Phase 4 (Phases 4-7 were skipped). Report covers architecture and patterns.
**Deep tier**: This is Phase 8. Report includes everything from Standard PLUS quality assessment, consistency scores, and ranked recommendations from Phases 4-7.

Generate and save `exploration-report.md` following this structure:

```markdown
# Codebase Exploration Report

## Executive Summary
[2-3 sentence overview of what this codebase does and how]

## Quick Facts
- Language: [primary language(s)]
- Framework: [main framework(s)]
- Architecture: [pattern name, e.g., layered, hexagonal, microservices]
- Test Strategy: [how tests are organized]

## Architecture Overview
[Layer diagram and component relationships from Phase 2]

## Key Components
### [Component Name]
- Purpose: [single responsibility]
- Location: [file path(s)]
- Dependencies: [what it uses]
- Dependents: [what uses it]

## Patterns and Conventions
- [Pattern]: [example with file reference]

## Critical Paths
- [Path name]: [entry point] -> [intermediate steps] -> [result]

## Next Steps for Understanding
1. Read [file] for [reason]
2. Trace [flow] to understand [concept]
```

**Gate**: Report saved to file with all sections populated from evidence gathered in prior phases. Report references actual file paths. Proceed only when gate passes.

---

## Error Handling

### Error: "Repository Too Large for Parallel Scan"
Cause: Monorepo or very large codebase overwhelms scanners
Solution:
1. Constrain scan to top 2 directory levels
2. Focus scanners on specific subdirectories if `--focus` provided
3. Use Glob patterns to sample representative files rather than exhaustive listing

### Error: "Scanner Subagent Timed Out"
Cause: Subagent stuck on large directory traversal or slow file reads
Solution:
1. Proceed with results from completed scanners (minimum 2 of 3)
2. Fill gaps with targeted manual investigation in Phase 3
3. Note incomplete coverage in the final report

### Error: "Architecture Pattern Not Clear"
Cause: Codebase lacks conventional structure or uses unfamiliar patterns
Solution:
1. Document what IS present rather than forcing a known pattern
2. Trace entry points to understand actual flow
3. Report "unconventional structure" with observed organization

---

## Anti-Patterns

### Anti-Pattern 1: Random File Reading
**What it looks like**: Opening files without a plan, hoping to stumble on understanding
**Why wrong**: Produces incomplete, biased picture weighted toward whatever was read first
**Do instead**: Systematic parallel scan with defined focus areas

### Anti-Pattern 2: No Saved Artifacts
**What it looks like**: Exploring entirely in context without saving findings to files
**Why wrong**: Knowledge lost when context compresses; cannot be reused across sessions
**Do instead**: Save architecture map and report to files at each phase

### Anti-Pattern 3: Skipping the Map Phase
**What it looks like**: Jumping from scanning straight to analysis
**Why wrong**: Misses component relationships; analysis lacks structural context
**Do instead**: Always create architecture map before deep analysis

### Anti-Pattern 4: Generating Recommendations Unsolicited
**What it looks like**: "Here are 10 things I would improve about this codebase"
**Why wrong**: User asked to understand, not to change. Scope creep wastes time and adds noise.
**Do instead**: Report what exists. Only recommend if user explicitly asks.

### Anti-Pattern 5: Same Depth for Every Question
**What it looks like**: Running all 4 phases with parallel scanners when the user just wants to know "what ORM does this use?"
**Why wrong**: Wastes time and tokens. A 15-minute pipeline for a 2-minute question erodes trust in the tool.
**Do instead**: Match depth to the question. Use the Tiered Depth Model below to select the right scope.

---

## Tiered Depth Model

Not every exploration question needs the same depth. Running a full pipeline for a quick fact-check wastes time; running a shallow scan for onboarding misses critical context. The tier is determined by the caller, not guessed. If depth is unspecified, default to **Standard**.

### Quick Verify (2-5 minutes)

**Purpose**: Confirm a specific fact about the codebase.

**Scope**: Answer one question. Read only the files necessary to answer it. No document generation -- the answer IS the output.

**Phases used**: Phase 1 (SCAN) only -- single targeted scanner, not parallel.

**Exit criteria**: Question answered with file path evidence, or "could not determine" with a list of what was checked.

**Examples**:
- "Does this project use dependency injection?"
- "What ORM does the API use?"
- "Is there a CI pipeline configured?"
- "What version of React is this using?"

**Output format**: Direct answer in conversation (no saved report file).

### Standard (15-30 minutes)

**Purpose**: Understand a subsystem or map one area of the codebase.

**Scope**: All 4 phases execute. Parallel scanners in Phase 1. Produce a single structured document covering the targeted area.

**Phases used**: All 4 phases (SCAN, MAP, ANALYZE, REPORT).

**Exit criteria**: Report covers the subsystem's boundaries, key patterns, and integration points. Saved as `exploration-report.md`.

**Examples**:
- "How does authentication work in this app?"
- "Map the payment processing flow."
- "Explain how the event system works."
- "What's the testing strategy for this repo?"

**Output format**: Saved `exploration-report.md` with all sections.

### Deep Dive (1+ hour)

**Purpose**: Full analysis — architectural understanding PLUS quality evaluation, consistency assessment, and pattern analysis.

**Scope**: All 8 phases. Phases 1-3 explore the codebase. Phases 4-7 compile findings, assess quality, synthesize recommendations, and verify against source. Phase 8 produces a comprehensive report.

**Phases used**: All 8 phases: SCAN → MAP → ANALYZE → COMPILE → ASSESS → SYNTHESIZE → REFINE → REPORT.

**Exit criteria**: Comprehensive report covers full architecture, quality assessment with scores, consistency evaluation, pattern analysis, and ranked recommendations. Multiple artifact files produced.

**Examples**:
- "I'm new to this codebase, give me the full picture."
- "We're considering a major refactor -- what do we need to know?"
- "Analyze the quality and consistency of our error handling."
- "Assess which patterns are used consistently vs inconsistently."
- "Full architectural review before we plan next quarter."
- "Evaluate the test coverage patterns across all modules."

**Output format**: Saved `exploration-report.md` plus supplementary files (`architecture-map.md`, `analysis-compilation.md`, component-specific documents as needed).

### Tier Selection Logic

```
If user specifies --tier or --quick or --deep:
  Use the specified tier.
Else if user asks a single specific question (what/which/does/is):
  Use Quick Verify.
Else if user asks to analyze/assess/evaluate/audit quality or patterns:
  Use Deep Dive (needs COMPILE + ASSESS + SYNTHESIZE + REFINE phases).
Else if user asks about a specific subsystem or flow:
  Use Standard.
Else if user asks for full picture / onboarding / comprehensive:
  Use Deep Dive.
Else:
  Default to Standard.
```

---

## Source Hierarchy for Research

When exploration requires looking up external information (framework conventions, library APIs, configuration options), follow this source hierarchy strictly. Lower-quality sources introduce hallucination risk -- a wrong framework convention applied confidently is worse than admitting uncertainty.

### Hierarchy (highest to lowest priority)

1. **Context7 MCP** (preferred) -- Use `resolve-library-id` then `query-docs` for up-to-date library documentation. This is the most reliable source because it pulls directly from official package documentation.
2. **Official documentation** -- Framework and library official docs via WebFetch if Context7 does not cover the library.
3. **Web search** -- Use WebSearch as a fallback when Context7 and official docs are insufficient. Cross-reference multiple results before citing.

### Rules

- **Never guess framework conventions** -- If you cannot confirm a convention from the source hierarchy, state "could not confirm" rather than assuming.
- **Cite the source tier** -- When reporting externally-sourced information, note where it came from: "(confirmed via Context7)", "(from official docs)", or "(from web search -- verify independently)".
- **Source code is ground truth** -- External documentation describes how things SHOULD work. The codebase shows how things ACTUALLY work. When they conflict, report both and flag the discrepancy.
- **Web search results degrade fastest** -- Blog posts and Stack Overflow answers may reference outdated APIs. Always note the date if visible and prefer recent results.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Pipeline design principles

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I read enough files to understand" | Sampling bias skews understanding | Complete all 3 parallel scans |
| "Architecture is obvious, skip mapping" | Obvious to whom? Document it. | Save architecture-map.md |
| "Quick overview is good enough" | Quick overviews miss relationships | Complete all 4 phases unless --quick |
| "I'll remember the structure" | Context compresses; memory is unreliable | Save artifacts to files |
