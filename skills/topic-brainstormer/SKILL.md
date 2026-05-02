---
name: topic-brainstormer
description: "Generate blog topic ideas: problem mining, gap analysis, expansion."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
command: /brainstorm
routing:
  triggers:
    - "brainstorm topics"
    - "content ideas"
    - "blog topic ideas"
    - "what to write about"
  category: content-creation
  pairs_with:
    - content-calendar
    - series-planner
    - research-pipeline
---

# Topic Brainstormer

## Overview

Generates blog topic ideas aligned with solving frustrating technical problems. Three sequential phases (ASSESS, DECIDE, GENERATE) with hard quality gates: every topic must pass a three-question content filter. Output is always a prioritized list with impact/vex/resolution scores.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `content-filter.md` | Loads detailed guidance from `content-filter.md`. |
| tasks related to this reference | `priority-scoring.md` | Loads detailed guidance from `priority-scoring.md`. |
| tasks related to this reference | `topic-sources.md` | Loads detailed guidance from `topic-sources.md`. |

## Instructions

### Phase 1: ASSESS

**Goal**: Gather context about existing content and available topic sources.

**Step 1: Scan existing content** -- Read all posts in the content directory. Document:

```markdown
## Content Landscape
Posts found: [N]
Content clusters: [list main themes]
Technologies covered: [list]
Last post date: [date]
```

**Step 2: Identify available sources**
- Problem Mining: Recent debugging sessions, errors, config struggles
- Gap Analysis: Cross-references in existing posts that lead nowhere
- Tech Expansion: Adjacent technologies not yet covered

**Step 3: Note cross-references** -- Extract "see also" and cross-reference mentions. Flag any pointing to nonexistent content.

**Gate**: Content landscape documented, at least 2 sources identified. Proceed only when gate passes.

---

### Phase 2: DECIDE

**Goal**: Generate candidates and filter through quality test.

**Quality Filter Rule**: Non-negotiable. Every candidate must answer YES to all three. Unfiltered lists waste user time.

**Step 1: Mine candidates** -- 5-10 raw candidates from at least 2 sources. Capture: source, raw topic area, initial vex signal.

**Step 2: Apply content quality filter**

Each topic must answer YES to all three:

1. **Genuine frustration?** Real time lost, multiple failed attempts, unclear docs, unexpected blocking behavior.
2. **Satisfying resolution?** Clear fix, understanding gained, prevention strategy, "a-ha moment" to share.
3. **Helps others?** Reproducible problem, not too environment-specific, actionable solution, relatable frustration.

Topics failing any question produce weak posts. "How to Set Up Hugo" lacks frustration. "Rewriting a Python CLI in Go Cut Startup Time by 10x" has concrete vex (400ms delay) and joy (40ms result).

**Step 3: Reject failures** -- Remove topics failing the filter. Document:

| Rejected Topic | Failed Question | Reason |
|----------------|-----------------|--------|
| [topic] | [1, 2, or 3] | [why] |

Do not generate tutorial-only topics: "How to Set Up X" with vex "learning a new tool" is not genuine frustration. Find the specific friction. "Hugo Local Build Works But Cloudflare Deploy Fails" has real vex.

Do not accept opinion without experience: "Why Go Is Better Than Python for CLI Tools" is debate, not experience. Ground in measurement.

**Gate**: At least 3 candidates pass the filter. If fewer, return to Step 1 with different sources. Proceed only when gate passes.

---

### Phase 3: GENERATE

**Goal**: Score, prioritize, and present filtered topics.

**Step 1: Score each topic**

```
Impact (1-5):     How many people face this problem?
Vex Level (1-5):  How frustrating is the problem?
Resolution (1-5): How satisfying is the solution?

Priority Score = Impact x Vex Level x Resolution

  60-125: HIGH PRIORITY    - Write this soon
  30-59:  MEDIUM PRIORITY  - Good candidate with right angle
  15-29:  LOW PRIORITY     - Needs more vex or broader impact
  1-14:   SKIP             - Not enough value for readers
```

**Step 2: Write specific titles** -- Replace vague categories with failure-mode titles:
- Bad: "Kubernetes Networking Issues"
- Good: "Pod-to-Pod Traffic Works But Service Discovery Fails"

Vague titles like "Kubernetes Networking Issues" are too broad. Use failure-mode: "CoreDNS Returns NXDOMAIN for Internal Services".

**Step 3: Present prioritized output**

```markdown
## Topic Brainstorm Results

### Source: [problem mining / gap analysis / tech expansion]

### HIGH PRIORITY (Strong vex potential)

1. "[Specific Topic Title]"
   The Vex: [What frustration this addresses]
   The Joy: [What satisfying resolution looks like]
   Fits existing: [Which content cluster this joins]
   Estimated: [word count range]
   Score: Impact(N) x Vex(N) x Resolution(N) = [total]

### MEDIUM PRIORITY (Good but needs angle)

2. "[Specific Topic Title]"
   The Vex: [frustration]
   The Joy: [resolution]
   Angle needed: [What narrative hook would strengthen this]
   Score: Impact(N) x Vex(N) x Resolution(N) = [total]

### GAP FILL (Based on existing content)

3. "[Specific Topic Title]"
   Referenced in: [which post mentions this]
   Missing: [what content would fill the gap]
   Score: Impact(N) x Vex(N) x Resolution(N) = [total]

### Recommendations
- Top pick: [Topic N] - [one sentence why]
- Quick win: [Topic N] - [one sentence why]
- Deep dive: [Topic N] - [one sentence why]
```

**Step 4: Handle score ties** -- Prefer topics that: (1) fill existing content gap, (2) complement recent posts, (3) use already-covered technologies, (4) have clearer narrative structure.

**Gate**: All topics scored, prioritized, presented with recommendations. Output complete.

---

## Examples

### Example 1: Problem Mining Session
User says: "I spent all day debugging a Hugo build issue, brainstorm some topics"
1. Scan existing posts for Hugo coverage (ASSESS)
2. Mine the debugging session for vex signals, filter (DECIDE)
3. Score and present with build issue as high-priority candidate (GENERATE)

### Example 2: Content Gap Analysis
User says: "What should I write about next?"
1. Read all existing posts, extract cross-references and themes (ASSESS)
2. Identify referenced-but-missing content, filter (DECIDE)
3. Score gap-fill topics alongside problem-mined candidates (GENERATE)

---

## Error Handling

### Error: "No Existing Posts to Analyze"
Cause: Content directory empty or nonexistent
Solution: Focus on problem mining. Ask about recent debugging sessions. Check CLAUDE.md for tech stack hints. Generate from technology interests.

### Error: "All Candidates Fail Filter"
Cause: Sources lack genuine frustration or resolutions
Solution: Ask probing questions ("What broke recently?"). Reframe tutorials ("What surprised you?"). Shift sources. If no vex exists, acknowledge honestly.

### Error: "Topic Too Broad to Score"
Cause: Category ("Kubernetes networking") not a specific problem
Solution: Break into failure modes. Ask "What specific moment was most frustrating?" Use pattern: "[Thing A] works but [Thing B] fails".

### Error: "Resolution Unclear or Missing"
Cause: Ongoing issue without resolution or workaround-only
Solution: Ask "Did you solve it? How?" If unresolved, defer. If workaround-only, assess whether understanding the workaround provides enough value. Consider "part 1" topic.

---

## References

Patterns used:
- **Content Quality Filter**: Three-question test (frustration + resolution + helpfulness)
- **Priority Scoring**: Impact x Vex x Resolution matrix
- **Failure-Mode Titles**: Specific problem descriptors, never vague categories
- **Problem Mining Signals**: Debugging sessions, Stack Overflow searches, error messages, config struggles
- **Gap Analysis**: Missing "see also" posts, prerequisites assumed, incomplete series
- **Technology Expansion**: Same tool/different feature, same category/different tool, integration opportunities
