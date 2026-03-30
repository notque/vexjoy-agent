# Autoresearch Optimization Guide

## Scope

The current autoresearch loop supports two optimization scopes:

- `description-only`: mutate the frontmatter `description` and score it with
  trigger-rate eval tasks
- `body-only`: mutate the instruction body and score it with `blind_compare`
  behavioral tasks

This is useful for improving skill routing accuracy and for short, repeatable
instruction-body improvements on real registered skills.

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

Two task families are supported:

### Trigger-rate tasks

Every trigger-rate task must include:

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

### Blind body-compare tasks

Every blind body-compare task must include:

- `query`: the prompt to test
- `eval_mode: blind_compare`
- `judge`: currently `heuristic_socratic_debugging`

Optional fields:

- `name`: label shown in logs and reports
- `split`: `train` or `test`
- `min_score`: minimum candidate score required for the task to count as passed

Example:

```json
{
  "tasks": [
    {
      "name": "socratic-first-turn",
      "query": "Help me think through this bug. My Python script sometimes returns None instead of a dict when the cache is warm. Please do not solve it for me directly.",
      "eval_mode": "blind_compare",
      "judge": "heuristic_socratic_debugging",
      "min_score": 0.7,
      "split": "train"
    }
  ]
}
```

Within one run, tasks must all belong to the same family. The optimizer rejects
mixed trigger-rate and blind body-compare task sets.

If no split markers are present, the loop performs a reproducible random split
using `--train-split` and seed `42`.

`run_eval.py` now accepts the same common task-file wrappers:

- raw list: `[{"query": "...", "should_trigger": true}]`
- task wrapper: `{"tasks": [...]}`
- query wrapper: `{"queries": [...]}`
- split wrapper: `{"train": [...], "test": [...]}`

## Command

Short default run:

```bash
python3 skills/agent-comparison/scripts/optimize_loop.py \
  --target skills/go-testing/SKILL.md \
  --goal "improve routing precision without losing recall" \
  --benchmark-tasks skills/agent-comparison/references/optimization-tasks.example.json \
  --report optimization-report.html \
  --output-dir evals/iterations \
  --verbose
```

Longer search:

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
- `--eval-mode auto|registered|alias`: choose how live trigger eval is isolated
- `--beam-width`: retain the best K improving candidates per round
- `--candidates-per-parent`: generate multiple sibling variants from each frontier candidate
- `--revert-streak-limit`: stop after N rounds without any ACCEPT candidates
- `--holdout-check-cadence`: evaluate the global best on held-out tasks every N rounds
- `--parallel-eval N`: run behavioral eval tasks in parallel isolated worktrees

Short defaults:

- `--max-iterations 1`
- `--revert-streak-limit 1`
- `--holdout-check-cadence 0`
- trigger eval `--num-workers 1`
- trigger eval `--runs-per-query 1`

Recommended search presets:

- Short proof run:
  - default flags only
- Single-path local search:
  - `--beam-width 1 --candidates-per-parent 1 --max-iterations 3 --revert-streak-limit 3`
- Balanced beam search:
  - `--beam-width 3 --candidates-per-parent 2`
- Aggressive exploration:
  - `--beam-width 5 --candidates-per-parent 3 --min-gain 0.0`

## Live Eval Isolation Modes

`run_eval.py` now has three modes:

- `auto`: default. If the target is a real repo skill at `skills/<name>/SKILL.md`, live eval runs in an isolated git worktree with the candidate content patched into the real path. Otherwise it falls back to alias mode.
- `registered`: force isolated worktree evaluation of a real registered skill.
- `alias`: force legacy dynamic command-file evaluation.

For real registered skills, `auto` is the preferred mode. It prevents the evaluator
from accidentally scoring the installed skill instead of the candidate under test.
It also patches the current working-copy skill content into the isolated worktree,
so local uncommitted edits are evaluated correctly.

## Evaluation Model

The loop follows the ADR-131 structure:

1. Hard gates
2. Weighted composite score
3. Held-out regression checks
4. Frontier retention

### Layer 1: Hard Gates

An iteration is rejected immediately if any of these mechanical validity gates fail:

- `parses`
- `compiles`
- `protected_intact`

For description optimization, `parses` and `protected_intact` are the most
important gates. Protected sections fenced by `DO NOT OPTIMIZE` markers must be
preserved verbatim.

### Layer 2: Composite Score

The loop converts evaluation results into a weighted composite score using the
built-in weights in `optimize_loop.py`. Task accuracy affects the component
dimensions (`correctness`, `error_handling`, `language_idioms`, `testing`,
`efficiency`) without zeroing the entire score. This preserves optimization
signal for incremental improvements when a task set is not yet perfect.

A candidate is accepted only if it beats its parent by more than `--min-gain`.

### Layer 3: Held-Out Regression Check

Every `--holdout-check-cadence` rounds, the current global best variant is
scored on the held-out test set. If held-out performance drops below the
baseline while train performance has improved, the loop raises a Goodhart
alarm and stops.

### Layer 4: Frontier Retention

When beam search is enabled:

- each frontier candidate generates `--candidates-per-parent` siblings
- every sibling is scored independently
- the top `--beam-width` ACCEPT candidates become the next frontier
- `best_variant.md` still tracks the single best candidate seen anywhere in the run

When `--beam-width 1 --candidates-per-parent 1`, the behavior collapses back to
the original single-path optimizer.

## Optimization Scopes

The optimizer supports two mutation scopes:

- `description-only`: replace only the YAML frontmatter `description`
- `body-only`: replace only the markdown body below the frontmatter

`generate_variant.py` reconstructs the full file around the selected scope so
the unchanged parts stay intact. Use `description-only` for routing-trigger
work and `body-only` for behavioral work judged from the skill's actual output.

For body optimization, pair `--optimization-scope body-only` with
`blind_compare` tasks so generation and evaluation are measuring the same
surface area.

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

- status, baseline, best score, accepted/rejected counts
- convergence chart
- iteration table with diffs
- review/export controls for accepted snapshot diffs from the original target

## Current Validation Status

What is currently demonstrated:
- deterministic end-to-end improvement runs with readable artifacts
- isolated live optimization for existing registered skills via temporary git worktrees
- blind body-eval runs that require actual skill-trigger evidence before scoring
- score calculations and accept/reject decisions that match the weighted rubric
- short live proof on `skills/read-only-ops/SKILL.md` using
  `references/read-only-ops-short-tasks.json`, improving from one failed positive
  to `2/2` live passes after the accepted description update
- short live body optimization on `skills/socratic-debugging/SKILL.md` using
  `references/socratic-debugging-body-short-tasks.json`, improving from `7.85`
  to `8.45` after the accepted instruction-body update

What remains imperfect:
- live optimization of temporary renamed skill copies still fails to show measured improvement through the dynamic command alias path

So the current tooling is operational for real registered skills and deterministic proof runs, but not yet fully proven for arbitrary temporary renamed clones.

## Short Live Commands

Routing optimization on a real registered skill:

```bash
python3 skills/agent-comparison/scripts/optimize_loop.py \
  --target skills/read-only-ops/SKILL.md \
  --goal "Improve read-only routing precision for realistic user prompts." \
  --benchmark-tasks skills/agent-comparison/references/read-only-ops-short-tasks.json
```

Body optimization on a real registered skill:

```bash
python3 skills/agent-comparison/scripts/optimize_loop.py \
  --target skills/socratic-debugging/SKILL.md \
  --goal "Improve the first response so it asks exactly one question, avoids direct diagnosis, avoids code examples, and does not add tool-permission preamble." \
  --benchmark-tasks skills/agent-comparison/references/socratic-debugging-body-short-tasks.json \
  --optimization-scope body-only
```

The blind body path now fails closed: if the intended skill does not trigger, or
the response falls back into tool-blocked/direct-guidance chatter, the run is
scored as a failure instead of being treated as a weak improvement.

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
