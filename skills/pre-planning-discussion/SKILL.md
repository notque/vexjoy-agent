---
name: pre-planning-discussion
description: |
  Resolve implementation ambiguities before planning begins. Two modes:
  Discussion mode surfaces gray areas with concrete options for greenfield work.
  Assumptions mode reads the codebase, forms evidence-based opinions, and asks
  the user to correct only what's wrong (brownfield work). Use for "discuss
  ambiguities", "resolve gray areas", "clarify before planning", "assumptions
  mode", "what are the gray areas", "before we plan". Do NOT use for broad
  design exploration (use feature-design) or for planning itself (use feature-plan).
version: 1.0.0
user-invocable: true
argument-hint: "[--assumptions] <topic>"
command: /pre-planning-discussion
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Edit
routing:
  triggers:
    - discuss ambiguities
    - resolve gray areas
    - clarify before planning
    - assumptions mode
    - what are the gray areas
    - before we plan
    - pre-planning discussion
  pairs_with:
    - feature-design
    - feature-plan
    - workflow-orchestrator
  complexity: Medium
  category: process
---

# Pre-Planning Discussion Skill

## Purpose

Resolve specific implementation ambiguities before a plan is created. This is an optional step between design and planning in the feature lifecycle (design → **ambiguity resolution** → plan → implement → validate → release), or a standalone step before any planning workflow.

The cost of a wrong assumption compounds: a silently wrong assumption at the planning stage produces a valid-looking plan that executes cleanly but delivers the wrong thing. The rework cost is the entire plan-execute cycle, not just a single task. This skill makes assumptions explicit so they can be corrected cheaply — before any code is written.

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before starting
- **Scope Guardrail**: This skill clarifies HOW to implement scoped work. It NEVER expands scope to add new capabilities or question WHETHER the work should be done. If an ambiguity implies scope expansion, classify it as OUT and move on. WHY: scope creep during ambiguity resolution defeats the purpose — the user already decided what to build; we're resolving how.
- **Prior Decision Carryforward**: Check for existing context from earlier phases (feature-design output, prior ambiguity resolution, ADR decisions). Never re-ask a settled question. WHY: re-asking erodes trust and wastes interaction budget.
- **Structured Output Required**: Both modes MUST produce the identical context document format (Resolved Decisions + Carried Forward + Scope Boundary + Canonical References). WHY: downstream consumers (feature-plan, workflow-orchestrator) depend on a predictable format regardless of which mode produced it.
- **Canonical References Accumulation**: Track every spec, ADR, config file, or interface definition referenced during the discussion. These become the "canonical refs" list in the output document. WHY: downstream agents need to know which files are authoritative for the decisions made.

### Default Behaviors (ON unless disabled)
- **Mode Auto-Detection**: If the working directory has substantial existing code (10+ source files in the relevant domain), default to Assumptions mode. Otherwise, default to Discussion mode. User can override.
- **Confidence Calibration**: In Assumptions mode, be honest about confidence. "Confident" means strong evidence from multiple files. "Likely" means one file or consistent pattern. "Unclear" means conflicting signals or insufficient data. Never inflate confidence.
- **Interaction Budget**: Assumptions mode targets 2-4 user interactions (corrections). Discussion mode targets 3-6 decisions. If either mode drifts beyond these bounds, something is wrong — the scope is too broad, or questions are too granular.

### Optional Behaviors (OFF unless enabled)
- **Auto-approve assumptions**: Accept all Confident/Likely assumptions without presenting them (for fast iteration)

## What This Skill CAN Do
- Identify implementation ambiguities (gray areas) and present concrete options
- Read codebase files to form evidence-based assumptions
- Produce a structured context document consumed by feature-plan or workflow-orchestrator
- Carry forward decisions from prior phases
- Accumulate canonical references for downstream agents

## What This Skill CANNOT Do
- Expand scope beyond the current task boundary (scope guardrail)
- Replace feature-design for broad design exploration
- Produce implementation plans (that's feature-plan)
- Write code or modify existing files (beyond the context document)

## Instructions

### Phase 0: PRIME

**Goal**: Load context, detect mode, identify the work to be clarified.

1. **Load prior context**: Check for existing artifacts that contain decisions:
   - `.feature/state/design/` — design documents from feature-design
   - `adr/` — architecture decision records relevant to this work
   - `task_plan.md` — any existing plan context
   - Prior ambiguity resolution output (if re-running)

2. **Extract carried-forward decisions**: From any prior artifacts, extract decisions already made. These go directly into the "Carried Forward" section and are NOT re-asked.

3. **Detect mode**: Assess the codebase:
   - If the user explicitly requested a mode, use that mode
   - If the working directory has substantial existing code in the relevant domain, use **Assumptions mode**
   - Otherwise, use **Discussion mode**

4. **Identify scope boundary**: From the user's request (and any design document), establish:
   - IN: What this task covers
   - OUT: What this task explicitly does not cover

**GATE**: Prior context loaded. Mode selected. Scope boundary established. Proceed to Execute.

### Phase 1: EXECUTE

#### Discussion Mode (greenfield / unclear requirements)

**Goal**: Surface gray areas — decisions that could go multiple ways — and present them with domain-aware options.

**Step 1: Identify Gray Areas**

Analyze the task requirements and classify ambiguities by domain:

| Domain | Typical Gray Areas |
|--------|--------------------|
| Visual features | Layout density, responsive breakpoints, animation behavior, color scheme interpretation |
| APIs | Contract shape, error response format, versioning strategy, auth mechanism |
| CLIs | Flag design, output format (human vs. machine), exit codes, stdin/stdout conventions |
| Data pipelines | Batch vs. streaming, idempotency guarantees, failure semantics, retry policy |
| Config/infrastructure | File format, environment variable naming, secret management, deployment strategy |
| Content/documentation | Audience level, tone, structure, depth, cross-reference strategy |

For each gray area, prepare 2-3 concrete options with tradeoffs. NOT open-ended questions.

**Step 2: Present Gray Areas**

Present all identified gray areas grouped by domain. For each:

```markdown
### Gray Area: [descriptive name]

**Domain**: [Visual / API / CLI / Data / Config / Content]

**Options**:
1. **[Option A]** — [1-sentence tradeoff]
2. **[Option B]** — [1-sentence tradeoff]
3. **[Option C]** (if applicable) — [1-sentence tradeoff]

**Default recommendation**: [which option and why, if you have a preference]
```

Present all gray areas at once (not one at a time) so the user can batch their decisions. If a gray area has an obvious best choice, state the recommendation — the user can accept or override.

**Step 3: Capture Decisions**

For each gray area the user responds to, record:
- The decision made
- The rationale (user's reasoning or acceptance of recommendation)
- Which options were rejected and why

If the user defers a decision ("I don't care" or "whatever you think"), accept your recommendation and record it as "defaulted to recommendation."

#### Assumptions Mode (brownfield / existing codebase)

**Goal**: Read the codebase, form evidence-based opinions, and present them for the user to correct. The user only intervenes where the agent is actually wrong.

**Step 1: Codebase Survey**

Read 5-15 files relevant to the task. Selection strategy:
- Entry points (main, index, router, handler files)
- Configuration (config files, env templates, package manifests)
- Files directly related to the area being modified
- Test files that reveal conventions
- Types/interfaces that define contracts

**Step 2: Form Assumptions**

For each relevant aspect of the implementation, form an assumption:

```markdown
### Assumption: [descriptive name]

- **Claim**: [what you believe is true]
- **Evidence**: `path/to/file.ext:L42` — [specific pattern observed]
- **Confidence**: Confident | Likely | Unclear
- **If wrong**: [concrete consequence of proceeding with this assumption]
```

Confidence calibration:
- **Confident**: Multiple files confirm the pattern, or explicit configuration states it
- **Likely**: One file shows the pattern, or it's consistent with the overall codebase style
- **Unclear**: Conflicting signals, insufficient data, or the codebase doesn't address this

**Step 3: Present Assumptions**

Present all assumptions organized by confidence level (Confident first, Unclear last). Tell the user:

> Here's what I believe about this codebase based on reading [N] files. Please correct anything that's wrong. You only need to respond to items that are incorrect — silence means agreement.

**Step 4: Process Corrections**

For each correction the user provides:
- Update the assumption to reflect the correct information
- Note the original (wrong) assumption and why it was wrong
- Adjust confidence on related assumptions if the correction reveals a pattern

### Phase 2: COMPILE OUTPUT

**Goal**: Produce the structured context document that downstream skills consume.

Both modes converge here. Produce a single document with this exact structure:

```markdown
# Pre-Planning Context: [Task Name]

## Resolved Decisions

[For each decision/confirmed assumption]
- **[ID]**: [Choice made] — [Rationale]

## Carried Forward

[Decisions from prior phases that remain valid]
- **[ID]**: [Decision] — (from [source]: design doc / ADR / prior resolution)

## Scope Boundary

- **IN**: [What this task covers]
- **OUT**: [What this task explicitly does not cover]

## Canonical References

[Files referenced during discussion that downstream agents should consult]
- `path/to/file.ext` — [why it's authoritative for this work]

## Mode Used

[Discussion | Assumptions] — [brief rationale for mode selection]
```

Save this document:
- If in a feature lifecycle: save to `.feature/state/design/pre-planning-context-FEATURE.md`
- If standalone: save to `task_plan_context.md` alongside `task_plan.md`

**GATE**: Context document produced with all required sections. All decisions recorded with rationale. Scope boundary defined. Canonical references listed.

### Phase 3: HANDOFF

**Goal**: Confirm completion and suggest next step.

1. Summarize: "[N] decisions resolved, [M] carried forward, [K] canonical references accumulated."

2. Suggest next step based on context:
   - If in feature lifecycle: "Run `/feature-plan` to create the implementation plan."
   - If standalone: "Proceed to planning. The context document is at [path]."

3. If any assumptions were marked "Unclear" and not resolved by the user, flag them:
   > **Warning**: [N] assumptions remain unclear. These may need revisiting during planning if they affect task decomposition.

**GATE**: Handoff complete. Context document saved. Next step communicated.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No gray areas found | Task is unambiguous or too vague to analyze | If unambiguous, skip this skill and go to planning. If too vague, return to feature-design |
| User defers all decisions | User wants the agent to decide everything | Accept all recommendations, record as "defaulted." Proceed. |
| Scope expansion detected | A gray area implies new capabilities | Classify as OUT in scope boundary. Do not resolve it. |
| Too many gray areas (>10) | Task scope is too broad | Group related gray areas or suggest breaking the task into smaller pieces |
| Codebase too small for Assumptions mode | <5 relevant files | Switch to Discussion mode |
| Conflicting prior decisions | Design doc and ADR disagree | Flag the conflict to the user. Do not resolve silently |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Asking 15-20 individual questions | Exhausts user patience, most answers are predictable | Use Assumptions mode: form opinions, ask for corrections |
| Open-ended questions ("How should we handle errors?") | Forces user to design the solution | Present 2-3 concrete options with tradeoffs |
| Re-asking settled decisions | Wastes interaction budget, erodes trust | Check prior context first; carry forward existing decisions |
| Expanding scope during discussion | Defeats the purpose of scoped ambiguity resolution | Apply scope guardrail: clarify HOW, never WHETHER |
| Presenting one option as a question | "Should we use JSON?" is not a gray area if there's only one option | Only present genuine gray areas with multiple valid approaches |
| Skipping evidence in Assumptions mode | Assumptions without evidence can't be evaluated | Every assumption MUST cite a file path and specific pattern |

## Anti-Rationalization

See [core patterns](../shared-patterns/anti-rationalization-core.md).

Domain-specific for pre-planning discussion:

| Rationalization | Why Wrong | Action |
|-----------------|-----------|--------|
| "The requirements are clear, no ambiguities" | Almost every task has ambiguities; you're not looking hard enough | Spend 2 minutes actively looking for gray areas before declaring none exist |
| "I'll figure it out during implementation" | That's exactly what this skill prevents — silent wrong assumptions | Surface the ambiguity now; it's cheaper to resolve |
| "This expands scope but it's important" | Scope guardrail is non-negotiable | Mark as OUT, note it for future work |
| "User will correct me if I'm wrong" | Users don't know what you assumed silently | Make assumptions explicit so they CAN correct you |
| "Confident enough, no need to show evidence" | Assumptions without evidence are untestable claims | Always cite file path and pattern |

## References

- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
- [ADR-072: Pre-Planning Ambiguity Resolution](../../adr/072-pre-planning-ambiguity-resolution.md)
