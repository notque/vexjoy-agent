---
name: condition-based-waiting
description: |
  Condition-based polling and retry patterns: exponential backoff, health
  checks, rate limit recovery, circuit breakers. Use when replacing arbitrary
  sleeps with condition checks, implementing retry logic, waiting for service
  availability, or handling API rate limits. Use for "wait for", "poll until",
  "retry with backoff", "health check", or "rate limit". Do NOT use for async
  event-driven architectures, distributed locking, or real-time guarantees.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - "exponential backoff"
    - "health check polling"
    - "retry pattern"
    - "wait for"
    - "keep trying until"
    - "poll until ready"
    - "retry until success"
  category: process
---

# Condition-Based Waiting Skill

## Operator Context

This skill operates as an operator for wait and retry implementations, configuring Claude's behavior for robust condition-based polling. It implements the **Pattern Selection** architectural approach -- identify wait scenario, select pattern, implement with safety bounds, verify behavior.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before implementation
- **Over-Engineering Prevention**: Only implement the pattern directly needed. Don't add circuit breakers when simple retries suffice. Don't add health checks when a single poll works.
- **Always Include Timeout**: Every wait loop MUST have a maximum timeout to prevent infinite hangs
- **Always Include Max Retries**: Every retry loop MUST have a maximum retry count
- **Always Add Jitter**: Exponential backoff MUST include random jitter to prevent thundering herd
- **Never Busy Wait**: Minimum 10ms between polls for local operations, 100ms for external services
- **Descriptive Timeout Errors**: Timeout messages MUST include what was waited for and last observed state

### Default Behaviors (ON unless disabled)
- **Progress Reporting**: Report wait progress with timeout values and retry counts
- **Cleanup on Timeout**: Cancel pending operations when timeout expires
- **Logging on Failure**: Log each retry attempt with failure reason and attempt number
- **Related Pattern Check**: Search codebase for existing wait/retry patterns to maintain consistency
- **Minimum Poll Interval Enforcement**: Enforce floor on polling frequency based on target type
- **Monotonic Clock Usage**: Use `time.monotonic()` (not `time.time()`) for elapsed time to avoid clock drift
- **Error Classification**: Separate transient from permanent errors before implementing retries

### Optional Behaviors (OFF unless enabled)
- **Progress Callbacks**: Report progress during long waits via user-provided callback
- **Metrics Collection**: Track retry counts, wait times, and failure rates for monitoring
- **Fallback Values**: Return cached/default values when retries exhausted
- **Dead Letter Logging**: Record permanently failed operations for manual review

## What This Skill CAN Do
- Implement condition-based polling with bounded timeouts
- Add exponential backoff with jitter to retry logic
- Handle API rate limits with Retry-After header support
- Wait for services to become healthy (TCP, HTTP, command)
- Implement circuit breaker patterns for cascade failure prevention
- Provide both Python and Bash implementations

## What This Skill CANNOT Do
- Fix underlying service issues (only handles transient failures)
- Guarantee eventual success (some operations permanently fail)
- Replace proper async/await patterns for event-driven code
- Handle distributed coordination (use distributed locks instead)
- Provide real-time guarantees (polling has inherent latency)

---

## Quick Reference

| Pattern | Use When | Key Safety Bound |
|---------|----------|-----------------|
| Simple Poll | Wait for condition to become true | Timeout + min poll interval |
| Exponential Backoff | Retry with increasing delays | Max retries + jitter + delay cap |
| Rate Limit Recovery | API returns 429 | Retry-After header + default fallback |
| Health Check | Wait for service(s) to be ready | All-pass requirement + per-check status |
| Circuit Breaker | Prevent cascade failures | Failure threshold + recovery timeout |

---

## Instructions

### Phase 1: IDENTIFY WAIT PATTERN

**Goal**: Select the correct pattern for the use case.

```
Decision Tree:

1. Waiting for a condition to become true?
   YES -> Simple Polling (Phase 2)
   NO  -> Continue

2. Retrying a failing operation?
   YES -> Rate-limited (429)?
         YES -> Rate Limit Recovery (Phase 4)
         NO  -> Exponential Backoff (Phase 3)
   NO  -> Continue

3. Waiting for a service to start?
   YES -> Health Check Waiting (Phase 5)
   NO  -> Continue

4. Service frequently failing, need fast-fail?
   YES -> Circuit Breaker (Phase 6)
   NO  -> Simple Poll or Backoff
```

**Gate**: Pattern selected with rationale. Proceed only when gate passes.

### Phase 2: SIMPLE POLLING

**Goal**: Wait for a condition to become true with bounded timeout.

**Step 1**: Define the condition function (returns truthy when ready)

**Step 2**: Set timeout and poll interval
- Local operations: 10-100ms poll interval, 30s timeout
- External services: 1-5s poll interval, 120s timeout

**Step 3**: Implement with safety bounds

```python
# Core pattern (full implementation in references/implementation-patterns.md)
start = time.monotonic()
deadline = start + timeout_seconds
while time.monotonic() < deadline:
    result = condition()
    if result:
        return result
    time.sleep(poll_interval)
raise TimeoutError(f"Timeout waiting for: {description}")
```

**Step 4**: Test with both success and timeout scenarios

**Gate**: Polling works for success case AND raises TimeoutError appropriately. Proceed only when gate passes.

### Phase 3: EXPONENTIAL BACKOFF

**Goal**: Retry failing operations with increasing delays and jitter.

**Step 1**: Identify retryable vs non-retryable errors
- Retryable: 408, 429, 500, 502, 503, 504, network timeouts, connection refused
- Non-retryable: 400, 401, 403, 404, validation errors, auth failures

**Step 2**: Configure backoff parameters
- `max_retries`: 3-5 for APIs, 5-10 for infrastructure
- `initial_delay`: 0.5-2s
- `max_delay`: 30-60s
- `jitter_range`: 0.5 (adds +/-50% randomness)

**Step 3**: Implement with jitter (MANDATORY)

```python
# Core pattern (full implementation in references/implementation-patterns.md)
for attempt in range(max_retries + 1):
    try:
        return operation()
    except retryable_exceptions as e:
        if attempt >= max_retries:
            raise
        jitter = 1.0 + random.uniform(-0.5, 0.5)
        actual_delay = min(delay * jitter, max_delay)
        time.sleep(actual_delay)
        delay = min(delay * backoff_factor, max_delay)
```

**Step 4**: Verify retry behavior with forced failures

**Gate**: Backoff includes jitter, respects max_retries, only retries transient errors. Proceed only when gate passes.

### Phase 4: RATE LIMIT RECOVERY

**Goal**: Handle HTTP 429 responses using Retry-After headers.

**Step 1**: Detect 429 status code in response

**Step 2**: Parse `Retry-After` header (seconds or HTTP-date format)

**Step 3**: Wait the specified duration, then retry

**Step 4**: Fall back to default wait (60s) if header missing

See `references/implementation-patterns.md` for full `RateLimitedClient` class.

**Gate**: Honors Retry-After header when present, uses sensible default when absent. Proceed only when gate passes.

### Phase 5: HEALTH CHECK WAITING

**Goal**: Wait for services to become healthy before proceeding.

**Step 1**: Define health checks by type

| Type | Check | Example |
|------|-------|---------|
| TCP | Port accepting connections | `localhost:5432` |
| HTTP | Endpoint returns 2xx | `http://localhost:8080/health` |
| Command | Exit code 0 | `pgrep -f 'celery worker'` |

**Step 2**: Set appropriate timeouts (services often need 30-120s to start)

**Step 3**: Poll all checks, succeed only when ALL pass

**Step 4**: Report status of each check during waiting

See `references/implementation-patterns.md` for full `wait_for_healthy()` implementation.

**Gate**: All health checks pass within timeout. Status reported per-check. Proceed only when gate passes.

### Phase 6: CIRCUIT BREAKER

**Goal**: Prevent cascade failures by failing fast after repeated errors.

**Step 1**: Configure thresholds
- `failure_threshold`: Number of failures before opening (typically 5)
- `recovery_timeout`: Time before testing recovery (typically 30s)
- `half_open_max_calls`: Successful calls needed to close (typically 3)

**Step 2**: Implement state machine
- CLOSED: Normal operation, count failures
- OPEN: Reject immediately, wait for recovery timeout
- HALF_OPEN: Allow test calls, close on success streak

**Step 3**: Add fallback behavior for OPEN state

**Step 4**: Test all state transitions

```
CLOSED --(failure_threshold reached)--> OPEN
OPEN   --(recovery_timeout elapsed)---> HALF_OPEN
HALF_OPEN --(success streak)----------> CLOSED
HALF_OPEN --(any failure)-------------> OPEN
```

See `references/implementation-patterns.md` for full `CircuitBreaker` class.

**Gate**: All four state transitions work correctly. Fallback provides degraded service. Proceed only when gate passes.

---

## Examples

### Example 1: Flaky Test with sleep()
User says: "This test uses sleep(5) and sometimes fails in CI"
Actions:
1. Identify as Simple Polling pattern (Phase 1)
2. Define condition: what the test is actually waiting for (Phase 2, Step 1)
3. Replace `sleep(5)` with `wait_for(condition, description, timeout=30)` (Phase 2, Step 3)
4. Run test 3 times to verify reliability (Phase 2, Step 4)
5. Verify timeout path: force condition to never be true, confirm TimeoutError
Result: Deterministic test that adapts to execution speed

### Example 2: API Integration with Rate Limits
User says: "Our batch job hits 429 errors from the API"
Actions:
1. Identify as Rate Limit Recovery + Exponential Backoff (Phase 1)
2. Classify errors: 429 is retryable, 400/401/404 are not (Phase 3, Step 1)
3. Add Retry-After header parsing with 60s default fallback (Phase 4)
4. Add exponential backoff with jitter for non-429 transient errors (Phase 3, Step 3)
5. Test: normal flow, 429 handling, exhausted retries, non-retryable errors
Result: Resilient API client that respects rate limits

### Example 3: Service Startup in Docker Compose
User says: "App crashes because it starts before the database is ready"
Actions:
1. Identify as Health Check Waiting (Phase 1)
2. Define checks: TCP on postgres:5432, HTTP on api:8080/health (Phase 5, Step 1)
3. Set 120s timeout with 2s poll interval (Phase 5, Step 2)
4. Implement wait_for_healthy() with all-pass requirement (Phase 5, Step 3)
5. Verify: services start within timeout, timeout fires when service is down
Result: Reliable startup ordering without arbitrary sleep()

---

## Error Handling

### Error: "Timeout expired before condition met"
Cause: Condition never became true within timeout window
Solution:
1. Verify condition function logic is correct
2. Increase timeout if operation legitimately needs more time
3. Add logging inside condition to observe state changes
4. Check for deadlocks or blocked resources

### Error: "All retries exhausted"
Cause: Operation failed on every attempt including retries
Solution:
1. Distinguish transient from permanent errors in retryable_exceptions
2. Verify external service is actually reachable
3. Check if authentication/configuration is correct
4. Increase max_retries only if error is genuinely transient

### Error: "Circuit breaker open"
Cause: Failure threshold exceeded, circuit rejecting calls
Solution:
1. Investigate why underlying service is failing
2. Implement fallback behavior for CircuitOpenError
3. Wait for recovery_timeout to elapse before testing
4. Consider adjusting failure_threshold for known-flaky services

---

## Anti-Patterns

### Anti-Pattern 1: Arbitrary Sleep Values
**What it looks like**: `time.sleep(5)` then check result
**Why wrong**: Works on fast machines, fails under load. Wastes time when fast, races when slow.
**Do instead**: `wait_for(condition, description, timeout=30)`

### Anti-Pattern 2: No Maximum Timeout
**What it looks like**: `while not condition(): time.sleep(0.1)` with no deadline
**Why wrong**: Hangs indefinitely if condition never met. Blocks CI pipelines forever.
**Do instead**: Always set a deadline with `time.monotonic() + timeout`

### Anti-Pattern 3: Backoff Without Jitter
**What it looks like**: `delay *= 2` with exact exponential growth
**Why wrong**: Thundering herd -- all clients retry simultaneously, amplifying load spikes
**Do instead**: `delay * random.uniform(0.5, 1.5)` to spread retries

### Anti-Pattern 4: Retrying Non-Retryable Errors
**What it looks like**: `except Exception: retry()` catching everything
**Why wrong**: 400/401/404 will never succeed on retry. Wastes time and quota.
**Do instead**: Only retry transient errors (408, 429, 500, 502, 503, 504)

### Anti-Pattern 5: Busy Waiting
**What it looks like**: `while not ready: pass` or polling every 1ms
**Why wrong**: Burns CPU, causes thermal throttling, starves other processes
**Do instead**: Minimum 10ms for local ops, 100ms+ for external services, 1-5s for network

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "sleep(5) is long enough" | Timing assumptions break under load | Replace with condition-based polling |
| "Jitter isn't necessary for small scale" | Scale changes; thundering herd hits early | Always add jitter to backoff |
| "No need for timeout, it always succeeds" | Always ≠ will always | Add timeout with descriptive error |
| "Retry everything, it's safer" | Retrying permanent errors wastes resources | Classify retryable vs non-retryable |

### Recommended Poll Intervals

| Target Type | Min Interval | Typical Interval | Example |
|-------------|-------------|-----------------|---------|
| In-process state | 10ms | 50-100ms | Flag, queue, state machine |
| Local file/socket | 100ms | 500ms | File exists, port open |
| Local service | 500ms | 1-2s | Database, cache |
| Remote API | 1s | 5-10s | HTTP endpoint, cloud service |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/implementation-patterns.md`: Complete Python/Bash implementations for all patterns
