---
name: agent-comparison
description: "A/B test agent variants for quality and token cost."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
routing:
  triggers:
    - "compare agents"
    - "A/B test agents"
    - "benchmark agents"
    - "optimize skill"
    - "optimize description"
    - "run autoresearch"
  category: meta-tooling
  pairs_with:
    - agent-evaluation
    - skill-eval
---

# Agent Comparison Skill

Compare agent variants through controlled A/B benchmarks. Runs identical tasks on both agents, grades output with domain-specific checklists, reports total session token cost to working solution. Use `agent-evaluation` for single-agent assessment, `skill-eval` for skill testing.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `benchmark-tasks.md` | Loads detailed guidance from `benchmark-tasks.md`. |
| example-driven tasks, errors | `examples-and-errors.md` | Loads detailed guidance from `examples-and-errors.md`. |
| tasks related to this reference | `grading-rubric.md` | Loads detailed guidance from `grading-rubric.md`. |
| tasks related to this reference | `methodology.md` | Loads detailed guidance from `methodology.md`. |
| tasks related to this reference | `optimization-guide.md` | Loads detailed guidance from `optimization-guide.md`. |
| tasks related to this reference | `optimize-phase.md` | Loads detailed guidance from `optimize-phase.md`. |
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |

## Instructions

> See `references/examples-and-errors.md` for error handling. See `references/optimize-phase.md` for Phase 5 OPTIMIZE full procedure. See `references/methodology.md` for December 2024 benchmark data.

### Phase 1: PREPARE

**Goal**: Create benchmark environment and validate both agent variants exist.

Read and follow the repository CLAUDE.md before starting.

**Step 1: Analyze original agent**

```bash
wc -l agents/{original-agent}.md
grep "^## " agents/{original-agent}.md
grep -c '```' agents/{original-agent}.md
```

**Step 2: Create or validate compact variant**

If creating a compact variant, preserve:
- YAML frontmatter (name, description, routing)
- Core patterns and principles
- Error handling philosophy

Remove or condense:
- Lengthy code examples (keep 1-2 per pattern)
- Verbose explanations (condense to bullets)
- Redundant instructions and changelogs

Target 10-15% of original size. Remove redundancy, not capability -- stripping error handling or concurrency guidance creates an unfair comparison.

**Step 3: Validate compact variant structure**

```bash
head -20 agents/{compact-agent}.md | grep -E "^(name|description):"
echo "Original: $(wc -l < agents/{original-agent}.md) lines"
echo "Compact:  $(wc -l < agents/{compact-agent}.md) lines"
```

**Step 4: Create benchmark directory and prepare prompts**

```bash
mkdir -p benchmark/{task-name}/{full,compact}
```

Write the task prompt ONCE, copy for both agents. Both must receive identical task descriptions character-for-character -- different requirements invalidate all measurements.

Keep benchmark scripts simple -- no speculative features or configurable frameworks.

**Gate**: Both variants exist with valid YAML. Benchmark directories created. Identical prompts written.

### Phase 2: BENCHMARK

**Goal**: Run identical tasks on both agents, capturing all metrics.

**Step 1: Run simple task benchmark (2-3 tasks)**

Use algorithmic problems with clear specs (e.g., Advent of Code Day 1-6). Simple tasks establish a baseline -- failure here indicates fundamental issues. Multiple tasks needed to distinguish luck from systematic quality.

Spawn both agents in parallel:

```
Task(
  prompt="[exact task prompt]\nSave to: benchmark/{task}/full/",
  subagent_type="{full-agent}"
)

Task(
  prompt="[exact task prompt]\nSave to: benchmark/{task}/compact/",
  subagent_type="{compact-agent}"
)
```

Run in parallel to avoid caching effects or load variance.

**Step 2: Run complex task benchmark (1-2 tasks)**

Use production-style problems requiring concurrency, error handling, edge cases -- where quality differences emerge. See `references/benchmark-tasks.md` for standard tasks.

Recommended: Worker Pool (rate limiting, graceful shutdown, panic recovery), LRU Cache with TTL (generics, background goroutines, zero-value semantics), HTTP Service (middleware, structured errors, health checks).

**Step 3: Capture metrics immediately after each agent completes**

| Metric | Full Agent | Compact Agent |
|--------|------------|---------------|
| Tests pass | X/X | X/X |
| Race conditions | X | X |
| Code lines (main) | X | X |
| Test lines | X | X |
| Session tokens | X | X |
| Wall-clock time | Xm Xs | Xm Xs |
| Retry cycles | X | X |

**Step 4: Run tests with race detector**

```bash
cd benchmark/{task-name}/full && go test -race -v -count=1
cd benchmark/{task-name}/compact && go test -race -v -count=1
```

`-count=1` disables test caching. Race conditions are automatic quality failures.

**Gate**: Both agents completed all tasks. Metrics captured. Test output saved.

### Phase 3: GRADE

**Goal**: Score code quality beyond pass/fail using domain-specific checklists.

**Step 1: Create quality checklist BEFORE reviewing code**

Define criteria before seeing results to prevent bias. See `references/grading-rubric.md` for standard rubrics.

| Criterion | 5/5 | 3/5 | 1/5 |
|-----------|-----|-----|-----|
| Correctness | All tests pass, no races | Some failures | Broken |
| Error Handling | Comprehensive, production-ready | Adequate | None |
| Idioms | Exemplary for the language | Acceptable | Anti-patterns |
| Documentation | Thorough | Adequate | None |
| Testing | Comprehensive coverage | Basic | Minimal |

**Step 2: Score each solution independently**

Grade one agent completely before starting the other. Every claim must be backed by measurable data (tokens, test counts, quality scores).

```markdown
## {Agent} Solution - {Task}

| Criterion | Score | Notes |
|-----------|-------|-------|
| Correctness | X/5 | |
| Error Handling | X/5 | |
| Idioms | X/5 | |
| Documentation | X/5 | |
| Testing | X/5 | |
| **Total** | **X/25** | |
```

**Step 3: Document specific bugs with production impact**

```markdown
### Bug: {description}
- Agent: {which agent}
- What happened: {behavior}
- Correct behavior: {expected}
- Production impact: {consequence}
- Test coverage: {did tests catch it? why not?}
```

"Tests pass" is necessary but not sufficient -- tests can miss goroutine leaks, wrong semantics, and other production issues. Apply the quality checklist.

**Step 4: Calculate effective cost**

```
effective_cost = total_tokens * (1 + bug_count * 0.25)
```

194k tokens with 0 bugs beats 119k tokens with 5 bugs. The metric is total cost to working, production-quality solution -- not prompt size. Check quality scores before claiming token savings.

**Gate**: Both solutions graded with evidence. Bugs documented. Effective cost calculated.

### Phase 4: REPORT

**Goal**: Generate comparison report with evidence-backed verdict.

**Step 1: Generate comparison report**

Use `references/report-template.md`. Include:
- Executive summary with clear winner per metric
- Per-task results with metrics tables
- Token economics (one-time prompt cost vs session cost)
- Specific bugs and production impact
- Verdict based on total evidence

**Step 2: Run comparison analysis**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/compare.py benchmark/{task-name}/
```

**Step 3: Analyze token economics**

Agent prompts are a one-time cost per session. Reasoning, code generation, debugging, retries cost tokens every turn.

| Pattern | Description |
|---------|-------------|
| Large agent, low churn | High initial cost, fewer retries, less debugging |
| Small agent, high churn | Low initial cost, more retries, more debugging |

Data: a 57-line agent used 69.5k tokens vs 69.6k for a 3,529-line agent on the same correct solution -- prompt size alone does not determine cost.

**Step 4: State verdict with evidence**

Include: which agent won simple tasks (expected: equivalent), which won complex tasks (expected: full agent), total session cost, effective cost with bug penalty, recommendation for when to use each variant.

See `references/methodology.md` for complete methodology with December 2024 data.

**Step 5: Clean up**

Remove temporary benchmark files and debug outputs. Keep only the comparison report and generated code.

**Gate**: Report generated with all metrics. Verdict stated with evidence. Report saved.

### Phase 5: OPTIMIZE (optional -- invoked explicitly)

**Goal**: Automated optimization loop improving a markdown target's frontmatter `description` using trigger-rate eval tasks, selecting best variants through beam search or single-path search.

Invoke when user says "optimize this skill", "optimize the description", or "run autoresearch". Manual A/B comparison (Phases 1-4) remains the path for full agent benchmarking.

> See `references/optimize-phase.md` for the full 9-step procedure, CLI flags, recommended modes, live eval defaults, and optional extensions.

**Gate**: Optimization complete. Results reviewed. Cherry-picked improvements applied and verified.

---

## References

- `${CLAUDE_SKILL_DIR}/references/methodology.md`: Complete testing methodology with December 2024 data
- `${CLAUDE_SKILL_DIR}/references/grading-rubric.md`: Detailed grading criteria and quality checklists
- `${CLAUDE_SKILL_DIR}/references/benchmark-tasks.md`: Standard benchmark task descriptions and prompts
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Comparison report template with all required sections
- `${CLAUDE_SKILL_DIR}/references/optimize-phase.md`: Full Phase 5 OPTIMIZE procedure (autoresearch loop, CLI flags, beam search, reality check)
- `${CLAUDE_SKILL_DIR}/references/examples-and-errors.md`: Error handling for common benchmark failures
