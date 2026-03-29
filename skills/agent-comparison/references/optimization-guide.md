# Autoresearch Optimization Guide

## Scope

The current autoresearch loop optimizes a markdown target's frontmatter
`description` using trigger-rate eval tasks. This is useful for improving
skill routing accuracy and similar description-driven dispatch behavior.

It is not a replacement for the manual agent benchmark workflow in Phases 1-4.
If you want to compare real code-generation quality across benchmark tasks, use
the normal A/B process.

## Supported Targets

- `skills/<name>/SKILL.md`
- Other markdown targets with valid YAML frontmatter and a non-empty
  `description`

The loop rejects targets without parseable frontmatter or without a
`description`, because trigger-rate evaluation depends on the target text that
drives routing.

## Supported Task Formats

Every task must include:

- `query`: the prompt to test
- `should_trigger`: whether the target should trigger for that prompt

Optional fields:

- `name`: label shown in logs and reports
- `split`: `train` or `test`
- `complexity`: used for stratified splitting when `split` is omitted

Flat task list:

```json
{
  "tasks": [
    {
      "name": "positive-1",
      "split": "train",
      "complexity": "complex",
      "query": "write table-driven Go tests with subtests and helper functions",
      "should_trigger": true
    },
    {
      "name": "negative-1",
      "split": "test",
      "complexity": "complex",
      "query": "debug a Kubernetes pod stuck in CrashLoopBackOff",
      "should_trigger": false
    }
  ]
}
```

Explicit train/test sets:

```json
{
  "train": [
    {
      "name": "positive-1",
      "query": "write race-safe Go tests for a worker pool",
      "should_trigger": true
    }
  ],
  "test": [
    {
      "name": "negative-1",
      "query": "optimize a PostgreSQL indexing strategy",
      "should_trigger": false
    }
  ]
}
```

If no split markers are present, the loop performs a reproducible random split
using `--train-split` and seed `42`.

## Command

```bash
python3 skills/agent-comparison/scripts/optimize_loop.py \
  --target skills/go-testing/SKILL.md \
  --goal "improve routing precision without losing recall" \
  --benchmark-tasks skills/agent-comparison/references/optimization-tasks.example.json \
  --train-split 0.6 \
  --max-iterations 20 \
  --min-gain 0.02 \
  --beam-width 3 \
  --candidates-per-parent 2 \
  --revert-streak-limit 20 \
  --holdout-check-cadence 5 \
  --report optimization-report.html \
  --output-dir evals/iterations \
  --verbose
```

By default this uses Claude Code's configured model via `claude -p`. Pass `--model` only when you want to override that explicitly.

Useful flags:

- `--dry-run`: exercise the loop mechanics without calling Claude Code
- `--report`: write a live HTML report
- `--output-dir`: persist iteration snapshots and `results.json`
- `--beam-width`: retain the best K improving candidates per round
- `--candidates-per-parent`: generate multiple sibling variants from each frontier candidate
- `--revert-streak-limit`: stop after N rounds without any KEEP candidates
- `--holdout-check-cadence`: evaluate the global best on held-out tasks every N rounds

Recommended search presets:

- Single-path local search:
  - `--beam-width 1 --candidates-per-parent 1`
- Balanced beam search:
  - `--beam-width 3 --candidates-per-parent 2`
- Aggressive exploration:
  - `--beam-width 5 --candidates-per-parent 3 --min-gain 0.0`

## Evaluation Model

The loop follows the ADR-131 structure:

1. Hard gates
2. Weighted composite score
3. Held-out regression checks
4. Frontier retention

### Layer 1: Hard Gates

An iteration is rejected immediately if any of these fail:

- `parses`
- `compiles`
- `tests_pass`
- `protected_intact`

For description optimization, `parses` and `protected_intact` are the most
important gates. Protected sections fenced by `DO NOT OPTIMIZE` markers must be
preserved verbatim.

### Layer 2: Composite Score

The loop converts trigger-rate evaluation results into a weighted composite
score using the built-in weights in `optimize_loop.py`. A candidate is kept only
if it beats its parent by more than `--min-gain`.

### Layer 3: Held-Out Regression Check

Every `--holdout-check-cadence` rounds, the current global best variant is
scored on the held-out test set. If held-out performance drops below the
baseline while train performance has improved, the loop raises a Goodhart
alarm and stops.

### Layer 4: Frontier Retention

When beam search is enabled:

- each frontier candidate generates `--candidates-per-parent` siblings
- every sibling is scored independently
- the top `--beam-width` KEEP candidates become the next frontier
- `best_variant.md` still tracks the single best candidate seen anywhere in the run

When `--beam-width 1 --candidates-per-parent 1`, the behavior collapses back to
the original single-path optimizer.

## Deletion Safety Rule

Deleting sections is allowed only with explicit justification.

- `generate_variant.py` detects removed `##` headings
- the model must return a `deletion_justification`
- `optimize_loop.py` rejects deletions without one

This enforces ADR-131's "no deletion without justification" rule.

## Iteration Artifacts

When `--output-dir` is set, the loop writes:

- `001/variant.md`
- `001/scores.json`
- `001/verdict.json`
- `001/diff.patch`
- `best_variant.md`
- `results.json`

`results.json` also records search metadata such as `beam_width`,
`candidates_per_parent`, and per-iteration frontier selection markers.

When `--report` is set, it also writes a live HTML dashboard showing:

- status, baseline, best score, kept/reverted counts
- convergence chart
- iteration table with diffs
- review/export controls for kept snapshot diffs from the original target

## Choosing Good Eval Tasks

1. Include both positive and negative prompts.
2. Put realistic user phrasing in both train and held-out sets.
3. Keep at least one out-of-domain negative example in held-out.
4. Do not let the eval set collapse into benchmark keywords only.

## Limitations

Current limitations are intentional and documented:

- The loop does not execute full code-generation benchmarks.
- Pattern-based benchmark tasks with `prompt`, `expected_patterns`, and
  `forbidden_patterns` are not supported by `optimize_loop.py`.
- For full agent quality comparisons, continue to use the manual benchmark and
  grading flow in Phases 1-4.
