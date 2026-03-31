# Validation Scripts Reference

Command reference and output schema for Phase 4 (VALIDATE) of the voice-writer pipeline.

---

## Primary Validation Command

```bash
python3 $HOME/claude-code-toolkit/scripts/voice-validator.py validate \
  --content /tmp/voice-content-draft.md \
  --profile $HOME/claude-code-toolkit/skills/voice-{name}/profile.json \
  --voice {name} \
  --format json
```

Replace `{name}` with the voice name (e.g., `myvoice`).

---

## Output Schema

The validator returns JSON with the following shape:

```json
{
  "pass": true,
  "score": 82,
  "threshold": 75,
  "iterations": 1,
  "violations": [
    {
      "line": 14,
      "text": "delve into",
      "type": "error",
      "rule": "banned_phrase",
      "suggestion": "Remove or replace with direct verb"
    }
  ],
  "warnings": [],
  "metrics": {
    "avg_sentence_len": 14.8,
    "contraction_rate": 0.65,
    "short_sentence_ratio": 0.32
  }
}
```

---

## Decision Logic (from Phase 4)

| Condition | Action |
|-----------|--------|
| `pass == true` AND `score >= threshold` | Proceed to Phase 6: JOY-CHECK |
| `pass == false` AND `iterations < 3` | Proceed to Phase 5: REFINE |
| `pass == false` AND `iterations >= 3` | Proceed to Phase 6: JOY-CHECK with failure report |

---

## Additional Scripts

### Negative Framing Scanner (Phase 6 pre-filter)

```bash
python3 $HOME/claude-code-toolkit/scripts/scan-negative-framing.py /tmp/voice-content-draft.md
```

Returns a list of regex-matched negative framing patterns (victimhood, accusation, bitterness, passive aggression) with suggested reframes.

If this script is unavailable, skip the regex pre-filter and proceed directly to LLM-based joy-check analysis. The regex pre-filter is an optimization, not a requirement.

---

## Validator Help

```bash
python3 $HOME/claude-code-toolkit/scripts/voice-validator.py --help
```

Use this to check available flags if the command syntax above fails.
