---
name: skill-eval
description: "Evaluate skills: trigger testing, A/B benchmarks, structure validation, head-to-head bake-offs."
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
    - self-improve skill
    - skill self-improvement
    - improve skill with variants
    - bake-off
    - bake off
    - head-to-head
    - head to head
    - compare implementations
    - grade two versions
    - which skill is better
  pairs_with:
    - agent-evaluation
    - verification-before-completion
  complexity: Medium-Complex
  category: meta
---

# Skill Evaluation & Improvement

Measure and improve skill quality through empirical testing. Also covers head-to-head bake-offs (Mode F).

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `schemas.md` | Loads detailed guidance from `schemas.md`. |
| tasks related to this reference | `self-improve-loop.md` | Loads detailed guidance from `self-improve-loop.md`. |
| "bake-off", "head-to-head", "compare implementations", "grade two versions", "which Feynman skill is better" | `bake-off-methodology.md` | Loads bake-off rubric, anti-rationalization gate, fold-filter, worked Feynman example. |

## Instructions

### Phase 1: ASSESS

**Step 1: Identify the skill**

```bash
python3 -m scripts.skill_eval.quick_validate <path/to/skill>
```

Checks: SKILL.md exists, valid frontmatter, required fields, kebab-case, description under 1024 chars, no angle brackets.

**Step 2: Choose evaluation mode**

| Intent | Mode | Script |
|--------|------|--------|
| "Test if description triggers correctly" | Trigger eval | `run_eval.py` |
| "Optimize/improve the description" | Route to `agent-comparison` | `optimize_loop.py` |
| "Compare skill vs no-skill output" | Output benchmark | Manual + `aggregate_benchmark.py` |
| "Validate skill structure" | Quick validate | `quick_validate.py` |
| "Self-improve skill" / "optimize skill" | Self-improvement loop | `references/self-improve-loop.md` |
| "Bake-off" / "head-to-head" / "compare X vs Y" | Head-to-head bake-off | `references/bake-off-methodology.md` |

**GATE**: Skill path confirmed, mode selected.

### Phase 2: EVALUATE

#### Mode A: Trigger Evaluation

**Step 1: Create eval set** (or use existing)

8-20 test queries in JSON. Use realistic prompts with detail, not abstract one-liners. Focus on edge cases where the skill competes with adjacent skills.

```json
[
  {"query": "ok so my boss sent me this xlsx file (Q4 sales final FINAL v2.xlsx) and she wants profit margin as a percentage", "should_trigger": true},
  {"query": "Format this data", "should_trigger": false}
]
```

**Step 2: Run evaluation**

```bash
python3 -m scripts.skill_eval.run_eval \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --runs-per-query 3 \
  --verbose
```

3 runs per query for reliability. Default 30s timeout; `--timeout 60` for complex queries. Always run baseline before improvements.

**GATE**: Eval results available. Proceed to improvement if failures found.

#### Mode B: Description Optimization

```bash
python3 -m scripts.skill_eval.run_loop \
  --eval-set evals.json \
  --skill-path <path/to/skill> \
  --max-iterations 5 \
  --verbose
```

1. Splits 60/40 train/test (stratified by should_trigger)
2. Evaluates current description (3 runs each)
3. Proposes improvements via `claude -p` based on training failures
4. Re-evaluates
5. Repeats until all pass or max iterations
6. Selects best by **test** score (not train -- prevents overfitting)
7. Opens HTML report

**GATE**: Loop complete. Best description identified.

#### Mode C: Output Benchmark

**Step 1**: Create 2-3 realistic test prompts.

**Step 2**: Spawn two agents per prompt (parallel): with-skill and baseline (no skill).

**Step 3**: Grade via `agents/grader.md`.

**Step 4**: Aggregate:
```bash
python3 -m scripts.skill_eval.aggregate_benchmark <workspace>/iteration-1 --skill-name <name>
```

**Step 5**: Optional blind comparison via `agents/comparator.md`, then analysis via `agents/analyzer.md`.

**GATE**: Benchmark results available.

#### Mode D: Quick Validate

```bash
python3 -m scripts.skill_eval.quick_validate <path/to/skill>
```

#### Mode E: Self-Improvement Loop

Read `${CLAUDE_SKILL_DIR}/references/self-improve-loop.md`.

5 phases: BASELINE (3+ test cases), HYPOTHESIZE (2-3 single-variable changes), GENERATE VARIANTS (minimal diffs), BLIND A/B TEST (paired via `agents/comparator.md`), PROMOTE OR KEEP (60%+ win rate, no regressions). All outcomes recorded to learning DB.

**GATE**: Protocol loaded. Proceed through 5 phases.

#### Mode F: Head-to-Head Bake-Off

Read `${CLAUDE_SKILL_DIR}/references/bake-off-methodology.md`.

5 phases: PREPARE (read both artifacts, pick neutral verifier), RUBRIC (5-12 criteria scored 0-10), GRADE (every score cites path/line/quote; anti-rationalization gate), FOLD (filter loser-wins through `docs/PHILOSOPHY.md`), REPORT (output to `tmp/<topic>-bakeoff-report.md`).

Canonical example: Feynman bake-off (toolkit 86 vs external 74, 11 criteria, 12-point margin).

**GATE**: Protocol loaded. Proceed through 5 phases.

### Phase 3: IMPROVE

**Step 1: Review results**

Trigger eval / description optimization: best vs original description, per-query results, train vs test scores.

Output benchmark: pass rate delta, timing/token cost delta, value-add assertions.

**Step 2: Apply changes** (with user confirmation)

1. Show before/after with scores
2. Confirm with user
3. Update SKILL.md frontmatter
4. Re-run quick_validate

**GATE**: Changes applied and validated, or user kept original.

---

## Error Handling

### No SKILL.md found
Cause: Invalid skill path.
Solution: Verify path contains `SKILL.md`. Must follow `skill-name/SKILL.md` structure.

### claude: command not found
Cause: CLI unavailable.
Solution: Install Claude Code CLI. Trigger eval requires `claude -p`.

### legacy SDK dependency
Cause: Outdated instructions expect direct SDK client.
Solution: Update to current scripts using `claude -p`.

### CLAUDECODE environment variable
Cause: Running eval inside Claude Code session blocks nested instances.
Solution: Scripts auto-strip `CLAUDECODE` env var. If issues persist, run from separate terminal.

### All queries timeout
Cause: Default 30s too short.
Solution: `--timeout 60`. Simple triggers should complete in <15s.

---

## References

### Scripts (in `scripts/skill_eval/`)
- `run_eval.py` -- Trigger evaluation
- `run_loop.py` -- Eval+improve loop
- `improve_description.py` -- Single-shot description improvement
- `generate_report.py` -- HTML report from loop output
- `aggregate_benchmark.py` -- Benchmark aggregation
- `quick_validate.py` -- Structural validation

### Bundled Agents (in `skills/skill-eval/agents/`)
- `grader.md` -- Evaluates assertions against outputs
- `comparator.md` -- Blind A/B comparison
- `analyzer.md` -- Post-hoc analysis of winners

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/schemas.md` -- JSON schemas for evals/grading/benchmark
- `${CLAUDE_SKILL_DIR}/references/self-improve-loop.md` -- Self-improvement protocol
- `${CLAUDE_SKILL_DIR}/references/bake-off-methodology.md` -- Bake-off protocol with Feynman worked example
