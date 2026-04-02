# A/B Test Plan: New Skills (Progressive Depth, Explanation Traces, Multi-Persona Critique)

## Overview

Blind A/B evaluation of three new skills before merge. Each skill is tested against a baseline (no skill loaded) to measure whether it adds measurable value over Claude's default behavior.

**Motivation**: ADR-127 established that A/B testing catches bugs that visual review misses. The first A/B test caught 2 CRITICAL bugs. Every new skill gets tested before merge.

## Test Methodology

**Blind evaluation**: The evaluator receives two outputs labeled A and B. They do not know which variant (skill-loaded vs baseline) produced which output. Assignment is randomized per case. This uses the existing `skill-eval/agents/comparator.md` blind comparator agent.

**Execution**: For each test case, spawn two parallel subagents:
- **Variant S** (skill): Load the skill, execute the prompt, save output
- **Variant B** (baseline): Same prompt, no skill loaded, save output

Randomize which output is labeled A vs B before passing to the evaluator.

**Sample size**: 5-7 test cases per skill (17 total across all three skills).

**Runs per case**: 3 runs per variant per case (for statistical reliability; pass `--runs-per-query 3` to `run_eval.py`).

## Skills Under Test

### 1. Progressive Depth Routing

**Claim**: Starting tasks at the shallowest viable depth and escalating on evidence produces better resource allocation than the current fixed-depth approach.

**Test design**: Same tasks routed WITH progressive-depth reference loaded vs WITHOUT.

**Metrics**:
- Depth appropriateness (1-5): Did the router select the right depth for this task's actual complexity?
- Escalation quality (1-5): When escalation happened, was it triggered by real evidence (not premature or delayed)?
- Resource efficiency (1-5): Did the task consume proportional resources to its actual complexity?

**Win condition**: Variant must win on 60%+ of cases (5/7 minimum).

### 2. Explanation Traces

**Claim**: Structured decision logging produces more accurate, falsifiable explanations than post-hoc LLM confabulation when users query "why did you do X?"

**Test design**: Users query "why did you do X?" WITH explanation-traces skill vs WITHOUT (baseline gets default LLM recall).

**Metrics**:
- Factual accuracy (1-5): Does the explanation reference actual decision factors from the session?
- Falsifiability (1-5): Could you disprove the explanation with evidence? (Post-hoc rationalizations score low here)
- Specificity (1-5): Does it cite concrete factors (file paths, trigger matches, complexity scores) vs vague generalizations?

**Win condition**: Variant must win on 60%+ of cases (3/5 minimum).

### 3. Multi-Persona Critique

**Claim**: Parallel critique from 5 philosophical personas produces higher-insight feedback than the existing `roast` skill (5 HackerNews personas) or plain evaluation.

**Test design**: Three-way comparison:
- **Variant A**: multi-persona-critique skill
- **Variant B**: existing `roast` skill
- **Variant C**: plain evaluation (no critique skill)

**Metrics**:
- Insight density (1-5): Number of non-obvious observations per unit of output
- Disagreement quality (1-5): When personas disagree, does it illuminate genuine tradeoffs?
- Synthesis usefulness (1-5): Is the final synthesis actionable and prioritized?
- Trap detection (1-5): Does the critique catch hidden flaws in proposals?

**Win condition**: Must beat BOTH roast and plain evaluation on 60%+ of cases to justify adding a new skill. If it ties or loses to roast, the existing skill is sufficient.

## Execution Steps

1. Run `python3 -m scripts.skill_eval.quick_validate` on each skill (once they exist)
2. Execute test cases per the case files in this directory
3. Use `skill-eval/agents/comparator.md` for blind comparison
4. Use `skill-eval/agents/analyzer.md` for post-hoc analysis of winners
5. Aggregate with `python3 -m scripts.skill_eval.aggregate_benchmark`
6. Document results in `benchmark.json` and `benchmark.md`

## File Index

| File | Skill | Cases |
|------|-------|-------|
| `progressive-depth-cases.md` | Progressive Depth Routing | 7 cases |
| `explanation-traces-cases.md` | Explanation Traces | 5 cases |
| `multi-persona-critique-cases.md` | Multi-Persona Critique | 5 cases |
| `scoring-rubric.md` | All skills | Blind evaluation rubric |
