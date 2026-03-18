# Contributing to the Eval System

This guide covers how to add new evaluation tasks, graders, rubrics, and how to use eval-driven development effectively.

## Table of Contents

1. [Adding New Eval Tasks](#adding-new-eval-tasks)
2. [Adding New Graders](#adding-new-graders)
3. [Creating Rubrics](#creating-rubrics)
4. [Eval-Driven Development Workflow](#eval-driven-development-workflow)
5. [Pull Request Checklist](#pull-request-checklist)

---

## Adding New Eval Tasks

### Step-by-Step Process

1. **Choose a category** - Tasks belong to categories based on what they test:
   - `routing/` - Tests for `/do` routing decisions
   - `agent-creation/` - Tests for agent-creator-engineer
   - `code-review/` - Tests for code review agents
   - `voice-generation/` - Tests for voice skills

2. **Create the task file** - Use the naming convention `task-NNN.yaml`:
   ```bash
   # Example: Create a new routing test
   touch evals/tasks/routing/task-003.yaml
   ```

3. **Write the task YAML** - Follow the schema in `task_schema.yaml`

4. **Add reference solution** (for complex tasks) - Create `task-NNN-ref.md`

5. **Test locally** - Run your task before committing

### File Naming Conventions

| Pattern | Purpose | Example |
|---------|---------|---------|
| `task-NNN.yaml` | Main task definition | `task-001.yaml` |
| `task-NNN-ref.md` | Reference solution | `task-001-ref.md` |

Task IDs should include the category prefix for uniqueness:
- `routing-001`, `routing-002`
- `agent-creation-001`, `agent-creation-002`
- `voice-generation-001`

### Required vs Optional Fields

```yaml
task:
  # === REQUIRED ===
  id: "routing-003"                    # Unique identifier
  name: "Human readable name"          # Display name
  description: "What this tests"       # Detailed description
  category: "routing"                  # Category folder name
  type: "capability"                   # or "regression" (see below)

  input:
    prompt: "The prompt to send"       # Required: what to send to agent

  execution:
    agent: "agent-name"                # Required: null for routing tests

  graders:
    - type: "string_contains"          # Required: at least one grader
      config:
        patterns: ["expected"]
      weight: 1.0

  # === OPTIONAL ===
  input:
    context_files: []                  # Files to copy to work dir
    setup_commands: []                 # Shell commands to run first

  execution:
    skill: null                        # Specific skill to invoke
    timeout_seconds: 300               # Default: 300 (5 minutes)
    trials: 1                          # Default: 1

  metrics:                             # What to track
    - turns
    - tokens
    - latency

  reference:
    solution_file: "task-001-ref.md"   # Path to reference solution
    notes: "Acceptable variations"     # Notes for human reviewers
```

### Task Types: Capability vs Regression

**Capability tasks** (`type: capability`):
- Test if an agent **can** do something
- Success metric: `pass@k` (at least one trial passes)
- Use for: New features, complex tasks, edge cases

```yaml
# Example: Can the agent create a valid agent spec?
task:
  type: "capability"
  # ...
  execution:
    trials: 3  # Run 3 times, pass if any succeed
```

**Regression tasks** (`type: regression`):
- Test if an agent **always** does something correctly
- Success metric: `pass^k` (all trials must pass)
- Use for: Core functionality, safety checks, routing correctness

```yaml
# Example: Does routing always avoid heavy agents for trivial lookups?
task:
  type: "regression"
  # ...
  execution:
    trials: 3  # Run 3 times, fail if any trial fails
```

### Testing Your Task Locally

```bash
# Run single task
python evals/harness.py run evals/tasks/routing/task-003.yaml

# Run with multiple trials for pass@k measurement
python evals/harness.py run evals/tasks/routing/task-003.yaml --trials 3

# Save transcripts for debugging
python evals/harness.py run evals/tasks/routing/task-003.yaml --save-transcripts

# Run all tasks in category
python evals/harness.py suite evals/tasks/routing/

# Run only capability or regression tasks
python evals/harness.py suite evals/tasks/ --type capability
```

### Complete Task Example

```yaml
# evals/tasks/routing/task-003.yaml
task:
  id: "routing-003"
  name: "Route Python debugging to correct agent"
  description: |
    Verify that Python debugging requests route to python-general-engineer
    or systematic-debugging skill, not to unrelated agents.
  category: "routing"
  type: "regression"  # Must always route correctly

  input:
    prompt: "/do debug why my pytest tests are failing in tests/unit/"

  execution:
    agent: null  # Let /do decide
    skill: "do"
    timeout_seconds: 60
    trials: 3  # Regression: all must pass

  graders:
    - type: "regex_match"
      config:
        target: "transcript"
        pattern: "(python-general-engineer|systematic-debugging|pytest)"
      weight: 0.5

    - type: "string_contains"
      config:
        target: "transcript"
        patterns:
          - "python"
        match_all: false
      weight: 0.3

    - type: "string_contains"
      config:
        target: "transcript"
        patterns:
          - "golang"  # Should NOT mention Go
        match_all: false
      weight: 0.2
      # Note: This grader FAILS if golang is found (we want inverse)
      # Consider using a dedicated "string_not_contains" grader

  reference:
    notes: |
      Should route to:
      - python-general-engineer
      - systematic-debugging with Python context
      Should NOT route to:
      - golang-general-engineer
      - typescript-frontend-engineer
```

---

## Adding New Graders

Graders evaluate task outputs. The harness supports these built-in graders:

| Type | Purpose |
|------|---------|
| `file_exists` | Check file creation |
| `string_contains` | Check for substrings |
| `regex_match` | Pattern matching |
| `tests_pass` | Run command, check exit code |
| `yaml_valid` | Validate YAML structure |
| `llm_rubric` | LLM-as-judge via CLI |
| `tool_calls` | Validate tool usage (V2) |
| `state_check` | Verify file/git state (V2) |
| `transcript_constraint` | Enforce transcript limits (V2) |
| `agent_evaluator` | Agent-based grading |

### Grader Function Signature

All graders follow this signature:

```python
def grade_your_grader(transcript: str, env: dict, config: dict) -> dict:
    """
    Evaluate a task output.

    Args:
        transcript: The agent's output text
        env: Environment dict with 'work_dir' key (temp directory path)
        config: Grader configuration from task YAML

    Returns:
        dict with:
            - type: str - Grader type name
            - passed: bool - Whether the check passed
            - score: float - Score from 0.0 to 1.0
            - details: str - Human-readable explanation
            - (optional) additional fields for debugging
    """
    # Your grading logic here
    return {
        "type": "your_grader",
        "passed": True,
        "score": 1.0,
        "details": "Explanation of result",
    }
```

### Registering in GRADERS Dict

Add your grader to the `GRADERS` registry in `harness.py`:

```python
# harness.py - near line 953

# Grader registry
GRADERS = {
    "file_exists": grade_file_exists,
    "string_contains": grade_string_contains,
    "regex_match": grade_regex_match,
    "tests_pass": grade_tests_pass,
    "yaml_valid": grade_yaml_valid,
    "llm_rubric": grade_llm_rubric,
    "agent_evaluator": grade_agent_evaluator,
    # Add your grader here:
    "your_grader": grade_your_grader,
}
```

### Creating Calibration Data

Calibration data ensures graders behave consistently. Create examples that test edge cases.

**Directory structure:**
```
evals/calibration/
  your_grader/
    examples.yaml
```

**Calibration file format:**
```yaml
# evals/calibration/your_grader/examples.yaml
examples:
  - id: "yg-001"
    description: "Clear success case"
    input:
      transcript: |
        The agent completed the task successfully.
        All requirements were met.
      config:
        # Your grader's config options
        threshold: 0.8
    expected:
      passed: true
      score: 1.0

  - id: "yg-002"
    description: "Partial success"
    input:
      transcript: |
        The task was partially completed.
      config:
        threshold: 0.8
    expected:
      passed: false
      score: 0.5

  - id: "yg-003"
    description: "Clear failure"
    input:
      transcript: |
        Error: Task failed immediately.
      config:
        threshold: 0.8
    expected:
      passed: false
      score: 0.0
```

**For LLM-based graders**, use score ranges to account for variance:
```yaml
expected:
  passed: true
  score_min: 0.85  # Allow variance
  score_max: 1.0
```

**Run calibration:**
```bash
# Calibrate single grader
python evals/harness.py calibrate your_grader

# Calibrate all graders
python evals/harness.py calibrate --all
```

### Example: Custom Grader Implementation

```python
def grade_import_check(transcript: str, env: dict, config: dict) -> dict:
    """Check that specific Python imports are used."""
    target = config.get("target", "transcript")

    # Get content to check
    if target == "transcript":
        content = transcript
    elif target.startswith("file:"):
        file_path = Path(env["work_dir"]) / target[5:]
        if not file_path.exists():
            return {
                "type": "import_check",
                "passed": False,
                "score": 0.0,
                "details": f"File not found: {target[5:]}",
            }
        content = file_path.read_text()
    else:
        content = transcript

    required_imports = config.get("required_imports", [])
    banned_imports = config.get("banned_imports", [])

    # Check required imports
    found_required = []
    for imp in required_imports:
        pattern = rf"^(?:from\s+\S+\s+)?import\s+.*{re.escape(imp)}"
        if re.search(pattern, content, re.MULTILINE):
            found_required.append(imp)

    # Check banned imports
    found_banned = []
    for imp in banned_imports:
        pattern = rf"^(?:from\s+\S+\s+)?import\s+.*{re.escape(imp)}"
        if re.search(pattern, content, re.MULTILINE):
            found_banned.append(imp)

    # Calculate score
    required_score = len(found_required) / len(required_imports) if required_imports else 1.0
    banned_penalty = len(found_banned) * 0.2  # -20% per banned import
    score = max(0.0, required_score - banned_penalty)
    passed = score >= 0.8 and len(found_banned) == 0

    return {
        "type": "import_check",
        "passed": passed,
        "score": score,
        "details": f"Found {len(found_required)}/{len(required_imports)} required, {len(found_banned)} banned",
        "found_required": found_required,
        "found_banned": found_banned,
        "missing_required": [i for i in required_imports if i not in found_required],
    }
```

---

## Creating Rubrics

Rubrics define evaluation criteria for LLM-as-judge grading.

### Rubric File Format

Store rubrics in `evals/rubrics/` as Markdown files:

```markdown
# Rubric: [Purpose]

Use this rubric to evaluate [what].

## Evaluation Criteria

### 1. Category Name (X points)
- Specific criterion 1
- Specific criterion 2
- Specific criterion 3

### 2. Category Name (Y points)
- Criterion...

## Scoring Guidelines

- **90-100**: Excellent - [description]
- **75-89**: Good - [description]
- **60-74**: Adequate - [description]
- **Below 60**: Needs work - [description]

## Red Flags (Automatic Deductions)
- [Issue] (-X points)
- [Issue] (-Y points)

## Pass Threshold
[Minimum score required to pass]
```

### Writing Effective Assertions

Assertions are the specific checks the LLM evaluator performs. Good assertions are:

**Specific and Observable:**
```yaml
# Good - specific, can be verified
assertions:
  - "Code includes type hints on function parameters and return values"
  - "Function has a docstring with Args and Returns sections"
  - "Error cases are handled with try/except blocks"

# Bad - vague, subjective
assertions:
  - "Code is well-written"
  - "Good error handling"
  - "Follows best practices"
```

**Binary (Pass/Fail):**
```yaml
# Good - clear pass/fail
assertions:
  - "File contains a class named UserService"
  - "Tests cover the happy path and at least one error case"

# Bad - requires judgment on degree
assertions:
  - "Code is reasonably efficient"
  - "Documentation is adequate"
```

**Relevant to Task Goal:**
```yaml
# For agent-creation task
assertions:
  - "Agent has YAML frontmatter with name, description, version"
  - "Agent specifies appropriate tools for the task"
  - "Agent includes at least one usage example"

# For code review task
assertions:
  - "Review identifies at least 3 specific issues"
  - "Each issue includes suggested fix"
  - "Review covers security implications if relevant"
```

### Rubric Examples

**Agent Quality Rubric** (`rubrics/agent_quality.md`):
```markdown
# Agent Quality Rubric

## Evaluation Criteria

### 1. Structure (25 points)
- Valid YAML frontmatter with required fields (name, description, version)
- Clear section organization
- Proper markdown formatting

### 2. Clarity (25 points)
- Description clearly explains the agent's purpose
- Triggers are specific and unambiguous
- Examples show realistic usage

### 3. Completeness (25 points)
- Appropriate tool list for the task
- Handles common edge cases
- Includes error handling guidance

### 4. Usability (25 points)
- Easy to understand when to use
- Clear differentiation from similar agents
- Actionable instructions

## Red Flags
- Missing required frontmatter fields (-20)
- No clear triggers defined (-15)
- Copy-pasted generic content (-10)
```

**Voice Authenticity Rubric** (`rubrics/voice_authenticity.md`):
```markdown
# Voice Authenticity Rubric

## Evaluation Criteria

### 1. Tone Match (30 points)
- Emotional register matches the voice
- Appropriate level of formality
- Consistent personality throughout

### 2. Vocabulary & Diction (25 points)
- Word choices characteristic of the voice
- Avoids words on the banned list
- Natural sentence rhythm

### 3. Anti-AI Markers (25 points)
- No corporate buzzwords
- No excessive hedging
- Natural imperfections present

## Red Flags
- Using "delve" or "tapestry" (-10 each)
- Corporate language (-15)
```

---

## Eval-Driven Development Workflow

### The Core Cycle

```
1. Write failing eval  -->  2. Implement feature  -->  3. Pass eval
       ^                                                    |
       |                                                    |
       +--------------------  Iterate  <--------------------+
```

### When to Write Which Type

| Scenario | Eval Type | Why |
|----------|-----------|-----|
| New feature being developed | Capability | Tests if agent CAN do it |
| Bug fix | Regression | Ensures bug stays fixed |
| Core routing logic | Regression | Must ALWAYS work correctly |
| Complex generation | Capability | Some variance is acceptable |
| Safety-critical behavior | Regression | Zero tolerance for failures |

### Workflow Example: Adding New Agent

**Step 1: Write the failing eval first**

```yaml
# evals/tasks/agent-creation/task-005.yaml
task:
  id: "agent-creation-005"
  name: "Create Rust linting agent"
  description: "Test creation of Rust-specific linting agent"
  category: "agent-creation"
  type: "capability"

  input:
    prompt: |
      Create an agent for Rust code linting using clippy.
      Save it as agents/rust-linter.md

  execution:
    agent: "agent-creator-engineer"
    timeout_seconds: 180
    trials: 1

  graders:
    - type: "file_exists"
      config:
        path: "agents/rust-linter.md"
      weight: 0.3

    - type: "yaml_valid"
      config:
        path: "agents/rust-linter.md"
        required_fields: ["name", "description"]
      weight: 0.3

    - type: "string_contains"
      config:
        target: "file:agents/rust-linter.md"
        patterns: ["clippy", "rust", "lint"]
      weight: 0.4
```

**Step 2: Run the eval (expect failure)**

```bash
python evals/harness.py run evals/tasks/agent-creation/task-005.yaml
# Output: FAIL - agent-creator-engineer doesn't know about Rust
```

**Step 3: Implement the feature**

Update `agents/agent-creator-engineer.md` to understand Rust tooling.

**Step 4: Run eval again (expect pass)**

```bash
python evals/harness.py run evals/tasks/agent-creation/task-005.yaml
# Output: PASS - Score: 0.95
```

**Step 5: Add regression protection**

If this is critical functionality, convert to regression:

```yaml
type: "regression"
execution:
  trials: 3  # Must pass all 3 times
```

### Continuous Improvement Cycle

```
Week 1: Identify capability gap
        --> Write capability eval
        --> Implement fix
        --> Verify pass@k

Week 2: Promote stable capabilities to regression
        --> Change type to "regression"
        --> Increase trials
        --> Monitor pass^k

Week 3: Review regression failures
        --> Analyze root causes
        --> Add edge case evals
        --> Iterate on implementation
```

### Metrics to Track

| Metric | Meaning | Target |
|--------|---------|--------|
| `pass@k` | At least one of k trials passed | >90% for capability |
| `pass^k` | All k trials passed | >95% for regression |
| `avg_score` | Mean score across trials | >0.85 |
| `tokens_total` | Total tokens consumed | Monitor for efficiency |
| `cost_usd` | Total cost in USD | Budget awareness |

### Suite-Level Analysis

```bash
# Run full suite with regression focus
python evals/harness.py suite evals/tasks/ --type regression --trials 3

# Review results
cat evals/results/eval-*.json | jq '.summary'

# Focus on failures
cat evals/results/eval-*.json | jq '.results[] | select(.["pass@k"] == false)'
```

---

## Pull Request Checklist

Before submitting a PR that adds or modifies evals:

### Required Checks

- [ ] **Task YAML validates**
  ```bash
  python -c "import yaml; yaml.safe_load(open('evals/tasks/category/task-NNN.yaml'))"
  ```

- [ ] **Task runs without errors**
  ```bash
  python evals/harness.py run evals/tasks/category/task-NNN.yaml
  ```

- [ ] **Task ID is unique**
  ```bash
  grep -r "id: \"your-task-id\"" evals/tasks/
  # Should return only your file
  ```

### For New Graders

- [ ] **Grader registered in GRADERS dict**
  ```bash
  grep "your_grader" evals/harness.py | head -5
  ```

- [ ] **Calibration data exists**
  ```bash
  ls evals/calibration/your_grader/examples.yaml
  ```

- [ ] **Calibration passes**
  ```bash
  python evals/harness.py calibrate your_grader
  # Agreement rate should be >80%
  ```

### For New Rubrics

- [ ] **Rubric file exists in rubrics/**
  ```bash
  ls evals/rubrics/your_rubric.md
  ```

- [ ] **Rubric referenced by at least one task**
  ```bash
  grep "rubric: \"rubrics/your_rubric.md\"" evals/tasks/**/*.yaml
  ```

### Documentation

- [ ] **Task has meaningful description**
- [ ] **Reference solution provided** (for complex tasks)
- [ ] **README updated** (if adding new category)

### Testing

- [ ] **Single run passes**
  ```bash
  python evals/harness.py run evals/tasks/category/task-NNN.yaml
  ```

- [ ] **Multi-trial consistency** (for regression tasks)
  ```bash
  python evals/harness.py run evals/tasks/category/task-NNN.yaml --trials 3
  # All trials should pass for regression type
  ```

- [ ] **Suite still passes**
  ```bash
  python evals/harness.py suite evals/tasks/category/
  ```

### Quick Validation Script

```bash
#!/bin/bash
# validate-eval-pr.sh

TASK_FILE=$1

if [ -z "$TASK_FILE" ]; then
    echo "Usage: ./validate-eval-pr.sh path/to/task.yaml"
    exit 1
fi

echo "=== Validating $TASK_FILE ==="

# Check YAML syntax
echo "1. Checking YAML syntax..."
python -c "import yaml; yaml.safe_load(open('$TASK_FILE'))" || exit 1
echo "   OK"

# Check required fields
echo "2. Checking required fields..."
python -c "
import yaml
with open('$TASK_FILE') as f:
    data = yaml.safe_load(f)
task = data.get('task', data)
required = ['id', 'name', 'description', 'category', 'type']
missing = [f for f in required if f not in task]
if missing:
    print(f'   Missing: {missing}')
    exit(1)
print('   OK')
"

# Run the task
echo "3. Running task..."
python evals/harness.py run "$TASK_FILE" || exit 1
echo "   OK"

echo ""
echo "=== All checks passed ==="
```

---

## Quick Reference

### Common Commands

```bash
# Run single task
python evals/harness.py run evals/tasks/routing/task-001.yaml

# Run with trials
python evals/harness.py run task.yaml --trials 3

# Run suite
python evals/harness.py suite evals/tasks/routing/

# Filter by type
python evals/harness.py suite evals/tasks/ --type regression

# Calibrate graders
python evals/harness.py calibrate string_contains
python evals/harness.py calibrate --all

# Grade agent quality
python evals/harness.py grade-agent agents/my-agent.md

# Test agent with evals
python evals/harness.py skill-test python-general-engineer --trials 3
```

### Grader Quick Reference

| Grader | Config Keys | Notes |
|--------|-------------|-------|
| `file_exists` | `path` | Relative to work_dir |
| `string_contains` | `target`, `patterns`, `match_all` | `target`: "transcript" or "file:path" |
| `regex_match` | `target`, `pattern` | Uses Python regex |
| `tests_pass` | `command`, `working_dir` | 60s timeout |
| `yaml_valid` | `path`, `required_fields` | Handles frontmatter in .md |
| `llm_rubric` | `rubric`, `assertions` | Uses claude CLI |
| `tool_calls` | `required_tools`, `forbidden_tools`, `tool_params` | V2: Validate tool usage patterns |
| `state_check` | `files_exist`, `file_contains`, `git_status` | V2: Verify final state |
| `transcript_constraint` | `max_turns`, `max_tool_calls`, `forbidden_patterns` | V2: Enforce limits |
| `agent_evaluator` | `agent`, `rubric`, `assertions` | Grade via specialized agent |

### Task Type Decision Matrix

| Scenario | Type | Trials |
|----------|------|--------|
| "Can the agent do X?" | capability | 1-3 |
| "Does the agent always do X?" | regression | 3-5 |
| New experimental feature | capability | 1 |
| Core routing logic | regression | 5 |
| Complex generation | capability | 3 |
| Safety-critical | regression | 5+ |
