# Voice Profile

**Status**: Not yet calibrated

---

## Instructions

Run `/voice calibrate` with 3-5 writing samples to generate a voice profile.

### Quick Start

```
/voice calibrate content/posts/2024-12-post-1.md content/posts/2024-12-post-2.md content/posts/2024-12-post-3.md
```

Or analyze all posts:

```
/voice calibrate --all
```

---

## Template

After calibration, this file will contain:

```markdown
## Voice Profile: [Author Name]

**Generated**: [Date]
**Samples Analyzed**: [N] posts ([X] words total)

### Sentence Patterns
[Distribution and opening patterns]

### Word Preferences
[Transitions, avoided words, technical style]

### Structural Habits
[Paragraph length, headers, lists]

### Tone Markers
[Formality, humor, person usage]

### Distinctive Elements
[Patterns that differentiate this voice]
```

---

## Usage After Calibration

Reference this profile when creating content:

1. **New posts**: "Write about [topic] using my voice profile"
2. **Editing**: "Review this draft against my voice profile"
3. **Quick check**: "Does this paragraph match my voice?"
