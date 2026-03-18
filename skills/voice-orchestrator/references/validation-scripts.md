# Voice Validation Script Reference

Commands and exit codes for the deterministic voice validation scripts.

## Full Validation

```bash
python3 $HOME/ai-overkill/scripts/voice_validator.py validate \
  --content /path/to/content.md \
  --profile $HOME/ai-overkill/skills/voice-{name}/profile.json \
  --voice {name} \
  --format json
```

## Check Banned Patterns Only (Fast)

```bash
python3 $HOME/ai-overkill/scripts/voice_validator.py check-banned \
  --content /path/to/content.md \
  --voice {name} \
  --format json
```

## Check Rhythm Only

```bash
python3 $HOME/ai-overkill/scripts/voice_validator.py check-rhythm \
  --content /path/to/content.md \
  --profile $HOME/ai-overkill/skills/voice-{name}/profile.json \
  --format json
```

## Analyze Writing Samples

```bash
python3 $HOME/ai-overkill/scripts/voice_analyzer.py analyze \
  --samples /path/to/samples/ \
  --output /path/to/profile.json
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pass (score >= 70) |
| 1 | Fail (score < 70 or errors) |
| 2 | Execution error (file not found, invalid JSON) |

## Expected JSON Output

```json
{
  "pass": true,
  "score": 85,
  "violations": [
    {
      "type": "banned_phrase|punctuation|rhythm_violation|metric_deviation|voice_specific",
      "severity": "error|warning|info",
      "line": 5,
      "column": 12,
      "text": "matched text",
      "message": "explanation",
      "suggestion": "how to fix"
    }
  ],
  "metrics": {
    "contraction_rate": 0.72,
    "comma_density": 0.045,
    "avg_sentence_length": 15.3
  },
  "summary": {
    "errors": 0,
    "warnings": 2,
    "info": 1,
    "passed_checks": 8,
    "total_checks": 10
  }
}
```

## CLI Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--voice` | Yes | Voice name (e.g., 'default', or any custom voice) |
| `--subject` | Yes* | Topic/subject for generation (*not needed with --validate) |
| `--mode` | No | Content mode from voice config |
| `--content` | No | Path to existing content file (for --validate) |
| `--validate` | No | Validate-only mode, no generation |
| `--skip-validation` | No | Draft mode, skip validation step |
| `--verbose` | No | Show full validation details |

## Related Files

- `scripts/voice_validator.py`: Deterministic validation CLI
- `scripts/voice_analyzer.py`: Profile generation CLI
- `scripts/data/banned-patterns.json`: Pattern database
- `skills/voice-{name}/profile.json`: Voice metrics targets
- `skills/voice-{name}/config.json`: Validation settings
- `skills/voice-{name}/SKILL.md`: Voice instructions and patterns
