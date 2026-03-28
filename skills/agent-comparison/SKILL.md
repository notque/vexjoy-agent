---
name: agent-comparison
description: |
  A/B test agent variants measuring quality and total session token cost
  across simple and complex benchmarks. Use when creating compact agent
  versions, validating agent changes, comparing internal vs external agents,
  or deciding between variants for production. Use for "compare agents",
  "A/B test", "benchmark agents", or "test agent efficiency". Route single-agent evaluation to agent-evaluation, testing skills, or optimizing prompts
  without variant comparison.
version: 2.0.0
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
  category: meta-tooling
---

# Agent Comparison Skill

Compare agent variants through controlled A/B benchmarks. Runs identical tasks on both agents, grades output quality with domain-specific checklists, and reports total session token cost to a working solution. This skill is exclusively for agent variant comparison — use `agent-evaluation` for single-agent assessment, and `skill-eval` for skill testing.

## Instructions

### Phase 1: PREPARE

**Goal**: Create benchmark environment and validate both agent variants exist.

Read and follow the repository CLAUDE.md before starting any execution.

**Step 1: Analyze original agent**

```bash
# Count original agent size
wc -l agents/{original-agent}.md

# Identify major sections
grep "^## " agents/{original-agent}.md

# Count code examples (candidates for removal in compact version)
grep -c '```' agents/{original-agent}.md
```

**Step 2: Create or validate compact variant**

If creating a compact variant, preserve:
- YAML frontmatter (name, description, routing)
- Core patterns and principles
- Error handling philosophy

Remove or condense:
- Lengthy code examples (keep 1-2 representative per pattern)
- Verbose explanations (condense to bullet points)
- Redundant instructions and changelogs

Target 10-15% of original size while keeping essential knowledge. Remove redundancy, not capability — stripping error handling patterns or concurrency guidance creates an unfair comparison because the compact agent is missing essential knowledge rather than expressing it concisely.

**Step 3: Validate compact variant structure**

```bash
# Verify YAML frontmatter
head -20 agents/{compact-agent}.md | grep -E "^(name|description):"

# Compare sizes
echo "Original: $(wc -l < agents/{original-agent}.md) lines"
echo "Compact:  $(wc -l < agents/{compact-agent}.md) lines"
```

**Step 4: Create benchmark directory and prepare prompts**

```bash
mkdir -p benchmark/{task-name}/{full,compact}
```

Write the task prompt ONCE, then copy it for both agents. Both agents must receive the exact same task description, character-for-character, because different requirements produce different solutions and invalidate all measurements.

Keep benchmark scripts simple — no speculative features or configurable frameworks that were not requested.

**Gate**: Both agent variants exist with valid YAML frontmatter. Benchmark directories created. Identical task prompts written. Proceed only when gate passes.

### Phase 2: BENCHMARK

**Goal**: Run identical tasks on both agents, capturing all metrics.

**Step 1: Run simple task benchmark (2-3 tasks)**

Use algorithmic problems with clear specifications (e.g., Advent of Code Day 1-6). Simple tasks establish a baseline — if an agent fails here, it has fundamental issues. Running multiple simple tasks is necessary because a single data point is sensitive to task selection bias and cannot distinguish luck from systematic quality.

Spawn both agents in parallel using Task tool. Each agent runs in a separate session to avoid contamination:

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

Run in parallel to avoid caching effects or system load variance skewing results.

**Step 2: Run complex task benchmark (1-2 tasks)**

Use production-style problems that require concurrency, error handling, edge case anticipation — these are where quality differences emerge because simple tasks mask differences in edge case handling. See `references/benchmark-tasks.md` for standard tasks.

Recommended complex tasks:
- **Worker Pool**: Rate limiting, graceful shutdown, panic recovery
- **LRU Cache with TTL**: Generics, background goroutines, zero-value semantics
- **HTTP Service**: Middleware chains, structured errors, health checks

**Step 3: Capture metrics for each run**

Record immediately after each agent completes — record immediately after each agent completes, because delayed recording loses precision. Track input/output token counts per turn where visible, since total session cost (not just prompt size) is what matters.

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

Use `-count=1` to disable test caching. All generated code must pass the same test suite with the `-race` flag because race conditions are automatic quality failures. Record them but record them as findings for the agent being tested.

**Gate**: Both agents completed all tasks. Metrics captured for every run. Test output saved. Proceed only when gate passes.

### Phase 3: GRADE

**Goal**: Score code quality beyond pass/fail using domain-specific checklists.

**Step 1: Create quality checklist BEFORE reviewing code**

Define criteria before seeing results to prevent bias — inventing criteria after seeing one agent's output skews the comparison. See `references/grading-rubric.md` for standard rubrics.

| Criterion | 5/5 | 3/5 | 1/5 |
|-----------|-----|-----|-----|
| Correctness | All tests pass, no race conditions | Some failures | Broken |
| Error Handling | Comprehensive, production-ready | Adequate | None |
| Idioms | Exemplary for the language | Acceptable | Anti-patterns |
| Documentation | Thorough | Adequate | None |
| Testing | Comprehensive coverage | Basic | Minimal |

**Step 2: Score each solution independently**

Grade each agent's code on all five criteria. Score one agent completely before starting the other. Report facts and show command output rather than describing it — every claim must be backed by measurable data (tokens, test counts, quality scores).

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

For each bug found, record:

```markdown
### Bug: {description}
- Agent: {which agent}
- What happened: {behavior}
- Correct behavior: {expected}
- Production impact: {consequence}
- Test coverage: {did tests catch it? why not?}
```

"Tests pass" is necessary but not sufficient — production bugs often pass tests. Clear() returning nothing passes if no test checks the return value. TTL=0 bugs pass if no test uses zero TTL. Apply the domain-specific quality checklist rather than relying only on test pass rates, because tests can miss goroutine leaks, wrong semantics, and other production issues.

**Step 4: Calculate effective cost**

```
effective_cost = total_tokens * (1 + bug_count * 0.25)
```

An agent using 194k tokens with 0 bugs has better economics than one using 119k tokens with 5 bugs requiring fixes. The metric that matters is total cost to working, production-quality solution — not prompt size, because prompt is a one-time cost while reasoning tokens dominate sessions. Check quality scores before claiming token savings, since savings that come from cutting corners are not real savings.

**Gate**: Both solutions graded with evidence. Specific bugs documented with production impact. Effective cost calculated. Proceed only when gate passes.

### Phase 4: REPORT

**Goal**: Generate comparison report with evidence-backed verdict.

**Step 1: Generate comparison report**

Use the report template from `references/report-template.md`. Include:
- Executive summary with clear winner per metric
- Per-task results with metrics tables
- Token economics analysis (one-time prompt cost vs session cost)
- Specific bugs found and their production impact
- Verdict based on total evidence

Generate a side-by-side comparison report with a clear verdict.

**Step 2: Run comparison analysis**

```bash
# TODO: scripts/compare.py not yet implemented
# Manual alternative: compare benchmark outputs side-by-side
diff benchmark/{task-name}/full/ benchmark/{task-name}/compact/
```

**Step 3: Analyze token economics**

The key economic insight: agent prompts are a one-time cost per session. Everything after — reasoning, code generation, debugging, retries — costs tokens on every turn. When a micro agent produces correct code, it uses approximately the same total tokens. The savings appear only when it cuts corners.

| Pattern | Description |
|---------|-------------|
| Large agent, low churn | High initial cost, fewer retries, less debugging |
| Small agent, high churn | Low initial cost, more retries, more debugging |

Our data showed a 57-line agent used 69.5k tokens vs 69.6k for a 3,529-line agent on the same correct solution — prompt size alone does not determine cost.

**Step 4: State verdict with evidence**

The verdict must be backed by data — back the verdict with quality and cost data. Include:
- Which agent won on simple tasks (expected: equivalent)
- Which agent won on complex tasks (expected: full agent)
- Total session cost comparison
- Effective cost comparison (with bug penalty)
- Clear recommendation for when to use each variant

See `references/methodology.md` for the complete testing methodology with December 2024 data.

**Step 5: Clean up**

Remove temporary benchmark files and debug outputs. Keep only the comparison report and generated code.

**Gate**: Report generated with all metrics. Verdict stated with evidence. Report saved to benchmark directory.

### Optional Extensions

These are off by default. Enable explicitly when needed:
- **Multiple Runs**: Run each benchmark 3x to account for variance
- **Blind Evaluation**: Hide agent identity during quality grading
- **Extended Benchmark Suite**: Run additional domain-specific tests
- **Historical Tracking**: Compare against previous benchmark runs

## Error Handling

### Error: "Agent Type Not Found"
Cause: Agent not registered or name misspelled
Solution: Verify agent file exists in agents/ directory. Restart Claude Code client to pick up new definitions.

### Error: "Tests Fail with Race Condition"
Cause: Concurrent code has data races
Solution: This is a real quality difference. Record as a finding in the grade. Record as a finding for the agent being tested.

### Error: "Different Test Counts Between Agents"
Cause: Agents wrote different test suites
Solution: Valid data point. Grade on test coverage and quality, not raw count. More tests is not always better.

### Error: "Timeout During Agent Execution"
Cause: Complex task taking too long or agent stuck in retry loop
Solution: Note the timeout and number of retries attempted. Record as incomplete with partial metrics. Increase timeout limit if warranted, but excessive retries are a quality signal — an agent that needs many retries is less efficient regardless of final outcome.

## References

- `${CLAUDE_SKILL_DIR}/references/methodology.md`: Complete testing methodology with December 2024 data
- `${CLAUDE_SKILL_DIR}/references/grading-rubric.md`: Detailed grading criteria and quality checklists
- `${CLAUDE_SKILL_DIR}/references/benchmark-tasks.md`: Standard benchmark task descriptions and prompts
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Comparison report template with all required sections
