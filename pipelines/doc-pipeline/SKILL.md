---
name: doc-pipeline
description: |
  Structured 5-phase documentation pipeline: Research, Outline, Generate,
  Verify, Output. Use when user asks to "document this", "create README",
  "write documentation", "generate docs", or any technical documentation
  task requiring research and accuracy. Do NOT use for editing existing
  docs, writing blog posts, or non-technical content creation.
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
context: fork
command: /doc
routing:
  triggers:
    - document this
    - create readme
    - write documentation
    - document codebase
    - generate docs
    - technical documentation
  pairs_with:
    - codebase-overview
    - technical-documentation-engineer
  complexity: medium
  category: documentation
---

# Documentation Pipeline Skill

## Operator Context

This skill operates as an operator for structured documentation creation, configuring Claude's behavior for thorough, research-backed technical writing. It implements the **Pipeline** architectural pattern -- Research, Outline, Generate, Verify, Output -- with **Artifact Persistence** at each phase ensuring no work is lost to context decay.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before any documentation work
- **Research Before Writing**: NEVER draft documentation without completing research phase first
- **Verify All Examples**: Every code example must be executed and proven to work
- **Artifact Persistence**: Each phase produces a saved file, not just context
- **Scope Discipline**: Document what exists. Do not document aspirational features or planned work.

### Default Behaviors (ON unless disabled)
- **Parallel Research**: Launch subagents for code analysis, usage patterns, and context gathering simultaneously
- **Save Phase Artifacts**: Write `doc-research.md`, `doc-outline.md`, `doc-draft.md` at each phase
- **Run Code Examples**: Execute all code snippets to confirm correctness before including them
- **Natural Voice**: Use clear, direct prose. Avoid corporate jargon and sterile technical writing.
- **Audience Awareness**: Identify target audience in research phase and write at their level

### Optional Behaviors (OFF unless enabled)
- **Skip Research**: Use `--skip-research` for trivial docs where subject is already well-understood
- **Draft Only**: Use `--draft` to produce documentation without verification phase
- **Voice Override**: Use `--voice [name]` to apply a specific voice profile instead of default

## What This Skill CAN Do
- Create documentation from scratch through structured research and generation
- Run parallel subagents to gather code analysis, usage patterns, and context simultaneously
- Verify code examples, installation steps, and API signatures against actual code
- Produce phased artifacts so work survives context limits
- Generate READMEs, API docs, usage guides, and technical reference material

## What This Skill CANNOT Do
- Edit or update existing documentation in place (use manual editing instead)
- Write blog posts or marketing content (use research-to-article instead)
- Generate documentation without researching the subject first
- Skip verification of code examples (broken examples are worse than no examples)
- Produce documentation for code that does not yet exist

---

## Instructions

### Phase 1: RESEARCH

**Goal**: Gather comprehensive understanding of the subject before writing a single line of documentation.

**Step 1: Launch parallel subagents**

Three subagents run simultaneously with a 5-minute timeout:

| Subagent | Focus | Output |
|----------|-------|--------|
| Code Analysis | Components, public APIs, dependencies, configuration | Structured findings |
| Usage Patterns | Test examples, common patterns, edge cases, error scenarios | Examples with context |
| Context Gathering | Problem solved, audience, prerequisites, related docs | Context summary |

**Step 2: Compile research**

Merge subagent findings into a single research document. Resolve any contradictions between subagents by re-reading the actual source code.

**Step 3: Save artifact**

Write compiled research to `doc-research.md` in the working directory.

**Gate**: Research artifact exists with findings from all three subagents. Subject is understood well enough to outline. Proceed only when gate passes.

### Phase 2: OUTLINE

**Goal**: Structure documentation based on research findings before generating prose.

**Step 1: Identify sections**

Standard documentation structure (adapt based on subject):

```markdown
# [Subject]
## Overview        - What it is, what problem it solves
## Setup           - Installation, configuration, prerequisites
## Quick Start     - Minimal working example
## Usage           - Detailed usage with examples
## API Reference   - Function/method signatures (if applicable)
## Troubleshooting - Common issues and solutions
## See Also        - Related documentation
```

**Step 2: Assign research to sections**

Map each research finding to the section where it belongs. Identify gaps where research is insufficient and gather additional information.

**Step 3: Save artifact**

Write outline to `doc-outline.md` in the working directory.

**Gate**: Outline covers all necessary sections. Every section has assigned content from research. No gaps remain. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Write documentation that is clear, accurate, and useful to the target audience.

**Step 1: Load context**

Read `doc-research.md` and `doc-outline.md` to ground generation in verified facts.

**Step 2: Write each section**

For each outlined section:
- Write in clear, direct prose. Avoid filler phrases and unnecessary hedging.
- Include working code examples drawn from research findings
- Assume the reader's knowledge level matches the identified audience
- Start with what the user needs to know most urgently

**Step 3: Save artifact**

Write complete draft to `doc-draft.md` in the working directory.

**Gate**: Draft covers every section from the outline. All code examples are included. No placeholder text remains. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Prove every claim and example in the documentation is accurate.

**Step 1: Execute code examples**

Run every code snippet in the documentation. Capture output. Compare against documented expectations.

**Step 2: Validate API signatures**

Cross-reference every function name, parameter, and return type against actual source code.

**Step 3: Check installation steps**

If the documentation includes setup instructions, execute them in order and confirm they work.

**Step 4: Fix issues**

For each verification failure:
1. Determine whether the documentation or the example is wrong
2. Fix the documentation to match reality (not the other way around)
3. Re-verify the fixed section

Maximum 3 fix-and-verify iterations. If still failing after 3 attempts, flag the section with a `<!-- NEEDS REVIEW -->` comment and proceed.

**Gate**: All code examples execute. API signatures match source. Installation steps work. Proceed only when gate passes.

### Phase 5: OUTPUT

**Goal**: Deliver final documentation to its target location.

**Step 1: Write to target**

Copy verified documentation to the requested output location. If no location specified, write to the most logical path in the repository.

**Step 2: Produce verification report**

Append a brief summary of what was verified:

```markdown
<!-- Verification Report
- Code examples: X/Y passed
- API signatures: verified against source
- Installation steps: executed successfully
- Generated: [date]
-->
```

**Step 3: Clean up artifacts**

Remove `doc-research.md`, `doc-outline.md`, and `doc-draft.md` unless the user requests they be kept.

**Gate**: Final documentation exists at target location. Verification report attached. Artifacts cleaned up.

---

## Error Handling

### Error: "Subagent Timeout During Research"
Cause: Subject is too broad or codebase is very large, causing subagents to exceed 5-minute timeout
Solution:
1. Narrow the research scope to a specific module or component
2. Re-launch only the timed-out subagent with a more focused prompt
3. If still timing out, run research sequentially instead of in parallel

### Error: "Code Examples Fail Verification"
Cause: Examples were derived from outdated patterns, test mocks, or incomplete context
Solution:
1. Re-read the actual source code for the function being demonstrated
2. Check if the function requires specific setup or environment
3. Rewrite the example based on working test cases in the codebase
4. If the function itself is broken, document the limitation rather than a broken example

### Error: "Research Finds No Usage Patterns"
Cause: Code is new, untested, or internal-only with no existing consumers
Solution:
1. Check git history for how the author used the code in commits
2. Look for related test files that exercise the code paths
3. Read the code directly and construct examples from the API surface
4. Flag the documentation as "based on API analysis, not observed usage"

---

## Anti-Patterns

### Anti-Pattern 1: Writing Without Research
**What it looks like**: Jumping straight to generating prose based on a quick glance at the code
**Why wrong**: Produces shallow documentation that misses edge cases, prerequisites, and actual usage patterns. Users will not trust docs that omit critical details.
**Do instead**: Complete Phase 1 fully. Save the research artifact. Only then proceed to outlining.

### Anti-Pattern 2: Documenting Aspirational Features
**What it looks like**: "This module will support clustering in the future" or documenting planned APIs
**Why wrong**: Users try to use documented features and fail. Aspirational docs rot faster than any other kind.
**Do instead**: Document only what exists and works today. Use a roadmap file for future plans.

### Anti-Pattern 3: Unverified Code Examples
**What it looks like**: Including code snippets that "should work" without executing them
**Why wrong**: Broken examples destroy documentation credibility. One bad example makes users distrust all examples.
**Do instead**: Execute every example in Phase 4. If it fails, fix it or remove it.

### Anti-Pattern 4: Over-Documentation
**What it looks like**: Documenting every private method, internal constant, and implementation detail
**Why wrong**: Readers cannot find what they need in a wall of irrelevant detail. Signal-to-noise ratio collapses.
**Do instead**: Focus on public APIs, common tasks, and what users actually need to accomplish.

### Anti-Pattern 5: Sterile Corporate Voice
**What it looks like**: "The system leverages enterprise-grade functionality to facilitate documentation workflows"
**Why wrong**: Nobody reads documentation that sounds like a press release. Users skim past corporate filler.
**Do instead**: Write like you are explaining to a colleague. Be direct. Be specific. Cut filler.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations during research and verification
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks before declaring documentation done
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Standard pipeline phase structure and artifact management

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know this code well enough to skip research" | Familiarity breeds blind spots | Complete Phase 1, save artifact |
| "Examples are obvious, no need to run them" | Obvious examples break in surprising ways | Execute every example in Phase 4 |
| "Draft is good enough, skip verification" | Unverified docs erode trust over time | Complete Phase 4 fully |
| "Nobody reads this section anyway" | You don't know what users read | Document all outlined sections |
