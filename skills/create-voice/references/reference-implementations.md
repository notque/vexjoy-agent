# Create Voice — Reference Implementations and Components

### Reference Implementations

Study any existing voice profile in `skills/voice-*/` to understand what "done" looks like. A complete voice profile contains:

| File | Typical Size | What to Learn |
|------|-------------|---------------|
| `skills/voice-{name}/SKILL.md` | 2000+ lines | Voice rules, samples, patterns, metrics |
| `skills/voice-{name}/references/samples/` | 5-10 files | How samples should be organized by source and date |
| `skills/voice-{name}/config.json` | ~20 lines | Validation configuration structure |
| `skills/voice-{name}/profile.json` | ~80 lines | Profile structure from voice-analyzer.py |

### Components This Skill Delegates To

| Component | Type | What It Does | When Called |
|-----------|------|-------------|-------------|
| `scripts/voice-analyzer.py analyze` | Script | Extract quantitative metrics from writing samples | Step 2: EXTRACT |
| `scripts/voice-analyzer.py compare` | Script | Compare two voice profiles | Optional (cross-voice comparison) |
| `scripts/voice-validator.py validate` | Script | Validate generated content against voice profile | Step 6: VALIDATE |
| `scripts/voice-validator.py check-banned` | Script | Quick banned pattern check | Step 6: VALIDATE |
| `scripts/data/banned-patterns.json` | Data | AI pattern database used by validator | Step 6 (via validator) |
| `skills/workflow/references/voice-calibrator.md` | Skill | Voice skill template (lines 1063-1554, including the validation checklist) | Step 5: GENERATE (template reference) |
