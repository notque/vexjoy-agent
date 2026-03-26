---
name: skill-eval
description: |
  Evaluate and improve skills through measured testing. Run trigger evaluations
  to test whether skill descriptions cause correct activation, optimize
  descriptions via automated train/test loops, benchmark skill output quality
  with A/B comparisons, and validate skill structure. Use when user says
  "improve skill", "test skill triggers", "optimize description", "benchmark
  skill", "eval skill", or "skill quality". Do NOT use for creating new skills
  (use skill-creator-engineer).
version: 1.0.0
user-invocable: false
argument-hint: "<skill-name>"
agent: skill-creator-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Agent
routing:
  triggers:
    - improve skill
    - test skill
    - eval skill
    - optimize description
    - benchmark skill
    - skill triggers
    - skill quality
  pairs_with:
    - agent-evaluation
    - verification-before-completion
  complexity: Medium-Complex
  category: meta
---

# Skill Evaluation & Improvement

Measure and improve skill quality through empirical testing — because structure doesn't guarantee behavior, and measurement beats assumption.

## Operator Context

This skill operates as the eval-driven improvement pipeline for Claude Code skills. It provides four capabilities: trigger evaluation, description optimization, output benchmarking, and structural validation.

### Hardcoded Behaviors (Always Apply)
- **Measure before changing**: Always run baseline eval before making improvements
- **Train/test split**: Use 60/40 holdout to prevent overfitting descriptions
- **Generalize, don't overfit**: Improvements should help across many prompts, not just test cases
- **Report results**: Always show before/after metrics

### Default Behaviors (ON unless disabled)
- **HTML reports**: Generate visual reports for description optimization
- **Verbose output**: Show per-query pass/fail during eval runs
- **3 runs per query**: Run each trigger test 3 times for reliability

### Optional Behaviors (OFF unless enabled)
- **Blind A/B comparison**: Use comparator agent for unbiased output comparison
- **Full benchmark suite**: Run aggregate benchmarks with timing and token metrics

## What This Skill CAN Do
- Test whether a skill's description triggers correctly for a set of queries
- Optimize descriptions via automated eval+improve loop (train/test split)
- Benchmark skill output quality (with-skill vs without-skill)
- Validate skill structure (frontmatter, naming, description length)
- Generate HTML reports for visual review

## What This Skill CANNOT Do
- Create new skills from scratch (use skill-creator-engineer)
- Modify skill instructions automatically (human reviews changes)
- Test skills that require specific MCP servers or external services
- Run evals without the `claude` CLI available

---

## Instructions

### Phase 1: ASSESS — Determine what to evaluate

**Step 1: Identify the skill**

```bash
# Validate skill structure first
python3 -m scripts.skill_eval.quick_validate <path/to/skill>
```

**Step 2: Choose evaluation mode**

| User Intent | Mode | Script |
|------------|------|--------|
| "Test if description triggers correctly" | Trigger eval | `run_eval.py` |
| "Optimize/improve the description" | Description optimization | `run_loop.py` |
| "Compare skill vs no-skill output" | Output benchmark | Manual + `aggregate_benchmark.py` |
| "Validate skill structure" | Quick validate | `quick_validate.py` |

**GATE**: Skill path confirmed, mode selected.

### Phase 2: EVALUATE — Run the appropriate evaluation

#### Mode A: Trigger Evaluation

Test whether a skill's description causes Claude to invoke it for the right queries.

**Step 1: Create eval set** (or use existing)

Create a JSON file with 8-20 test queries:
```json
[
  {"query": "realistic user prompt that should trigger", "should_trigger": true},
  {"query": "similar but different domain prompt", "should_trigger": false}
]
```

**Eval set quality matters** — use realistic prompts with detail (file paths, context, casual phrasing), not abstract one-liners. Focus on edge cases where the skill competes with adjacent skills.

**Step 2: Run evaluation**

```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --runs-per-query 3 \
  --verbose
```

This spawns `claude -p` for each query, checking whether it invokes the skill. Output includes pass/fail per query with trigger rates.

**GATE**: Eval results available. Proceed to improvement if failures found.

#### Mode B: Description Optimization

Automated loop that tests, improves, and re-tests descriptions.

```bash
python3 -m scripts.skill_eval.run_loop \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --model claude-opus-4-6 \
  --max-iterations 5 \
  --verbose
```

This will:
1. Split eval set 60/40 train/test (stratified by should_trigger)
2. Evaluate current description on all queries (3 runs each)
3. Use Claude with extended thinking to propose improvements based on failures
4. Re-evaluate the new description
5. Repeat until all pass or max iterations reached
6. Select best description by **test** score (prevents overfitting)
7. Open an HTML report in the browser

**GATE**: Loop complete. Best description identified.

#### Mode C: Output Benchmark

Compare skill quality by running prompts with and without the skill.

**Step 1: Create test prompts** — 2-3 realistic user prompts

**Step 2: Run with-skill and without-skill** in parallel subagents:

For each test prompt, spawn two agents:
- **With skill**: Load the skill, run the prompt, save outputs
- **Without skill** (baseline): Same prompt, no skill, save outputs

**Step 3: Grade outputs**

Spawn a grader subagent using the prompt in `agents/grader.md`. It evaluates assertions against the outputs.

**Step 4: Aggregate**

```bash
python3 -m scripts.skill_eval.aggregate_benchmark <workspace>/iteration-1 --skill-name <name>
```

Produces `benchmark.json` and `benchmark.md` with pass rates, timing, and token usage.

**Step 5: Analyze** (optional)

For blind comparison, use `agents/comparator.md` to judge outputs without knowing which skill produced them. Then use `agents/analyzer.md` to understand why the winner won.

**GATE**: Benchmark results available.

#### Mode D: Quick Validate

```bash
python3 -m scripts.skill_eval.quick_validate <path/to/skill>
```

Checks: SKILL.md exists, valid frontmatter, required fields (name, description), kebab-case naming, description under 1024 chars, no angle brackets.

### Phase 3: IMPROVE — Apply results

**Step 1: Review results**

For trigger eval / description optimization:
- Show the best description vs original
- Show per-query results (which queries improved, which regressed)
- Show train vs test scores

For output benchmark:
- Show pass rate delta (with-skill vs without-skill)
- Show timing and token cost delta
- Highlight assertions that only pass with the skill (value-add)

**Step 2: Apply changes** (with user confirmation)

If description optimization found a better description:
1. Show before/after with scores
2. Ask user to confirm
3. Update the skill's SKILL.md frontmatter
4. Re-run quick_validate to confirm the update is valid

**GATE**: Changes applied and validated, or user chose to keep original.

---

## Error Handling

### Error: "No SKILL.md found"
**Cause**: Skill path doesn't point to a valid skill directory
**Solution**: Verify path contains a `SKILL.md` file. Skills must follow the `skill-name/SKILL.md` structure.

### Error: "claude: command not found"
**Cause**: Claude CLI not available for trigger evaluation
**Solution**: Install Claude Code CLI. Trigger eval requires `claude -p` to test skill invocation.

### Error: "anthropic SDK not installed"
**Cause**: Description optimization requires the Anthropic Python SDK
**Solution**: `pip install anthropic`. Only needed for `improve_description.py` and `run_loop.py`.

### Error: "CLAUDECODE environment variable"
**Cause**: Running eval from inside a Claude Code session blocks nested instances
**Solution**: The scripts automatically strip the `CLAUDECODE` env var. If issues persist, run from a separate terminal.

### Error: "All queries timeout"
**Cause**: Default 30s timeout too short for complex queries
**Solution**: Increase with `--timeout 60`. Simple trigger queries should complete in <15s.

---

## Anti-Patterns

### Anti-Pattern 1: Abstract Eval Queries
**What it looks like**: `"Format this data"`, `"Create a chart"`
**Why wrong**: Real users write detailed, specific prompts. Abstract queries don't test real triggering behavior.
**Do instead**: `"ok so my boss sent me this xlsx file (Q4 sales final FINAL v2.xlsx) and she wants profit margin as a percentage"`

### Anti-Pattern 2: Overfitting to Test Cases
**What it looks like**: Adding specific query text to the description to force triggers
**Why wrong**: Works for test set, fails on real usage. Bloats the description.
**Do instead**: Generalize from failures to broader categories of user intent.

### Anti-Pattern 3: Skipping Baseline
**What it looks like**: Running with-skill only, no without-skill comparison
**Why wrong**: Can't prove the skill adds value without a baseline. Maybe Claude handles it fine without the skill.
**Do instead**: Always run both configurations. The delta is what matters.

---

## References

### Scripts (in `scripts/skill_eval/`)
- `run_eval.py` — Trigger evaluation: tests description against query set
- `run_loop.py` — Eval+improve loop: automated description optimization
- `improve_description.py` — Single-shot description improvement via Claude API
- `generate_report.py` — HTML report from loop output
- `aggregate_benchmark.py` — Benchmark aggregation from grading results
- `quick_validate.py` — Structural validation of SKILL.md

### Bundled Agents (in `skills/skill-eval/agents/`)
- `grader.md` — Evaluates assertions against execution outputs
- `comparator.md` — Blind A/B comparison of two outputs
- `analyzer.md` — Post-hoc analysis of why one version beat another

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/schemas.md` — JSON schemas for evals.json, grading.json, benchmark.json

### Shared Patterns
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md)
- [Verification Checklist](../shared-patterns/verification-checklist.md)
