---
name: research-pipeline
description: |
  Formal 5-phase research pipeline with artifact saving and source quality gates:
  SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER. Parallel research agents
  mandatory (min 3). Saves findings to research/{topic}/ for future reference.
  Use when research needs to produce a citable, resumable artifact. Use for
  "research pipeline", "formal research", "research with artifacts".
version: 1.0.0
user-invocable: true
argument-hint: "<research topic>"
agent: research-coordinator-engineer
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Write
routing:
  triggers:
    - research pipeline
    - formal research
    - research with artifacts
    - structured research
    - research topic
  pairs_with:
    - domain-research
    - explore-pipeline
  complexity: Medium
  category: meta
---

# Research Pipeline

## Operator Context

This skill formalizes the research-coordinator-engineer's parallel research workflow into
a 5-phase pipeline with artifact saving at each phase. It is the go-to path when research
needs to produce a citable, resumable output — not just an in-session answer.

### Hardcoded Behaviors (Always Apply)
- **Parallel dispatch mandatory**: Phase 2 (GATHER) MUST dispatch minimum 3 parallel `research-subagent-executor` agents in a single message. Sequential research is forbidden. This is validated by A/B testing (Rule 12, pipeline-orchestrator): sequential research loses quality vs. parallel.
- **Artifact saving at every phase**: Each phase writes to `research/{topic}/` before proceeding. Context-only storage is not acceptable — context is ephemeral, files are not.
- **Scope before gather**: Phase 1 (SCOPE) must produce `scope.md` before any research agents are dispatched. Gathering without a defined question produces unfocused findings.
- **Report is the canonical output**: `research/{topic}/report.md` is the artifact reported to the user. Inline chat is supplementary.

### Default Behaviors (ON unless disabled)
- **Save raw findings per agent**: Each parallel agent in Phase 2 writes its own `raw-{angle}.md` file, not a shared file. This preserves distinct perspectives for synthesis.
- **Evidence quality ratings**: Phase 3 labels each finding Strong/Moderate/Weak based on source specificity.
- **Gap check**: Phase 4 explicitly checks whether the synthesis answers every sub-question from scope.md.
- **Standard depth**: ~10 tool calls per research agent unless user specifies "quick" or "deep".

### Optional Behaviors (OFF unless enabled)
- **Deep mode**: ~20 tool calls per research agent. Enable with "deep research" or "thorough research".
- **Quick mode**: ~5 tool calls per research agent. Enable with "quick research" or "brief research".
- **Extra agents**: Dispatch more than 3 parallel agents for broad topics. Enable with "comprehensive" or when primary question has 5+ distinct angles.

## What This Skill CAN Do
- Define a precise research scope with primary question and 2-5 sub-questions
- Dispatch 3+ parallel `research-subagent-executor` agents, each assigned a distinct angle
- Compile raw findings into a synthesis with evidence quality ratings per claim
- Check the synthesis against the original scope for gaps and bias
- Produce a structured final report saved to `research/{topic}/report.md`

## What This Skill CANNOT Do
- Guarantee factual accuracy — it surfaces evidence quality but cannot verify all claims
- Replace domain-specific research workflows (e.g., `go-code-review` for Go code analysis)
- Produce audio, images, or non-text artifacts

---

## Instructions

### Phase 1: SCOPE

**Goal**: Define the research question precisely before gathering begins.

**Step 1**: Parse the user's request into a precise research question. If the request is vague ("research AI trends"), ask one clarifying question to narrow it. If specific enough ("research the tradeoffs of CRDTs vs. OT for collaborative editing"), proceed.

**Step 2**: Make the following decisions and document them:

| Decision | Options | Default |
|----------|---------|---------|
| Primary question | One sentence, answerable | Required |
| Sub-questions | 2–5 specific angles | Derive from primary |
| Source types | `web` / `codebase` / `docs` / `hybrid` | `hybrid` |
| Depth | `quick` (~5 calls) / `standard` (~10 calls) / `deep` (~20 calls) | `standard` |
| Output format | `technical-report` / `summary` / `structured-data` | `technical-report` |

**Step 3**: Create the output directory and write the scope artifact:

```bash
mkdir -p research/{topic}
```

Write `research/{topic}/scope.md`:

```markdown
# Research Scope: {topic}

## Primary Question
{one sentence}

## Sub-Questions
1. {angle 1}
2. {angle 2}
3. {angle 3}
[...]

## Source Types
{web / codebase / docs / hybrid}

## Depth
{quick / standard / deep} — {N} tool calls per agent

## Output Format
{technical-report / summary / structured-data}

## Parallel Agents
{N} agents, angles: {angle 1}, {angle 2}, {angle 3} [...]
```

**Gate**: `scope.md` written. Primary question is specific enough that an agent could pursue it without further clarification. Proceed to Phase 2.

---

### Phase 2: GATHER

**Goal**: Execute parallel research with mandatory multi-agent dispatch.

**Step 1**: Assign a distinct angle to each agent. Angles should cover the scope without overlapping. Good angle patterns for most research topics:

| Angle | Focus |
|-------|-------|
| `current-state` | What is the present situation, mainstream approach, or dominant solution? |
| `historical-context` | How did we get here? What are the origins or evolution? |
| `tradeoffs` | What are the pros and cons, limitations, known failure modes? |
| `alternatives` | What competing approaches or solutions exist? |
| `expert-opinions` | What do practitioners, papers, or authoritative sources say? |
| `technical-details` | Implementation specifics, data structures, algorithms, performance |
| `real-world-usage` | Who uses this, how, at what scale? |

Choose 3–5 angles that are relevant to the primary question and sub-questions from scope.md.

**Step 2**: Dispatch minimum 3 parallel `research-subagent-executor` agents in a single message. Each agent receives:
- Its assigned angle
- The primary question from scope.md
- The sub-questions relevant to its angle
- The source types from scope.md
- The depth setting (number of tool calls)
- Its output file: `research/{topic}/raw-{angle}.md`

Example dispatch instruction for one agent:
```
You are the "tradeoffs" research agent for: {primary question}

Your angle: Investigate the tradeoffs, limitations, and known failure modes.

Sub-questions you are responsible for:
- {sub-question 2}
- {sub-question 4}

Depth: standard (~10 tool calls)
Source types: web + docs

Save your findings to: research/{topic}/raw-tradeoffs.md

Format:
# Raw Research: Tradeoffs — {topic}
## Findings
[bullet points with sources]
## Key Claims
[claims you found, with evidence strength note]
## Gaps
[what you couldn't find]
```

**Step 3**: Wait for all agents to complete. Do NOT proceed until all raw-{angle}.md files exist.

```bash
ls research/{topic}/raw-*.md
```

**Gate**: All dispatched agents complete. All `research/{topic}/raw-{angle}.md` files exist. Minimum 3 files present.

If an agent times out or fails to write its file:
- Re-dispatch the failed agent once with the same instructions
- If re-dispatch also fails, note the angle as "unavailable" and continue with remaining agents — do NOT block on a single failed agent

---

### Phase 3: SYNTHESIZE

**Goal**: Compile parallel findings into a coherent structure with evidence quality ratings.

**Step 1**: Read all `research/{topic}/raw-*.md` files.

**Step 2**: Identify:
- **Consensus findings**: Claims that appear in 2+ agents' raw files
- **Contradictions**: Claims that conflict between agents (note both sides)
- **Gaps**: Sub-questions from scope.md that no agent addressed well

**Step 3**: Rate the evidence quality for each key finding:

| Rating | Criteria |
|--------|----------|
| **Strong** | Backed by specific sources, data, or multiple independent agents |
| **Moderate** | Supported by one source or general practitioner consensus |
| **Weak** | Inferred, speculative, or from a single low-authority source |

**Step 4**: Write `research/{topic}/synthesis.md`:

```markdown
# Research Synthesis: {topic}

## Key Findings

### Finding 1: {title}
**Evidence Quality**: Strong / Moderate / Weak
{summary, 2–4 sentences. Note which raw files support this.}

### Finding 2: {title}
...

## Contradictions
- {claim A} (from raw-{angle}.md) vs. {claim B} (from raw-{angle}.md)
  Resolution: {which is better supported, or "unresolved"}

## Open Gaps
- {sub-question N} — not answered by any agent
- {sub-question M} — partially answered (weak evidence only)

## Sources Referenced
- [list sources cited across raw files]
```

**Gate**: `synthesis.md` written. At least 3 key findings documented. Proceed to Phase 4.

---

### Phase 4: VALIDATE

**Goal**: Check research quality before delivery.

**Step 1 — Source quality check**: For each finding in synthesis.md, verify the evidence rating:
- Are "Strong" findings backed by specific sources or just multiple agents agreeing (which could be shared bias)?
- Are any "Weak" findings load-bearing for the primary question? If so, flag them explicitly.

**Step 2 — Gap check**: Compare synthesis.md's "Open Gaps" against scope.md's sub-questions:
- Does the synthesis answer the primary question, at least partially?
- Are any sub-questions completely unanswered? Note whether this is due to limited sources or inherently unanswerable.

**Step 3 — Bias check**: Review the raw files for source diversity:
- Are multiple independent source types represented (web + docs + codebase)?
- Do the findings reflect a range of viewpoints, or only one school of thought?

**Step 4**: Append a quality assessment section to `synthesis.md`:

```markdown
## Quality Assessment

**Coverage**: {N}/{M} sub-questions answered (fully or partially)
**Evidence distribution**: {N} Strong, {N} Moderate, {N} Weak findings
**Source diversity**: {web: N sources, docs: N sources, codebase: N references}
**Bias flags**: {none / describe any single-perspective risk}
**Flagged weak findings**: {list any Weak findings that are load-bearing}
**Research verdict**: Sufficient to answer primary question / Partial answer / Insufficient
```

**Gate**: Research answers the primary question from Phase 1 (even if partially). If "Research verdict" is "Insufficient" and the user did not specify a depth limit, consider re-dispatching GATHER for the gaps before proceeding. Otherwise, proceed to Phase 5 with limitations documented.

---

### Phase 5: DELIVER

**Goal**: Produce the final formatted report.

**Step 1**: Write `research/{topic}/report.md` — the canonical output artifact.

Structure:

```markdown
# Research Report: {topic}

**Date**: {date}
**Primary Question**: {from scope.md}
**Research Depth**: {quick/standard/deep}, {N} parallel agents

---

## Executive Summary

- {key finding 1 — one bullet}
- {key finding 2 — one bullet}
- {key finding 3 — one bullet}
[3–5 bullets maximum]

---

## Detailed Findings

### {Sub-question 1}
{2–4 paragraphs addressing this angle, citing sources}

### {Sub-question 2}
...

---

## Evidence Quality

| Finding | Rating | Basis |
|---------|--------|-------|
| {finding 1} | Strong | {source or basis} |
| {finding 2} | Moderate | {source or basis} |
| {finding 3} | Weak | {source or basis} |

---

## Gaps and Limitations

- {unanswered sub-question or limitation}
- {weak evidence area}
- {scope boundary — what this research did NOT cover}

---

## Sources

{list all sources cited across raw files and synthesis}

---

## Artifact Index

| File | Contents |
|------|----------|
| `research/{topic}/scope.md` | Research question and decisions |
| `research/{topic}/raw-{angle}.md` | Raw findings per research agent |
| `research/{topic}/synthesis.md` | Compiled findings with quality ratings |
| `research/{topic}/report.md` | This file — final formatted report |
```

**Step 2**: Report the artifact path to the user:

```
Research complete.

Report: research/{topic}/report.md
Artifacts: research/{topic}/ ({N} files)

Primary question: {question}
Coverage: {N}/{M} sub-questions answered
Evidence: {N} Strong, {N} Moderate, {N} Weak findings
```

**Gate**: `research/{topic}/report.md` written and readable. All 5 phase artifacts present in `research/{topic}/`.

---

## Error Handling

### Error: "Agent timed out without writing raw-{angle}.md"
Cause: Research sub-agent exceeded time or context limit.
Solution: Re-dispatch once with identical instructions. If second attempt fails, mark angle as "unavailable" in synthesis.md and continue. Do NOT block Phase 3 indefinitely on one failed angle.

### Error: "Synthesis has fewer than 3 key findings"
Cause: Raw files contained very sparse findings, or topic is too narrow.
Solution: Check if raw files have actual content. If raw files are empty or minimal, re-dispatch GATHER agents with looser search terms. If topic is genuinely narrow, proceed with fewer findings and note it in Quality Assessment.

### Error: "Primary question unanswerable — Research verdict: Insufficient"
Cause: The topic is outside available sources, too specialized, or too recent.
Solution: Report this to the user with specifics: which angles failed and why. Offer to (a) narrow the question, (b) change source types, or (c) deliver the partial findings with strong caveats. Do NOT silently deliver an insufficient report as if it were complete.

### Error: "research/{topic}/ directory conflict — prior research exists"
Cause: A previous run left artifacts at the same path.
Solution: Check if prior `report.md` exists. If it does, ask the user: re-run (overwrite) or resume from existing scope.md? Resuming from scope.md is faster if the primary question is unchanged.

---

## Anti-Patterns

### Anti-Pattern 1: Sequential Research
**What it looks like**: Dispatching one research agent, waiting, dispatching the next, waiting, etc.
**Why wrong**: Sequential research takes 3–5x longer and produces lower quality output than parallel dispatch (A/B validated, Rule 12). Each agent also lacks awareness of the other angles, producing redundant findings.
**Do instead**: Dispatch all agents in a single message with distinct angles. Wait once for all to complete.

### Anti-Pattern 2: Not Saving Artifacts
**What it looks like**: Reading all raw files and synthesizing in context without writing synthesis.md or report.md to disk.
**Why wrong**: Context is ephemeral. If the session ends or context compresses, all synthesis work is lost. The user cannot reference findings later.
**Do instead**: Write synthesis.md after Phase 3 and report.md after Phase 5, always. These are the persistent record.

### Anti-Pattern 3: Treating Synthesis as Delivery
**What it looks like**: Skipping Phase 4 (VALIDATE) and Phase 5 (DELIVER), sending synthesis.md content directly to the user.
**Why wrong**: Synthesis is an intermediate artifact. It lacks quality assessment, bias check, and the formatted structure of a final report. Gaps are not yet surfaced for the user.
**Do instead**: Always run VALIDATE before DELIVER. Quality assessment is what distinguishes research from note-taking.

### Anti-Pattern 4: Single-Agent Research
**What it looks like**: Dispatching one agent with instructions to "research everything" about the topic.
**Why wrong**: A single agent pursues one thread of inquiry and cannot cover multiple angles in parallel. It also hits depth limits faster.
**Do instead**: Assign distinct angles to distinct agents. Minimum 3.

### Anti-Pattern 5: Vague Scope
**What it looks like**: Skipping Phase 1 and dispatching agents with the user's raw query as the research question.
**Why wrong**: Raw queries like "research Kubernetes" produce unfocused findings across too many angles with no synthesis structure.
**Do instead**: Always write scope.md first. A 2-minute scoping step saves significant synthesis effort.

---

## Examples

### Example 1: Technical tradeoff research
User: "Research the tradeoffs of CRDTs vs. operational transforms for collaborative editing"
Actions: Phase 1 defines primary question ("What are the tradeoffs between CRDTs and OT for real-time collaborative editing at scale?"), 4 sub-questions (conflict resolution model, performance, implementation complexity, production adoption). Phase 2 dispatches 4 agents: current-state, tradeoffs, technical-details, real-world-usage. Phase 3 synthesizes 8 key findings with evidence ratings. Phase 4 identifies 1 weak finding (performance at very large scale — limited data). Phase 5 delivers `research/crdt-vs-ot/report.md`.

### Example 2: Quick competitive landscape research
User: "Quick research on vector database options for a new project"
Actions: Phase 1 sets depth=quick (~5 calls per agent), 3 sub-questions. Phase 2 dispatches 3 agents: current-state (mainstream options), tradeoffs (when to use each), real-world-usage (adoption and maturity). Phase 5 delivers `research/vector-databases/report.md` with executive summary that directly answers "which to pick for a new project."

### Example 3: Resuming interrupted research
User: "Continue the research on distributed consensus algorithms"
Actions: Check if `research/distributed-consensus/` exists. If scope.md and some raw-*.md files exist, read scope.md to re-establish context, check which angles are missing, and resume from Phase 3 (SYNTHESIZE) if all raw files are present, or re-dispatch missing angles if some are absent.

---

## References

- [domain-research](../domain-research/SKILL.md) - Subdomain discovery pipeline that uses similar parallel research patterns
- [explore-pipeline](../explore-pipeline/SKILL.md) - Systematic codebase exploration pipeline for research within a repository
- [research-subagent-executor](../../agents/research-subagent-executor.md) - Agent dispatched in Phase 2 for parallel research execution
