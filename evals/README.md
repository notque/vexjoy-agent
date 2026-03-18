# Agent Evaluation System

A formal evaluation infrastructure for testing Claude Code agents and skills.

## Quick Start

```bash
# Run a single task
python evals/harness.py run evals/tasks/routing/task-001.yaml

# Run with multiple trials (for pass@k measurement)
python evals/harness.py run evals/tasks/voice-generation/task-001.yaml --trials 3

# Run all tasks in a category
python evals/harness.py suite evals/tasks/routing/

# Save transcripts for agent-based grading
python evals/harness.py run evals/tasks/code-review/task-001.yaml --save-transcripts
```

## Directory Structure

```
evals/
├── harness.py           # Main eval runner
├── task_schema.yaml     # Schema documentation for tasks
├── tasks/
│   ├── routing/         # Tests for /do routing decisions
│   ├── agent-creation/  # Tests for agent-creator-engineer
│   ├── code-review/     # Tests for code review agents
│   └── voice-generation/ # Tests for voice skills
├── graders/             # Custom grader implementations
├── rubrics/             # LLM-as-judge rubric documents
├── results/             # Eval run outputs (JSON)
└── scripts/             # Utility scripts
```

## Task YAML Format

```yaml
task:
  id: "unique-task-id"
  name: "Human readable name"
  description: "What this task tests"
  category: "routing"
  type: "capability"  # or "regression"

  input:
    prompt: "The prompt to send"

  execution:
    agent: "agent-name"  # or null for routing tests
    skill: "skill-name"  # optional
    timeout_seconds: 300
    trials: 1

  graders:
    - type: "file_exists"
      config:
        path: "expected/file.md"
      weight: 0.3

    - type: "llm_rubric"
      config:
        rubric: "rubrics/quality.md"
        assertions:
          - "Criterion 1"
          - "Criterion 2"
      weight: 0.7

  reference:
    notes: "What constitutes a valid solution"
```

## Grader Types

| Type | Purpose | Config |
|------|---------|--------|
| `file_exists` | Check file creation | `path` |
| `string_contains` | Check for substrings | `target`, `patterns`, `match_all` |
| `regex_match` | Pattern matching | `target`, `pattern` |
| `tests_pass` | Run command, check exit code | `command`, `working_dir` |
| `yaml_valid` | Validate YAML structure | `path`, `required_fields` |
| `llm_rubric` | LLM-as-judge via CLI | `rubric`, `assertions` |
| `agent_evaluator` | Agent-based grading (in-session) | `rubric`, `assertions` |

### Grading Approaches

**CLI Mode (llm_rubric)**: Uses `claude` CLI for LLM grading. Best for automated batch evals.

**Agent Mode (agent_evaluator)**: Uses Task tool to spawn evaluator agent. Best for interactive testing within Claude Code sessions. Writes evaluation to JSON file.

## Metrics

- **pass@k**: At least one of k trials passes (measures capability)
- **pass^k**: All k trials pass (measures reliability)
- **score**: Weighted average of grader scores (0.0 - 1.0)

## Results Output

Results are saved to `evals/results/` as JSON:

```json
{
  "task_id": "routing-001",
  "trials": [...],
  "pass@k": true,
  "pass^k": false,
  "avg_score": 0.85,
  "timestamp": "2026-01-11T12:00:00"
}
```

## Adding New Tasks

1. Create a new YAML file in the appropriate `tasks/` subdirectory
2. Define the task following `task_schema.yaml`
3. Add any needed rubrics to `rubrics/`
4. Test with `python harness.py run your-task.yaml`

## Philosophy

Following Anthropic's eval methodology:
- **Capability evals**: Test what agents can do (pass@k matters)
- **Regression evals**: Ensure reliability (pass^k matters)
- **Multiple graders**: Combine deterministic checks with LLM judgment
- **Rubric-based**: Clear criteria avoid subjective grading
