---
name: adr-consultation
description: "Multi-agent consultation for architecture decisions."
version: 1.0.0
model: sonnet
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
  - Task
routing:
  triggers:
    - "consult on ADR"
    - "challenge this design"
    - "review before implementing"
    - "multi-agent consultation"
    - "architecture consultation"
    - "should we proceed"
    - "adr consultation"
  pairs_with:
    - feature-lifecycle
  complexity: Medium
  category: meta
---

# ADR Consultation Skill

Multi-agent architecture consultation that dispatches 3 specialized reviewers in parallel against an ADR and synthesizes their findings into a PROCEED or BLOCKED verdict. This is the gate between feature-lifecycle plan and implement phases for Medium+ decisions because challenging architecture decisions before implementation prevents costly post-implementation rework.

## Instructions

### Phase 1: DISCOVER

**Goal**: Identify the ADR and prepare the consultation directory.

**Step 1: Locate the ADR**

Check for ADR path in this order:
1. User-provided path (e.g., `adr/intent-based-routing.md`)
2. Active session context from adr-system hook (`.adr-session.json`)
3. Ask the user which ADR to consult on

Do not guess which ADR to consult on because an incorrect guess wastes a full consultation cycle.

```bash
# Check for active ADR session
cat .adr-session.json 2>/dev/null

# List available ADRs if no session
ls adr/*.md
```

Even if this ADR was discussed informally, run the formal consultation because undocumented discussion produces no persistent artifacts and cannot be referenced by future sessions.

**Step 2: Check for prior consultation**

Before dispatching, scan `adr/{adr-name}/` for existing agent files because silently overwriting prior consultation work destroys the audit trail.

```bash
ls adr/{adr-name}/ 2>/dev/null
```

If existing files are found, report them and their timestamps. Ask the user whether to overwrite (re-run consultation) or use existing results.

**Step 3: Read the ADR**

Read the full ADR content. Extract:
- The decision being made
- Key components/changes proposed
- Any stated risks or consequences
- The ADR name (filename without `.md`) for the consultation directory

**Step 4: Create consultation directory**

Create `adr/{adr-name}/` before dispatching agents because agents need a valid directory to write their output files.

```bash
mkdir -p adr/{adr-name}
```

**Gate**: ADR content read, consultation directory created, ADR name confirmed. Do NOT dispatch agents until this gate passes because agents need the ADR content and a valid directory to write to.

---

### Phase 2: DISPATCH

**Goal**: Launch all consultation agents in a single message for true parallel execution.

All three Task calls MUST appear in ONE response because sequential dispatch triples wall-clock time with no cross-perspective benefit. The value of this skill is simultaneous independent judgment. If you find yourself dispatching agents one at a time, stop and restructure into a single message.

Dispatch all 3 agents even if the ADR "seems simple" because partial consultation gives false confidence. Let agents report "no concerns" if genuinely clean — that is a fast, cheap confirmation that removing a safety net cannot replicate.

Even when there is time pressure, do not skip consultation because blocking concerns discovered post-implementation cost dramatically more to fix than the minutes this consultation takes.

**Standard mode (3 agents)**: Always dispatch all three.

**Complex mode (5 agents)**: For Complex decisions (new subsystem, major API change), add `reviewer-security` and a second domain expert. Enable with "complex consultation" or "full consultation".

Each agent receives:
1. The full ADR content as context
2. Its specific lens and analysis focus
3. Explicit output path: `adr/{adr-name}/{agent-name}.md`
4. The structured output format defined below

**Agent 1: reviewer-contrarian**

Lens: Challenge assumptions, find simpler alternatives, validate premises.

Prompt template:
```
You are reviewing the following ADR as a contrarian analyst. Your job is to challenge
fundamental assumptions, find simpler alternatives, and identify where the plan might be
solving the wrong problem.

ADR Content:
{full adr content}

Write your consultation response to: adr/{adr-name}/reviewer-contrarian.md

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

**Agent 2: reviewer-user-advocate**

Lens: Evaluate user impact, UX complexity cost, whether this makes the system harder to use.

Prompt template:
```
You are reviewing the following ADR as a user advocate. Your job is to evaluate user impact:
does this make the system easier or harder to use? Does it add complexity without proportional
user value? Who bears the cognitive load of this change?

ADR Content:
{full adr content}

Write your consultation response to: adr/{adr-name}/reviewer-user-advocate.md

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

**Agent 3: reviewer-meta-process**

Lens: System health, single points of failure, whether this makes one component indispensable, whether it aligns with established architecture principles.

Prompt template:
```
You are reviewing the following ADR as a meta-process analyst. Your job is to evaluate system
health: does this create a single point of failure? Does it make one component indispensable
in ways that will hurt later? Does it align with the repository's established architecture
principles? Does it introduce hidden coupling?

ADR Content:
{full adr content}

Also read the repository's CLAUDE.md for established principles before analyzing.

Write your consultation response to: adr/{adr-name}/reviewer-meta-process.md

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

**Gate**: All Task calls dispatched in a single message. Proceed to Phase 3 only when all agents have returned and written their files to `adr/{adr-name}/`.

---

### Phase 3: SYNTHESIZE

**Goal**: Read all agent responses from the consultation directory and produce a synthesis.

**Step 1: Read all agent responses from files**

Read the response files from disk, not from Task return context, because files persist across sessions while context does not — synthesis from context is not reproducible.

```bash
cat adr/{adr-name}/reviewer-contrarian.md
cat adr/{adr-name}/reviewer-user-advocate.md
cat adr/{adr-name}/reviewer-meta-process.md
```

**Step 2: Extract all concerns**

Track every concern raised by any agent in `adr/{adr-name}/concerns.md` with severity and resolution status because structured tracking prevents concerns from being lost during synthesis.

```markdown
# Concerns: {adr-name}

## Concern 1: [Title]
- **Raised by**: reviewer-contrarian | reviewer-user-advocate | reviewer-meta-process
- **Severity**: blocking | important | minor
- **Description**: [What's wrong or at risk]
- **Resolution**: UNRESOLVED

Resolution states (update as concerns are addressed):
- UNRESOLVED — not yet addressed
- RESOLVED: {description} — addressed in implementation
- ACCEPTED: {description} — accepted as a known limitation
- DEFERRED: {description} — will address in future work

## Concern 2: [Title]
...
```

**Step 3: Identify verdict agreement**

Do not treat NEEDS_CHANGES as equivalent to PROCEED because NEEDS_CHANGES means the agent identified real concerns that should be addressed. Multiple NEEDS_CHANGES aggregates to a higher concern level, not a softer approval.

When one reviewer disagrees with the majority, track the minority concern with full severity assessment because minority dissent catches real failures that consensus misses.

| Pattern | Meaning |
|---------|---------|
| All 3 PROCEED | Strong consensus — proceed with confidence |
| 2 PROCEED, 1 NEEDS_CHANGES | Soft consensus — address changes, then proceed |
| Any BLOCK | Hard block — must resolve before proceeding |
| Mixed NEEDS_CHANGES | Significant concerns — address before proceeding |

The synthesizer can also identify cross-cutting concerns that individual agents missed because agents assess separately and may not see emergent issues visible only in combination. Document any orchestrator-level concern in concerns.md and factor it into the verdict.

**Step 4: Write synthesis**

Write `adr/{adr-name}/synthesis.md`:

```markdown
# Consultation Synthesis: {adr-name}

## Verdict: [PROCEED | BLOCKED]

## Agent Verdicts
| Agent | Verdict |
|-------|---------|
| reviewer-contrarian | [verdict] |
| reviewer-user-advocate | [verdict] |
| reviewer-meta-process | [verdict] |

## Areas of Agreement
[Where all agents agree — positive or negative.]

## Areas of Disagreement
[Where agents see the same aspect differently.]

## Blocking Concerns
[Concerns with severity: blocking. These MUST be resolved before implementation.]

## Important Concerns
[Concerns with severity: important. Should be addressed; non-blocking.]

## Minor Concerns
[Concerns with severity: minor. Nice-to-have improvements.]

## Synthesis Rationale
[Why the overall verdict is PROCEED or BLOCKED, given the above.]
```

**Gate**: All concerns extracted to concerns.md, synthesis.md written. Proceed to Phase 4 only when both files exist in `adr/{adr-name}/`.

---

### Phase 4: GATE

**Goal**: Issue a final PROCEED or BLOCKED verdict and communicate it clearly.

**Step 1: Check for blocking concerns**

Read `adr/{adr-name}/concerns.md`. If any concern has `**Severity**: blocking`, the verdict is BLOCKED. This is a hard gate, not advisory, because blocking concerns that surface post-implementation cost dramatically more to fix.

Do not rationalize blocking concerns as "theoretical" because theoretical risk is still risk, and the gate exists specifically to prevent implementation from proceeding with unresolved blocking issues.

**Step 2: Issue verdict**

**If BLOCKED:**

```
═══════════════════════════════════════════════════════════════
 ADR CONSULTATION: BLOCKED
═══════════════════════════════════════════════════════════════

 ADR: {adr-name}
 Consultation: adr/{adr-name}/

 BLOCKING CONCERNS — do not proceed to implementation:

 1. [{raised by}] {concern title}
    {description}

 2. [{raised by}] {concern title}
    {description}

 Next Steps:
   - Address each blocking concern in the ADR
   - Re-run /adr-consultation to verify concerns are resolved
   - Do NOT dispatch feature-lifecycle implement phase until PROCEED verdict
═══════════════════════════════════════════════════════════════
```

**If PROCEED:**

```
═══════════════════════════════════════════════════════════════
 ADR CONSULTATION: PROCEED
═══════════════════════════════════════════════════════════════

 ADR: {adr-name}
 Consultation: adr/{adr-name}/

 Verdict: PROCEED — no blocking concerns found.

 Agent Verdicts:
   - reviewer-contrarian:    [verdict]
   - reviewer-user-advocate: [verdict]
   - reviewer-meta-process:  [verdict]

 Important Concerns (non-blocking):
   [{raised by}] {concern title} — {brief description}

 Consultation artifacts:
   - adr/{adr-name}/reviewer-contrarian.md
   - adr/{adr-name}/reviewer-user-advocate.md
   - adr/{adr-name}/reviewer-meta-process.md
   - adr/{adr-name}/synthesis.md
   - adr/{adr-name}/concerns.md
═══════════════════════════════════════════════════════════════
```

**Gate**: Verdict issued, artifacts confirmed written to disk. Consultation is complete.

---

### Phase 5: LIFECYCLE (optional — run when consultation is no longer needed)

**Goal**: Clean up consultation artifacts after an ADR's implementation is complete and merged.

When an ADR's implementation is complete and merged:
1. The consultation artifacts in `adr/{name}/` can be archived or deleted
2. Update the ADR status to indicate consultation is complete
3. The synthesis verdict and concerns are the permanent record — agent responses can be removed

**Cleanup instructions:**

1. **Keep**: `adr/{name}/synthesis.md` (permanent record of verdict)
2. **Keep**: `adr/{name}/concerns.md` (permanent record of concerns + resolutions)
3. **Delete**: `adr/{name}/reviewer-*.md` (agent responses — value extracted into synthesis)
4. **Update**: ADR status to reflect implementation completion

```bash
# Remove agent response files (value already extracted into synthesis)
rm adr/{name}/reviewer-*.md

# Verify permanent records remain
ls adr/{name}/synthesis.md adr/{name}/concerns.md
```

The consultation directory is auto-created by Phase 1 (`mkdir -p adr/{adr-name}`). No `.gitkeep` is needed because the `adr/` directory is gitignored and the skill handles creation on demand.

---

## Error Handling

### Error: "No ADR found / ADR path unclear"
**Cause**: User invoked skill without specifying which ADR, and no active session context exists.
**Solution**: List available ADRs with `ls adr/*.md` and ask the user to specify. Do not guess.

### Error: "Agent times out or fails to write file"
**Cause**: One or more Task agents exceed execution time or fail to create their output file.
**Solution**:
1. Report which agent(s) failed to complete.
2. Run the failed agent(s) individually with the same prompt.
3. Do not issue a synthesis or verdict until all 3 agents have written their files.
4. If re-run also fails, report the failure and ask the user how to proceed.

### Error: "All agents return PROCEED but synthesis shows deeper issue"
**Cause**: Agents each assessed separately may miss emergent concerns visible only in combination.
**Solution**: The synthesizer (the orchestrator reading all three files) can identify cross-cutting
concerns that individual agents missed. Document this as an orchestrator-level concern in
concerns.md and factor it into the verdict.

### Error: "Consultation directory already exists with prior agent files"
**Cause**: A prior consultation was run on the same ADR. Files may be stale.
**Solution**: Report the existing files and their timestamps. Ask the user whether to overwrite
(re-run consultation) or use existing results. Do not silently overwrite prior consultation work.

---

## References

- [ADR: Multi-Agent Consultation](../../adr/multi-agent-consultation.md) — The architecture decision this skill implements
- [parallel-code-review](../parallel-code-review/SKILL.md) — Fan-out/fan-in pattern this skill adapts
- [reviewer-contrarian](../../agents/reviewer-contrarian.md) — Contrarian lens agent
