---
name: roast
description: |
  Constructive critique through 5 HackerNews commenter personas with
  evidence-based claim validation. Use when user wants devil's advocacy,
  stress testing, or critical review of ideas, docs, architecture, or code.
  Use for "roast", "critique this", "poke holes", "devil's advocate",
  "stress test", or "what's wrong with". Do NOT use for code review
  (use systematic-code-review), implementation changes, or performance
  profiling without a specific critique request.
version: 2.0.0
user-invocable: true
argument-hint: "<target to critique>"
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Task
  - Skill
context: fork
---

# Roast: Devil's Advocate Analysis

## Operator Context

This skill operates as an operator for critical analysis workflows, configuring Claude's behavior for systematic, evidence-based critique through 5 specialized personas. It implements a **Parallel Analysis + Validation** pattern -- spawn multiple critical perspectives, then validate every claim against actual evidence.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before analysis
- **Over-Engineering Prevention**: Analysis must be direct and focused. No elaborate frameworks beyond the 5-persona + validation workflow
- **Read-Only Enforcement**: NEVER use Write, Edit, or destructive Bash commands. Only Read, Glob, Grep, and read-only Bash operations allowed
- **Evidence-Based Claims**: Every critique must reference specific files, lines, or concrete artifacts. No vague criticisms
- **Validation Required**: All claims must be validated against actual evidence before appearing in final report

### Default Behaviors (ON unless disabled)
- **Five Persona Coverage**: All 5 personas analyze the target for comprehensive perspective coverage
- **Claim Validation**: Coordinator validates all claims and categorizes as VALID, PARTIAL, UNFOUNDED, or SUBJECTIVE
- **Prioritized Reporting**: Final report prioritizes VALID and PARTIAL findings, shows dismissed claims for transparency
- **Strength Inclusion**: Report includes validated strengths, not just problems
- **Constructive Tone**: Agent outputs are synthesized into improvement-oriented language

### Optional Behaviors (OFF unless enabled)
- **Focused Persona Analysis**: User can request specific personas only (e.g., "Just the Senior Engineer perspective")
- **Shallow Review**: Quick critique without full validation for rapid feedback
- **Critique-Only Focus**: Skip strengths section, focus exclusively on issues

## What This Skill CAN Do
- Critique documentation, code, architecture, or ideas through 5 distinct critical perspectives
- Generate specific, evidence-based claims referencing actual files and lines
- Validate all claims against repository contents to separate valid from unfounded critiques
- Produce prioritized, actionable findings backed by concrete evidence
- Identify both weaknesses and validated strengths
- Operate in strict read-only mode without modifying any files
- Surface assumptions, edge cases, operational concerns, and accessibility issues

## What This Skill CANNOT Do
- Make modifications -- strictly read-only analysis, cannot fix issues found
- Execute code or run tests to validate runtime behavior
- Access external resources, APIs, or documentation outside the repository
- Resolve subjective disputes -- can identify style differences but not declare winners
- Replace domain expertise like security auditing or performance profiling
- Skip validation phase -- all claims must be checked against evidence

---

## Instructions

### Phase 1: ACTIVATE READ-ONLY MODE

**Goal**: Establish guardrails before any analysis begins.

Invoke the `read-only-ops` skill:

```
skill: read-only-ops
```

This ensures no modifications can occur during the analysis workflow.

**Allowed operations:**
- `Read` tool for file contents
- `Glob` tool for file patterns
- `Grep` tool for content search
- Bash: `ls`, `wc`, `du`, `git status`, `git log`, `git diff`

**Forbidden operations:**
- `Write` tool -- no file creation
- `Edit` tool -- no file modification
- Bash: `rm`, `mv`, `cp`, `mkdir`, `touch`, `git add`, `git commit`, `git push`

**Gate**: Read-only mode active. Proceed only when gate passes.

### Phase 2: GATHER CONTEXT

**Goal**: Understand the target thoroughly before spawning critical perspectives.

**Step 1: Identify target type**

| Input | Target | Action |
|-------|--------|--------|
| No argument | README.md + repo structure | Read README, survey project layout |
| `@file.md` | Specific file | Read that file, identify related files |
| Description | Described concept | Search repo for related implementation |

**Step 2: Read key files**

Use Read tool to examine: README.md, main documentation, key implementation files relevant to the target.

**Step 3: Survey structure**

Use Glob to map the landscape:
- `**/*.md` for documentation coverage
- Source code organization and entry points
- Configuration files and dependency declarations

**Step 4: Search for patterns**

Use Grep to find: specific claims to verify, usage patterns, dependency references, related test files.

**Step 5: Ground verbal descriptions**

If user describes a concept rather than pointing to a file, search the repo for existing implementation. Critique grounded in actual code beats critique of a strawman every time.

**Gate**: Target identified and sufficient context gathered. Proceed only when gate passes.

### Phase 3: SPAWN ROASTER AGENTS (Parallel)

Launch 5 general-purpose agents in parallel via Task tool, each embodying a roaster persona. Load the full persona specification from the corresponding agent file into each prompt.

**The 5 parallel tasks:**

1. **Skeptical Senior** (`agents/reviewer-skeptical-senior.md`)
   Focus: Sustainability, maintenance burden, long-term viability

2. **Well-Actually Pedant** (`agents/reviewer-pedant.md`)
   Focus: Precision, intellectual honesty, terminological accuracy

3. **Enthusiastic Newcomer** (`agents/reviewer-newcomer.md`)
   Focus: Onboarding experience, documentation clarity, accessibility

4. **Contrarian Provocateur** (`agents/reviewer-contrarian.md`)
   Focus: Fundamental assumptions, alternative approaches

5. **Pragmatic Builder** (`agents/reviewer-pragmatic-builder.md`)
   Focus: Production readiness, operational concerns

Each agent must:
- Invoke `read-only-ops` skill first
- Follow their systematic 5-step review process
- Tag ALL claims as `[CLAIM-N]` with `file:line` references
- Provide specific evidence for every claim

See `references/personas.md` for full prompt template and claim format.

**CRITICAL**: Wait for all 5 agents to complete before proceeding to Phase 4. Do not begin validation on partial results -- all perspectives must be collected first.

**Gate**: All 5 agents complete with tagged claims. Proceed only when gate passes.

### Phase 4: COORDINATE (Validate Claims)

Collect and validate every `[CLAIM-N]` from all 5 agents.

**Step 1: Collect all claims**

Extract every `[CLAIM-N]` tag from all 5 agent outputs. For each, track:
- Claim ID and text
- Source persona (Senior, Pedant, Newcomer, Contrarian, Builder)
- Referenced file:line location

**Step 2: Validate each claim**

For each `[CLAIM-N]`, read the referenced file/line using Read tool and assign a verdict:

| Verdict | Meaning | Criteria |
|---------|---------|----------|
| VALID | Claim is accurate | Evidence directly supports it |
| PARTIAL | Overstated but has merit | Some truth, some exaggeration |
| UNFOUNDED | Not supported | Evidence contradicts or doesn't exist |
| SUBJECTIVE | Opinion, can't verify | Matter of preference/style |

**Step 3: Cross-reference**

Note claims found independently by multiple agents -- these carry higher confidence. If 3+ personas independently identify the same issue, escalate to HIGH priority regardless of individual severity.

**Step 4: Prioritize**

Sort VALID and PARTIAL findings by impact:
- **HIGH**: Core functionality, security, or maintainability
- **MEDIUM**: Important improvements with moderate impact
- **LOW**: Minor issues or polish

**Gate**: All claims validated with evidence. Proceed only when gate passes.

### Phase 5: SYNTHESIZE (Generate Report)

**Goal**: Transform aggressive persona outputs into constructive, actionable report.

Follow the full template in `references/report-template.md`. Key synthesis rules:

1. **Filter by verdict**: Only VALID and PARTIAL claims appear in improvement opportunities
2. **Dismissed section**: UNFOUNDED claims go in dismissed section with evidence showing why
3. **Subjective section**: SUBJECTIVE claims noted as opinion-based, user decides
4. **Strengths required**: Coordinator validates what works well -- not just problems
5. **Constructive tone**: Strip sarcasm, mockery, dismissive language from agent outputs. Preserve technical accuracy and file references.
6. **Implementation roadmap**: Group actions by immediacy (immediate / short-term / long-term)

```markdown
## Claim Validation Summary

| Claim | Agent | Verdict | Evidence |
|-------|-------|---------|----------|
| [CLAIM-1] | Senior | VALID | [file:line shows X] |
| [CLAIM-2] | Pedant | PARTIAL | [true that X, but Y mitigates] |
| [CLAIM-3] | Newcomer | UNFOUNDED | [code shows otherwise] |
```

**Gate**: Report complete with all sections populated. Analysis done.

---

## Examples

### Example 1: Roast a README
User says: "Roast this repo"
```
skill: roast
```
Actions:
1. Activate read-only mode (Phase 1)
2. Read README.md, survey repo structure, identify key files (Phase 2)
3. Spawn 5 persona agents in parallel, each analyzing README + structure (Phase 3)
4. Collect all [CLAIM-N] tags, validate each against actual files (Phase 4)
5. Synthesize constructive report with prioritized improvement opportunities (Phase 5)
Result: Evidence-based critique with actionable improvements and validated strengths

### Example 2: Roast a Design Doc
User says: "Poke holes in the architecture doc"
```
skill: roast @README.md
```
Actions:
1. Activate read-only mode, read the target document (Phases 1-2)
2. Survey related implementation files referenced by the doc (Phase 2)
3. Spawn 5 agents focused on that document and its claims (Phase 3)
4. Validate claims against both doc content and referenced code (Phase 4)
5. Report with architecture-specific improvements and alternatives (Phase 5)
Result: Multi-perspective architecture review grounded in implementation

### Example 3: Roast an Approach
User says: "Devil's advocate on using SQLite for the error learning database"
```
skill: roast the idea of using SQLite for the error learning database
```
Actions:
1. Search repo for existing SQLite implementation and related code (Phase 2)
2. Spawn agents to critique both the concept AND actual code found (Phase 3)
3. Validate claims against implementation evidence (Phase 4)
4. Report grounded in real code, not just theoretical critique (Phase 5)
Result: Critique anchored in actual implementation, not a strawman

---

## Error Handling

### Error: "Agent Returns Claims Without File References"
Cause: Persona agent skipped evidence-gathering or analyzed verbally
Solution:
1. Dismiss ungrounded claims as UNFOUNDED
2. If majority of claims lack references, re-run that specific agent with explicit instruction to cite file:line
3. Never promote ungrounded claims to the validated findings section

### Error: "Read-Only Mode Not Activated"
Cause: Phase 1 skipped or `read-only-ops` skill invocation failed
Solution:
1. Stop all analysis immediately
2. Invoke `read-only-ops` before proceeding
3. If skill unavailable, manually enforce: no Write, Edit, or destructive Bash

### Error: "Agent Attempts to Fix Issues"
Cause: Persona agent crossed from analysis into implementation
Solution:
1. Discard any modifications attempted
2. Extract only the analytical findings from that agent's output
3. Remind: this is read-only analysis, fixes are the user's decision

### Error: "No Target Found or Empty Repository"
Cause: User invoked roast without specifying target and no README.md exists
Solution:
1. Check for alternative entry points: CONTRIBUTING.md, docs/, main source files
2. If repo has code but no docs, analyze the code structure and entry points
3. If truly empty, inform user and ask for a specific file or concept to analyze

---

## Anti-Patterns

### Anti-Pattern 1: Vague, Unsupported Claims
**What it looks like**: `[CLAIM-1] The error handling seems insufficient`
**Why wrong**: No file/line reference, cannot be validated, not actionable
**Do instead**: `[CLAIM-1] No error handling in process_request() (server.py:45-67)`

### Anti-Pattern 2: Skipping Validation Phase
**What it looks like**: Generating 5 persona critiques then jumping straight to action items
**Why wrong**: Persona critiques may be incorrect or overstated. Unfounded claims pollute findings.
**Do instead**: Validate every claim against actual evidence before including in report

### Anti-Pattern 3: All-Negative Critique
**What it looks like**: 5 personas list problems, report ends with 15 prioritized issues, no strengths
**Why wrong**: Demotivating, ignores what works, unbalanced perspective
**Do instead**: Coordinator validates strengths too. Include "Validated Strengths" section.

### Anti-Pattern 4: Fixing Instead of Reporting
**What it looks like**: Builder agent finds missing error handling, uses Edit tool to add it
**Why wrong**: Violates read-only constraint. User didn't ask for changes.
**Do instead**: Report the finding with evidence and suggested action. User decides.

### Anti-Pattern 5: Analyzing Without Context
**What it looks like**: User says "roast this approach", agent critiques verbal description without checking repo
**Why wrong**: Misses existing implementation, may critique a strawman
**Do instead**: Search repo for related code first. Ground critique in actual evidence.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I can see the issue, no need to validate" | Visual inspection misses nuance | Validate every claim against evidence |
| "All 5 agents agree, must be true" | Consensus doesn't mean correct | Still verify against actual files |
| "User just wants a quick roast" | Quick doesn't mean unvalidated | Run validation, skip only if shallow mode |
| "This claim is obviously valid" | Obviously is a rationalization word | Read the file, check the line |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Full report output template with tone transformation rules
- `${CLAUDE_SKILL_DIR}/references/personas.md`: Persona specifications, prompt template, and claim format
- `agents/reviewer-skeptical-senior.md`: Senior engineer persona
- `agents/reviewer-pedant.md`: Pedant persona
- `agents/reviewer-newcomer.md`: Newcomer persona
- `agents/reviewer-contrarian.md`: Contrarian persona
- `agents/reviewer-pragmatic-builder.md`: Builder persona

### Dependencies
- **read-only-ops skill**: Enforces no-modification guardrails during analysis
