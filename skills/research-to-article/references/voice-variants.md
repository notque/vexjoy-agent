# Voice-Specific Variants

## Community/Warm Voice Pipeline

```
/research-article --voice {name} --topic "[subject] [year]" --mode profile
```

### Generation Prompt Template

```
Using the research document at [path], generate an article about [subject].

Voice: {voice-name}
Mode: [profile/awards/journey/etc]

Key constraints:
- NEVER expose analytics or ratings - transform to narrative
- Match the voice's sentence patterns
- Fragment punches for emphasis
- Forward momentum - end looking ahead
- Wabi-sabi: natural imperfections are features

Generate the full article. Focus on the human story, the community.
```

### Default Emotional Anchors
- Community celebration
- Finding light in every story
- Forward momentum

---

## Technical Voice Pipeline

```
/research-article --voice {name} --topic "[tech topic]" --mode technical
```

### Generation Prompt Template

```
Using the research document at [path], generate an article about [subject].

Voice: {voice-name}
Mode: [technical/opinion/tutorial/review]

Key constraints:
- Precision-driven writing
- Systems framing
- Wabi-sabi: natural imperfections are features

Generate the full article.
```

### Default Emotional Anchors
- Precision and clarity
- Systems thinking
- Earned enthusiasm
- Practical application

---

## CLI Usage

```bash
# Full pipeline
/research-article --voice myvoice --topic "Subject 2025" --mode profile

# With existing research
/research-article --voice myvoice --topic "Subject 2025" \
  --research content/test/subject-2025-research.md

# Quick mode (single research agent)
/research-article --voice myvoice --topic "Quick update" --quick

# Skip validation (draft mode)
/research-article --voice myvoice --topic "Draft piece" --skip-validation
```

---

## Example: Full Pipeline Run

This pipeline structure has generated articles with 97/100 validation scores.

### Research Prompts Pattern

**Agent 1 - Core Domain:**
```
Research [subject]'s career/work in [year].
Find: key achievements, notable milestones, significant events.
```

**Agent 2 - Narrative:**
```
Research [subject]'s story arcs in [year].
Find: major transitions, relationships, turning points.
```

**Agent 3 - External:**
```
Research [subject]'s external ventures in [year].
Find: side projects, cross-domain activity, outside interests.
```

**Agent 4 - Community:**
```
Research community reaction to [subject] in [year].
Find: fan response, social media sentiment, viral moments.
```

**Agent 5 - Business:**
```
Research [subject]'s business/contract situation in [year].
Find: deal status, future prospects, industry context.
```

### Validation Result

```
Status: PASSED
Score: 97/100
Errors: 0
Warnings: 1
Iterations: 1
```
