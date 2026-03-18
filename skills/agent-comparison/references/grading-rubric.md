# Agent Comparison Grading Rubric

## Quality Scoring (5-Criteria Rubric)

Score each agent's output independently on each criterion.

### Criterion 1: Correctness (1-5)

| Score | Description |
|-------|-------------|
| 5/5 | All tests pass, no race conditions, handles all edge cases |
| 4/5 | All tests pass, minor edge cases missed |
| 3/5 | Some test failures, core functionality works |
| 2/5 | Major test failures, significant bugs |
| 1/5 | Broken, does not compile or run |

### Criterion 2: Error Handling (1-5)

| Score | Description |
|-------|-------------|
| 5/5 | Comprehensive: all error paths handled, meaningful messages, recovery where possible |
| 4/5 | Good: most error paths handled, reasonable messages |
| 3/5 | Adequate: happy path errors handled, some gaps |
| 2/5 | Minimal: only obvious errors handled |
| 1/5 | None: errors ignored or panicked |

### Criterion 3: Language Idioms (1-5)

| Score | Description |
|-------|-------------|
| 5/5 | Exemplary: idiomatic patterns, proper naming, clean structure |
| 4/5 | Standard: follows conventions, occasional non-idiomatic choices |
| 3/5 | Acceptable: generally readable, some non-idiomatic patterns |
| 2/5 | Non-idiomatic: transliterated from another language style |
| 1/5 | Anti-patterns: fundamentally wrong patterns for the language |

### Criterion 4: Documentation (1-5)

| Score | Description |
|-------|-------------|
| 5/5 | Thorough: package docs, function docs, complex logic explained |
| 4/5 | Good: key functions documented, types explained |
| 3/5 | Adequate: some comments, exported items documented |
| 2/5 | Sparse: minimal or misleading comments |
| 1/5 | None: no documentation at all |

### Criterion 5: Testing (1-5)

| Score | Description |
|-------|-------------|
| 5/5 | Comprehensive: table-driven, edge cases, race detection, error paths |
| 4/5 | Good: main paths tested, some edge cases |
| 3/5 | Basic: happy path tested, minimal edge cases |
| 2/5 | Minimal: one or two tests, no edge cases |
| 1/5 | None or broken: no tests or tests don't run |

## Score Card Template

```markdown
## {Agent Name} Solution - {Task Name}

| Criterion | Score | Notes |
|-----------|-------|-------|
| Correctness | X/5 | |
| Error Handling | X/5 | |
| Language Idioms | X/5 | |
| Documentation | X/5 | |
| Testing | X/5 | |
| **Total** | **X/25** | |

### Bugs Found
1. [Bug description] - Production impact: [impact]
2. [Bug description] - Production impact: [impact]
```

## Domain-Specific Quality Checklists

Define these BEFORE reviewing code to prevent bias.

### Concurrent Go Code Checklist

- [ ] WaitGroups for goroutine lifecycle management
- [ ] Context cancellation propagation
- [ ] Mutex scope minimization (hold lock for shortest time)
- [ ] No defer in hot loops
- [ ] Graceful shutdown with timeout
- [ ] Channel direction annotations on function parameters
- [ ] No goroutine leaks (all goroutines have exit conditions)

### Cache Implementation Checklist

- [ ] Zero-value semantics documented (TTL=0 means no expiration)
- [ ] Clear() returns count of items removed
- [ ] Delete() returns whether item existed
- [ ] Metrics exposed (hits, misses, evictions)
- [ ] Background goroutine tracked with WaitGroup
- [ ] Thread-safe operations verified with `-race`
- [ ] isExpired handles zero time correctly

### HTTP Service Checklist

- [ ] Middleware chain properly ordered
- [ ] Request timeout handling
- [ ] Graceful shutdown implementation
- [ ] Error responses use consistent format
- [ ] Health check endpoint
- [ ] Request ID propagation
- [ ] Structured logging

### Worker Pool Checklist

- [ ] Configurable worker count and queue size
- [ ] Backpressure handling (blocking or error)
- [ ] Graceful shutdown with in-flight job completion
- [ ] Panic recovery in workers
- [ ] Metrics (processed, failed, queue depth)
- [ ] Context cancellation support
- [ ] No goroutine leaks on shutdown

## Effective Cost Calculation

```
effective_cost = total_session_tokens * (1 + bug_count * penalty_multiplier)
```

Default penalty multiplier: 0.25 per bug

| Scenario | Tokens | Bugs | Effective Cost |
|----------|--------|------|----------------|
| Full agent | 194k | 0 | 194k |
| Compact agent | 119k | 5 | 119k * 1 + (5 * 0.25) = 267.75k |

The full agent has better economics despite higher raw token cost because bugs have real downstream cost: debugging time, human review, production risk.
