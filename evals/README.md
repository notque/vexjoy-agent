# Evals

Blind A/B testing framework for evaluating new skills before they merge into the toolkit.

## Purpose

Every new skill must prove it adds measurable value over Claude's default behavior (no skill loaded). Visual code review alone misses subtle quality regressions -- the first A/B test caught 2 critical bugs that review missed (ADR-127). This directory holds the test plans, scoring rubrics, and case files for each evaluation.

## Methodology

1. **Parallel execution**: Each test case runs two variants -- one with the skill loaded, one without (baseline). For three-way comparisons, a third variant uses an existing alternative skill.
2. **Blind evaluation**: Outputs are labeled A/B (or X/Y/Z) with randomized assignment. The evaluator never knows which variant produced which output.
3. **Integer scoring**: Each output is scored 1-5 on skill-specific dimensions, then dimension averages are compared.
4. **60% win condition**: The skill variant must win on 60%+ of test cases to pass. Ties count against the new skill -- it must prove it adds value.
5. **Statistical reliability**: Each variant runs 3 times per case (`--runs-per-query 3`).

Verdict thresholds:
- **PASS** (>= 60%): Skill adds measurable value, proceed to merge.
- **MARGINAL** (40-59%): Skill needs improvement before merge.
- **FAIL** (< 40%): Skill does not add value over baseline.

## Adding a New Evaluation

1. Create a subdirectory: `evals/<skill-name>-eval/` (or a descriptive grouping name).
2. Add a `README.md` with the test plan: skills under test, claims, metrics, win conditions.
3. Add a `scoring-rubric.md` defining dimensions with 1-5 anchor descriptions.
4. Add `*-cases.md` files with concrete test prompts (5-7 cases per skill).
5. Run the eval using the `skill-eval` toolchain (see execution steps in each test plan).

## Directory Structure

```
evals/
  README.md                  # This file
  new-skills-ab-test/        # Canonical example evaluation
    README.md                # Test plan (progressive depth, explanation traces, multi-persona critique)
    scoring-rubric.md        # Blind evaluation rubric with dimension anchors
    *-cases.md               # Test case files per skill
```

See `new-skills-ab-test/` for the canonical example of a well-structured evaluation.
