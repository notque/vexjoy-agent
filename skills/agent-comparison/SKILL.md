---
name: agent-comparison
description: |
  A/B test agent variants measuring quality and total session token cost
  across simple and complex benchmarks. Use when creating compact agent
  versions, validating agent changes, comparing internal vs external agents,
  or deciding between variants for production. Use for "compare agents",
  "A/B test", "benchmark agents", or "test agent efficiency". Do NOT use
  for evaluating single agents, testing skills, or optimizing prompts
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
---

# Agent Comparison Skill

## Operator Context

This skill operates as an operator for agent A/B testing workflows, configuring Claude's behavior for rigorous, evidence-based variant comparison. It implements the **Benchmark Pipeline** architectural pattern — prepare variants, run identical tasks, measure outcomes, report findings — with **Domain Intelligence** embedded in the comparison methodology.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Keep benchmark scripts simple. No speculative features or configurable frameworks that were not requested
- **Identical Task Prompts**: Both agents MUST receive the exact same task description, character-for-character
- **Isolated Execution**: Each agent runs in a separate session to avoid contamination
- **Test-Based Validation**: All generated code MUST pass the same test suite with `-race` flag
- **Evidence-Based Reporting**: Every claim backed by measurable data (tokens, test counts, quality scores)
- **Total Session Cost**: Measure total tokens to working solution, not just prompt size

### Default Behaviors (ON unless disabled)
- **Communication Style**: Report facts without self-congratulation. Show command output rather than describing it
- **Temporary File Cleanup**: Remove temporary benchmark files and debug outputs at completion. Keep only comparison report and generated code
- **Two-Tier Benchmarking**: Run both simple (algorithmic) and complex (production) tasks
- **Token Tracking**: Record input/output token counts per turn where visible
- **Quality Grading**: Score code on correctness, error handling, idioms, documentation, testing
- **Comparative Summary**: Generate side-by-side comparison report with clear verdict

### Optional Behaviors (OFF unless enabled)
- **Multiple Runs**: Run each benchmark 3x to account for variance
- **Blind Evaluation**: Hide agent identity during quality grading
- **Extended Benchmark Suite**: Run additional domain-specific tests
- **Historical Tracking**: Compare against previous benchmark runs

## What This Skill CAN Do
- Systematically compare agent variants through controlled benchmarks
- Measure total session token cost (prompt + reasoning + tools + retries)
- Grade code quality using domain-specific checklists
- Reveal quality differences invisible to simple metrics (prompt size, line count)
- Generate comparison reports with evidence-backed verdicts

## What This Skill CANNOT Do
- Compare agents without running identical tasks on both
- Declare a winner based on prompt size alone
- Skip quality grading and rely only on test pass rates
- Evaluate single agents in isolation (use quality-grading skill instead)
- Compare skills or prompts (this is for agent variants only)

---

## Instructions

### Phase 1: PREPARE

**Goal**: Create benchmark environment and validate both agent variants exist.

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
- Operator Context (Hardcoded/Default/Optional)
- Core patterns and principles
- Error handling philosophy

Remove or condense:
- Lengthy code examples (keep 1-2 representative per pattern)
- Verbose explanations (condense to bullet points)
- Redundant instructions and changelogs

Target: 10-15% of original size while keeping essential knowledge. Removing capability (error handling patterns, concurrency patterns) invalidates the comparison. Remove redundancy, not knowledge.

**Step 3: Validate compact variant structure**

```bash
# Verify YAML frontmatter
head -20 agents/{compact-agent}.md | grep -E "^(name|description):"

# Verify Operator Context preserved
grep -c "### Hardcoded Behaviors" agents/{compact-agent}.md

# Compare sizes
echo "Original: $(wc -l < agents/{original-agent}.md) lines"
echo "Compact:  $(wc -l < agents/{compact-agent}.md) lines"
```

**Step 4: Create benchmark directory and prepare prompts**

```bash
mkdir -p benchmark/{task-name}/{full,compact}
```

Write the task prompt ONCE, then copy it for both agents. NEVER customize prompts per agent.

**Gate**: Both agent variants exist with valid YAML frontmatter. Benchmark directories created. Identical task prompts written. Proceed only when gate passes.

### Phase 2: BENCHMARK

**Goal**: Run identical tasks on both agents, capturing all metrics.

**Step 1: Run simple task benchmark (2-3 tasks)**

Use algorithmic problems with clear specifications (e.g., Advent of Code Day 1-6). Both agents should perform identically on well-defined problems. Simple tasks establish a baseline — if an agent fails here, it has fundamental issues.

Spawn both agents in parallel using Task tool for fair timing:

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

Use production-style problems that require concurrency, error handling, edge case anticipation. These are where quality differences emerge. See `references/benchmark-tasks.md` for standard tasks.

Recommended complex tasks:
- **Worker Pool**: Rate limiting, graceful shutdown, panic recovery
- **LRU Cache with TTL**: Generics, background goroutines, zero-value semantics
- **HTTP Service**: Middleware chains, structured errors, health checks

**Step 3: Capture metrics for each run**

Record immediately after each agent completes. Do NOT wait until all runs finish.

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

Use `-count=1` to disable test caching. Race conditions are automatic quality failures — record them but do NOT fix them for the agent being tested.

**Gate**: Both agents completed all tasks. Metrics captured for every run. Test output saved. Proceed only when gate passes.

### Phase 3: GRADE

**Goal**: Score code quality beyond pass/fail using domain-specific checklists.

**Step 1: Create quality checklist BEFORE reviewing code**

Define criteria before seeing results to prevent bias. Do NOT invent criteria after seeing one agent's output. See `references/grading-rubric.md` for standard rubrics.

| Criterion | 5/5 | 3/5 | 1/5 |
|-----------|-----|-----|-----|
| Correctness | All tests pass, no race conditions | Some failures | Broken |
| Error Handling | Comprehensive, production-ready | Adequate | None |
| Idioms | Exemplary for the language | Acceptable | Anti-patterns |
| Documentation | Thorough | Adequate | None |
| Testing | Comprehensive coverage | Basic | Minimal |

**Step 2: Score each solution independently**

Grade each agent's code on all five criteria. Score one agent completely before starting the other.

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

"Tests pass" is necessary but not sufficient. Production bugs often pass tests — Clear() returning nothing passes if no test checks the return value. TTL=0 bugs pass if no test uses zero TTL.

**Step 4: Calculate effective cost**

```
effective_cost = total_tokens * (1 + bug_count * 0.25)
```

An agent using 194k tokens with 0 bugs has better economics than one using 119k tokens with 5 bugs requiring fixes. The metric that matters is total cost to working, production-quality solution.

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

**Step 2: Run comparison analysis**

```bash
# TODO: scripts/compare.py not yet implemented
# Manual alternative: compare benchmark outputs side-by-side
diff benchmark/{task-name}/full/ benchmark/{task-name}/compact/
```

**Step 3: Analyze token economics**

The key economic insight: agent prompts are a one-time cost per session. Everything after — reasoning, code generation, debugging, retries — costs tokens on every turn.

| Pattern | Description |
|---------|-------------|
| Large agent, low churn | High initial cost, fewer retries, less debugging |
| Small agent, high churn | Low initial cost, more retries, more debugging |

When a micro agent produces correct code, it uses approximately the same total tokens. The savings appear only when it cuts corners.

**Step 4: State verdict with evidence**

The verdict MUST be backed by data. Include:
- Which agent won on simple tasks (expected: equivalent)
- Which agent won on complex tasks (expected: full agent)
- Total session cost comparison
- Effective cost comparison (with bug penalty)
- Clear recommendation for when to use each variant

See `references/methodology.md` for the complete testing methodology with December 2024 data.

**Gate**: Report generated with all metrics. Verdict stated with evidence. Report saved to benchmark directory.

---

## Examples

### Example 1: Creating a Compact Agent
User says: "Create a compact version of golang-general-engineer and test it"
Actions:
1. Analyze original, create compact variant at 10-15% size (PREPARE)
2. Run simple task (Advent of Code) + complex task (Worker Pool) on both (BENCHMARK)
3. Score both with domain-specific checklist, calculate effective cost (GRADE)
4. Generate comparison report with verdict (REPORT)
Result: Data-driven recommendation on whether compact version is viable

### Example 2: Comparing Internal vs External Agent
User says: "Compare our Go agent against go-expert-0xfurai"
Actions:
1. Validate both agents exist, prepare identical task prompts (PREPARE)
2. Run two-tier benchmarks with token tracking (BENCHMARK)
3. Grade with production quality checklist, document all bugs (GRADE)
4. Report with token economics showing prompt cost vs session cost (REPORT)
Result: Evidence-based comparison showing true cost of each variant

---

## Error Handling

### Error: "Agent Type Not Found"
Cause: Agent not registered or name misspelled
Solution: Verify agent file exists in agents/ directory. Restart Claude Code client to pick up new definitions.

### Error: "Tests Fail with Race Condition"
Cause: Concurrent code has data races
Solution: This is a real quality difference. Record as a finding in the grade. Do NOT fix for the agent being tested.

### Error: "Different Test Counts Between Agents"
Cause: Agents wrote different test suites
Solution: Valid data point. Grade on test coverage and quality, not raw count. More tests is not always better.

### Error: "Timeout During Agent Execution"
Cause: Complex task taking too long or agent stuck in retry loop
Solution: Note the timeout and number of retries attempted. Record as incomplete with partial metrics. Increase timeout limit if warranted, but excessive retries are a quality signal — an agent that needs many retries is less efficient regardless of final outcome.

---

## Anti-Patterns

### Anti-Pattern 1: Comparing Only Prompt Size
**What it looks like**: "Compact agent is 90% smaller, therefore 90% more efficient"
**Why wrong**: Prompt is one-time cost. Session reasoning, retries, and debugging dominate total tokens. Our data showed a 57-line agent used 69.5k tokens vs 69.6k for a 3,529-line agent on the same correct solution.
**Do instead**: Measure total session tokens to working solution.

### Anti-Pattern 2: Different Task Prompts
**What it looks like**: Giving the full agent harder requirements than the compact agent
**Why wrong**: Creates unfair comparison. Different requirements produce different solutions, invalidating all measurements.
**Do instead**: Copy-paste identical prompts character-for-character. Verify before running.

### Anti-Pattern 3: Treating Test Failures as Equal Quality
**What it looks like**: "Both agents completed the task" when one has 12/12 tests and the other has 8/12
**Why wrong**: Bugs have real cost. False equivalence between producing code and producing working code.
**Do instead**: Grade quality rigorously. Calculate effective cost with bug penalty multiplier.

### Anti-Pattern 4: Single Benchmark Declaration
**What it looks like**: "Tested on one puzzle. Compact agent wins!"
**Why wrong**: Single data point is sensitive to task selection bias. Simple tasks mask differences in edge case handling. Cannot distinguish luck from systematic quality.
**Do instead**: Run two-tier benchmarking with 2-3 simple tasks and 1-2 complex tasks.

### Anti-Pattern 5: Removing Core Patterns to Create Compact Agent
**What it looks like**: Compact version removes error handling patterns, concurrency guidance, and testing requirements to reduce size
**Why wrong**: Creates unfair comparison. Compact agent is missing essential knowledge, guaranteeing quality degradation rather than testing if brevity is possible.
**Do instead**: Remove verbose examples and redundant explanations, not capability. Keep one representative example per pattern. Condense explanations to bullet points but retain key insights.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Compact agent saved 50% tokens" | Savings may come from cutting corners, not efficiency | Check quality scores before claiming savings |
| "Tests pass, agents are equal" | Tests can miss production bugs (goroutine leaks, wrong semantics) | Apply domain-specific quality checklist |
| "One benchmark is enough" | Single task is sensitive to selection bias | Run two-tier benchmarks (simple + complex) |
| "Prompt size determines cost" | Prompt is one-time; reasoning tokens dominate sessions | Measure total session cost to working solution |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/methodology.md`: Complete testing methodology with December 2024 data
- `${CLAUDE_SKILL_DIR}/references/grading-rubric.md`: Detailed grading criteria and quality checklists
- `${CLAUDE_SKILL_DIR}/references/benchmark-tasks.md`: Standard benchmark task descriptions and prompts
- `${CLAUDE_SKILL_DIR}/references/report-template.md`: Comparison report template with all required sections
