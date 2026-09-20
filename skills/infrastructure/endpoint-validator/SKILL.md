---
name: endpoint-validator
promoted_to: deploy
description: "Execute the repository's deterministic HTTP endpoint contract and produce CI-compatible PASS/FAIL/SLOW results."
user-invocable: false
allowed-tools: [Bash, Read, Write, Glob, Edit]
routing:
  triggers: ["validate endpoints", "smoke test API", "health check endpoints", "test endpoint"]
  category: infrastructure
  not_for: "Daemon liveness or process uptime."
---

# Endpoint Validator

Discover `endpoints.json`, then `tests/endpoints.json`, then a user-supplied inline contract. Honor repository base-URL/env conventions. Configuration is:

```json
{"base_url":"http://localhost:8000","endpoints":[
  {"path":"/health","expect_status":200},
  {"path":"/api/users","expect_key":"data","timeout":10,"max_time":2.0}
]}
```

`path` is required. Defaults are GET, status 200, timeout 5 seconds. Optional fields are `expect_key` (top-level JSON key), `max_time` (SLOW threshold), `method`, and per-endpoint `headers`.

Expand environment references without printing secrets. Before executing POST/PUT/PATCH/DELETE against a non-local base URL, obtain explicit confirmation. Confirm the base is reachable, then test sequentially and record actual status, elapsed time, and contract checks.

Verdicts:

- FAIL on status mismatch, timeout/refusal, or invalid/missing JSON when `expect_key` is set.
- SLOW when `max_time` is exceeded; preserve the HTTP result separately.
- For non-local HTTPS, WARN (not FAIL) for missing HSTS, CSP, `X-Content-Type-Options`, or clickjacking protection. CSP `frame-ancestors` satisfies the latter; do not require HSTS over HTTP.

Print a compact per-path report and totals. Exit 1 if any endpoint fails, otherwise 0. Include command output and exit code as evidence; do not infer results.
