# answers/

Drop one Haiku routing answer per query here, named `<id>.json` (e.g. `q00.json`),
matching the ids in `../queries.json`. Each file is the verbatim JSON the
`model:"haiku"` routing agent returns for the corresponding prompt in
`../prompts/<id>.txt`:

```json
{"agent": "...|null", "skill": "...|null", "pipeline": "...|null", "reasoning": "one sentence", "confidence": "high/medium/low"}
```

Once all 49 answers are present, run from the repo root (or this worktree):

```bash
python3 scripts/routing-ab-test.py --score        # -> ../raw.json (both arms + cost)
python3 scripts/routing-ab-test.py --build-judge  # -> ../judge-input.json (+ private ../uid-map.json)
# dispatch ONE judge agent over judge-input.json, save its JSON to ../judge-output.json
python3 scripts/routing-ab-test.py --rejoin       # -> ../scoreboard.json (per-arm + per-bucket accuracy)
```

This directory is intentionally empty of answers in the committed tree: the live
Haiku run requires an agent-dispatch capability and has not been executed yet.
