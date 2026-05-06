# Artifact Schemas

JSON contracts for all eval pipeline artifacts. Field names, types, and nesting are
contracts between producers and consumers. Downstream scripts parse by field name —
do not rename fields without updating all consumers.

## Producer/Consumer Map

| Schema | Producer | Consumer(s) |
|--------|----------|-------------|
| `evals.json` | Skill creator (human) | `run_eval.py`, grader agent |
| `grading.json` | grader agent | `aggregate_benchmark.py`, analyzer agent |
| `benchmark.json` | `aggregate_benchmark.py` | analyzer agent, `package_results.py` |
| `comparison.json` | comparator agent | analyzer agent |
| `analysis.json` | analyzer agent | `package_results.py`, skill creator |
| `timing.json` | `run_eval.py` | `aggregate_benchmark.py` |
| `metrics.json` | `run_eval.py` | grader agent |
| `eval_metadata.json` | `run_eval.py` | grader agent, comparator agent |
| `trigger-eval.json` | Skill creator (human) | `optimize_description.py` |

---

## evals.json

Location: `skill-workspace/evals/evals.json`

```json
[
  {
    "eval_id": "string — unique identifier for this eval, used as directory name",
    "prompt": "string — the test prompt text passed to claude -p",
    "assertions": [
      "string — one assertion per entry, binary and evidence-checkable"
    ],
    "metadata": {
      "description": "string — optional human-readable description of what this eval tests",
      "tags": ["optional array of tags for filtering"]
    }
  }
]
```

**Rules**:
- `eval_id` must be a valid directory name (kebab-case recommended)
- Each assertion must be binary: it either passes or fails, with evidence
- Assertions should test skill-specific behavior, not generic output properties

---

## grading.json

Location: `skill-workspace/iteration-N/{eval-id}/grading.json`

```json
{
  "eval_id": "string — matches the eval_id from evals.json",
  "configuration": "string — 'with_skill' or 'without_skill'",
  "timestamp": "string — ISO 8601 timestamp",
  "assertions": [
    {
      "assertion": "string — the assertion text from evals.json",
      "verdict": "string — 'PASS' or 'FAIL'",
      "evidence": "string — quoted excerpt or file reference",
      "confidence": "string — 'high', 'medium', or 'low'"
    }
  ],
  "pass_count": "integer",
  "fail_count": "integer",
  "pass_rate": "float — range 0.0 to 1.0",
  "implicit_claims": [
    {
      "claim": "string",
      "verdict": "string — 'VERIFIED', 'UNVERIFIED', or 'CONTRADICTED'",
      "evidence": "string"
    }
  ],
  "eval_critique": {
    "non_discriminating_assertions": ["array of assertion text strings"],
    "recommendation": "string"
  },
  "grader_notes": "string or null"
}
```

**Required fields for `aggregate_benchmark.py`**: `pass_rate`, `pass_count`, `fail_count`

---

## benchmark.json

Location: `skill-workspace/iteration-N/benchmark.json`

```json
{
  "skill_name": "string",
  "workspace": "string — absolute path",
  "timestamp": "string — ISO 8601",
  "eval_count": "integer",
  "with_skill": {
    "pass_rate": {
      "mean": "float",
      "stddev": "float",
      "min": "float",
      "max": "float"
    },
    "tokens": {
      "mean": "float",
      "stddev": "float"
    },
    "time_seconds": {
      "mean": "float",
      "stddev": "float"
    }
  },
  "without_skill": {
    "pass_rate": { "mean": "float", "stddev": "float", "min": "float", "max": "float" },
    "tokens": { "mean": "float", "stddev": "float" },
    "time_seconds": { "mean": "float", "stddev": "float" }
  },
  "delta": {
    "pass_rate": "float or null — with_skill minus without_skill",
    "description": "string — human-readable interpretation"
  },
  "eval_results": [
    {
      "eval_id": "string",
      "configuration": "string",
      "pass_rate": "float",
      "pass_count": "integer",
      "fail_count": "integer",
      "without_skill_pass_rate": "float or null",
      "with_skill_tokens": "integer",
      "with_skill_duration": "float",
      "without_skill_tokens": "integer",
      "without_skill_duration": "float"
    }
  ]
}
```

**Required fields for analyzer agent**: `with_skill.pass_rate.mean`,
`without_skill.pass_rate.mean`, `delta.pass_rate`

---

## comparison.json

Location: `skill-workspace/iteration-N/{eval-id}/comparison.json`

```json
{
  "eval_id": "string",
  "timestamp": "string — ISO 8601",
  "rubric": [
    {
      "criterion": "string",
      "description": "string",
      "weight": "float — all weights sum to 1.0"
    }
  ],
  "scores": {
    "A": {
      "criteria_scores": [
        {
          "criterion": "string — must match rubric criterion name",
          "score": "integer — 1 to 5",
          "rationale": "string — specific evidence"
        }
      ],
      "total_score": "float — weighted sum normalized to 1-10 scale",
      "assertion_pass_rate": "float or null"
    },
    "B": {
      "criteria_scores": [],
      "total_score": "float",
      "assertion_pass_rate": "float or null"
    }
  },
  "winner": "string — 'A', 'B', or 'tie'",
  "winner_margin": "float — absolute difference in total_score",
  "reasoning": "string — 2-4 sentences with specific criterion references",
  "confidence": "string — 'high', 'medium', or 'low'",
  "comparator_notes": "string or null"
}
```

**Required fields for analyzer agent**: `winner`, `scores.A.total_score`,
`scores.B.total_score`, `reasoning`

---

## analysis.json

Location: `skill-workspace/iteration-N/analysis.json`

```json
{
  "mode": "string — 'comparison' or 'benchmark'",
  "timestamp": "string — ISO 8601",
  "skill_won": "boolean",
  "findings": [
    {
      "category": "string — one of: winner_factors, loser_improvements, instruction_analysis, transcript_waste, assertion_quality, metric_outliers, variance",
      "priority": "string — 'high', 'medium', or 'low'",
      "finding": "string — specific observation with evidence",
      "actionable_suggestion": "string — concrete change"
    }
  ],
  "improvements_for_skill": [
    {
      "target": "string — which section/instruction",
      "current_behavior": "string",
      "desired_behavior": "string",
      "rationale": "string",
      "generalization_risk": "string — 'low', 'medium', or 'high'"
    }
  ],
  "improvements_for_evals": [
    {
      "assertion": "string",
      "problem": "string",
      "replacement": "string"
    }
  ],
  "benchmark_summary": {
    "with_skill_pass_rate_mean": "float or null",
    "without_skill_pass_rate_mean": "float or null",
    "delta": "float or null",
    "comparator_win_rate": "float or null",
    "top_failure_categories": ["array of strings"]
  },
  "analyzer_notes": "string or null"
}
```

**Required fields for `package_results.py`**: `findings`, `improvements_for_skill`,
`benchmark_summary.delta`

---

## timing.json

Location: `skill-workspace/iteration-N/{eval-id}/{configuration}/timing.json`

```json
{
  "duration_seconds": "float — wall-clock seconds for the claude -p run",
  "tokens_total": "integer — sum of input_tokens and output_tokens",
  "timed_out": "boolean — true if the run hit the timeout limit"
}
```

Produced by: `run_eval.py`
Consumed by: `aggregate_benchmark.py`

---

## metrics.json

Location: `skill-workspace/iteration-N/{eval-id}/{configuration}/metrics.json`

```json
{
  "tool_usage": {
    "Read": "integer — number of Read tool calls",
    "Write": "integer",
    "Edit": "integer",
    "Bash": "integer",
    "Grep": "integer",
    "Glob": "integer",
    "Agent": "integer"
  },
  "total_tool_calls": "integer — sum of all tool_usage values"
}
```

Produced by: `run_eval.py`
Consumed by: grader agent (for context about execution behavior)

---

## trigger-eval.json

Location: `skill-workspace/evals/trigger-eval.json`

```json
[
  {
    "query": "string — user prompt to test triggering",
    "should_trigger": "boolean — true if the skill should activate for this query"
  }
]
```

**Conventions**:
- Include 10 should_trigger: true entries (vary directness and phrasing)
- Include 10 should_trigger: false entries (near-miss adjacent domains)
- Use realistic prompts with context, not abstract one-liners
- Test edge cases where the skill competes with adjacent skills

Produced by: Skill creator (human)
Consumed by: `optimize_description.py`
