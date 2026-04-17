# Skill Creator Bundled Components

## Bundled Agents

The `agents/` directory contains prompts for specialized subagents used by this skill. Read them when you need to spawn the relevant subagent.

- `agents/grader.md` -- Evaluate assertions against outputs with cited evidence
- `agents/comparator.md` -- Blind A/B comparison of two outputs
- `agents/analyzer.md` -- Post-hoc analysis of why one version beat another

## Bundled Scripts

- `scripts/run_eval.py` -- Execute a skill against a test prompt via `claude -p`
- `scripts/aggregate_benchmark.py` -- Compute pass rate statistics across runs
- `scripts/optimize_description.py` -- Train/test description optimization loop
- `scripts/package_results.py` -- Consolidate iteration artifacts into a report
- `scripts/eval_compare.py` -- Generate blind comparison HTML viewer

## Workspace Layout

Organize eval results by iteration:

```
skill-workspace/
├── evals/evals.json
├── iteration-1/
│   ├── eval-descriptive-name/
│   │   ├── with_skill/outputs/
│   │   ├── without_skill/outputs/
│   │   └── grading.json
│   └── benchmark.json
└── iteration-2/
    └── ...
```

## Eval evals.json Format

Save test cases to `evals/evals.json` in the workspace (not in the skill directory -- eval data is ephemeral):

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "name": "descriptive-name",
      "prompt": "The realistic user prompt",
      "assertions": []
    }
  ]
}
```

## Description Optimization

After the skill works well, optimize the description for triggering accuracy.

Generate 20 eval queries -- 10 that should trigger, 10 that should not. The should-not queries are most important: near-misses from adjacent domains, not obviously irrelevant queries.

Run the optimization loop:
```bash
python3 scripts/optimize_description.py \
  --skill-path path/to/skill \
  --eval-set evals/trigger-eval.json \
  --max-iterations 5
```

This splits queries 60/40 train/test, evaluates the current description (3 runs per query for reliability), proposes improvements based on failures, and selects the best description by test-set score to avoid overfitting.
