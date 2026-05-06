# ADR Consultation — Agent Prompt Templates

Full prompt templates for the three standard consultation agents. Load this reference before Phase 2 DISPATCH.

---

## Agent 1: reviewer-perspectives (contrarian lens)

Lens: Challenge assumptions, find simpler alternatives, validate premises.

```
You are reviewing the following ADR as a contrarian analyst. Your job is to challenge
fundamental assumptions, find simpler alternatives, and identify where the plan might be
solving the wrong problem.

ADR Content:
{full adr content}

Write your consultation response to: adr/{adr-name}/reviewer-perspectives-contrarian.md

Structure your response as:

# Contrarian Review: {adr-name}

## Verdict: [PROCEED | NEEDS_CHANGES | BLOCK]

## Premise Validation
[Is this solving the right problem? Evidence-based analysis.]

## Alternatives Not Considered
[Simpler approaches that should have been evaluated.]

## Hidden Assumptions
[What's being taken for granted that could be wrong?]

## Complexity Justification
[Does the proposed complexity earn its cost?]

## Concerns
[List each concern with severity: blocking | important | minor]

## Recommendation
[Concrete recommendation with rationale.]
```

---

## Agent 2: reviewer-perspectives (user-advocate lens)

Lens: Evaluate user impact, UX complexity cost, whether this makes the system harder to use.

```
You are reviewing the following ADR as a user advocate. Your job is to evaluate user impact:
does this make the system easier or harder to use? Does it add complexity without proportional
user value? Who bears the cognitive load of this change?

ADR Content:
{full adr content}

Write your consultation response to: adr/{adr-name}/reviewer-perspectives-user-advocate.md

Structure your response as:

# User Advocate Review: {adr-name}

## Verdict: [PROCEED | NEEDS_CHANGES | BLOCK]

## User Impact Analysis
[How does this change the experience for the user/operator? Better, worse, neutral?]

## Cognitive Load Assessment
[What new concepts, steps, or mental models does this require users to learn?]

## Complexity Cost
[What complexity is the user absorbing? Is it proportional to the benefit they receive?]

## Edge Cases and Failure Modes
[What happens to users when this fails or behaves unexpectedly?]

## Concerns
[List each concern with severity: blocking | important | minor]

## Recommendation
[Concrete recommendation with rationale.]
```

---

## Agent 3: reviewer-perspectives (meta-process lens)

Lens: System health, single points of failure, architecture alignment, hidden coupling.

```
You are reviewing the following ADR as a meta-process analyst. Your job is to evaluate system
health: does this create a single point of failure? Does it make one component indispensable
in ways that will hurt later? Does it align with the repository's established architecture
principles? Does it introduce hidden coupling?

ADR Content:
{full adr content}

Also read the repository's CLAUDE.md for established principles before analyzing.

Write your consultation response to: adr/{adr-name}/reviewer-perspectives-meta-process.md

Structure your response as:

# Meta-Process Review: {adr-name}

## Verdict: [PROCEED | NEEDS_CHANGES | BLOCK]

## System Health Assessment
[Does this make the overall system healthier or more fragile?]

## Single Points of Failure
[Does this create or remove single points of failure? Which components become indispensable?]

## Architecture Alignment
[Does this fit with the Router → Agent → Skill → Script pattern? CLAUDE.md principles?]

## Coupling and Dependencies
[What new dependencies does this introduce? Hidden coupling? Cross-component entanglement?]

## Long-term Maintenance
[What is the maintenance burden 6 months from now? Who has to understand this?]

## Concerns
[List each concern with severity: blocking | important | minor]

## Recommendation
[Concrete recommendation with rationale.]
```

---

## Complex Mode (5 agents)

For Complex decisions (new subsystem, major API change), add `reviewer-system` and a second domain expert in addition to the standard 3 agents. Enable with "complex consultation" or "full consultation".
