---
name: skill-creation-pipeline
description: |
  Formal 5-phase pipeline for creating new skills with quality gates:
  DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE. Prevents skill
  duplication, enforces complexity tier selection, validates quality before
  routing integration. Use when creating new skills for the agent system.
  Use for "create skill pipeline", "new skill formal", "skill with gates".
version: 1.0.0
user-invocable: false
agent: skill-creator-engineer
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
routing:
  force_route: true
  triggers:
    - create skill pipeline
    - new skill formal
    - skill with gates
    - "create skill formally"
    - "new skill with gates"
    - "skill creation pipeline"
    - "formal skill creation"
  pairs_with:
    - agent-evaluation
    - routing-table-updater
  complexity: Medium
  category: meta
---

# Skill Creation Pipeline

## Operator Context

This pipeline wraps `skill-creator-engineer` with explicit discovery, design
review, and validation gates. It is the **formal path** for creating new skills
— as opposed to ad-hoc creation — and should be used whenever skill quality,
uniqueness, or routing correctness is important. The pipeline does not replace
the creator agent; it provides the scaffolding around it.

### Hardcoded Behaviors (Always Apply)
- **DISCOVER Before Any Files**: Phase 1 (DISCOVER) must complete before any
  SKILL.md is written. No exceptions. This prevents duplicate skills from being
  added to the repo.
- **ADR Check in DISCOVER**: During Phase 1, check for active ADR session (`.adr-session.json`) and run `python3 ~/.claude/scripts/adr-query.py list` to find related ADRs. If an active session exists, read relevant sections via `adr-query.py context --role skill-creator`. If creating a new skill as part of a pipeline, verify the ADR hash before proceeding.
- **Group-Prefix Naming**: New skills MUST use the same prefix as related existing skills. During DISCOVER, run `ls skills/ | grep {domain}` to find the group. Examples: voice skills start with `voice-`, Go skills with `go-`, PR skills with `pr-`, writing/content skills with `writing-`, review skills with `review-`. If no group exists, the new skill starts one. The directory name and the `name:` frontmatter field must match.
- **Design Brief Before SCAFFOLD**: Phase 2 (DESIGN) must produce a saved design
  brief before Phase 3 begins. Writing a skill without a tier decision and phase
  list produces inconsistent results.
- **Score Before INTEGRATE**: Phase 4 (VALIDATE) must call `agent-evaluation` on
  the new SKILL.md and produce a numeric score before Phase 5 begins. Self-
  assessment ("this looks good") does not satisfy this gate.
- **Minimum Grade B**: A new skill must score 75+ to proceed to integration. If
  it scores below 75, return to Phase 3 (SCAFFOLD) and fix before re-scoring. Max
  3 iterations — after that, surface the scoring breakdown to the user.
- **INDEX.json Update Is Non-Optional**: Phase 5 (INTEGRATE) must add the new
  skill to `skills/INDEX.json`. A skill that exists on disk but not in the index
  is invisible to routing.

### Default Behaviors (ON unless disabled)
- **Overlap Threshold at 70%**: In DISCOVER, if an existing skill covers ≥70%
  of the requested domain, surface the overlap and recommend extending rather
  than creating. Proceed only after a deliberate "create new" decision.
- **Complexity Tier Confirmation**: If the tier is ambiguous (user's description
  could fit Simple or Medium, or Medium vs. Complex), ask before proceeding to
  SCAFFOLD. Tier errors are cheaper to fix in DESIGN than after SCAFFOLD.
- **Save Design Brief to File**: Write the DESIGN output to
  `skills/{name}/design-brief.md` before SCAFFOLD begins. This file is the
  single source of truth for Phase 3.

### Optional Behaviors (OFF unless enabled)
- **Skip DISCOVER**: Skip the duplication check (enable with "skip discover" or
  "I've already checked for duplicates"). Use only when the skill name is
  intentionally novel and overlap checking is unnecessary.
- **Skip VALIDATE**: Skip agent-evaluation scoring (enable with "skip validation"
  or "quick creation"). Accepts the risk of lower quality at integration time.
- **Auto-Approve Design Brief**: Proceed from DESIGN to SCAFFOLD without
  confirming the tier (enable with "auto" or "no confirmation needed").

## What This Skill CAN Do
- Detect overlap with existing skills before any files are written
- Select the appropriate complexity tier based on the skill's requirements
- Generate a complete SKILL.md following AGENT_TEMPLATE_V2.md patterns
- Score the result against the agent-evaluation rubric (100-point scale)
- Wire the new skill into `skills/INDEX.json` and prompt routing updates

## What This Skill CANNOT Do
- Create agents — use `agent-creator-engineer` for new agents
- Update routing tables autonomously — Phase 5 prompts the update, but
  `routing-table-updater` or manual edits handle the actual changes
- Guarantee an A-grade on first pass — iteration may be required
- Modify existing skills — use direct editing or `system-upgrade` for that

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Prevent duplication by scanning the existing skill and agent indexes
before any files are written.

**Step 1**: Extract the domain keywords from the user's request. These are the
terms that describe what the skill does (e.g., "code review", "branch naming",
"Go testing", "PR creation").

**Step 2**: Search `skills/INDEX.json` for existing skills with overlapping
descriptions or triggers.

```bash
# Search INDEX for keyword overlap
grep -i "<keyword>" /path/to/skills/INDEX.json
```

Also search `agents/INDEX.json` for agents that already handle this domain as
part of their core capability.

**Step 3**: For each potentially overlapping skill, read its SKILL.md description
and phase list. Estimate overlap percentage based on:
- Same domain verbs (review, create, debug, deploy)
- Same target artifact (Go files, PRs, branches, agents)
- Same phase structure (does the existing skill already cover what's needed?)

**Step 4**: Report findings.

```
DISCOVER RESULTS
================

Request: [user's skill description in one line]
Keywords: [extracted keywords]

Existing skills checked: [N]

[If no overlap found:]
  No overlap found. Safe to create new skill.
  Proceeding to DESIGN.

[If overlap found:]
  Overlap detected:

  skills/[name]/SKILL.md — [estimated overlap]% overlap
    Description: [first 2 lines of their description]
    Why it overlaps: [1 sentence]

  Recommendation: [Extend existing skill | Create new skill]
  Reason: [1 sentence]
```

**Gate**: If overlap ≥70% with any existing skill, present the recommendation
and wait for the user's decision. If the user says "create new anyway" or
"extend" the existing skill, act accordingly. If <70% overlap, proceed
automatically to Phase 2.

---

### Phase 2: DESIGN

**Goal**: Choose the complexity tier and produce a complete design brief before
any SKILL.md content is written.

**Step 1**: Classify the skill's complexity tier.

| Tier | Characteristics | Phase Count | Fan-Out |
|------|----------------|-------------|---------|
| **Simple** | Single-step or linear workflow, no coordination | 1–3 phases | None |
| **Medium** | Multi-step with optional branching or parallel work | 3–5 phases | Optional |
| **Complex** | Multi-agent coordination, fan-out required | 5+ phases | Required |
| **Comprehensive** | Cross-system pipeline, multi-phase with full validation | 5+ phases + validation | Multi-agent |

Use these signals to classify:
- "Generate one file" → Simple
- "Review then fix" → Medium
- "Parallel agents + verdict synthesis" → Complex
- "Full lifecycle with before/after scoring" → Comprehensive

**Step 2**: Draft the design brief.

```
DESIGN BRIEF: [skill-name]
==========================

Complexity Tier: [Simple | Medium | Complex | Comprehensive]
Agent Binding:   skill-creator-engineer (default) or [other agent if domain-specific]
User-Invocable:  [true | false]

Phases:
  1. [Phase name]: [one-line description]
  2. [Phase name]: [one-line description]
  ...

Reference Files Needed:
  - [file or "none"]

Key Behaviors (Hardcoded):
  - [behavior]

Anti-Patterns to Prevent:
  - [pattern]
```

**Step 3**: If the tier is unambiguous given the request, auto-select and note
the reason. If ambiguous (the request could reasonably fit two tiers), present
both options and ask the user to choose before proceeding.

**Step 4**: Save the design brief.

Write to `skills/{name}/design-brief.md`.

**Gate**: Design brief saved. Tier confirmed (either auto-selected with rationale
or user-confirmed). Proceed to Phase 3.

---

### Phase 3: SCAFFOLD

**Goal**: Generate the SKILL.md file from the confirmed design brief.

**Step 1**: Read the saved design brief from `skills/{name}/design-brief.md`.

**Step 2**: Generate the SKILL.md following these requirements. Every skill MUST
have all of these sections — no exceptions:

| Section | Requirement |
|---------|-------------|
| Frontmatter | `name`, `description`, `version`, `user-invocable`, `agent`, `allowed-tools` |
| Operator Context | Hardcoded / Default / Optional behaviors (three subsections) |
| Capabilities | "What This Skill CAN Do" and "What This Skill CANNOT Do" |
| Instructions | One `### Phase N: NAME` section per phase in the design brief |
| Error Handling | At least 2–3 named error cases with cause and solution |
| Anti-Patterns | At least 2–3 named anti-patterns with what/why/do-instead |
| Examples | At least 1 realistic example with user input and step trace |

**Step 3**: Apply these structural patterns from AGENT_TEMPLATE_V2:

- Phase headers: `### Phase N: PHASENAME`
- Gates at end of each phase: `**Gate**: [condition]. [action].`
- Operator Context subsections named exactly: `### Hardcoded Behaviors (Always Apply)`, `### Default Behaviors (ON unless disabled)`, `### Optional Behaviors (OFF unless enabled)`
- Anti-patterns use: `**What it looks like**: ... **Why wrong**: ... **Do instead**: ...`

**Step 4**: Write to `skills/{name}/SKILL.md`.

**Gate**: File written. Confirm path exists before proceeding to Phase 4.

---

### Phase 4: VALIDATE

**Goal**: Score the new skill against the agent-evaluation rubric and enforce
the minimum quality gate before integration.

**Step 1**: Run `agent-evaluation` on the new SKILL.md.

Use the `agent-evaluation` skill, pointing it at `skills/{name}/SKILL.md`. This
produces a score breakdown across:

| Criterion | Points |
|-----------|--------|
| Structure (YAML, phases, gates) | 20 |
| Operator Context (behaviors) | 15 |
| Error Handling | 15 |
| Reference Files | 10 |
| Validation Scripts | 10 |
| Content Depth | 30 |
| **Total** | **100** |

**Step 2**: Report the score.

```
VALIDATE RESULTS
================

Skill: skills/{name}/SKILL.md
Score: [N]/100
Grade: [A (90+) | B (75–89) | C (60–74) | F (<60)]

Breakdown:
  Structure:         [N]/20
  Operator Context:  [N]/15
  Error Handling:    [N]/15
  Reference Files:   [N]/10
  Validation Scripts:[N]/10
  Content Depth:     [N]/30

[If grade A or B:]
  Gate passed. Proceeding to INTEGRATE.

[If grade C or F:]
  Gate failed. Returning to SCAFFOLD.
  Fix required: [list specific missing sections or weak areas from breakdown]
  Iterations remaining: [3 | 2 | 1]
```

**Step 3**: If grade C or below:
- List the specific sections that are weak or missing
- Return to Phase 3 with explicit instructions to fix those sections
- Re-run Phase 4 after the fix
- Track iterations. After 3 failed iterations, surface the full scoring
  breakdown to the user and ask whether to continue or redesign from Phase 2.

**Gate**: Score ≥ 75 (grade B or above). Proceed to Phase 5.

---

### Phase 5: INTEGRATE

**Goal**: Wire the validated skill into the routing system so it is immediately
usable.

**Step 1**: Add to `skills/INDEX.json`.

Read the current INDEX.json and append an entry for the new skill:

```json
{
  "name": "skill-name",
  "path": "skills/skill-name/SKILL.md",
  "description": "[first line of the frontmatter description]",
  "user-invocable": true,
  "agent": "skill-creator-engineer"
}
```

**Step 2**: Check whether the skill needs a routing entry in `/do`.

A routing entry is needed if:
- The skill is user-invocable AND
- The skill has natural trigger phrases that aren't already routed elsewhere

If a routing entry is needed:
- Run `routing-table-updater` or instruct the user to add the entries manually
- Do NOT silently modify routing tables without reporting what changed

If no routing entry is needed (internal skill, or triggers already covered):
- Note this in the output and proceed.

**Step 3**: Confirm integration.

```
INTEGRATE COMPLETE
==================

Skill:   skills/{name}/SKILL.md
Index:   Added to skills/INDEX.json
Routing: [Added triggers: "..." | No routing entry needed | Routing update pending]

Grade at integration: [B | A]
Score:  [N]/100

New skill is ready to use.
```

**Gate**: INDEX.json updated. Routing status reported. Phase 5 complete.

---

## Error Handling

### Error: "Overlap detected but user wants to proceed"
Cause: Existing skill covers ≥70% of the domain but user explicitly wants a
separate skill (e.g., different scope, different agent binding, different audience).
Solution: Document the distinction in the design brief's "Why this is not X"
section. Proceed with a clear rationale for the new skill's existence.

### Error: "SCAFFOLD produces skill below grade B after 3 iterations"
Cause: The complexity tier may be wrong, the phase structure may be incoherent,
or the domain is too narrow to support a full Operator Context + Error Handling
section.
Solution: Return to Phase 2 (DESIGN). Reconsider the tier — Simple skills don't
need elaborate error handling. If the skill is genuinely too narrow, consider
whether it should be a section within an existing skill rather than a standalone
SKILL.md.

### Error: "agent-evaluation skill not available"
Cause: `agent-evaluation` is not in the current session's tool set or the skill
file is missing.
Solution: Perform a manual rubric check against the 6 criteria table. Document
the manual score and proceed if ≥75. Flag that automated validation was skipped.

### Error: "INDEX.json malformed after update"
Cause: JSON edit introduced a syntax error.
Solution: Run `python3 -c "import json; json.load(open('skills/INDEX.json'))"` to
validate. Fix the syntax before completing Phase 5.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping DISCOVER to Save Time
**What it looks like**: Jumping directly to DESIGN because "this skill is clearly
new" without checking the INDEX
**Why wrong**: The repo has 120+ skills. Near-duplicates exist under non-obvious
names. A 30-second INDEX scan has caught duplicates in practice.
**Do instead**: Always run Phase 1. If you're confident there's no overlap, the
scan will confirm it in seconds.

### Anti-Pattern 2: Writing SKILL.md Before the Design Brief
**What it looks like**: Going straight from DISCOVER to writing SKILL.md content
without a tier decision and phase list
**Why wrong**: Tier errors discovered mid-SCAFFOLD require starting over. A 2-
minute design brief prevents a 20-minute rewrite.
**Do instead**: Complete Phase 2 and save the design brief before writing a single
line of SKILL.md.

### Anti-Pattern 3: Self-Certifying VALIDATE
**What it looks like**: Saying "this skill looks complete, I'll give it a B" instead
of running `agent-evaluation`
**Why wrong**: Self-assessment of your own output is unreliable. The rubric has
6 specific criteria with point values. Without scoring against them, gaps in Error
Handling or Reference Files are routinely missed.
**Do instead**: Always invoke `agent-evaluation`. Even if the result is an A, you'll
have the breakdown to show the user.

### Anti-Pattern 4: Silently Skipping INDEX Update
**What it looks like**: Finishing SCAFFOLD and VALIDATE and declaring the skill
"done" without updating INDEX.json
**Why wrong**: A skill that isn't in the index is invisible to `/do` routing and
to any tool that builds skill lists from INDEX.json. The skill exists on disk but
is unreachable.
**Do instead**: INDEX.json update is the first step of Phase 5. It is not optional.

---

## Examples

### Example 1: Simple skill, no overlap
User: "Create a skill for generating conventional commit messages."
Actions: Phase 1 scans INDEX — finds `git-commit-flow` but it handles the full
commit workflow, not message generation specifically; overlap ~40%, under
threshold. Phase 2 selects Simple tier (1–2 phases: gather context, generate
message). Design brief saved. Phase 3 scaffolds a 2-phase SKILL.md. Phase 4
scores 81/100 (grade B). Phase 5 adds to INDEX.json, notes routing trigger
"commit message" should be added.

### Example 2: Overlap detected, extend recommended
User: "Create a skill for reviewing Go PRs."
Actions: Phase 1 scans INDEX — finds `go-code-review` with 85% overlap (same
domain, same artifact, same review steps). DISCOVER gate fires: recommends
extending `go-code-review` rather than creating a duplicate. User agrees and
redirects to editing the existing skill instead.

### Example 3: Complex tier, multiple iterations
User: "Create a skill that runs security, performance, and architecture reviews
in parallel and synthesizes a final verdict."
Actions: Phase 1 finds no overlap. Phase 2 selects Complex tier (5 phases:
GATHER, DISPATCH, COLLECT, SYNTHESIZE, REPORT). Design brief saved. Phase 3
first scaffold scores 64/100 (C — missing Operator Context subsections and Error
Handling). Returns to Phase 3 with specific fixes. Second scaffold scores 82/100
(B). Phase 4 passes. Phase 5 integrates with routing trigger "parallel review".

---

## References

- [AGENT_TEMPLATE_V2.md](../../AGENT_TEMPLATE_V2.md) - Template for agent and skill structural patterns
- [agent-evaluation](../../skills/agent-evaluation/SKILL.md) - Rubric-based scoring used in Phase 4 VALIDATE
- [routing-table-updater](../../skills/routing-table-updater/SKILL.md) - Routing integration used in Phase 5 INTEGRATE
