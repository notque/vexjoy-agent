---
name: pre-planning-discussion
description: "Resolve implementation ambiguities before planning begins."
version: 1.0.0
user-invocable: false
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
  force_route: true
  triggers:
    - discuss ambiguities
    - resolve gray areas
    - clarify before planning
    - assumptions mode
    - what are the gray areas
    - before we plan
    - pre-planning discussion
  pairs_with:
    - feature-lifecycle
    - workflow-orchestrator
  complexity: Medium
  category: process
---

# Pre-Planning Discussion Skill

Resolve specific implementation ambiguities before a plan is created. This is an optional step between design and planning in the feature lifecycle (design → **ambiguity resolution** → plan → implement → validate → release), or a standalone step before any planning workflow.

The cost of a wrong assumption compounds: a silently wrong assumption at the planning stage produces a valid-looking plan that executes cleanly but delivers the wrong thing. The rework cost is the entire plan-execute cycle, not just a single task. This skill makes assumptions explicit so they can be corrected cheaply — before any code is written.

## Instructions

### Phase 0: PRIME

**Goal**: Load context, detect mode, identify the work to be clarified.

1. **Read repository CLAUDE.md** and follow its requirements throughout execution. This happens before any other work.

2. **Load prior context**: Check for existing artifacts that contain decisions:
   - `.feature/state/design/` — design documents from feature-lifecycle design phase
   - `adr/` — architecture decision records relevant to this work
   - `task_plan.md` — any existing plan context
   - Prior ambiguity resolution output (if re-running)

3. **Extract carried-forward decisions**: From any prior artifacts, extract decisions already made. These go directly into the "Carried Forward" section and are NOT re-asked. Re-asking a settled question erodes trust and wastes interaction budget — if a prior phase decided it, carry it forward silently.

4. **Detect mode**: Assess the codebase:
   - If the user explicitly requested a mode, use that mode
   - If the working directory has substantial existing code in the relevant domain (10+ source files), use **Assumptions mode**
   - Otherwise, use **Discussion mode**
   - Optional: if "auto-approve assumptions" is enabled, accept all Confident/Likely assumptions without presenting them (for fast iteration)

5. **Establish scope boundary**: From the user's request (and any design document), define:
   - IN: What this task covers
   - OUT: What this task explicitly does not cover

   This skill clarifies HOW to implement scoped work. It never expands scope to add new capabilities or question WHETHER the work should be done. If an ambiguity implies scope expansion, classify it as OUT and move on. Scope creep during ambiguity resolution defeats the purpose — the user already decided what to build; we are resolving how.

**GATE**: Prior context loaded (carried-forward decisions extracted). Mode selected. Scope boundary established. Proceed to Execute.

### Phase 1: EXECUTE

#### Discussion Mode (greenfield / unclear requirements)

**Goal**: Surface gray areas — decisions that could go multiple ways — and present them with domain-aware options. Target 3-6 decisions total. If you find yourself drifting beyond that, the scope is too broad or the questions are too granular.

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

For each gray area, prepare 2-3 concrete options with tradeoffs. Never ask open-ended questions like "How should we handle errors?" — that forces the user to design the solution. Present specific options so the user can pick, not invent.

Only present genuine gray areas where multiple approaches are valid. If there is only one reasonable option, it is not a gray area — just proceed with it. "Should we use JSON?" is not a gray area if JSON is the only sensible choice.

Before declaring "no gray areas found," spend at least 2 minutes actively looking. Almost every task has ambiguities — if you found none, you are not looking hard enough.

**Step 2: Present Gray Areas**

Present all identified gray areas grouped by domain, all at once (not one at a time) so the user can batch their decisions. For each:

```markdown
### Gray Area: [descriptive name]

**Domain**: [Visual / API / CLI / Data / Config / Content]

**Options**:
1. **[Option A]** — [1-sentence tradeoff]
2. **[Option B]** — [1-sentence tradeoff]
3. **[Option C]** (if applicable) — [1-sentence tradeoff]

**Default recommendation**: [which option and why, if you have a preference]
```

If a gray area has an obvious best choice, state the recommendation — the user can accept or override.

**Step 3: Capture Decisions**

For each gray area the user responds to, record:
- The decision made
- The rationale (user's reasoning or acceptance of recommendation)
- Which options were rejected and why

If the user defers a decision ("I don't care" or "whatever you think"), accept your recommendation and record it as "defaulted to recommendation."

Throughout this phase, track every spec, ADR, config file, or interface definition you reference. These become the "canonical refs" list in the output document — downstream agents need to know which files are authoritative for the decisions made.

#### Assumptions Mode (brownfield / existing codebase)

**Goal**: Read the codebase, form evidence-based opinions, and present them for the user to correct. The user only intervenes where the agent is actually wrong. Target 2-4 user interactions (corrections). If you are drifting beyond that, the scope is too broad or you are asking about things you should decide yourself.

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

Every assumption MUST cite a file path and specific pattern. Assumptions without evidence are untestable claims that the user cannot evaluate. If you cannot point to evidence, the assumption is "Unclear" — say so honestly.

Confidence calibration:
- **Confident**: Multiple files confirm the pattern, or explicit configuration states it
- **Likely**: One file shows the pattern, or it is consistent with the overall codebase style
- **Unclear**: Conflicting signals, insufficient data, or the codebase does not address this

Never inflate confidence. Do not rationalize "confident enough, no need to show evidence" — always cite the file path and pattern regardless of confidence level.

**Step 3: Present Assumptions**

Present all assumptions organized by confidence level (Confident first, Unclear last). Tell the user:

> Here's what I believe about this codebase based on reading [N] files. Please correct anything that's wrong. You only need to respond to items that are incorrect — silence means agreement.

Make assumptions explicit so the user CAN correct you. The anti-pattern is assuming "the user will correct me if I'm wrong" while keeping assumptions silent — users cannot correct what they do not see.

**Step 4: Process Corrections**

For each correction the user provides:
- Update the assumption to reflect the correct information
- Note the original (wrong) assumption and why it was wrong
- Adjust confidence on related assumptions if the correction reveals a pattern

Throughout this phase, track every file you reference as a canonical reference for the output document.

### Phase 2: COMPILE OUTPUT

**Goal**: Produce the structured context document that downstream skills consume.

Both modes converge here and MUST produce the identical format. Downstream consumers (feature-lifecycle plan phase, workflow-orchestrator) depend on a predictable structure regardless of which mode produced it.

Produce a single document with this exact structure:

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
   - If in feature lifecycle: "Run `/feature-lifecycle` to create the implementation plan."
   - If standalone: "Proceed to planning. The context document is at [path]."

3. If any assumptions were marked "Unclear" and not resolved by the user, flag them:
   > **Warning**: [N] assumptions remain unclear. These may need revisiting during planning if they affect task decomposition.

**GATE**: Handoff complete. Context document saved. Next step communicated.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No gray areas found | Task is unambiguous or too vague to analyze | If unambiguous, skip this skill and go to planning. If too vague, return to feature-lifecycle design phase |
| User defers all decisions | User wants the agent to decide everything | Accept all recommendations, record as "defaulted." Proceed. |
| Scope expansion detected | A gray area implies new capabilities | Classify as OUT in scope boundary. Do not resolve it. |
| Too many gray areas (>10) | Task scope is too broad | Group related gray areas or suggest breaking the task into smaller pieces |
| Codebase too small for Assumptions mode | <5 relevant files | Switch to Discussion mode |
| Conflicting prior decisions | Design doc and ADR disagree | Flag the conflict to the user. Do not resolve silently |

## References

- [ADR-072: Pre-Planning Ambiguity Resolution](../../adr/072-pre-planning-ambiguity-resolution.md)
