# Test Blind Spot Taxonomy

Structured categories of what high-coverage test suites commonly miss. Use this taxonomy to move testing from "did you write tests?" to "did you test the right things?"

## Category 1: Concurrency & Race Conditions

| Blind Spot | Example Scenario |
|------------|-----------------|
| Double-submit | Button clicked twice rapidly — two orders created |
| Concurrent mutations | Two requests modifying same resource simultaneously |
| Webhook replay | Same event delivered twice — duplicate side effects |
| Read-after-write inconsistency | Cache returns stale data immediately after update |
| Lock contention under load | Mutex held too long causes timeouts at scale |
| Goroutine / async task leak | Fire-and-forget task never completes, accumulates |

## Category 2: State & Data Integrity

| Blind Spot | Example Scenario |
|------------|-----------------|
| Cache invalidation | Update succeeds but cached copy served to next request |
| Partial transaction failure | Step 3 of 5 fails — what state are we left in? |
| Ordering assumptions | Events arrive out of order — handler assumes sequence |
| Idempotency | Same operation applied twice produces different results |
| State machine invalid transitions | Order goes from "shipped" back to "pending" |
| Orphaned references | Parent deleted but child records remain with dangling FK |

## Category 3: Boundary & Extreme Values

| Blind Spot | Example Scenario |
|------------|-----------------|
| Zero and negative values | Quantity: 0, price: -1, count: -999 |
| Integer overflow | MAX_INT + 1 wraps to negative |
| Empty inputs | Empty string, empty array, null, undefined, nil |
| Unicode edge cases | RTL text, emoji, zero-width characters, surrogate pairs |
| Huge payloads | 1MB JSON body, 10K element arrays, deeply nested objects |
| Date boundaries | Midnight, DST transitions, leap seconds, year 2038, Feb 29 |
| Floating point | 0.1 + 0.2 != 0.3, currency rounding errors |

## Category 4: Security Edge Cases

| Blind Spot | Example Scenario |
|------------|-----------------|
| XSS in user content | Markdown renderer executes injected script tags |
| IDOR | Accessing resource by incrementing ID in URL |
| Mass assignment | Extra fields in request body modify protected attributes |
| JWT edge cases | Algorithm confusion (none/HS256), expired but cached tokens |
| Path traversal | `../../etc/passwd` in file upload filename |
| SSRF | User-provided URL causes server to fetch internal resources |
| Rate limit bypass | Distributed requests from multiple IPs evade per-IP limits |

## Category 5: Integration & External Dependencies

| Blind Spot | Example Scenario |
|------------|-----------------|
| Timeout handling | Third-party API takes 30s — what happens? |
| Malformed responses | External service returns invalid JSON or wrong schema |
| Rate limiting (429) | API returns 429 — retry? backoff? fail? queue? |
| DNS resolution failure | Domain unreachable — is error surfaced or swallowed? |
| TLS issues | Certificate expired, hostname mismatch, self-signed cert |
| Partial success | Batch operation: 8 of 10 items succeed, 2 fail |
| Version skew | API v2 response consumed by client expecting v1 shape |

## Category 6: Error Recovery & Resilience

| Blind Spot | Example Scenario |
|------------|-----------------|
| Disk full during write | File write succeeds partially — corrupt data on disk |
| Connection pool exhausted | All DB connections in use — new requests hang or fail |
| Memory pressure | Large result set loaded into memory — OOM kill |
| Graceful shutdown | In-flight requests during SIGTERM — completed or dropped? |
| Retry storms | Failed retries trigger more retries — exponential load |
| Circuit breaker state | Breaker opens but never half-opens to test recovery |
| Crash recovery | Process restarts mid-operation — consistent state restored? |

## How to Use This Taxonomy

1. **During test planning**: For each feature, scan the 6 categories and ask "does this apply here?"
2. **During test review**: Score existing tests against relevant categories — which are covered, which are gaps?
3. **During TDD RED phase**: Before writing implementation, consider which blind spots should have failing tests
4. **Post-incident**: After a production bug, identify which taxonomy category it falls into and add tests for the entire category

Not every category applies to every feature. Apply judgment — a CLI tool doesn't need SSRF tests, and a batch processor doesn't need double-click protection.
