# Agent Evaluation System

A formal evaluation infrastructure for testing Claude Code agents and skills. The system provides deterministic and LLM-based grading, multi-trial statistical analysis, and integration with agent development workflows.

## Table of Contents

1. [Overview](#overview)
2. [Philosophy](#philosophy)
3. [Architecture](#architecture)
4. [Task Design Guide](#task-design-guide)
5. [Grader Reference](#grader-reference)
6. [CLI Reference](#cli-reference)
7. [Scoring System](#scoring-system)
8. [Integration Points](#integration-points)
9. [Calibration System](#calibration-system)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The evaluation system tests Claude Code agents and skills by:

1. **Executing tasks** - Running agents with defined prompts in isolated environments
2. **Grading outputs** - Applying deterministic checks and LLM-based rubric evaluation
3. **Computing metrics** - Calculating pass rates, scores, and statistical measures
4. **Reporting results** - Generating structured reports for analysis and decision-making

The system supports both capability testing (can the agent do X?) and regression testing (does the agent reliably do X?).

### Directory Structure

```
evals/
├── harness.py              # Main evaluation runner and graders
├── task_schema.yaml        # Task YAML format documentation
├── EVALS.md                # This documentation
├── README.md               # Quick start guide
│
├── tasks/                  # Evaluation task definitions
│   ├── routing/            # Tests for /do routing decisions
│   ├── agent-creation/     # Tests for agent-creator workflows
│   ├── code-review/        # Tests for code review agents
│   └── voice-generation/   # Tests for voice skills
│
├── rubrics/                # LLM-as-judge evaluation rubrics
│   ├── agent_quality.md    # Agent specification quality
│   ├── agent_structural.md # Structural completeness
│   └── voice_authenticity.md # Voice output quality
│
├── calibration/            # Grader calibration data
│   ├── string_contains/    # Calibration for string_contains grader
│   │   └── examples.yaml   # Gold standard examples
│   └── llm_rubric/         # Calibration for llm_rubric grader
│       └── examples.yaml   # Gold standard examples
│
├── integrations/           # Skill and workflow integrations
│   ├── testing_skill.py    # testing-agents-with-subagents bridge
│   └── agent_evaluation.py # agent-evaluation skill bridge
│
└── results/                # Evaluation outputs (JSON)
```

---

## Philosophy

The evaluation system follows Anthropic's evaluation methodology principles:

### Capability vs Regression Testing

| Type | Question | Key Metric | When to Use |
|------|----------|------------|-------------|
| **Capability** | Can the agent do X? | pass@k | Testing new features, exploratory capabilities |
| **Regression** | Does the agent always do X? | pass^k | Ensuring reliability, preventing regressions |

**Capability evaluations** measure what an agent CAN do. A single success among multiple trials indicates capability. Use pass@k (at least one of k trials passes).

**Regression evaluations** measure what an agent ALWAYS does. All trials must pass to confirm reliability. Use pass^k (all k trials pass).

### Grading Philosophy

The system combines two grading approaches:

1. **Deterministic graders** - Fast, reproducible, no variance. Use for structural checks, file existence, pattern matching, test execution.

2. **LLM-based graders** - Nuanced judgment, rubric-based. Use for quality assessment, semantic understanding, complex criteria.

**Principle**: Use deterministic graders when possible. Reserve LLM graders for criteria that require judgment.

### Rubric-Based Evaluation

LLM graders use explicit rubrics rather than implicit judgment:

- **Bad**: "Is this output good?"
- **Good**: "Does the output include type hints? Does it handle edge cases? Is there a docstring?"

Rubrics make grading criteria explicit, reproducible, and debuggable.

---

## Architecture

### Harness Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Setup    │───▶│   Execute   │───▶│    Grade    │───▶│   Report    │
│ Environment │    │    Agent    │    │   Output    │    │   Results   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
  Create temp        Run claude         Apply all         Compute
  directory,         CLI with           configured        weighted
  copy context       prompt, skill,     graders           scores,
  files, run         or agent                             save JSON
  setup commands
```

### Phase Details

#### 1. Setup Phase
- Creates isolated temporary directory
- Executes setup commands (e.g., creating test fixtures)
- Copies context files into working directory
- Prepares environment variables

#### 2. Execution Phase
- Invokes `claude` CLI with the task prompt
- Captures JSON output including token usage
- Extracts transcript from assistant messages
- Tracks timing and cost metrics

#### 3. Grading Phase
- Runs all configured graders against output
- Each grader returns: passed (bool), score (0.0-1.0), details
- Supports weighted scoring across graders
- Graders can check transcript, files, or run commands

#### 4. Reporting Phase
- Computes weighted average score
- Determines pass/fail based on threshold (default: 0.7)
- Aggregates multi-trial statistics (pass@k, pass^k)
- Saves results to JSON with full details

### Component Relationships

```
Task YAML ─────────────▶ Harness ─────────────▶ Results JSON
    │                       │                       │
    ├── input.prompt        ├── setup_environment   ├── task_id
    ├── execution.agent     ├── execute_agent       ├── score
    ├── graders[]           ├── run_graders         ├── passed
    └── reference           └── compute_score       └── grades[]
           │                       │
           │                       ▼
           │            ┌──────────────────────┐
           │            │      Graders         │
           │            ├──────────────────────┤
           │            │ file_exists          │
           │            │ string_contains      │
           │            │ regex_match          │
           │            │ tests_pass           │
           │            │ yaml_valid           │
           │            │ llm_rubric           │
           │            │ agent_evaluator      │
           │            │ tool_calls (V2)      │
           │            │ state_check (V2)     │
           │            │ transcript_constraint│
           │            └──────────────────────┘
           │
           ▼
    Rubric Files (for LLM graders)
```

---

## Task Design Guide

### Task YAML Structure

```yaml
task:
  # Required: Unique identifier for the task
  id: "routing-001"

  # Required: Human-readable name
  name: "Route Go debug request to golang agent"

  # Required: What this task tests
  description: |
    Verify that when a user asks to debug Go tests, the /do command
    correctly routes to golang-general-engineer.

  # Required: Task category for grouping
  category: "routing"

  # Required: Evaluation type
  # - "capability": Tests if agent CAN do something (pass@k)
  # - "regression": Tests if agent ALWAYS does something (pass^k)
  type: "capability"

  # Input configuration
  input:
    # Required: The prompt to send to the agent
    prompt: "/do debug why my Go tests are failing in pkg/worker"

    # Optional: Files to copy into working directory
    context_files: []

    # Optional: Commands to run before agent execution
    setup_commands:
      - "mkdir -p pkg/worker"
      - "touch pkg/worker/worker_test.go"

  # Execution configuration
  execution:
    # Optional: Specific agent to use (null = let routing decide)
    agent: null

    # Optional: Specific skill to invoke
    skill: "do"

    # Optional: Maximum execution time in seconds (default: 300)
    timeout_seconds: 60

    # Optional: Number of trials for pass@k calculation
    trials: 1

  # Grading configuration
  graders:
    - type: "string_contains"
      config:
        target: "transcript"
        patterns:
          - "golang"
        match_all: false
      weight: 0.3

    - type: "regex_match"
      config:
        target: "transcript"
        pattern: "(golang-general-engineer|go-testing|systematic-debugging)"
      weight: 0.4

    - type: "llm_rubric"
      config:
        rubric: "rubrics/routing_quality.md"
        assertions:
          - "Routes to a Go-specialized agent or skill"
          - "Does not route to Python or generic agents"
      weight: 0.3

  # Optional: Tracking metrics
  metrics:
    - turns
    - tokens
    - latency

  # Optional: Reference information
  reference:
    # Path to reference solution file
    solution_file: null

    # Notes about acceptable solutions
    notes: |
      Acceptable outcomes:
      - Routes to golang-general-engineer agent
      - Invokes systematic-debugging skill with Go context
      - Uses go-testing skill
```

### Choosing Task Type

**Use `type: "capability"` when:**
- Testing if an agent CAN accomplish a task
- Exploring new functionality
- Some variance in approach is acceptable
- Success metric: At least one trial passes

**Use `type: "regression"` when:**
- Testing reliability of existing behavior
- Preventing regressions from changes
- Consistent behavior is required
- Success metric: All trials must pass

### Choosing Graders

| Criterion | Recommended Grader | Example |
|-----------|-------------------|---------|
| File was created | `file_exists` | Agent should create output.md |
| Output contains text | `string_contains` | Must mention "error handling" |
| Output matches pattern | `regex_match` | Should reference agent-name format |
| Tests pass | `tests_pass` | Unit tests should succeed |
| YAML is valid | `yaml_valid` | Config file has required fields |
| Quality/semantic check | `llm_rubric` | Code follows best practices |

**Grader Selection Guidelines:**

1. Start with deterministic graders (fast, reproducible)
2. Add LLM grader only for criteria requiring judgment
3. Combine multiple graders with weights for comprehensive evaluation
4. Use higher weights for critical criteria

### Writing Good Assertions

Assertions guide LLM-based grading. Write them to be:

**Specific** - State exactly what to check
```yaml
# Bad
assertions:
  - "Output is good"

# Good
assertions:
  - "Code includes type hints on function signatures"
  - "Function has docstring with Args and Returns sections"
```

**Binary** - Should be clearly PASS or FAIL
```yaml
# Bad
assertions:
  - "Code is well-organized"

# Good
assertions:
  - "Related functions are grouped together"
  - "No function exceeds 50 lines"
```

**Evidence-based** - Point to observable criteria
```yaml
# Bad
assertions:
  - "Error handling is appropriate"

# Good
assertions:
  - "All external calls are wrapped in try-except blocks"
  - "Error messages include the original exception"
```

### Reference Solutions

Include reference solutions for:
- Complex tasks with subjective quality criteria
- Tasks where correct output format matters
- Calibrating LLM graders against expected outcomes
- Training new evaluators on acceptable outputs

**Reference Solution Format:**

```markdown
# Reference Solution: task-001

## Task Summary
Brief description of what the task tests.

## Acceptable Output
```
[Example of correct output]
```

## Why This Passes
- Criterion 1: Present because...
- Criterion 2: Satisfied by...

## Unacceptable Examples

### Example 1: Missing X
```
[Bad output]
```
**Fails because**: Does not include required X.

## Acceptable Variations
- Alternative approach A is acceptable
- Minor phrasing differences are fine
- Order of sections may vary
```

---

## Grader Reference

### file_exists

Checks if a file was created in the working directory.

```yaml
- type: "file_exists"
  config:
    path: "output/result.md"  # Relative to working directory
  weight: 1.0
```

**Returns:**
- `passed`: true if file exists
- `score`: 1.0 if exists, 0.0 otherwise

---

### string_contains

Checks if target contains specified patterns.

```yaml
- type: "string_contains"
  config:
    # Where to search: "transcript" or "file:path/to/file"
    target: "transcript"

    # Patterns to find
    patterns:
      - "error handling"
      - "validation"
      - "tests pass"

    # Whether all patterns must match (default: true)
    match_all: true
  weight: 1.0
```

**Returns:**
- `passed`: true if match criteria met
- `score`: If match_all, proportion of patterns matched (e.g., 2/3 = 0.67)
         If not match_all, 1.0 if any match, 0.0 otherwise
- `matched`: List of patterns that matched
- `missing`: List of patterns that did not match

---

### regex_match

Checks if target matches a regular expression.

```yaml
- type: "regex_match"
  config:
    target: "transcript"  # or "file:path/to/file"
    pattern: "(golang-general-engineer|python-general-engineer)"
  weight: 1.0
```

**Returns:**
- `passed`: true if pattern matches
- `score`: 1.0 if matched, 0.0 otherwise

**Note:** Uses Python's `re.MULTILINE` flag. Pattern should be a valid Python regex.

---

### tests_pass

Runs a command and checks if it succeeds (exit code 0).

```yaml
- type: "tests_pass"
  config:
    command: "pytest tests/ -v"
    working_dir: "."  # Relative to work_dir
  weight: 1.0
```

**Returns:**
- `passed`: true if exit code is 0
- `score`: 1.0 if passed, 0.0 otherwise
- `stdout`: First 500 chars of stdout
- `stderr`: First 500 chars of stderr

**Timeout:** 60 seconds (hardcoded)

---

### yaml_valid

Validates YAML structure and required fields.

```yaml
- type: "yaml_valid"
  config:
    path: "config.yaml"  # Relative to work_dir
    required_fields:
      - "name"
      - "description"
      - "version"
  weight: 1.0
```

**Handles:**
- Plain YAML files
- Markdown files with YAML frontmatter (between `---` delimiters)

**Returns:**
- `passed`: true if valid YAML with all required fields
- `score`: Proportion of required fields present

---

### llm_rubric

Uses Claude CLI for LLM-as-judge evaluation against assertions.

```yaml
- type: "llm_rubric"
  config:
    # Optional: Path to rubric document
    rubric: "rubrics/code_quality.md"

    # Required: Specific assertions to evaluate
    assertions:
      - "Code includes type hints"
      - "Functions have docstrings"
      - "Error cases are handled"
  weight: 1.0
```

**How It Works:**
1. Constructs prompt with transcript, rubric, and assertions
2. Calls `claude -p <prompt> --output-format text`
3. Parses JSON response with pass/fail for each assertion
4. Computes overall score from assertion results

**Returns:**
- `passed`: true if overall_pass from LLM
- `score`: 0.0-1.0 from LLM assessment
- `assertions`: Detailed pass/fail with reasoning for each
- `summary`: Brief overall assessment

**Best For:**
- Quality assessment beyond pattern matching
- Semantic understanding of content
- Subjective criteria requiring judgment

**Limitations:**
- Slower than deterministic graders
- Results may vary between runs
- Requires clear, specific assertions

---

### agent_evaluator

Uses a sub-agent for evaluation (within Claude Code sessions).

```yaml
- type: "agent_evaluator"
  config:
    rubric: "Evaluate code quality and completeness"
    assertions:
      - "Implementation is correct"
      - "Edge cases are handled"
  weight: 1.0
```

**Usage Context:**
- Designed for use within Claude Code sessions
- Uses Task tool to spawn evaluator agent
- Agent writes results to `eval_grade.json`

**Fallback Behavior:**
- In CLI mode, returns placeholder with prompt
- For CLI-based evaluations, use `llm_rubric` instead

---

### tool_calls (V2)

Validates which tools were called during execution. Requires `raw_json_output` in env.

```yaml
- type: "tool_calls"
  config:
    # Required tools that must be called
    required_tools: ["Read", "Edit"]

    # Forbidden tools that should not be called
    forbidden_tools: ["Bash"]

    # Optional: Max number of tool calls allowed
    max_tool_calls: 20

    # Optional: Validate tool parameters match patterns
    tool_params:
      Edit:
        file_path: ".*\\.py$"  # Edit should only modify Python files
  weight: 1.0
```

**Returns:**
- `passed`: true if all constraints met
- `score`: 1.0 if passed, 0.0 otherwise
- `num_calls`: Total tool calls made
- `calls_by_tool`: Count per tool name
- `details`: Explanation of pass/fail reason

**Use Cases:**
- Ensuring agent uses the right tools for a task
- Preventing dangerous operations (e.g., blocking Bash for review tasks)
- Validating tool parameters (e.g., file paths match expected patterns)

---

### state_check (V2)

Validates the state of the working directory after execution.

```yaml
- type: "state_check"
  config:
    # Check if files exist
    files_exist:
      - "src/main.py"
      - "tests/test_main.py"

    # Check if files contain patterns (regex)
    file_contains:
      "src/main.py":
        - "def process_data"
        - "class DataHandler"
      "tests/test_main.py":
        - "def test_"

    # Check git status patterns (requires git repo)
    git_status:
      patterns:
        - "M src/main.py"      # Modified file
        - "\\?\\? tests/"       # New untracked directory
  weight: 1.0
```

**Returns:**
- `passed`: true if all checks pass
- `score`: Proportion of checks that passed (0.0-1.0)
- `total_checks`: Number of checks performed
- `passed_checks`: Number that passed
- `issues`: List of failed checks with details

**Use Cases:**
- Verifying agent created/modified expected files
- Checking code contains required patterns
- Validating git state after operations

---

### transcript_constraint (V2)

Validates transcript metrics like length, turns, and content patterns.

```yaml
- type: "transcript_constraint"
  config:
    # Token limits
    max_tokens: 5000
    min_tokens: 100

    # Turn limits (for multi-turn conversations)
    max_turns: 10

    # Required patterns in transcript
    required_patterns:
      - "completed successfully"
      - "no errors"

    # Forbidden patterns (agent should not say these)
    forbidden_patterns:
      - "I'm sorry"
      - "I cannot"
  weight: 1.0
```

**Returns:**
- `passed`: true if all constraints met
- `score`: 1.0 if passed, 0.0 otherwise
- `details`: Explanation of which constraints passed/failed
- `actual_tokens`: Measured token count
- `actual_turns`: Measured turn count

**Use Cases:**
- Ensuring agent responses are appropriately sized
- Preventing verbose or terse responses
- Checking agent doesn't produce refusal patterns

---

## CLI Reference

### Run Single Task

```bash
python harness.py run <task.yaml> [options]
```

**Options:**
- `--trials N` - Number of trials for pass@k (default: 1)
- `--output, -o PATH` - Output JSON file path
- `--save-transcripts` - Save transcripts to results/ for later analysis

**Examples:**
```bash
# Basic run
python harness.py run tasks/routing/task-001.yaml

# Multiple trials
python harness.py run tasks/voice-generation/task-001.yaml --trials 5

# Save transcripts
python harness.py run tasks/code-review/task-001.yaml --save-transcripts

# Custom output location
python harness.py run tasks/routing/task-001.yaml -o my-results.json
```

**Output:**
```
Trial 1: Score=0.85 (PASS) [1,234 tokens, $0.0156]
Trial 2: Score=0.90 (PASS) [1,189 tokens, $0.0143]
Trial 3: Score=0.70 (PASS) [1,456 tokens, $0.0178]

pass@3: True
pass^3: True

Total: 3,879 tokens, $0.0477

Results saved to: results/eval-20260111-143022.json
```

---

### Run Suite

```bash
python harness.py suite <directory> [options]
```

**Options:**
- `--trials N` - Trials per task (default: 1)
- `--output, -o PATH` - Output JSON file path
- `--type TYPE` - Filter by task type: "capability" or "regression"
- `--save-transcripts` - Save all transcripts

**Examples:**
```bash
# Run all tasks in directory
python harness.py suite tasks/routing/

# Run with multiple trials
python harness.py suite tasks/routing/ --trials 3

# Run only regression tests
python harness.py suite tasks/ --type regression

# Run only capability tests
python harness.py suite tasks/ --type capability
```

**Output:**
```
Running: task-001.yaml
  Score: 0.85 (PASS)
Running: task-002.yaml
  Score: 0.70 (PASS)

==================================================
SUMMARY
==================================================
Total tasks: 2
Passed (any trial): 2
Passed (all trials): 2
Average score: 0.78

Capability tasks (2):
  pass@k: 2/2 (100%)

Total tokens: 2,456
Total cost: $0.0312

Results saved to: results/eval-20260111-143500.json
```

---

### Calibrate Graders

```bash
python harness.py calibrate [grader_type] [options]
```

**Options:**
- `grader_type` - Specific grader to calibrate (e.g., "string_contains")
- `--all` - Calibrate all graders with calibration data
- `--output, -o PATH` - Save calibration report

**Examples:**
```bash
# Calibrate specific grader
python harness.py calibrate string_contains

# Calibrate all graders
python harness.py calibrate --all

# Save calibration report
python harness.py calibrate string_contains -o calibration-report.json
```

**Output:**
```
============================================================
GRADER CALIBRATION REPORT
============================================================

Calibrating grader: string_contains
Running 5 calibration examples...
------------------------------------------------------------
  [ALIGNED] sc-001: All patterns present - should pass with score 1.0
  [ALIGNED] sc-002: Partial match - should fail with partial score
  [ALIGNED] sc-003: No matches - should fail with score 0.0
  [ALIGNED] sc-004: match_all=false with one match - should pass
  [ALIGNED] sc-005: match_all=false with no matches - should fail
------------------------------------------------------------
Agreement rate: 100.0% (5/5)
Avg score deviation: 0.0000
Max score deviation: 0.0000
Status: EXCELLENT - Grader is well-calibrated
```

---

### Grade Agent/Skill

```bash
python harness.py grade-agent <path> [options]
```

**Options:**
- `--format FORMAT` - Output format: "json", "markdown", "summary"
- `--output, -o PATH` - Save report to file
- `--batch` - Grade all agents/skills in directory

**Examples:**
```bash
# Grade single agent
python harness.py grade-agent agents/golang-general-engineer.md

# Grade skill
python harness.py grade-agent skills/test-driven-development/

# JSON output
python harness.py grade-agent agents/python-general-engineer.md --format json

# Batch grade all agents
python harness.py grade-agent agents/ --batch

# Summary format
python harness.py grade-agent agents/golang-general-engineer.md --format summary
```

**Output (markdown):**
```markdown
# Assessment Report: golang-general-engineer.md

**Type**: Agent
**Overall Score**: 92/100 (A)

## Score Breakdown
- Structural: 50/50
- Content Depth: 30/30 (EXCELLENT)
- Total Lines: 2,345

## Component Scores
| Component | Score | Status | Details |
|-----------|-------|--------|---------|
| YAML Front Matter | 10/10 | PASS | All required fields present |
| Operator Context | 20/20 | PASS | All 3 behavior types present |
| Examples | 10/10 | PASS | Found 5 examples (3+ required) |
| Error Handling | 10/10 | PASS | Error handling section found |

## Issues Found
(none)

## Recommendations
(none)
```

---

### Skill Test

```bash
python harness.py skill-test <agent> [options]
```

**Options:**
- `--trials N` - Trials per task (default: 3)
- `--format FORMAT` - Output format: "json", "markdown", "skill-report"
- `--output, -o PATH` - Save report to file
- `--list-agents` - List all agents with evaluation tasks

**Examples:**
```bash
# List agents with tasks
python harness.py skill-test --list-agents

# Run tests for agent
python harness.py skill-test python-general-engineer

# More trials for higher confidence
python harness.py skill-test python-general-engineer --trials 5

# Save results
python harness.py skill-test golang-general-engineer -o agent-test.md
```

**Output:**
```
Found 3 eval tasks for python-general-engineer
Running 3 trials per task...
------------------------------------------------------------
Running: task-001.yaml
  pass@3: PASS (rate: 100.0%, avg score: 0.92)
Running: task-002.yaml
  pass@3: PASS (rate: 67.0%, avg score: 0.78)

============================================================
SUMMARY
============================================================
Agent: python-general-engineer
Tasks: 3
Trials per task: 3
Pass rate (pass@k): 100.0%
Avg score: 0.85
Total tokens: 12,456
Total cost: $0.1567
```

---

## Scoring System

### Weighted Scoring

Each grader produces a score (0.0-1.0) and has a weight. The final score is:

```
final_score = Sum(grader_score * grader_weight) / Sum(grader_weight)
```

**Example:**
```yaml
graders:
  - type: file_exists
    weight: 0.3
    # Result: score=1.0

  - type: string_contains
    weight: 0.3
    # Result: score=0.67 (2/3 patterns matched)

  - type: llm_rubric
    weight: 0.4
    # Result: score=0.85

# Final: (1.0*0.3 + 0.67*0.3 + 0.85*0.4) / (0.3+0.3+0.4)
#      = (0.3 + 0.201 + 0.34) / 1.0
#      = 0.841
```

### Pass/Fail Threshold

A task passes if `score >= 0.7` (default threshold).

### Multi-Trial Statistics

#### pass@k

**Definition:** At least one of k trials passes.

**Use case:** Measuring capability. If an agent CAN do something (even occasionally), pass@k is true.

**Formula:** `pass@k = any(trial.passed for trial in trials)`

#### pass^k

**Definition:** All k trials pass.

**Use case:** Measuring reliability. If an agent ALWAYS does something correctly, pass^k is true.

**Formula:** `pass^k = all(trial.passed for trial in trials)`

#### Pass Rate

**Definition:** Proportion of trials that passed.

**Formula:** `pass_rate = count(passed) / total_trials`

**Example:**
```
Trials: [PASS, PASS, FAIL, PASS, PASS]
pass@5: true  (at least one passed)
pass^5: false (not all passed)
pass_rate: 80% (4/5)
```

### Agent/Skill Structural Scoring

The `grade-agent` command uses a 100-point system:

**Structural Validation (70 points):**

| Component | Points | Requirement |
|-----------|--------|-------------|
| YAML front matter | 10 | name, description present |
| Operator Context | 20 | Section with 3 behavior types |
| Examples | 10 | 3+ examples (agents) |
| Error Handling | 10 | Section exists |
| Reference Files | 10 | References directory with content (skills) |
| Validation Script | 10 | scripts/validate.py exists (skills) |

**Content Depth (30 points):**

| Total Lines | Grade | Score |
|-------------|-------|-------|
| >2000 | EXCELLENT | 30/30 |
| 1000-2000 | GOOD | 25/30 |
| 500-1000 | ADEQUATE | 20/30 |
| 200-500 | THIN | 10/30 |
| <200 | INSUFFICIENT | 0/30 |

**Grade Calculation:**

| Score | Grade |
|-------|-------|
| 90-100 | A |
| 80-89 | B |
| 70-79 | C |
| 60-69 | D |
| <60 | F |

---

## Integration Points

### testing-agents-with-subagents Skill

The harness integrates with the testing-agents-with-subagents skill for agent validation workflows.

**Integration Module:** `integrations/testing_skill.py`

**Usage from skill:**
```python
from evals.integrations.testing_skill import run_agent_eval, EvalResult

# Run all evaluation tasks for an agent
result = run_agent_eval("python-general-engineer", num_trials=3)

# Access results
print(f"Pass rate: {result.pass_rate:.1%}")
print(f"Tasks passed: {result.passed_any}/{result.total_tasks}")
```

**CLI Usage:**
```bash
# List agents with evaluation tasks
python harness.py skill-test --list-agents

# Run tests for specific agent
python harness.py skill-test python-general-engineer --trials 3
```

**Data Classes:**

```python
@dataclass
class EvalResult:
    agent_name: str
    num_trials: int
    timestamp: str
    tasks: list[TaskResult]
    total_tasks: int
    passed_any: int      # Tasks with at least one passing trial
    passed_all: int      # Tasks with all trials passing
    pass_rate: float     # Percentage of tasks with pass@k
    avg_score: float
    tokens_total: int
    cost_usd: float
```

### agent-evaluation Skill

The harness includes agent/skill structural assessment following the agent-evaluation skill's rubric.

**Integration Module:** `integrations/agent_evaluation.py`

**Usage:**
```python
from evals.integrations.agent_evaluation import run_agent_eval, format_report

# Evaluate an agent
result = run_agent_eval("agents/golang-general-engineer.md")

# Format as report
print(format_report(result))
```

**CLI Usage:**
```bash
# Grade single agent
python harness.py grade-agent agents/golang-general-engineer.md

# Batch grade all
python harness.py grade-agent agents/ --batch
```

**Scoring Criteria:**
- Same 100-point system as agent-evaluation skill
- Structural validation: 70 points
- Content depth: 30 points
- Includes component breakdown, issues, recommendations

### Workflow Integration

The recommended workflow for agent development:

```
1. Create/modify agent definition
       |
       v
2. Manual testing with testing-agents-with-subagents skill
   - Run agent with test inputs
   - Verify outputs match expectations
   - Fix issues, iterate
       |
       v
3. Create evaluation task YAML for the agent
   - Define capability and regression tests
   - Add to evals/tasks/{category}/
       |
       v
4. Run harness for automated validation
   $ python harness.py skill-test <agent> --trials 5
       |
       v
5. Run structural evaluation
   $ python harness.py grade-agent agents/<agent>.md
       |
       v
6. Deploy when both pass
```

---

## Calibration System

### Purpose

Calibration ensures graders produce consistent, expected results. Use calibration to:

1. Verify graders work correctly after changes
2. Understand grader behavior on edge cases
3. Tune LLM graders for alignment
4. Document expected grader behavior

### Calibration Data Structure

Each grader type can have calibration examples in `calibration/{grader_type}/examples.yaml`:

```yaml
examples:
  - id: "sc-001"
    description: "All patterns present - should pass with score 1.0"
    input:
      transcript: |
        The agent successfully created a new file called main.py.
        It contains a function called process_data.
        All tests pass.
      config:
        target: transcript
        patterns:
          - "main.py"
          - "process_data"
          - "tests pass"
        match_all: true
    expected:
      passed: true
      score: 1.0

  - id: "sc-002"
    description: "Partial match - should fail with partial score"
    input:
      transcript: |
        Created the file utils.py with helper functions.
      config:
        target: transcript
        patterns:
          - "utils.py"
          - "helper functions"
          - "tests pass"
          - "coverage report"
        match_all: true
    expected:
      passed: false
      score: 0.5  # 2/4 patterns matched
```

### LLM Grader Calibration

LLM graders use score ranges to account for variance:

```yaml
examples:
  - id: "llm-001"
    description: "Clear success case"
    input:
      transcript: |
        [Example output that should pass]
      config:
        assertions:
          - "Code includes type hints"
          - "Function has docstring"
    expected:
      passed: true
      score_min: 0.9  # Allow variance
      score_max: 1.0
```

### Running Calibration

```bash
# Calibrate specific grader
python harness.py calibrate string_contains

# Calibrate all graders
python harness.py calibrate --all
```

### Interpreting Results

| Agreement Rate | Status | Action |
|----------------|--------|--------|
| >= 95% | EXCELLENT | Grader is well-calibrated |
| 80-94% | GOOD | Minor adjustments may be needed |
| 60-79% | FAIR | Review misaligned examples |
| < 60% | POOR | Significant calibration work needed |

### Creating Calibration Examples

**For Deterministic Graders:**
1. Include clear pass cases (all criteria met)
2. Include clear fail cases (no criteria met)
3. Include partial cases (some criteria met)
4. Test edge cases (empty input, unusual formats)

**For LLM Graders:**
1. Include unambiguous pass cases
2. Include unambiguous fail cases
3. Use score ranges to account for variance
4. Keep ranges narrow for well-defined criteria
5. Include borderline cases to test judgment

---

## Best Practices

### When to Use Deterministic vs LLM Graders

**Use Deterministic Graders When:**
- Checking for presence/absence of content
- Validating file creation
- Running automated tests
- Checking structural requirements
- Pattern matching is sufficient

**Use LLM Graders When:**
- Evaluating quality (not just presence)
- Checking semantic correctness
- Assessing code practices
- Judging natural language output
- Criteria require interpretation

**Hybrid Approach:**
Combine both for comprehensive evaluation:

```yaml
graders:
  # Deterministic: Did it create the file?
  - type: file_exists
    config:
      path: "output.md"
    weight: 0.2

  # Deterministic: Does it have required sections?
  - type: string_contains
    config:
      target: "file:output.md"
      patterns:
        - "## Summary"
        - "## Recommendations"
    weight: 0.3

  # LLM: Is the content quality good?
  - type: llm_rubric
    config:
      assertions:
        - "Recommendations are specific and actionable"
        - "Summary accurately reflects the analysis"
    weight: 0.5
```

### Writing Good Rubrics

**Structure rubrics clearly:**

```markdown
# Code Review Quality Rubric

## Criteria

### 1. Issue Identification (40 points)
- Identifies all critical issues (security, correctness)
- Identifies important issues (performance, maintainability)
- Does not flag non-issues

### 2. Explanation Quality (30 points)
- Clear explanation of why each issue matters
- Specific location of each issue
- Understandable by the code author

### 3. Recommendation Quality (30 points)
- Provides specific fix suggestions
- Fixes are correct and complete
- Follows codebase conventions
```

**Include examples in rubrics:**

```markdown
## Example: PASS

**Issue found:**
Line 45: SQL injection vulnerability in user input handling.
**Explanation:** User input is concatenated directly into SQL query.
**Fix:** Use parameterized query: `db.execute("SELECT * FROM users WHERE id = ?", (user_id,))`

## Example: FAIL

**Issue found:**
Line 45: Code looks suspicious
**Why this fails:** No specific vulnerability identified, no clear fix provided.
```

### Calibrating LLM Graders

1. **Start with clear cases** - Build examples that any evaluator would agree on
2. **Add borderline cases** - Test where the grader draws lines
3. **Use narrow score ranges** - Tighten ranges as grader proves consistent
4. **Review misaligned examples** - Adjust rubric or examples based on analysis
5. **Track over time** - Re-run calibration after model updates

### Task Design Tips

1. **One thing per task** - Test a single capability or behavior
2. **Clear success criteria** - Know exactly what passing looks like
3. **Realistic inputs** - Use representative prompts, not contrived examples
4. **Appropriate graders** - Match grader type to what you're measuring
5. **Reasonable weights** - Weight by importance, not convenience
6. **Reference solutions** - Document expected outputs for complex tasks

### Token and Cost Management

Monitor costs during development:

```bash
# Run single task, observe costs
python harness.py run tasks/complex/task-001.yaml
# Output includes: [1,234 tokens, $0.0156]

# Run suite with budget awareness
python harness.py suite tasks/expensive/ --trials 1  # Start with 1 trial
```

**Cost Optimization:**
- Use deterministic graders when possible (no LLM cost)
- Start with fewer trials, increase for production validation
- Use shorter prompts in tasks when detail isn't needed
- Filter by task type to run targeted validation

---

## Troubleshooting

### Common Issues

#### Task Execution Timeout

**Symptom:** Task fails with "Execution timed out after N seconds"

**Causes:**
- Agent taking too long
- Infinite loop in agent behavior
- External service delay

**Solutions:**
1. Increase timeout in task YAML: `timeout_seconds: 600`
2. Simplify the task prompt
3. Check agent for blocking operations

---

#### LLM Grader JSON Parse Error

**Symptom:** "Failed to parse LLM response: ..."

**Causes:**
- LLM returned non-JSON content
- LLM wrapped JSON in markdown code blocks
- Response was truncated

**Solutions:**
1. Harness handles code block extraction automatically
2. Check rubric prompt for clarity
3. Simplify assertions

---

#### No Tasks Found for Agent

**Symptom:** `skill-test` returns "No tasks found for agent"

**Causes:**
- No tasks have `execution.agent` matching the agent name
- Tasks are in wrong directory

**Solutions:**
1. Check task YAML files for `execution.agent` field
2. Ensure agent name matches exactly
3. Use `--list-agents` to see available agents

---

#### Calibration Misalignment

**Symptom:** Calibration shows misaligned examples

**Causes:**
- Expected values don't match actual grader behavior
- Grader logic changed
- Edge case handling differs

**Solutions:**
1. Review the specific misaligned example
2. Determine if expected value or grader is wrong
3. Update calibration examples or fix grader logic

---

#### File Grader Can't Find File

**Symptom:** file_exists or file-based graders return "Target file not found"

**Causes:**
- File path is incorrect
- Agent didn't create the file
- Path is absolute instead of relative

**Solutions:**
1. Paths should be relative to `work_dir`
2. Check agent actually creates the file
3. Verify exact filename (case-sensitive)

---

### Debug Mode

Add verbose output for debugging:

```python
# In harness.py, the execute_agent function captures full output
# Access via results JSON

result = run_task("tasks/debug/task.yaml")
print(result["transcript_preview"])  # First 500 chars
```

For full transcripts:

```bash
python harness.py run task.yaml --save-transcripts
# Transcripts saved to results/{task-id}-trial{n}-transcript.txt
```

---

## Appendix: Result JSON Schema

```json
{
  "task_id": "routing-001",
  "task_name": "Route Go debug request to golang agent",
  "trial": 0,
  "success": true,
  "score": 0.85,
  "passed": true,
  "grades": [
    {
      "type": "string_contains",
      "passed": true,
      "score": 1.0,
      "weight": 0.3,
      "details": "Matched 1/1 patterns",
      "matched": ["golang"],
      "missing": []
    },
    {
      "type": "regex_match",
      "passed": true,
      "score": 1.0,
      "weight": 0.4,
      "details": "Pattern matched: golang-general-engineer"
    },
    {
      "type": "llm_rubric",
      "passed": true,
      "score": 0.85,
      "weight": 0.3,
      "details": "Agent correctly routed to Go specialist",
      "assertions": [
        {
          "assertion": "Routes to a Go-specialized agent",
          "passed": true,
          "reasoning": "Selected golang-general-engineer"
        }
      ]
    }
  ],
  "metrics": {
    "elapsed_seconds": 12.5,
    "exit_code": 0,
    "tokens_input": 1234,
    "tokens_output": 567,
    "tokens_cache_read": 0,
    "tokens_cache_creation": 0,
    "tokens_total": 1801,
    "cost_usd": 0.0234
  },
  "transcript_preview": "I'll help debug your Go tests...",
  "timestamp": "2026-01-11T14:30:22.123456"
}
```

---

## Changelog

### Version 1.0.0 (2026-01-11)

- Initial documentation release
- Comprehensive coverage of harness functionality
- Task design guide with examples
- Grader reference with all supported types
- CLI reference with all commands
- Scoring system documentation
- Integration point documentation
- Calibration system guide
- Best practices and troubleshooting
