---
name: feature-design
description: |
  Collaborative design phase for feature lifecycle: explore requirements,
  discuss trade-offs, produce design document. Use when starting a new feature
  that needs design before implementation. Use for "design feature", "let's
  think through", "explore approaches", or "/feature-design". Do NOT use for
  simple bug fixes or tasks that don't need design discussion.
version: 2.0.0
user-invocable: true
command: /feature-design
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  triggers:
    - feature design
    - design feature
    - think through
    - explore approaches
    - design first
    - feature-design
  pairs_with:
    - feature-plan
    - workflow-orchestrator
  complexity: Medium
  category: process
---

# Feature Design Skill

## Purpose

Transform a feature idea into a structured design document through collaborative dialogue. This is Phase 1 of the feature lifecycle pipeline (design → plan → implement → validate → release).

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before design
- **Over-Engineering Prevention**: Design only what's requested. Don't add speculative requirements.
- **State Management via Script**: All state operations go through `python3 scripts/feature-state.py`
- **Gate Enforcement**: Check gate status before proceeding past decision points
- **Design Doc Required**: Phase CANNOT complete without a design document artifact in `.feature/state/design/`
- **ADR for Design Decisions**: Write an ADR to `adr/{feature-name}.md` documenting architectural decisions made during design exploration. Register the ADR session (`python3 scripts/adr-query.py register --adr adr/{name}.md`) so sub-phase skills (feature-plan, feature-implement) receive design context via hook injection.
- **Branch Safety**: Create feature branch via worktree, never work on main

### Default Behaviors (ON unless disabled)
- **Collaborative Dialogue**: Ask clarifying questions before committing to an approach
- **Multiple Approaches**: Generate 2-3 approaches with trade-offs before selecting
- **Context Loading**: Read L0 and L1 context at phase start

### Optional Behaviors (OFF unless enabled)
- **Auto-approve gates**: Skip human approval for design gates (requires config)

## What This Skill CAN Do
- Facilitate design discussion with the user
- Produce structured design documents
- Initialize feature state and worktree
- Load and update feature context hierarchy

## What This Skill CANNOT Do
- Skip design and go straight to code
- Produce implementation plans (that's feature-plan)
- Write code (that's feature-implement)
- Modify published context directly (retro loop only)

## Instructions

### Phase 0: PRIME

**Goal**: Initialize feature state and load context.

1. Initialize feature state:
   ```bash
   python3 scripts/feature-state.py init "FEATURE_NAME"
   ```

2. Load L0 context:
   ```bash
   python3 scripts/feature-state.py context-read "" L0
   ```

3. Load L1 design context:
   ```bash
   python3 scripts/feature-state.py context-read "" L1 --phase design
   ```

4. If existing L2 context is relevant, load on-demand:
   ```bash
   python3 scripts/feature-state.py context-read "" L2 --phase design
   ```

5. **Surface relevant seeds** (ADR-075): Check `.seeds/index.json` for dormant seeds whose trigger conditions match the current feature. Compare the feature name and description against each seed's `trigger` field using fuzzy keyword overlap. If matches are found, present them:

   ```
   ## Relevant Seeds (N matched)

   ### seed-YYYY-MM-DD-slug [Scope]
   Trigger: "trigger condition"
   Rationale: Why this matters...
   Action: What to do when triggered
   Breadcrumbs: file1.go, file2.py

   > Incorporate into current design? [yes/no/defer]
   ```

   - **yes**: Include the seed's action and rationale as a design input for Phase 1. Mark seed as `active` in index.json.
   - **no**: Dismiss the seed (move to `.seeds/archived/`, status `dismissed`).
   - **defer**: Leave the seed dormant for future surfacing.

   If `.seeds/` does not exist or contains no dormant seeds, skip this step silently.

**Gate**: Feature state initialized. Context loaded. Seeds surfaced (if any). Proceed to Execute.

### Phase 1: EXECUTE (Design Dialogue)

**Goal**: Collaborative exploration of the feature requirements and approach.

**Step 1: Understand Requirements**

Check gate: `python3 scripts/feature-state.py gate FEATURE design.intent-discussion`

If gate mode is `human`:
- Ask clarifying questions about the feature, one at a time
- Prefer multiple-choice when possible
- Establish success criteria
- Identify constraints

If gate mode is `auto`:
- Derive intent from the feature description
- Document assumptions explicitly

**Step 2: Explore Approaches**

Check gate: `python3 scripts/feature-state.py gate FEATURE design.approach-selection`

Generate 2-3 approaches:
```markdown
## Approach 1: [Name]
**Pros**: [advantages]
**Cons**: [disadvantages]
**Complexity**: Low/Medium/High
**Risk**: Low/Medium/High
**Domain agents needed**: [which agents from our system would implement this]
```

If gate is `human`: present approaches and ask user to select.
If gate is `auto`: select the approach that best balances simplicity and completeness.

**Step 3: Draft Design Document**

Create the design document:

```markdown
# Design: [Feature Name]

## Problem Statement
[What problem does this solve?]

## Requirements
- [ ] Requirement 1
- [ ] Requirement 2

## Selected Approach
[Which approach and why]

## Components
[What needs to be built/modified]

## Domain Agents
[Which agents from our system will handle implementation]

## Open Questions
[Anything unresolved]

## Trade-offs Accepted
[What we're giving up and why]
```

**Gate**: Design document drafted. Proceed to Validate.

### Phase 2: VALIDATE

**Goal**: Verify design document is complete.

Check gate: `python3 scripts/feature-state.py gate FEATURE design.design-approval`

Validation checklist:
- [ ] Problem statement is clear
- [ ] Requirements are enumerable (not vague)
- [ ] Approach is selected with rationale
- [ ] Components are identified
- [ ] Domain agents are identified
- [ ] Open questions are listed (even if empty)

If gate is `human`: present design to user for approval.
If gate is `auto`: verify checklist passes.

**Gate**: Design approved. Proceed to Checkpoint.

### Phase 3: CHECKPOINT

**Goal**: Save artifacts, run retro pipeline, advance.

1. Save design document:
   ```bash
   echo "DESIGN_CONTENT" | python3 scripts/feature-state.py checkpoint FEATURE design
   ```

2. **Record learnings** — if this phase produced non-obvious insights, record them:
   ```bash
   python3 scripts/learning-db.py record TOPIC KEY "VALUE" --category design
   ```

3. Advance to plan phase:
   ```bash
   python3 scripts/feature-state.py advance FEATURE
   ```

4. Suggest next step:
   ```
   Design complete. Run /feature-plan to break this into implementation tasks.
   ```

**Gate**: Artifacts saved. Retro complete. Phase finished.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Feature already exists | `init` called twice | Use `status` to check, work with existing state |
| Gate returns exit 2 | Human input required | Present decision to user, wait for response |
| No design doc produced | Skipped design dialogue | Return to Phase 1, complete all steps |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Skip design, go straight to code | Undesigned features require rework | Complete design dialogue first |
| Design everything at once | Over-engineering | Design only what's needed for this feature |
| Ignore existing context | Loses previous learnings | Load L0/L1 at prime |

## References

- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
- [Retro Loop](../shared-patterns/retro-loop.md)
- [State Conventions](../_feature-shared/state-conventions.md)
- [Plant Seed](../plant-seed/SKILL.md) — seed-based deferred work surfaced in Phase 0 (ADR-075)
