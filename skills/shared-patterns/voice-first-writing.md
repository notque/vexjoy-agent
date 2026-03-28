# Voice-First Writing Pattern

**All writing in this repository follows the voice-first research pipeline.**

This pattern applies to:
- Blog articles
- Documentation
- READMEs
- Commit messages
- Technical explanations
- Any written content

---

## The Pipeline

```
RESEARCH → COMPILE → GROUND → GENERATE → VALIDATE
```

### Why This Works

A reference article achieved 97/100 validation using this exact pipeline:

1. **5 parallel research agents** gathered comprehensive data
2. **Research compilation** structured findings with story arc
3. **Grounding** established emotional anchor and audience
4. **Generation** used voice skill with research as context
5. **Validation** ensured quality through deterministic checks
6. **Wabi-sabi** prevented over-polishing (perfection is an AI tell)

---

## Quick Reference

### For Any Writing Task

```
1. RESEARCH - What needs to be understood first?
   - Launch parallel agents if complex
   - Single focused search if simple
   - Gather context before writing

2. COMPILE - Structure what you learned
   - Story arc / purpose first
   - Key facts
   - Relevant context

3. GROUND - Establish the frame
   - Who is reading this?
   - What emotion/purpose drives it?
   - What voice profile?

4. GENERATE - Write with voice
   - Load voice skill
   - Reference research
   - Never expose raw data

5. VALIDATE - Check quality
   - Run voice_validator.py
   - Score >= 60 for pass
   - Fix errors, accept warnings
```

### Voice Selection

Select the appropriate voice profile based on content type. Match the voice to the audience and purpose:

| Content Type | Voice Traits | Why |
|--------------|-------------|-----|
| Community articles | Warmth, celebration | Inclusive, welcoming tone |
| Technical articles | Precision, systems thinking | Clarity, earned enthusiasm |
| Technical docs | Clarity, precision | Direct, informative |
| READMEs | Casual mode | Direct, helpful |
| Commit messages | Minimal | Concise, accurate |

---

## The Research Prompt That Works

This is the proven prompt structure:

```
Research [TOPIC] for [PURPOSE].

Find:
1. Key facts with specific details
2. Direct quotes where possible
3. Context and background
4. Forward-looking elements

Return structured markdown with clear headers.
```

For comprehensive coverage, launch 5 agents in parallel:

| Agent | Focus |
|-------|-------|
| 1 | Primary subject matter |
| 2 | Narrative/story elements |
| 3 | External context |
| 4 | Community/audience perspective |
| 5 | Future/implications |

---

## The Generation Prompt That Works

```
Using the research at [path], [write/generate/create] [content type] about [topic].

Voice: [voice-name]
Mode: [see voice skill for modes]

Key constraints:
- [Voice-specific constraints from skill]
- Wabi-sabi: natural imperfections are features
- Never expose raw data/analytics - transform to narrative

[Specific requirements for this piece]
```

---

## The Wabi-Sabi Principle

**Perfection is an AI tell.**

What NOT to "fix":
- Run-on sentences that build excitement
- Sentence fragments for emphasis
- Casual punctuation that flows naturally
- Self-corrections and refinements
- Parenthetical asides

These "imperfections" are fingerprints of human writing.

See: `skills/shared-patterns/wabi-sabi-authenticity.md`

---

## Validation Requirements

All voice content must pass validation:

```bash
python3 ~/.claude/scripts/voice_validator.py validate \
  --content [file] \
  --voice [voice-name] \
  --format json
```

**Pass criteria:**
- Score >= 60
- Errors = 0 (hard stop on errors)
- Warnings acceptable (wabi-sabi)

---

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Writing without research | Shallow content | Research first, always |
| Skipping grounding | Inconsistent voice | Establish frame before writing |
| Over-polishing | Wabi-sabi violation | Keep natural texture |
| Ignoring validation | Quality drift | Always validate |
| Exposing raw data | Data-forward, not story-forward | Transform to narrative |
| Generic language | Lacks specificity | Name actual things |

---

## Examples

### README (Casual Mode)

```markdown
Research: What does this module do? What problem does it solve?
Ground: Reader is developer wanting to use this.
Generate: Clear, direct explanation with examples.
Validate: Check for corporate jargon, ensure clarity.
```

### Blog Article (Community Voice)

```markdown
Research: 5 parallel agents on subject's year.
Compile: Story arc + key facts + quotes.
Ground: Community celebration, finding light.
Generate: Warm, specific, forward-looking.
Validate: Score >= 60, no em-dashes.
```

### Technical Doc (Technical Mode)

```markdown
Research: How does this actually work?
Compile: Architecture + patterns + gotchas.
Ground: Reader knows basics, wants depth.
Generate: Precise, systems-thinking, practical.
Validate: Accuracy over style.
```

---

## Integration Points

This pattern is referenced by:
- `pipelines/voice-writer/SKILL.md` - Full orchestration
- `skills/voice-{name}/SKILL.md` - Individual voice skills
- `pipelines/research-to-article/SKILL.md` - Article pipeline
- `CLAUDE.md` - Repository default behavior
