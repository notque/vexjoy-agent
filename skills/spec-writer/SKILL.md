---
name: spec-writer
description: |
  Structured specification with explicit scope boundaries: user stories,
  acceptance criteria, out-of-scope definition, risks, and estimation.
  Positions before feature-design in the feature lifecycle pipeline.

  Use when: "write spec", "user stories", "define requirements", "scope this",
  "what should this do", "acceptance criteria", "define scope"
version: 1.0.0
user-invocable: false
routing:
  triggers:
    - write spec
    - user stories
    - define requirements
    - scope this
    - what should this do
    - acceptance criteria
    - define scope
    - spec out
  pairs_with:
    - feature-design
    - feature-plan
    - feature-validate
  complexity: Simple
  category: process
---

# Spec Writer Skill

## Purpose

Produce a structured SPEC.md before any design or implementation begins. This is Phase 0 of the feature lifecycle pipeline (spec --> design --> plan --> implement --> validate --> release). The spec defines WHAT to build and WHERE the boundaries are. It says nothing about HOW.

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **Phase 3 (Out of Scope) is MANDATORY** -- never skip it. Without explicit exclusions, scope creep is invisible until it's too late. Every "while we're at it" addition started as an unwritten assumption.
- **Minimum 3 out-of-scope items** -- if you cannot list 3 things this feature does NOT do, the scope is not yet defined. This forces real boundary thinking rather than a rubber-stamp section.
- **Max 7 user stories** -- more than 7 means the feature is too broad. Decompose into multiple specs first. This constraint forces prioritization: which stories are essential vs. nice-to-have?
- **Acceptance criteria must be testable** -- no subjective language ("should feel fast", "user-friendly", "intuitive"). Every criterion must have a verifiable assertion. WHY: untestable criteria become opinion debates during review.
- **Spec says WHAT, not HOW** -- no code, no architecture, no database schemas, no implementation details. Those belong in feature-design.

### Default Behaviors (ON unless disabled)
- **Save output as SPEC.md** in project root, or `.feature/SPEC.md` if worktree is active
- **Include all 5 sections** in order (stories, criteria, out-of-scope, risks, estimation)
- **Use GIVEN/WHEN/THEN format** for acceptance criteria

### Optional Behaviors (OFF unless enabled)
- **Skip estimation** -- omit Section 5 for exploratory or research-phase work
- **Test stub generation** -- render acceptance criteria as pseudocode test stubs

## Instructions

### Step 1: Gather Context

1. Read the repository CLAUDE.md if present
2. Ask the user what feature or capability they want to specify
3. Identify the target users/roles (who benefits?)
4. Identify existing related functionality (what already exists?)

**GATE**: You have a clear understanding of the feature intent and target users before writing any stories.

### Step 2: Write SPEC.md

Produce the spec with all 5 sections. Use this structure:

```markdown
# Spec: [Feature Name]

## 1. User Stories

> Max 7 stories. Each has single responsibility.

- **US-1**: As a [role], I want [action] so that [benefit].
- **US-2**: As a [role], I want [action] so that [benefit].

## 2. Acceptance Criteria

> 2-5 criteria per story. All must be verifiable.

### US-1: [Story title]
- GIVEN [context] WHEN [action] THEN [result]
- GIVEN [context] WHEN [action] THEN [result]

### US-2: [Story title]
- GIVEN [context] WHEN [action] THEN [result]

## 3. Out of Scope

> Minimum 3 items. Each states WHY it is excluded.

This feature does NOT:
- [ ] Handle X (deferred to future work because Y)
- [ ] Support Y (explicitly excluded because Z)
- [ ] Replace Z (existing solution remains because W)

## 4. Risks & Assumptions

| Risk/Assumption | Impact | Mitigation |
|-----------------|--------|------------|
| Assumption could be wrong | What breaks | How to detect/recover |
| External dependency blocks | Delay estimate | Fallback plan |

## 5. Estimation

| Dimension | Assessment | Justification |
|-----------|------------|---------------|
| T-shirt size | S / M / L / XL | Why this size |
| Files changed | ~N files | Which areas of codebase |
| Testing complexity | Low / Medium / High | What makes testing easy or hard |
```

**GATE**: All 5 sections present. Out-of-scope has >= 3 items. Stories <= 7. All criteria use verifiable language.

### Step 3: Validate and Save

1. Review each acceptance criterion -- flag any that use subjective language
2. Review out-of-scope -- flag if fewer than 3 items
3. Review story count -- flag if more than 7
4. Save the spec:
   - If `.feature/` directory exists: save to `.feature/SPEC.md`
   - Otherwise: save to `SPEC.md` in project root
5. Report the artifact location and suggest next step:
   ```
   Spec saved to [path]. Run /feature-design to begin design exploration.
   ```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Cannot identify target users | Vague feature request | Ask user to describe who benefits and how |
| More than 7 stories | Scope too broad | Decompose into multiple specs, one per coherent capability |
| Cannot list 3 out-of-scope items | Scope not yet defined | Brainstorm adjacent features, related capabilities, and future enhancements that are NOT part of this work |
| Acceptance criteria use subjective language | "fast", "easy", "intuitive" | Replace with measurable assertion: latency threshold, click count, error rate |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Kitchen sink spec (>7 stories) | Scope is too broad to implement or validate coherently | Decompose into multiple specs, prioritize |
| Empty out-of-scope | If nothing is excluded, everything is included -- that is a scope problem | Force 3+ exclusions with reasoning |
| Untestable criteria | "Should be user-friendly" becomes an opinion debate during review | Use measurable assertions: "<3 clicks", "<200ms", "zero data loss" |
| Spec as implementation | Spec says WHAT, not HOW. Code and schemas belong in feature-design | Remove implementation details, keep behavioral descriptions |

## Integration

This skill produces the input artifact for the feature lifecycle:

```
spec-writer (SPEC.md)
  --> feature-design (reads stories + scope boundaries)
    --> feature-plan (reads acceptance criteria for test requirements)
      --> feature-implement
        --> feature-validate (checks acceptance criteria as quality gates)
          --> feature-release
```

## References

- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
