# Research Agent Configuration

## The 5 Research Agents

Launch these **in parallel** using the Task tool with `run_in_background=True`:

| Agent | Focus | What to Find |
|-------|-------|--------------|
| **Career/Work** | Core performance | Key achievements, milestones, notable projects, collaborations |
| **Storylines** | Narrative arcs | Career evolution, transitions, partnerships |
| **Outside Ventures** | Non-primary domain | Music, acting, podcasts, business, personal |
| **Fan Reaction** | Community response | Chants, social media, merchandise, viral moments |
| **Business Context** | Industry landscape | Contract status, industry commentary, future direction |

## Parallel Agent Prompt Template

```markdown
Research [TOPIC] focusing on [FOCUS AREA] for [YEAR].

Find:
1. Key facts with specific dates
2. Direct quotes where possible
3. Significant moments/events
4. Context and background
5. Forward-looking elements (what's next?)

Return structured research with:
- Chronological timeline if applicable
- Notable quotes
- Community reactions
- Industry implications

Format as markdown with clear headers.
```

## Launching Parallel Agents

```
# In a SINGLE message, launch all 5 with run_in_background:
Task(subagent_type=research-subagent-executor, prompt="Research [subject] career/matches [year]...", run_in_background=True)
Task(subagent_type=research-subagent-executor, prompt="Research [subject] storylines [year]...", run_in_background=True)
Task(subagent_type=research-subagent-executor, prompt="Research [subject] outside ventures [year]...", run_in_background=True)
Task(subagent_type=research-subagent-executor, prompt="Research [subject] fan reaction [year]...", run_in_background=True)
Task(subagent_type=research-subagent-executor, prompt="Research [subject] contract/business [year]...", run_in_background=True)
```

## Timeout Management

**Maximum wait: 5 minutes per agent, 10 minutes total for research phase.**

```
Timeline:
  0:00  - Launch all 5 agents
  2:00  - First progress check (TaskOutput block=false)
  4:00  - Second progress check
  5:00  - HARD TIMEOUT: Proceed with available data

Graceful Degradation:
  5/5 complete -> Full pipeline
  3-4/5 complete -> Proceed, note gaps
  1-2/5 complete -> Supplement with direct WebSearch
  0/5 complete -> Fallback to synchronous research
```

**Why this matters:** In practice, agents can get stuck on paywall fetches for 29+ minutes. Proceeding with gathered data still achieves strong validation scores. Sufficient research > comprehensive research.

## Research Document Structure

After all agents return, compile into this format:

```markdown
# [Subject] Research Compilation

**Compiled**: [Date]
**Sources**: 5 parallel research agents
**Purpose**: Article generation with [Voice] pipeline

---

## THE STORY ARC

[1-2 paragraphs summarizing the overall narrative arc. This is the MOST IMPORTANT
section - it frames everything else. What is the story of this subject's year?]

---

## KEY FACTS

### [Major Event 1]
- **Date**:
- **What happened**:
- **Quote**:
- **Significance**:

### [Major Event 2]
...

---

## QUOTES FOR ARTICLE

**On [topic]**: "[Direct quote]"
**On [topic]**: "[Direct quote]"

---

## ARTICLE ANGLE

**Suggested framing**: [How to approach this story]

**[Voice] voice notes**:
- [What emotional anchors to emphasize]
- [What community aspects to highlight]
- [What humor/personality to include]
- [What forward momentum to establish]
```

## Save Location

```bash
content/[site]/test/[subject]-research.md

# Example:
content/your-site/test/subject-2025-research.md
```
