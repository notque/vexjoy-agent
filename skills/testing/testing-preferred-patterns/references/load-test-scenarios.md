# Load Test Scenario Reference

Structured taxonomy of load testing approaches. Use when generating test
scripts (k6, Artillery, Locust) or reviewing load test coverage.

## Scenario Types

### 1. Smoke Test
**Purpose**: Verify the system works at all under minimal load.
**Configuration**: 1-2 virtual users, 1-2 minutes.
**When to use**: After every deployment. Quick sanity check.

```
Duration: 1-2 minutes
Users: 1-2
Thresholds:
  - All requests succeed (error rate = 0%)
  - p95 response time < baseline + 50%
```

### 2. Load Test
**Purpose**: Verify the system handles expected production load.
**Configuration**: Target production user count, 10-15 minutes sustained.
**When to use**: Before releases. Baseline performance validation.

```
Duration: 10-15 minutes
Users: Expected production peak (from analytics)
Ramp-up: 30 seconds per 10% of target
Thresholds:
  - Error rate < 1%
  - p95 response time < SLO target
  - p99 response time < 3x SLO target
```

### 3. Stress Test
**Purpose**: Find the breaking point. How far past normal can we go?
**Configuration**: Ramp beyond expected load until failures appear.
**When to use**: Capacity planning. Finding bottlenecks.

```
Duration: 15-20 minutes
Users: Ramp from 0 to 200-300% of expected peak
Ramp-up: Gradual increase every 2 minutes
Watch for:
  - Error rate spike (which endpoint breaks first?)
  - Response time degradation curve (linear or exponential?)
  - Resource exhaustion (CPU, memory, connections, disk I/O)
```

### 4. Spike Test
**Purpose**: How does the system handle sudden traffic bursts?
**Configuration**: Normal load → instant jump to peak → back to normal.
**When to use**: Systems exposed to viral traffic, marketing campaigns, flash sales.

```
Duration: 10 minutes
Pattern: 2min normal → instant spike to 500% → hold 3min → drop to normal → 3min recovery
Watch for:
  - Recovery time after spike subsides
  - Error rate during spike
  - Queue depth behavior
  - Auto-scaling response time (if applicable)
```

### 5. Soak Test (Endurance)
**Purpose**: Find memory leaks, connection pool exhaustion, log disk fill.
**Configuration**: Normal load sustained for hours.
**When to use**: Before major releases. Detecting slow-burn issues.

```
Duration: 2-8 hours
Users: Expected production average (not peak)
Thresholds:
  - Memory usage doesn't trend upward over time
  - Response times don't degrade over time
  - Error rate stays flat
  - No file descriptor / connection pool exhaustion
```

### 6. Breakpoint Test
**Purpose**: Find exact capacity ceiling with precision.
**Configuration**: Slow, controlled ramp until SLO violation.
**When to use**: Capacity planning with specific numbers.

```
Duration: Until SLO breach
Users: Start at 50%, increase by 5% every 2 minutes
Record:
  - Exact user count where p95 exceeds SLO
  - Exact user count where error rate exceeds threshold
  - Resource utilization at breakpoint (CPU%, memory%, connections)
```

## Critical Endpoints to Test

For any web service, prioritize these in load tests:

| Priority | Endpoint Type | Why |
|----------|--------------|-----|
| 1 | Authentication (login/token refresh) | Gate to everything else. If auth breaks, nothing works. |
| 2 | Most-hit read endpoint | Highest traffic volume. Often the first to show degradation. |
| 3 | Write endpoints (create/update) | Database contention, lock conflicts surface here. |
| 4 | Search/query with filters | Complex queries degrade fastest under load. |
| 5 | File upload/download | I/O bound, different bottleneck profile than compute. |
| 6 | Webhook receivers | External systems don't respect your capacity limits. |

## Common Mistakes in Load Tests

| Mistake | Why It's Wrong | Fix |
|---------|---------------|-----|
| Testing from same machine as server | Network isn't tested, localhost is unrealistic | Use separate load generator machine or cloud service |
| Single endpoint only | Real traffic hits many endpoints concurrently | Create realistic user journey scenarios |
| No think time between requests | Real users pause between actions | Add 1-5 second think time between requests |
| Ignoring ramp-up | Instant full load triggers different failures than gradual | Always ramp up over 30-60 seconds minimum |
| Not checking server-side metrics | Client-side metrics miss server resource exhaustion | Monitor CPU, memory, DB connections, disk I/O during test |
| Testing against production | Risk of outage, data corruption | Use staging with production-like data volume |

## How to Use This Reference

1. **Start with smoke**: Every deployment gets a smoke test
2. **Baseline with load**: Establish normal performance baseline before optimizing
3. **Find limits with stress**: Know your breaking point before production tells you
4. **Test resilience with spike**: Validate auto-scaling and recovery
5. **Catch leaks with soak**: Run overnight before major releases
