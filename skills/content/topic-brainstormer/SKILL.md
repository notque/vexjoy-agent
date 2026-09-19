---
name: topic-brainstormer
promoted_to: content
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
    - "angles"
    - "story angles"
  category: content-creation
  pairs_with:
    - content
    - research
---

# Topic Brainstormer

Generate blog topic ideas that align with a content identity built around solving frustrating technical problems. Three phases: ASSESS, DECIDE, GENERATE. Every topic must pass the three-question content quality filter before presentation.

## Deep References

| Signal | Load | Content |
|---|---|---|
| Filtering topics: three-question test, category examples | `references/content-filter.md` | Full quality filter with green/red/yellow topic categories, salvage patterns |
| Scoring: impact, vex, resolution matrix | `references/priority-scoring.md` | Rubrics per dimension, score ranges, calibration, worked examples |
| Mining: problem sources, gap analysis, expansion | `references/topic-sources.md` | Mining prompts, signal strength, gap types, expansion strategies |

## Phase 1: ASSESS

Gather context about existing content and available sources.

1. Read all posts in the content directory. Document post count, content clusters, technologies covered, last post date.
2. Identify available sources: problem mining (recent debugging, errors, config struggles), gap analysis (cross-references leading nowhere), tech expansion (adjacent technologies).
3. Extract all "see also" and cross-reference mentions. Flag any pointing to content that does not exist.

**Gate**: Content landscape documented, at least 2 sources identified with material.

## Phase 2: DECIDE

Generate candidates and filter through the content quality test.

1. Mine 5-10 raw candidates from at least 2 sources. Capture: source type, raw topic, initial vex signal.
2. Apply the content quality filter -- every candidate must answer YES to all three:
   - **Was there genuine frustration?** Real time lost, failed attempts, unclear docs, unexpected behavior.
   - **Is there a satisfying resolution?** Clear fix, understanding gained, prevention strategy, "a-ha moment."
   - **Would this help others?** Reproducible problem, actionable solution, relatable frustration.
3. Reject failing candidates. Document each rejection: topic, failed question, reason.

Failure modes to catch:
- **Tutorial-only topics**: "How to Set Up X" with vex listed as "learning a new tool" is not genuine frustration. Find the specific friction. "Hugo Local Build Works But Cloudflare Deploy Fails" has real vex.
- **Opinion without experience**: "Why Go Is Better Than Python" is debate, not experience. Ground in measurement.

**Gate**: At least 3 candidates pass. Fewer than 3 -- return to Step 1 with different sources.

## Phase 3: GENERATE

Score, prioritize, and present the filtered list.

**Scoring**: `Priority = Impact(1-5) x Vex(1-5) x Resolution(1-5)`. Thresholds: 60-125 HIGH, 30-59 MEDIUM, 15-29 LOW, 1-14 SKIP.

**Titles**: Replace vague categories with failure-mode titles. Bad: "Kubernetes Networking Issues". Good: "Pod-to-Pod Traffic Works But Service Discovery Fails".

**Output format**: Grouped by priority tier. Each topic: title, vex, joy, content cluster fit, word estimate, score breakdown. End with recommendations: top pick, quick win, deep dive.

**Tie-breaking**: prefer topics that fill an existing gap, complement recent posts, use already-covered technologies, have clearer narrative structure.

**Gate**: All topics scored, prioritized, presented with recommendations.

## Angle Lenses Mode

When the task asks for angles on a single topic (not fresh candidates), apply these six lenses instead of the content quality filter:

| Lens | Question |
|------|----------|
| Perspective shift | Whose view changes the story? |
| Ladder of abstraction | One rung up (the trend) or down (the single case)? |
| News values | Which value carries it: conflict, proximity, novelty, impact, human interest? |
| Data angle | What does the dataset say that the narrative misses? |
| Contrarian | What if the consensus framing is wrong? |
| Timeliness peg | Why now? What event or deadline makes this urgent? |

Rules: one lens per kept angle (distinctness is structural). Each kept angle must pass the "so what?" gate -- one sentence naming a concrete reader payoff. Log refused angles with reason.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No existing posts | Content directory empty | Focus on problem mining; ask about recent debugging sessions |
| All candidates fail filter | Sources lack frustration signals | Ask probing questions: "What broke recently?" Shift sources. |
| Topic too broad | Category, not a specific problem | Break into failure modes: "[A] works but [B] fails" |
| Resolution unclear | Ongoing issue, no fix yet | Defer until resolved; or assess if "understanding the workaround" suffices |
