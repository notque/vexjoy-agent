# Voice Infrastructure Reference

Detailed reference for voice file structures, modes, and profile/config schemas.

## Voice File Structure

Each voice requires these files:

```
skills/voice-{name}/SKILL.md        # AI instructions and patterns
skills/voice-{name}/profile.json    # Quantitative metrics targets
skills/voice-{name}/config.json     # Validation settings
skills/voice-{name}/references/samples/  # Few-shot examples (if available)
```

## config.json Schema

| Field | Purpose |
|-------|---------|
| `validation.required_checks` | Checks that must pass |
| `thresholds.pass_score` | Minimum validation score (default: 70) |
| `thresholds.error_max` | Maximum allowed errors (usually 0) |
| `thresholds.warning_max` | Maximum allowed warnings |
| `voice_specific_patterns` | Custom pattern checks for this voice |
| `modes` | Available content modes for this voice |

### Example config.json

```json
{
  "name": "Example Voice",
  "version": "1.0.0",
  "modes": ["technical", "casual", "opinion"],
  "validation": {
    "required_checks": ["banned_phrases", "punctuation"],
    "metric_tolerance": 0.25
  },
  "thresholds": {
    "pass_score": 70,
    "error_max": 0,
    "warning_max": 5
  }
}
```

## profile.json Schema

| Field | Purpose |
|-------|---------|
| `sentence_metrics.average_length` | Target sentence word count |
| `sentence_metrics.length_distribution` | Short/medium/long distribution |
| `word_metrics.contraction_rate` | Target contraction usage |
| `punctuation_metrics.comma_density` | Target comma density |
| `structure_metrics.fragment_rate` | Target fragment usage |
| `pattern_signatures` | Transition words, opening/closing patterns |

## Available Voice Modes

Modes are defined per voice profile in `config.json`. Common mode patterns:

| Mode | Use Case |
|------|----------|
| `technical` | Systems explanation, how-things-work |
| `opinion` | Position pieces with reasoning |
| `tutorial` | Step-by-step guidance |
| `review` | Product/tool assessment |
| `casual` | Chat, conversation |
| `profile` | Subject deep-dives |
| `journey` | Career/project retrospectives |

Create your own voice profiles with `/create-voice` and define custom modes in `config.json`.

## Refinement Fix Strategies

| Violation Type | Fix Strategy |
|---------------|--------------|
| `banned_phrase` | Replace with suggestion or rephrase |
| `punctuation` | Replace em-dash with comma/period |
| `rhythm_violation` | Add short or long sentence to break pattern |
| `metric_deviation` | Adjust overall usage (contractions, etc.) |
| `voice_specific` | Apply voice-specific fix from suggestion |

## Integration with Other Skills

| Skill | Integration Point |
|-------|-------------------|
| `voice-{name}` | Loads SKILL.md for voice patterns and rules |
| `voice-calibrator` | Uses profiles created by calibrator |
| `voice-validator` | Complementary manual validation interface |
| `voice-writer` | Unified voice content generation pipeline |
| `anti-ai-editor` | Uses same banned-patterns.json database |
