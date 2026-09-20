# Wait and retry contracts

This reference carries the decisions that are easy to miss in production code.

| Shape | Required contract |
|---|---|
| Poll | monotonic deadline; bounded interval; return the successful value; timeout names the unmet condition |
| Retry | initial attempt plus explicit retry count; retryable exception/status allowlist; exponential delay with jitter and cap; re-raise the last failure |
| HTTP 429 | parse `Retry-After` when valid, otherwise use a bounded fallback; do not retry 400/401/403/404 by default |
| Health wait | all required checks must pass in the same observation; timeout reports the last status of each check |
| Circuit breaker | explicit closed/open/half-open transitions; failure threshold; recovery deadline; bounded half-open probes |

For HTTP work, 408/429/500/502/503/504 are common retry candidates, not universal permission. Repository/client semantics outrank this list.

Tests must use injected sleep/clock or mocks—never real elapsed delays—and assert attempts, delay progression/cap, permanent-error passthrough, timeout/exhaustion, and recovery transitions. A mocked sleep without asserting attempts can hide a retry loop that never ran.

Frequent failure signatures:

- fixed sleep before checking readiness: wasted time or race;
- `while True` without a deadline: hung CI/process;
- wall-clock elapsed time: NTP/clock adjustments extend or shorten waits;
- identical retry schedule across clients: thundering herd;
- broad exception retry: authentication and input errors consume quota;
- tight polling loop: CPU saturation;
- timeout reporting only “failed”: loss of the last observed state.
