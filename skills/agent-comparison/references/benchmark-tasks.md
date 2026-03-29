# Standard Benchmark Tasks

## Task Selection Principles

1. **Two-tier structure**: Simple tasks (algorithmic) + complex tasks (production)
2. **Simple tasks** test baseline capability. Both agents should perform identically
3. **Complex tasks** reveal real differences in edge case handling and production patterns
4. **Identical prompts**: Copy-paste the exact same description for both agents. No hints

## Simple Task: Advent of Code

Use Day 1-6 of any year. These have:
- Clear input/output specification
- Testable with provided examples
- No ambiguity in requirements
- No domain-specific knowledge needed

### Example Prompt (AoC-style)

```
Solve this algorithm problem in Go.

Problem: Given a list of integers, find the two entries that sum to 2020
and return their product.

Input format: One integer per line
Example:
  1721
  979
  366
  299
  675
  1456

Expected output for example: 514579 (1721 * 299)

Requirements:
1. Create solution in main.go
2. Write comprehensive tests in main_test.go
3. Include the provided example as a test case
4. Handle edge cases appropriately

Save files to: benchmark/{task-name}/{agent-variant}/
```

## Complex Task: Worker Pool

Production-style concurrent processing. Reveals differences in:
- Goroutine lifecycle management
- Graceful shutdown patterns
- Error handling under concurrency
- Race condition prevention

### Prompt

```
Build a production-ready rate-limited worker pool in Go.

Requirements:
- Configurable number of workers
- Configurable queue size with backpressure options
- Token bucket rate limiting
- Graceful shutdown with timeout
- Context cancellation support
- Metrics (jobs processed, failed, queue depth)
- Health check endpoint data
- Panic recovery in workers

Include comprehensive tests covering:
- Basic job processing
- Rate limiting behavior
- Backpressure (blocking vs error)
- Graceful shutdown
- Context cancellation
- Concurrent access safety (use -race flag)

Save to: benchmark/workerpool/{agent-variant}/
```

## Complex Task: LRU Cache with TTL

Tests generic programming, background goroutines, and semantic correctness. Known to expose bugs around zero-value handling.

### Prompt

```
Build a generic LRU cache with TTL support in Go.

Requirements:
- Generic types for key and value
- Configurable max size
- Per-item TTL support
- Background cleanup goroutine
- Thread-safe operations
- Methods: Get, Set, Delete, Clear, Len, Stats

Include comprehensive tests with race detection.

Save to: benchmark/cache/{agent-variant}/
```

### Known Bug Patterns (from December 2024 testing)

These bugs appeared in 2-3 out of 4 tested agents:

| Bug | Frequency | Production Impact |
|-----|-----------|-------------------|
| TTL=0 treated as "expire immediately" | 2/4 agents | Items vanish on insert |
| Clear() returns nothing | 3/4 agents | Cannot track cache evictions |
| No WaitGroup for background goroutine | 3/4 agents | Goroutine leak on shutdown |
| Delete() doesn't return existence | 2/4 agents | Cannot do conditional logic |

## Complex Task: HTTP Service

Tests standard patterns: middleware, routing, logging, error handling.

### Prompt

```
Build an HTTP service in Go with the following endpoints:

- POST /items - Create item
- GET /items/:id - Get item by ID
- GET /items - List items with pagination
- DELETE /items/:id - Delete item

Requirements:
- In-memory storage (no database)
- Request logging middleware
- Request ID middleware
- Graceful shutdown
- Health check endpoint at /health
- Structured JSON error responses
- Input validation

Include comprehensive tests for all endpoints and middleware.

Save to: benchmark/httpservice/{agent-variant}/
```

## Benchmark Directory Structure

```
benchmark/
  {task-name}/
    full/
      main.go
      main_test.go
      go.mod
    compact/
      main.go
      main_test.go
      go.mod
```

## Running Benchmarks

### Step 1: Create directories

```bash
mkdir -p benchmark/{task-name}/{full,compact}
```

### Step 2: Run agents in parallel

Use Task tool to spawn both agents simultaneously for fair timing:

```
Task(prompt="[task prompt]\nSave to: benchmark/{task}/full/", subagent_type="{full-agent}")
Task(prompt="[task prompt]\nSave to: benchmark/{task}/compact/", subagent_type="{compact-agent}")
```

### Step 3: Validate with race detection

```bash
cd benchmark/{task-name}/full && go test -race -v
cd benchmark/{task-name}/compact && go test -race -v
```

### Step 4: Run comparison analysis

```bash
# TODO: scripts/compare.py not yet implemented
# Manual alternative: compare outputs side-by-side using diff
diff benchmark/{task-name}/full/ benchmark/{task-name}/compact/
```

## Optimization Loop Task Format

The current optimization loop is for frontmatter-description and routing-trigger quality. It does not run full code-generation benchmarks. Use Phase 5 with trigger-rate eval tasks, then use Phases 1-4 for full agent benchmarking.

### Supported Task File Schemas

Flat list with optional split markers:

```json
{
  "tasks": [
    {
      "name": "go-testing-positive",
      "split": "train",
      "complexity": "complex",
      "query": "write table-driven tests for a Go parser with subtests and helpers",
      "should_trigger": true
    },
    {
      "name": "kubernetes-negative",
      "split": "test",
      "complexity": "complex",
      "query": "debug a kubernetes pod stuck in CrashLoopBackOff",
      "should_trigger": false
    }
  ]
}
```

Explicit top-level train/test sets:

```json
{
  "train": [
    {
      "name": "positive-1",
      "query": "write Go benchmarks and race tests for a worker pool",
      "should_trigger": true
    }
  ],
  "test": [
    {
      "name": "negative-1",
      "query": "design a PostgreSQL indexing strategy",
      "should_trigger": false
    }
  ]
}
```

### Required Fields

- `query`: the prompt used to test routing behavior
- `should_trigger`: expected boolean outcome for the target description

### Optional Fields

- `name`: human-readable label shown in reports
- `split`: `train` or `test` when using a flat `tasks` list
- `complexity`: used for stratified splitting when no explicit split is provided

### Split Strategy

- `train` tasks are used during each optimization iteration.
- `test` tasks are held out and checked every 5 iterations for Goodhart divergence.
- If no split markers are present, the loop performs a reproducible random split with seed `42`, stratified by `complexity`.

### Task Selection Principles for Optimization

1. Cover both positive and negative routing examples. A description that only improves recall while tanking precision is not an improvement.
2. Put at least one out-of-domain prompt in the held-out set. This catches overfitting where the description starts matching benchmark phrasing instead of the real scope.
3. Use realistic user wording, not only canonical trigger phrases. Optimization on synthetic wording alone produces brittle routing behavior.
