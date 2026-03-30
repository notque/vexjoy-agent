---
name: skill-eval
description: |
  Evaluate and improve skills through measured testing. Run trigger evaluations
  to test whether skill descriptions cause correct activation, benchmark skill output quality
  with A/B comparisons, and validate skill structure. Use when user says
  "improve skill", "test skill triggers", "benchmark
  skill", "eval skill", or "skill quality". Do NOT use for creating new skills
  (use skill-creator). Route autoresearch loops for description/body optimization
  to agent-comparison.
version: 1.0.0
user-invocable: false
argument-hint: "<skill-name>"
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

## Instructions

### Phase 1: ASSESS — Determine what to evaluate

**Step 1: Identify the skill**

```bash
# Validate skill structure first
python3 -m scripts.skill_eval.quick_validate <path/to/skill>
```

This checks: SKILL.md exists, valid frontmatter, required fields (name, description), kebab-case naming, description under 1024 chars, no angle brackets.

**Step 2: Choose evaluation mode based on user intent**

| Intent | Mode | Script |
|--------|------|--------|
| "Test if description triggers correctly" | Trigger eval | `run_eval.py` |
| "Optimize/improve the description through autoresearch" | Route to `agent-comparison` | `optimize_loop.py` |
| "Compare skill vs no-skill output" | Output benchmark | Manual + `aggregate_benchmark.py` |
| "Validate skill structure" | Quick validate | `quick_validate.py` |

**GATE**: Skill path confirmed, mode selected.

### Phase 2: EVALUATE — Run the appropriate evaluation

#### Mode A: Trigger Evaluation

Test whether a skill's description causes Claude to invoke it for the right queries.

**Step 1: Create eval set** (or use existing)

Create a JSON file with 8-20 test queries. **Eval set quality matters** — use realistic prompts with detail (file paths, context, casual phrasing), not abstract one-liners. Focus on edge cases where the skill competes with adjacent skills.

Example of good eval queries:
```json
[
  {"query": "ok so my boss sent me this xlsx file (Q4 sales final FINAL v2.xlsx) and she wants profit margin as a percentage", "should_trigger": true},
  {"query": "Format this data", "should_trigger": false}
]
```

**Why**: Real users write detailed, specific prompts. Abstract queries don't test real triggering behavior. Overfitting descriptions to abstract test cases bloats the description and fails on real usage.

**Step 2: Run evaluation**

```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --runs-per-query 3 \
  --verbose
```

This spawns `claude -p` for each query, checking whether it invokes the skill. Runs each query 3 times for reliability. Output includes pass/fail per query with trigger rates. Default 30s timeout; increase with `--timeout 60` if needed for complex queries.

**Constraints applied**:
- Always run baseline eval before making improvements
- 3 runs per query ensures statistical reliability
- Verbose output shows per-query pass/fail during eval runs

**GATE**: Eval results available. Proceed to improvement if failures found.

#### Mode B: Description Optimization

Automated loop that tests, improves, and re-tests descriptions using Claude with extended thinking.

```bash
python3 -m scripts.skill_eval.run_loop \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --max-iterations 5 \
  --verbose
```

This will:
1. Split eval set 60/40 train/test (stratified by should_trigger) — prevents overfitting to test cases
2. Evaluate current description on all queries (3 runs each for reliability)
3. Use `claude -p` to propose improvements based on training failures
4. Re-evaluate the new description
5. Repeat until all pass or max iterations reached
6. Select best description by **test** score (not train score — prevents overfitting)
7. Open an HTML report in the browser

**Why 60/40 split**: Improvements should help across many prompts, not just test cases. Training on failures, validating on holdout ensures generalization.

**Why report HTML**: Visual reports enable quick review of which queries improved, which regressed, and what the new description looks like.

**GATE**: Loop complete. Best description identified.

#### Mode C: Output Benchmark

Compare skill quality by running prompts with and without the skill.

**Step 1: Create test prompts** — 2-3 realistic user prompts

**Step 2: Run with-skill and without-skill** in parallel subagents:

For each test prompt, spawn two agents:
- **With skill**: Load the skill, run the prompt, save outputs
- **Without skill** (baseline): Same prompt, no skill, save outputs

**Why baseline matters**: Can't prove the skill adds value without a baseline. Maybe Claude handles it fine without the skill. The delta is what matters.

**Step 3: Grade outputs**

Spawn a grader subagent using `agents/grader.md`. It evaluates assertions against the outputs.

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

**Constraint**: Always show results before/after with metrics. This enables informed decisions.

**GATE**: Changes applied and validated, or user chose to keep original.

---

## Error Handling

### Error: "No SKILL.md found"
**Cause**: Skill path doesn't point to a valid skill directory
**Solution**: Verify path contains a `SKILL.md` file. Skills must follow the `skill-name/SKILL.md` structure.

### Error: "claude: command not found"
**Cause**: Claude CLI not available for trigger evaluation
**Solution**: Install Claude Code CLI. Trigger eval requires `claude -p` to test skill invocation.

### Error: "legacy SDK dependency"
**Cause**: Outdated instructions or an old checkout still expects a direct SDK client
**Solution**: Update to the current scripts. Description optimization now runs through `claude -p`.

### Error: "CLAUDECODE environment variable"
**Cause**: Running eval from inside a Claude Code session blocks nested instances
**Solution**: The scripts automatically strip the `CLAUDECODE` env var. If issues persist, run from a separate terminal.

### Error: "All queries timeout"
**Cause**: Default 30s timeout too short for complex queries
**Solution**: Increase with `--timeout 60`. Simple trigger queries should complete in <15s.

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
