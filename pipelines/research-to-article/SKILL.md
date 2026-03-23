---
name: research-to-article
description: |
  Multi-agent research pipeline for voice content generation. Parallel
  research agents gather data, compile findings, then voice pipeline
  generates validated article. Use for "research then write", "article
  with research", "write about [topic]", "full article pipeline", or any
  content needing fact-gathering before voice generation. Do NOT use for
  simple writing without research, editing existing articles, or content
  that does not require a voice profile.
version: 2.0.0
user-invocable: false
context: fork
command: /research-article
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - research then write
    - article with research
    - write about
    - research and article
    - full article pipeline
    - comprehensive article
  pairs_with:
    - voice-orchestrator
  complexity: complex
  category: content-pipeline
---

# Research-to-Article Pipeline

## Operator Context

This skill orchestrates the complete content pipeline: parallel research gathering, structured compilation, voice generation, validation, and output. It implements the **Pipeline Architecture** pattern — gather, compile, ground, generate, validate — with **Domain Intelligence** embedded in voice-first content methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before starting pipeline
- **Over-Engineering Prevention**: Generate the article requested. No speculative additions, no "while I'm here" improvements to other content
- **Parallel Research**: Launch 5 parallel research agents for comprehensive coverage
- **Research-Voice Separation**: Research informs but NEVER dominates narrative. Raw data must be transformed to story
- **Deterministic Validation**: Always validate final output with `voice_validator.py`
- **Wabi-Sabi Authenticity**: Natural imperfections are features, not bugs. Do not over-polish
- **Artifact Persistence**: Save research doc AND article to disk. Context is ephemeral, files persist

### Default Behaviors (ON unless disabled)
- **5 Research Agents**: Primary domain, narrative arcs, external context, community reaction, business context
- **Research Compilation**: Structure findings with Story Arc first, key facts second
- **Voice Mode Selection**: Auto-select mode based on content type (profile, awards, journey, etc.)
- **Article Voice Notes**: Include voice-specific notes in compiled research doc
- **Full Validation**: Run `voice_validator.py` before declaring output complete
- **Timeout Enforcement**: 5-minute per-agent hard timeout, proceed with available data

### Optional Behaviors (OFF unless enabled)
- **Skip Research**: Use provided research data (`--skip-research`)
- **Skip Validation**: Draft mode without deterministic validation (`--skip-validation`)
- **Single Agent Research**: Faster but less thorough (`--quick`)
- **Custom Agent Count**: Override default 5 agents for simpler topics

## What This Skill CAN Do
- Orchestrate end-to-end research-to-article pipeline with parallel agents
- Compile multi-source research into structured documents with story arcs
- Generate voice-authentic articles using voice skills and profiles
- Validate output deterministically with `voice_validator.py`
- Gracefully degrade when research agents timeout or return incomplete data

## What This Skill CANNOT Do
- Generate articles without researching first (use voice-orchestrator instead)
- Edit existing articles (use the appropriate voice skill directly)
- Optimize article performance or SEO (not a content optimization tool)
- Skip validation phases (use `--skip-validation` flag explicitly if draft mode needed)
- Upload to WordPress (use wordpress-uploader skill after pipeline completes)

---

## Instructions

### Phase 1: GATHER (Parallel Research)

**Goal**: Launch parallel research agents to gather comprehensive data on the subject.

**Step 1: Define research scope**

Identify the subject, timeframe, and 6 research dimensions:

```markdown
## Research Scope
Subject: [Person/topic]
Timeframe: [Year or date range]
Agents:
1. [Primary domain] - Core facts, timeline, achievements
2. [Narrative] - Story arcs, character development, turning points
3. [External] - Outside ventures, cross-domain activity
4. [Community] - Fan/audience reaction, social response
5. [Context] - Industry landscape, business implications
6. [Current news] - Last 1-2 weeks: upcoming events, recent developments, announcements
```

**MANDATORY: Agent 6 (Current News) cannot be skipped for profile articles.** The article must feel timely. Search for:
- Upcoming events involving the subject
- Recent developments from the last 2-3 weeks
- Significant changes or announcements
- Media coverage, press conferences, official statements
- Social media announcements or reactions

**Important**: Raw analytics, ratings, or database numbers are for research context only. NEVER surface raw data in the final article. Use data to understand trajectory, then transform to narrative.

**Step 2: Launch 5 parallel agents**

Launch ALL agents in a single message using `Task` with `run_in_background=True`. See `references/research-agents.md` for prompt templates and agent configuration.

**Step 3: Monitor with timeouts**

```
Timeline:
  0:00  - Launch all 5 agents
  2:00  - First progress check (TaskOutput block=false)
  4:00  - Second progress check
  5:00  - HARD TIMEOUT: Proceed with available data
```

**Gate**: At least 3 of 5 agents have returned data. If fewer than 3, supplement with direct WebSearch. Proceed only when gate passes.

### Phase 2: COMPILE (Structure Research)

**Goal**: Merge agent outputs into a single structured research document.

**Step 1: Identify the story arc**

Before organizing facts, determine: What is the STORY here? The story arc is the most important element — it frames every fact, quote, and detail.

**Step 2: Compile research document**

Structure the compiled document following the template in `references/research-agents.md`:
- Story Arc (1-2 paragraphs — the throughline)
- Key Facts (chronological, with dates and quotes)
- Quotes for Article (direct quotes organized by topic)
- Article Angle (suggested framing + voice notes)

**Step 3: Save research artifact**

```bash
content/[site]/test/[subject]-research.md
```

**Gate**: Research document saved to disk with story arc, key facts, and article angle. Proceed only when gate passes.

### Phase 3: GROUND (Establish Context)

**Goal**: Define the emotional anchor, audience, and voice mode before generation.

Answer these four questions:

| Question | Answer |
|----------|--------|
| What emotion drives this? | [e.g., "comedic irony", "celebration", "redemption"] |
| Who is reading? | [e.g., "community members, enthusiasts"] |
| What voice mode? | [e.g., profile, technical, opinion, tutorial] |
| What is the throughline? | [The single story to tell] |

**Gate**: All four grounding questions answered. Voice and mode selected. Proceed only when gate passes.

### Phase 4: GENERATE (Voice Article)

**Goal**: Generate the article using the appropriate voice skill with research as context.

**Step 1: Load voice skill**

Invoke the appropriate voice skill (e.g., `voice-{name}`) via the Skill tool. See `references/voice-variants.md` for voice-specific prompt templates.

**Step 2: Generate with research context**

Key constraints for ALL voices:
- NEVER expose analytics, ratings, or raw data — transform to narrative
- Reference the compiled research document by path
- Apply wabi-sabi: natural imperfections are features
- End with forward momentum — point ahead, not backward

**Step 3: Save draft**

```bash
content/[site]/test/[subject]-article.md
```

**Gate**: Draft article saved to disk. Proceed only when gate passes.

### Phase 5: VALIDATE

**Goal**: Run deterministic validation and refine if needed.

**Step 1: Run validator**

```bash
python3 $HOME/claude-code-toolkit/scripts/voice_validator.py validate \
  --content /path/to/article-draft.md \
  --profile $HOME/claude-code-toolkit/skills/voice-[name]/profile.json \
  --voice [name] \
  --format json
```

**Step 2: Check pass criteria**

| Metric | Requirement |
|--------|-------------|
| Score | >= 60 |
| Errors | 0 |
| Warnings | <= 5 |

**Step 3: Refine if needed**

If validation fails:
1. Address errors first (banned patterns, em-dashes)
2. Address warnings (rhythm, metrics)
3. Re-validate
4. Maximum 3 iterations — if still failing after 3, output with validation report and note issues

**Gate**: Validation passes OR 3 refinement iterations exhausted. Proceed only when gate passes.

### Phase 6: OUTPUT

**Goal**: Deliver final article with validation report and saved artifacts.

**Step 1: Present final output**

```
========================================
 ARTICLE: [Title]
========================================

[Full article content]

========================================
 VALIDATION REPORT
========================================

 Status: PASSED/FAILED
 Score: [X]/100
 Iterations: [N]

 Research: [path to research doc]
 Article: [path to article]

========================================
```

**Step 2: Verify artifacts exist**

Confirm both files are saved:
- Research document at `content/[site]/test/[subject]-research.md`
- Article at `content/[site]/test/[subject]-article.md`

**Gate**: Final output presented with validation report. Both artifacts confirmed on disk. Pipeline complete.

---

## Examples

### Example 1: Full Article Pipeline
User says: "Write an article about [subject]'s 2025"
Actions:
1. Launch 5 parallel research agents on [subject] 2025 (GATHER)
2. Compile findings into story arc (COMPILE)
3. Ground: celebration, community, profile mode (GROUND)
4. Generate with appropriate voice skill, research as context (GENERATE)
5. Validate with voice_validator.py, score 97/100 (VALIDATE)
6. Output article with validation report, both files saved (OUTPUT)
Result: Published-quality article with deterministic validation

### Example 2: Research with Existing Data
User says: "Write article using this research I already have"
Actions:
1. Skip GATHER phase, load provided research (--skip-research)
2. Verify research has story arc, compile if needed (COMPILE)
3. Ground voice and mode based on content type (GROUND)
4. Generate article from provided research (GENERATE)
5. Validate and refine (VALIDATE)
6. Output with report (OUTPUT)
Result: Article from pre-gathered research, still validated

---

## Error Handling

### Error: "Research Agents Timeout After 5 Minutes"
Cause: Agents stuck on paywalled sites, rate-limited APIs, or unresponsive sources
Solution:
1. Proceed with data from agents that completed (graceful degradation)
2. Supplement gaps with direct WebSearch on specific questions
3. Note missing dimensions in compiled research
4. Article quality is still achievable — sufficient research > comprehensive research

### Error: "Validation Score Below 60"
Cause: Voice drift, research language leaking into article, or banned patterns present
Solution:
1. Check for research language ("metrics show", "data indicates") and replace with narrative
2. Check for banned patterns (em-dashes, corporate jargon) and remove
3. Re-read voice profile and adjust tone
4. Maximum 3 refinement iterations before outputting with warning

### Error: "Voice Skill Not Found"
Cause: Requested voice skill does not exist or has wrong path
Solution:
1. List available voice skills with `ls skills/voice-*/SKILL.md`
2. Verify skill name matches exactly (e.g., `voice-yourname` not `voice-your`)
3. Fall back to `voice-orchestrator` which handles voice selection internally

### Error: "Research Document Missing Story Arc"
Cause: Agents returned facts without narrative structure
Solution:
1. Re-read all agent outputs and identify the connecting thread
2. Write story arc manually based on compiled facts
3. Story arc must answer: "What is the STORY of this subject's [timeframe]?"
4. Do not proceed to GENERATE without a clear story arc

---

## Anti-Patterns

### Anti-Pattern 1: Research Language in Article
**What it looks like**: "Data shows that fan engagement increased 40% during Q3"
**Why wrong**: Exposes raw analytics. Readers want stories, not reports. Voice authenticity destroyed.
**Do instead**: Transform data to narrative — "the audience grew every week, and by summer the momentum was undeniable"

### Anti-Pattern 2: Skipping Research Compilation
**What it looks like**: Passing raw agent outputs directly to voice generation
**Why wrong**: No story arc means no throughline. Article becomes a list of facts, not a narrative.
**Do instead**: Complete Phase 2 COMPILE. Identify the story arc FIRST, then organize facts around it.

### Anti-Pattern 3: Over-Polishing the Output
**What it looks like**: Fixing every run-on sentence, removing all fragments, standardizing punctuation
**Why wrong**: Wabi-sabi violation. Natural imperfections are voice fingerprints. Sterile perfection is an AI tell.
**Do instead**: Fix errors (banned patterns, factual mistakes). Keep warnings (rhythm, fragments, run-ons). These are features.

### Anti-Pattern 4: Waiting Indefinitely for Research Agents
**What it looks like**: "Still waiting for Agent 4... it's been 15 minutes..."
**Why wrong**: Diminishing returns. 3-4 agents provide sufficient data. Waiting wastes time without improving quality.
**Do instead**: Enforce 5-minute hard timeout. Proceed with available data. Supplement with targeted WebSearch if needed.

### Anti-Pattern 5: Summarizing at the End
**What it looks like**: "In conclusion, [subject]'s 2025 was defined by three key themes..."
**Why wrong**: Voice-authentic writing never summarizes. Summary paragraphs are an AI tell.
**Do instead**: Point forward. End with momentum -- what comes next, what to watch for, why you should care tomorrow.

### Anti-Pattern 6: Citing Raw Stats in Articles
**What it looks like**: "At 1771.7 in the ratings and climbing, with a community rating of 8.40"
**Why wrong**: Readers don't know or care about raw database numbers. This reads like a stats dump, not a story.
**Do instead**: Use data during research to understand trajectory. In the article, transform to narrative: "having the best stretch of their career right now"

### Anti-Pattern 7: Missing Current News
**What it looks like**: A profile piece about a subject who has a major event tomorrow, but the article doesn't mention it
**Why wrong**: Makes the article feel like a Wikipedia summary rather than timely journalism. Misses the entire reason to read NOW.
**Do instead**: Always search for upcoming events, recent developments, and announcements. The closing sections should reflect where the story is RIGHT NOW.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Pipeline design principles
- [Voice-First Writing](../shared-patterns/voice-first-writing.md) - Voice generation methodology
- [Wabi-Sabi Authenticity](../shared-patterns/wabi-sabi-authenticity.md) - Natural imperfection principle

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Research is good enough with 2 agents" | Missing dimensions lead to shallow articles | Launch all 6, proceed with 4+ after timeout |
| "I can write without compiling first" | No story arc = fact dump, not article | Complete COMPILE phase with story arc |
| "Validation is optional for good writers" | Self-assessment is unreliable | Run `voice_validator.py`, every time |
| "This sounds natural, skip wabi-sabi check" | Over-polished = AI tell | Verify imperfections preserved |
| "Readers won't notice research language" | "Data indicates" kills voice authenticity | Transform ALL data to narrative |
| "Raw data adds credibility" | Readers don't know or care about database numbers | Use data for context, never cite raw numbers in article |
| "Historical facts are enough" | Missing current news makes article feel stale | Search last 1-2 weeks of news, upcoming events |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/research-agents.md`: Agent configuration, prompts, and timeout management
- `${CLAUDE_SKILL_DIR}/references/voice-variants.md`: Voice-specific templates, CLI usage, and proven examples

### Integration

| Skill | Integration |
|-------|-------------|
| `voice-orchestrator` | Used for Phase 4 voice generation |
| `voice-{name}` | Loaded for target voice content |
| `wordpress-uploader` | Upload final article (post-pipeline) |
