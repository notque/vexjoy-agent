---
name: explore-pipeline
description: |
  Systematic 4-phase codebase exploration pipeline: Scan, Map, Analyze, Report
  with parallel subagents. Use when user asks to "understand codebase", "explore
  repo", "how does X work", "map architecture", or "explain this code". Do NOT
  use for code changes, debugging, refactoring, or any task that modifies files.
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
- Skip any of the 4 phases

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

### Phase 4: REPORT

**Goal**: Produce a structured, reusable exploration report.

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
