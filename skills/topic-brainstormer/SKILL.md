---
name: topic-brainstormer
description: |
  Generate blog post topic ideas through problem mining, gap analysis, and
  technology expansion. Use when user needs content ideas, wants to brainstorm
  articles, asks "what should I write about", or needs to fill content gaps.
  Use for "brainstorm", "topic ideas", "what to write", "content gaps", or
  "blog ideas". Do NOT use for writing posts, creating outlines, or SEO
  optimization without a specific ideation need.
version: 2.0.0
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
---

# Topic Brainstormer

## Operator Context

This skill operates as an operator for topic ideation workflows, configuring Claude's behavior for generating blog post ideas that align with a content identity built around solving frustrating technical problems. It implements the **Assess-Decide-Generate** pattern -- gather signals, filter candidates, prioritize output -- with **Domain Intelligence** embedded in the content quality filter methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before brainstorming
- **Over-Engineering Prevention**: Generate topic ideas only. No outlines, no drafts, no full posts
- **content quality Filter Enforcement**: Every topic MUST pass the vex test (frustration + resolution + value to others)
- **No Tutorial-Only Topics**: Reject topics that are "how to do X" without a struggle narrative
- **No Opinion Pieces**: Reject commentary without concrete hands-on experience
- **Priority Matrix Required**: All outputs must include impact/vex/resolution scoring

### Default Behaviors (ON unless disabled)
- **Existing Post Analysis**: Read existing posts to identify gaps and themes before generating
- **Multi-Source Generation**: Mine from at least 2 different sources per session
- **Angle Suggestions**: Include specific narrative angles for medium-priority topics
- **Specific Titles**: Use failure-mode titles, not vague category titles
- **Complete Output**: Show full brainstorm report with all sections

### Optional Behaviors (OFF unless enabled)
- **Deep Gap Analysis**: Exhaustive scan of all cross-references and "see also" mentions
- **Tech Stack Expansion**: Suggest adjacent technologies not yet covered
- **Series Planning**: Group related topics into potential multi-part series

## What This Skill CAN Do
- Generate topic ideas from problem mining (debugging sessions, errors, config struggles)
- Identify content gaps based on existing post references and cross-links
- Analyze technology patterns in existing content to find expansion opportunities
- Apply the content quality filter to validate every topic candidate
- Score topics by impact, vex level, and resolution satisfaction
- Suggest specific narrative angles for each topic
- Estimate word counts and categorize by priority tier

## What This Skill CANNOT Do
- Write blog posts (use blog-post-writer instead)
- Create post outlines (use post-outliner instead)
- Guarantee topics will resonate with readers (user judgment required)
- Generate topics without applying the content quality filter
- Accept tutorial-only or opinion-only topics that lack struggle narratives
- Skip the priority scoring step

---

## Instructions

### Phase 1: ASSESS

**Goal**: Gather context about existing content and available topic sources.

**Step 1: Scan existing content**

Read all posts in the content directory. Document:

```markdown
## Content Landscape
Posts found: [N]
Content clusters: [list main themes]
Technologies covered: [list]
Last post date: [date]
```

**Step 2: Identify available sources**

Determine which topic sources have material to mine:
- Problem Mining: Recent debugging sessions, errors, config struggles
- Gap Analysis: Cross-references in existing posts that lead nowhere
- Tech Expansion: Adjacent technologies not yet covered

**Step 3: Note cross-references**

Extract all "see also", "related", and cross-reference mentions from existing posts. Flag any that point to content that does not exist.

**Gate**: Content landscape documented, at least 2 sources identified with material. Proceed only when gate passes.

### Phase 2: DECIDE

**Goal**: Generate topic candidates and filter them through the content quality test.

**Step 1: Mine candidates from identified sources**

Generate 5-10 raw topic candidates from at least 2 sources. For each candidate, capture:
- Source (problem mining, gap analysis, or tech expansion)
- Raw topic area
- Initial vex signal (what frustration exists)

**Step 2: Apply content quality filter to every candidate**

Each topic must answer YES to all three questions:

1. **Was there genuine frustration?** Real time lost, multiple failed attempts, unclear docs, or unexpected behavior that blocked progress.
2. **Is there a satisfying resolution?** Clear fix exists, understanding gained, prevention strategy available, or "a-ha moment" to share.
3. **Would this help others?** Problem is reproducible, not too environment-specific, solution is actionable, frustration is relatable.

**Step 3: Reject failing candidates**

Remove any topic that fails the filter. Document why each rejection failed:

| Rejected Topic | Failed Question | Reason |
|----------------|-----------------|--------|
| [topic] | [1, 2, or 3] | [why] |

**Gate**: At least 3 candidates pass the content quality filter. If fewer than 3 pass, return to Step 1 with different sources. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Score, prioritize, and present the filtered topic list.

**Step 1: Score each passing topic**

Apply the priority matrix to every candidate:

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

**Step 2: Write specific titles**

Replace vague category titles with failure-mode titles:
- Bad: "Kubernetes Networking Issues"
- Good: "Pod-to-Pod Traffic Works But Service Discovery Fails"

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

**Step 4: Handle score ties**

When scores are equal, prefer topics that:
1. Fill an existing content gap
2. Complement recent posts
3. Use technologies already covered (lower research overhead)
4. Have clearer narrative structure

**Gate**: All topics scored, prioritized, and presented with recommendations. Output is complete.

---

## Examples

### Example 1: Problem Mining Session
User says: "I spent all day debugging a Hugo build issue, brainstorm some topics"
Actions:
1. Scan existing posts for Hugo coverage (ASSESS)
2. Mine the debugging session for vex signals, filter through content quality test (DECIDE)
3. Score and present topics with the build issue as high-priority candidate (GENERATE)
Result: Prioritized topic list with the fresh debugging experience as top pick

### Example 2: Content Gap Analysis
User says: "What should I write about next?"
Actions:
1. Read all existing posts, extract cross-references and themes (ASSESS)
2. Identify referenced-but-missing content, filter through content quality test (DECIDE)
3. Score gap-fill topics alongside any problem-mined candidates (GENERATE)
Result: Prioritized list mixing gap fills with fresh topic candidates

---

## Error Handling

### Error: "No Existing Posts to Analyze"
Cause: Content directory is empty or does not exist yet
Solution:
1. Focus entirely on problem mining instead of gap analysis
2. Ask user about recent debugging sessions or technical struggles
3. Check repository CLAUDE.md or project docs for tech stack hints
4. Generate topics from technology interests alone

### Error: "All Candidates Fail content quality Filter"
Cause: Sources lack genuine frustration signals or resolutions
Solution:
1. Ask probing questions: "What broke recently?" or "What took hours to fix?"
2. Reframe tutorial candidates: "What surprised you?" or "What mistake does everyone make?"
3. Shift to a different source (e.g., from gap analysis to problem mining)
4. If no vex exists, acknowledge honestly -- not every session yields topics

### Error: "Topic Too Broad to Score"
Cause: Candidate is a category ("Kubernetes networking") rather than a specific problem
Solution:
1. Break into multiple specific failure modes
2. Ask: "What specific moment was most frustrating?"
3. Use failure-mode title pattern: "[Thing A] works but [Thing B] fails"

### Error: "Resolution Unclear or Missing"
Cause: User has an ongoing issue without a resolution, or the fix is a workaround with no understanding
Solution:
1. Ask: "Did you solve it? How?"
2. If unresolved, defer the topic until resolution is found
3. If workaround-only, assess whether "understanding why the workaround works" provides enough joy
4. Consider documenting the investigation so far as a "part 1" topic (requires series planning)

---

## Anti-Patterns

### Anti-Pattern 1: Generating Tutorial Topics
**What it looks like**: "How to Set Up Hugo" with vex listed as "learning a new tool"
**Why wrong**: No actual frustration. "Learning something new" is not a vex. Official docs already cover installation.
**Do instead**: Find the specific friction point. "Hugo Local Build Works But Cloudflare Deploy Fails" has real vex (version mismatch between local and CI).

### Anti-Pattern 2: Opinion Without Experience
**What it looks like**: "Why Go Is Better Than Python for CLI Tools" with vex listed as "other languages are slower"
**Why wrong**: This is debate, not experience. No specific problem was solved, no measurable outcome.
**Do instead**: Ground in measurement. "Rewriting a Python CLI in Go Cut Startup Time by 10x" has concrete vex (400ms startup delay) and concrete joy (40ms result).

### Anti-Pattern 3: Skipping the content quality Filter
**What it looks like**: Generating 10 topics and presenting all of them without evaluating each against the three-question test.
**Why wrong**: Quantity over quality. Dilutes content identity. User must re-evaluate every topic manually.
**Do instead**: Apply the filter to every candidate. Reject topics that fail any question. Only present topics that pass all three.

### Anti-Pattern 4: Vague Topic Titles
**What it looks like**: "Kubernetes Networking Issues" or "Docker Problems"
**Why wrong**: Too broad to act on. Which issues? What specifically failed? Reader cannot tell what the post is about.
**Do instead**: Use failure-mode titles. "CoreDNS Returns NXDOMAIN for Internal Services" or "NetworkPolicy Blocks Traffic It Shouldn't" are specific and signal real vex.

### Anti-Pattern 5: Missing Priority Scoring
**What it looks like**: Presenting a topic list without impact/vex/resolution scores or priority tiers.
**Why wrong**: No way to prioritize. User must mentally re-evaluate all topics to decide what to write first.
**Do instead**: Always include the priority matrix with scores for every topic. Always include recommendations (top pick, quick win, deep dive).

---

## Topic Source Quick Reference

### Problem Mining Signals

| Signal | Where to Find | Topic Potential |
|--------|---------------|-----------------|
| Debugging sessions | Recent git commits, shell history | High - fresh frustration |
| Stack Overflow searches | Browser history, bookmarks | High - common problems |
| Error messages | Logs, terminal output | Medium - depends on depth |
| Configuration struggles | Config file changes, dotfiles | Medium - relatable pain |
| "This took forever" | User conversation, retrospectives | High - strong vex signal |

### Gap Analysis Signals

| Gap Type | How to Identify | Value |
|----------|-----------------|-------|
| "See also" missing | Referenced but no post exists | High - reader expectation |
| Prerequisites assumed | "Assuming you know X" statements | Medium - onboarding help |
| Incomplete series | "Part 1" with no Part 2 | Medium - completeness |
| Follow-up questions | Comments, emails, feedback | High - proven demand |

### Technology Expansion Strategy
- Same tool, different feature (Hugo -> Hugo modules)
- Same category, different tool (Hugo -> Zola)
- Integration between covered technologies (Hugo + Cloudflare Pages)
- Common pain points in the ecosystem

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "These are all good topics" | Unfiltered lists waste user time | Apply content quality filter to every candidate |
| "Close enough to vex" | Weak vex = weak post | Reject or find stronger frustration signal |
| "Scoring slows me down" | Unscored lists require user re-evaluation | Complete priority matrix for all topics |
| "The title can be refined later" | Vague titles hide weak topics | Use failure-mode titles now |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/content-filter.md`: Detailed filter criteria and examples
- `${CLAUDE_SKILL_DIR}/references/topic-sources.md`: Mining strategies for each source type
- `${CLAUDE_SKILL_DIR}/references/priority-scoring.md`: Scoring rubrics and examples
