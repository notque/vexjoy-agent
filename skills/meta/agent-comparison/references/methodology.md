# Agent Comparison Methodology

## The Key Insight

Agent prompt tokens are a **one-time cost** per session. Everything after that - reasoning, code generation, debugging, retries - costs tokens on **every turn**.

Our actual testing revealed something more specific:

**When micro agents produced correct code, they used the same tokens as the full agent. The apparent savings came from tasks where they cut corners.**

## Actual Testing We Performed (December 2024)

### Agents Tested

| Agent | Lines | Source |
|-------|-------|--------|
| golang-general-engineer (Full) | 3,529 | Local, with detailed patterns |
| golang-general-engineer-compact | 328 | Minimal version (10% of full) |
| go-expert-0xfurai | 57 | External micro-agent (548 GitHub stars) |
| golang-pro-voltagent | 46 | External micro-agent |

### Tasks Executed

1. **LRU Cache with TTL** - Complex logic with edge cases
2. **Worker Pool** - Concurrent processing with graceful shutdown
3. **HTTP Service** - Standard patterns (middleware, routing, logging)

### How We Ran the Tests

#### Step 1: Create Benchmark Directory Structure

```bash
mkdir -p benchmark/cache/{full,compact,0xfurai,voltagent}
mkdir -p benchmark/workerpool/{full,compact,0xfurai,voltagent}
mkdir -p benchmark/httpservice/{full,compact,0xfurai,voltagent}
```

#### Step 2: Run Each Agent with Identical Prompts

We used the Task tool to spawn each agent with the exact same prompt. **Critical: No hints about patterns or edge cases.**

Example prompt for cache task:

```
Task(
  prompt="""
  Build a generic LRU cache with TTL support in Go.

  Requirements:
  - Generic types for key and value
  - Configurable max size
  - Per-item TTL support
  - Background cleanup goroutine
  - Thread-safe operations
  - Methods: Get, Set, Delete, Clear, Len, Stats

  Include comprehensive tests with race detection.

  Save to: benchmark/cache/{agent-name}/
  """,
  subagent_type="{agent-type}"
)
```

**Important**: We ran all 4 agents in parallel using multiple Task tool calls in a single message. This ensures fair timing comparison.

#### Step 3: Capture Token Counts

After each agent completed, we recorded the session token count from Claude Code's output. Example format:

```
Cache task tokens:
- Full: 57.4k
- Compact: 28.9k
- 0xfurai: 29.3k
- Voltagent: 25.7k
```

#### Step 4: Run Tests with Race Detector

```bash
cd benchmark/cache/full && go test -race -v
cd benchmark/cache/compact && go test -race -v
cd benchmark/cache/0xfurai && go test -race -v
cd benchmark/cache/voltagent && go test -race -v
```

**All agents must pass with `-race` flag.** Race conditions are automatic failures.

#### Step 5: Apply Quality Checklist

For the cache task, we used a 7-point production checklist:

| Criterion | Description | Why It Matters |
|-----------|-------------|----------------|
| WaitGroup for cleanup goroutine | Background goroutine tracked properly | Prevents goroutine leaks on shutdown |
| Stop() waits for completion | Graceful shutdown waits for cleanup | Prevents resource leaks |
| Clear() returns count | Returns number of items cleared | Enables metrics and observability |
| Delete() returns bool | Returns whether item existed | Enables conditional logic |
| Metrics struct | Exposes hits, misses, evictions | Production observability |
| TTL=0 means no expiration | Zero TTL = infinite lifetime | Correct semantic behavior |
| isExpired checks zero time | Handles "no expiration" case | Prevents false expirations |

**Score each agent**: Check each criterion, count passes. 7/7 = bug-free.

#### Step 6: Document Specific Bugs Found

For each bug, document:
- What the agent did wrong
- What the correct behavior should be
- How it would manifest in production

Example from our testing:

**The "Forever" Bug**
- What: 2/4 agents treated TTL=0 as "expire immediately"
- Correct: TTL=0 should mean "never expire"
- Production impact: Items vanish immediately on insert

**The Observability Bug**
- What: 3/4 agents returned nothing from Clear()
- Correct: Should return count of items cleared
- Production impact: Impossible to track cache evictions in metrics

**The Leak Bug**
- What: 3/4 agents didn't use WaitGroup for background goroutine
- Correct: Track goroutine lifecycle with WaitGroup
- Production impact: Goroutine leak on shutdown, graceful shutdown hangs

### Actual Results from Our Testing

#### Per-Task Token Usage

| Task | Full | Compact | 0xfurai | Voltagent |
|------|------|---------|---------|-----------|
| LRU Cache | 57.4k | 28.9k | 29.3k | 25.7k |
| Worker Pool | 69.6k | 63.8k | 69.5k | 62.9k |
| HTTP Service | 67.7k | 28.7k | 39.9k | 30.6k |
| **Total** | **194.7k** | 121.4k | 138.7k | **119.2k** |

#### Quality Scores (Cache Task)

| Agent | Score | Bugs |
|-------|-------|------|
| Full | 7/7 | 0 |
| 0xfurai | 4/7 | 3 |
| Voltagent | 4/7 | 3 |
| Compact | 2/7 | 5 |

#### Key Finding: Worker Pool Tokens

This is the critical data point. On Worker Pool, where **all agents produced correct code**:

| Agent | Tokens | vs Full |
|-------|--------|---------|
| Full | 69.6k | baseline |
| 0xfurai | 69.5k | -0.1% |
| Compact | 63.8k | -8% |
| Voltagent | 62.9k | -10% |

The 57-line micro agent (0xfurai) used 69.5k tokens. The 3,529-line full agent used 69.6k tokens.

**The difference: 100 tokens. 0.1%.**

When the micro agent had to actually solve the problem correctly, it used the same tokens as the full agent.

## Methodology Principles

### 1. Identical Prompts

Copy-paste the exact same task description. No hints, no pattern suggestions, no edge case warnings.

```
# BAD - gives hints
"Build a cache. Remember to handle the TTL=0 case as 'no expiration'."

# GOOD - no hints
"Build a cache with per-item TTL support."
```

### 2. Parallel Execution

Run all agents in parallel to ensure fair comparison. If you run sequentially, caching effects or system load changes can skew results.

### 3. Test-Based + Manual Review

"Tests pass" is necessary but not sufficient. Production bugs often pass tests:

- Clear() returning nothing passes tests that don't check return value
- TTL=0 bug passes if no test uses TTL=0
- Goroutine leaks pass short-running tests

**Always manually review for production patterns.**

### 4. Quality Checklists

Create domain-specific checklists before testing. Don't invent criteria after seeing results.

For concurrent Go code:
- [ ] WaitGroups for goroutine lifecycle
- [ ] Context cancellation propagation
- [ ] Mutex scope minimization
- [ ] No defer in hot loops
- [ ] Graceful shutdown with timeout

For caches:
- [ ] Zero-value semantics documented
- [ ] Clear returns count
- [ ] Delete returns existence
- [ ] Metrics exposed
- [ ] Background goroutine tracked

### 5. Document Everything

Record:
- Exact prompts used
- Token counts per task per agent
- Test pass/fail with `-race`
- Quality checklist scores
- Specific bugs found with production impact

## When to Run Agent Comparisons

### Run when:
- Creating a compact version of an existing agent
- Validating that agent changes don't degrade quality
- Comparing internal agents to external alternatives
- Deciding which agent to use for production tasks

### Skip Conditions
- The task is trivial (use any agent)
- You only care about simple tasks (compact agents are fine)
- You're prototyping (use cheapest agent)

## Future Testing Directions

- Test with prompt caching enabled (changes economics)
- Test with different Claude models (Sonnet vs Opus)
- Test with multi-turn tasks (not single-shot)
- Test debugging scenarios (given broken code, fix it)
- Test refactoring tasks (given working code, improve it)
