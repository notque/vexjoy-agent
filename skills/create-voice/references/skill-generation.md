# Skill Generation Guide

Detailed reference for Step 5: GENERATE of the create-voice pipeline.

---

## Files to Create

1. **`skills/voice-{name}/SKILL.md`** -- The voice skill itself (2000+ lines)
2. **`skills/voice-{name}/config.json`** -- Validation configuration
3. **`skills/voice-{name}/profile.json`** -- Already created in Step 2

---

## SKILL.md Structure

The sections, in order of importance by line count. Target 400+ lines of samples and ~200 lines of rules, because V7-V9 had 500+ lines of rules with 100 lines of samples and failed authorship matching -- V10 inverted that ratio and passed 5/5:

| Section | Target Lines | Why This Size |
|---------|-------------|---------------|
| Extensive Authentic Samples | 400+ | THIS IS WHAT MAKES AUTHORSHIP MATCHING WORK. V7-V9 failed with rules-only. V10 passed with 100+ samples. |
| Voice Metrics (from profile.json) | ~100 | Quantitative targets give the model measurable goals, not vague aspirations |
| Rules and Prohibitions | ~200 | Hard constraints prevent the worst AI tells |
| Phrase Fingerprints | ~50 | Exact phrases that roasters use to confirm identity |
| Generation Protocol | ~100 | Pre/During/Post checklists keep output consistent |
| Natural Typos | ~20 | Authenticity markers that signal human-ness |
| Contrastive Examples | ~50 | Shows the model what NOT to do with concrete alternatives |
| Thinking Patterns | ~80 | Cognitive architecture, not just surface style |

**Total: 2000+ lines minimum. Most should be SAMPLES, not rules.** Do NOT pad with verbose rules to hit the line count -- the goal is 2000+ lines of USEFUL content, primarily samples.

---

## SKILL.md Frontmatter

```yaml
---
name: voice-{name}
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
description: |
  Apply {Name}'s voice profile for content generation: [2-3 key traits],
  and modal writing. Use when generating content that must match {Name}'s
  distinctive voice. Do NOT use for voice analysis, voice profile creation,
  or generating content in other voices.
version: 1.0.0
command: /voice-{name}
---
```

---

## Sample Organization (THE MOST IMPORTANT SECTION)

Organize samples from Step 1 into the SKILL.md following this structure:

**By Response Length:**
- Very short (1 sentence, ~{X}% of responses): Include 10+ samples
- Short (2-3 sentences, ~{X}% of responses): Include 15+ samples
- Medium (4-6 sentences, ~{X}% of responses): Include 10+ samples
- Long (paragraph+, ~{X}% of responses): Include 5+ samples

**By Pattern Type:**
- Admitting Mistakes: 5+ samples
- Acknowledging Limits: 5+ samples
- Respectful Disagreement: 5+ samples
- Technical Expertise (delivered casually): 5+ samples
- Strong Opinions (unhedged): 5+ samples
- Casual Closers: 5+ samples
- Sarcasm/Wit (if applicable): examples

---

## Voice Metrics Section

Transfer the profile.json data into human-readable tables with targets and tolerances:

```markdown
| Metric | Target | Tolerance | Notes |
|--------|--------|-----------|-------|
| Average sentence length | {X} words | +/- 2 words | Primary rhythm indicator |
| Short sentences (3-10 words) | {X}% | +/- 5% | For emphasis and pacing |
```

---

## Two-Layer Architecture

Design the skill with two layers:

- **Layer A (Always-On Base Voice)**: Core traits, sentence rhythm, punctuation signature, contraction rate, function word signature. These apply to ALL content regardless of mode.
- **Layer B (Mode-Specific Overlays)**: Different modes (e.g., technical, casual, opinion, review) that adjust tone, formality, and structure while keeping Layer A constant.

---

## Prompt Engineering Techniques (Apply Throughout)

These techniques were validated over 10 iterations of a reference voice:

1. **Probability Dampening**: Use "**subtly**", "**slightly**", "**generally**" before traits. Without dampening, the model cranks traits to 100%
2. **Attention Anchoring**: **Bold** all negative constraints. The model pays more attention to formatted text
3. **XML Context Tags**: Use `<context type="static-instructions">` for directives and `<context type="safety-guardrails">` for prohibitions. Structured tags signal instruction priority to the model
4. **Few-Shot Examples**: Include 3+ examples for every prohibition (especially "It's not X. It's Y"). Rules without examples are abstract; examples are concrete
5. **Contrastive Pairs**: For every "DO" include a "DON'T" with concrete text. The model needs to see both sides of the boundary

---

## config.json Template

Create the validation configuration:

```json
{
  "name": "{Name}",
  "version": "1.0.0",
  "description": "{Brief voice description}",
  "modes": ["technical", "casual", "opinion"],
  "validation": {
    "strict_banned_patterns": true,
    "em_dash_forbidden": true,
    "metric_tolerance": 0.20,
    "required_checks": ["banned_phrases", "punctuation", "rhythm"],
    "optional_checks": ["metrics", "sentence_starters", "opening_pattern"]
  },
  "thresholds": {
    "pass_score": 70,
    "error_max": 0,
    "warning_max": 3
  },
  "voice_specific_patterns": []
}
```

Adjust `em_dash_forbidden`, `modes`, and `pass_score` based on the specific voice's characteristics.
