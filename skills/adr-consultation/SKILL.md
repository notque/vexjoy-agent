---
name: adr-consultation
description: |
  Multi-agent consultation for architecture decisions. Dispatches 3 specialized reviewers
  in parallel (contrarian, user advocate, meta-process) to challenge a plan or ADR before
  implementation begins, producing a synthesis with a PROCEED or BLOCKED verdict.
  Use for "consult on this ADR", "challenge this design", "review before implementing",
  "should we proceed", or any Medium+ architecture decision. Do NOT use for trivial
  changes, simple bug fixes, or decisions already in implementation.
version: 1.0.0
model: sonnet
user-invocable: true
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
    - feature-design
    - feature-plan
    - feature-implement
  complexity: Medium
  category: meta
---

# ADR Consultation Skill

## Operator Context

This skill operates as an orchestrator for multi-agent architecture consultation, configuring
Claude's behavior to dispatch 3 specialized reviewer agents in parallel against an ADR and
synthesize their findings into a PROCEED or BLOCKED verdict. It implements the **ConsensusCode
file-based communication protocol** adapted to our ADR system — agents write responses to
`adr/{name}/` directories, enabling inter-agent communication and persistence across sessions.

The design principle: challenge architecture decisions BEFORE implementation, not after. A
BLOCKED verdict stops implementation dispatch. A PROCEED verdict explicitly clears the path.
This is the gate between feature-plan and feature-implement for Medium+ decisions.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before dispatching agents.
- **Single-Message Dispatch**: All 3 Task calls MUST appear in ONE response for true parallelism.
  Sequential dispatch defeats the purpose and triples wall-clock time.
- **Artifacts Over Memory**: Every agent writes to `adr/{name}/{agent-name}.md`. Synthesis reads
  from files, not from context. This makes consultation results persistent across sessions.
- **Gate Enforcement**: If blocking concerns exist in concerns.md, do NOT proceed to
  implementation. Report the blocks and stop. This is not advisory — it is a hard gate.
- **All 3 Agents Required**: Do not skip a reviewer because the ADR "seems simple". Let
  agents report "no concerns" if genuinely clean. Partial consultation gives false confidence.

### Default Behaviors (ON unless disabled)

- **Consultation Directory Creation**: Create `adr/{adr-name}/` before dispatching agents.
- **Structured Concerns Tracking**: Every concern raised by any agent is tracked in
  `adr/{adr-name}/concerns.md` with severity (blocking/important/minor) and resolution status.
- **Synthesis Production**: After all agents complete, produce `adr/{adr-name}/synthesis.md`
  with areas of agreement, disagreement, and final verdict rationale.
- **Verdict Output**: Always produce a final PROCEED or BLOCKED verdict with supporting reasons.

### Optional Behaviors (OFF unless enabled)

- **5-Agent Mode**: For Complex decisions (new subsystem, major API change), add
  `reviewer-security` and a second domain expert. Enable with "complex consultation" or
  "full consultation".
- **Prior Consultation Check**: Before dispatching, scan `adr/{name}/` for existing agent
  files to avoid duplicate consultation. Enable with "check for prior consultation".

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Identify the ADR being consulted on and prepare the consultation directory.

**Step 1: Locate the ADR**

Check for ADR path in this order:
1. User-provided path (e.g., `adr/intent-based-routing.md`)
2. Active session context from adr-system hook (`.adr-session.json`)
3. Ask the user which ADR to consult on

```bash
# Check for active ADR session
cat .adr-session.json 2>/dev/null

# List available ADRs if no session
ls adr/*.md
```

**Step 2: Read the ADR**

Read the full ADR content. Extract:
- The decision being made
- Key components/changes proposed
- Any stated risks or consequences
- The ADR name (filename without `.md`) for the consultation directory

**Step 3: Create consultation directory**

```bash
mkdir -p adr/{adr-name}
```

**Gate**: ADR content read, consultation directory created, ADR name confirmed. Do NOT dispatch
agents until this gate passes — agents need the ADR content and a valid directory to write to.

---

### Phase 2: DISPATCH

**Goal**: Launch all 3 consultation agents in a single message for true parallel execution.

**CRITICAL**: All three Task calls MUST appear in ONE response. If you dispatch them one at a
time, you are running sequential analysis at 3x the cost with none of the cross-perspective
benefit. The value of this skill is in simultaneous independent judgment.

Each agent receives:
1. The full ADR content as context
2. Its specific lens and analysis focus
3. Explicit output path: `adr/{adr-name}/{agent-name}.md`
4. The structured output format defined below

Dispatch exactly these 3 agents:

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

Lens: System health, single points of failure, whether this makes one component indispensable,
whether it aligns with established architecture principles.

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

**Gate**: All 3 Task calls dispatched in a single message. Proceed to Phase 3 only when all 3
agents have returned and written their files to `adr/{adr-name}/`.

---

### Phase 3: SYNTHESIZE

**Goal**: Read all agent responses from the consultation directory and produce a synthesis.

**Step 1: Read all agent responses**

```bash
cat adr/{adr-name}/reviewer-contrarian.md
cat adr/{adr-name}/reviewer-user-advocate.md
cat adr/{adr-name}/reviewer-meta-process.md
```

**Step 2: Extract all concerns**

For each concern raised across all agents, record in `adr/{adr-name}/concerns.md`:

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

| Pattern | Meaning |
|---------|---------|
| All 3 PROCEED | Strong consensus — proceed with confidence |
| 2 PROCEED, 1 NEEDS_CHANGES | Soft consensus — address changes, then proceed |
| Any BLOCK | Hard block — must resolve before proceeding |
| Mixed NEEDS_CHANGES | Significant concerns — address before proceeding |

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

**Gate**: All concerns extracted to concerns.md, synthesis.md written. Proceed to Phase 4
only when both files exist in `adr/{adr-name}/`.

---

### Phase 4: GATE

**Goal**: Issue a final PROCEED or BLOCKED verdict and communicate it clearly.

**Step 1: Check for blocking concerns**

Read `adr/{adr-name}/concerns.md`. If any concern has `**Severity**: blocking`, the verdict
is BLOCKED.

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
   - Do NOT dispatch feature-implement until PROCEED verdict
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

To clean up after implementation is complete:
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

**Note**: The consultation directory is auto-created by Phase 1 (`mkdir -p adr/{adr-name}`).
No `.gitkeep` is needed — the `adr/` directory is gitignored and the skill handles creation
on demand. The lifecycle is: skill creates directory -> consultation runs -> implementation
completes -> cleanup removes ephemeral agent responses -> permanent records remain.

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

## Anti-Patterns

### Anti-Pattern 1: Sequential Dispatch
**What it looks like**: Dispatching agents one at a time, waiting for each to return.
**Why wrong**: Triples wall-clock time, defeats the purpose of parallel consultation.
**Do instead**: All 3 Task calls in ONE message. This is not optional.

### Anti-Pattern 2: Skipping an Agent Because the ADR "Seems Simple"
**What it looks like**: "This is a small change, we don't need the user advocate."
**Why wrong**: "Simple" changes often carry hidden user impact or coupling risks. Let the
agent return "no concerns" — that's a fast, cheap confirmation. Skipping removes a safety net.
**Do instead**: Dispatch all 3 always. Scale down from Complex (5-agent) to Standard (3-agent),
not from Standard to incomplete.

### Anti-Pattern 3: Issuing Verdict Without Reading Agent Files
**What it looks like**: Synthesizing from agent return values in context rather than reading files.
**Why wrong**: Violates artifacts-over-memory principle. Files persist; context does not.
Synthesis from context is not reproducible across sessions.
**Do instead**: Always read `adr/{name}/*.md` files explicitly before synthesizing.

### Anti-Pattern 4: Treating NEEDS_CHANGES as PROCEED
**What it looks like**: "Two agents said NEEDS_CHANGES, that's basically approval."
**Why wrong**: NEEDS_CHANGES means the agent identified real concerns that should be addressed.
Multiple NEEDS_CHANGES aggregates to a higher concern level.
**Do instead**: Extract every concern, assess severity. Two NEEDS_CHANGES with important
concerns is not the same as one PROCEED with no concerns.

### Anti-Pattern 5: Proceeding Despite Blocking Concerns
**What it looks like**: "We'll fix it during implementation." "It's probably fine."
**Why wrong**: This is exactly what the gate is designed to prevent. Blocking concerns that
surface post-implementation cost dramatically more to fix.
**Do instead**: Hard stop. Update the ADR to address blocking concerns. Re-run consultation.

---

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The ADR looks solid, consultation is ceremony" | Unreviewed plans have blind spots | Run consultation; let agents find nothing if it's solid |
| "One reviewer disagreed but the others agreed" | Minority dissent catches real failures | Track the concern; evaluate severity |
| "We're on a deadline, skip consultation" | Blocking concerns discovered post-impl cost more | Run consultation; it takes minutes |
| "The contrarian is always negative" | Structured dissent is the feature, not a bug | Record the concern; assess validity |
| "We already discussed this informally" | Undocumented discussion is not a consultation | Run the formal consultation; create artifacts |
| "Blocking concern is theoretical" | Theoretical risk is risk | Require explicit resolution in ADR before proceeding |

---

## References

- [ADR: Multi-Agent Consultation](../../adr/multi-agent-consultation.md) — The architecture decision this skill implements
- [parallel-code-review](../parallel-code-review/SKILL.md) — Fan-out/fan-in pattern this skill adapts
- [dispatching-parallel-agents](../dispatching-parallel-agents/SKILL.md) — Core parallel dispatch mechanics
- [anti-rationalization-core.md](../shared-patterns/anti-rationalization-core.md) — Universal rationalization patterns
- [reviewer-contrarian](../../agents/reviewer-contrarian.md) — Contrarian lens agent
