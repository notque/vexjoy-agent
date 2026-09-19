---
name: endpoint-validator
promoted_to: deploy
description: "Deterministic API endpoint validation with pass/fail reporting."
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Edit
routing:
  triggers:
    - "validate endpoints"
    - "smoke test API"
    - "health check endpoints"
    - "test endpoint"
    - "check API"
    - "smoke test"
  category: infrastructure
  not_for: "process/service uptime or daemon liveness (use service-health-check); only HTTP/API endpoint request validation"
  pairs_with:
    - assessment
    - testing
---

# Endpoint Validator Skill

Deterministic HTTP endpoint validation: discover config, test each endpoint
against expectations, report pass/fail with CI-compatible exit codes.

## Deep References

Load on demand when the signal matches.

| Signal | Reference | Content |
|--------|-----------|---------|
| Security header WARNs, HSTS/CSP/X-Frame | `references/security-headers.md` | Header checks, required values, remediation |
| Config errors, hardcoded IPs, timeouts | `references/endpoint-config-preferred-patterns.md` | Configuration failure modes and fixes |
| 401/403 failures, auth patterns | `references/auth-endpoint-patterns.md` | Bearer, API-key, cookie auth validation |

## Instructions

### Phase 1: DISCOVER

Read repository CLAUDE.md for base URL conventions or env var names.

Search for endpoint config in order: `endpoints.json` in project root,
`tests/endpoints.json`, inline specification from user. Prefer version-controlled
config over ad-hoc lists.

Config shape:

```json
{
  "base_url": "http://localhost:8000",
  "endpoints": [
    {"path": "/health", "expect_status": 200},
    {"path": "/api/v1/users", "expect_key": "data", "timeout": 10},
    {"path": "/api/v1/search?q=test", "max_time": 2.0}
  ]
}
```

Endpoint fields: `path` (required), `expect_status` (default 200),
`expect_key` (top-level JSON key), `timeout` (default 5s), `max_time` (SLOW
threshold), `method` (default GET), `headers` (per-endpoint).

Rules:
- Warn before POST/PUT/DELETE against production base URLs.
- Use hostnames or `${ENV_VAR}` in `base_url`, not hardcoded IPs.
- Confirm base URL reachable before the full suite.

**Gate**: config parsed, base URL reachable, at least one endpoint defined.

### Phase 2: VALIDATE

**Execute, do not reason.** Run the request. Paste the exit code and output.

Test endpoints sequentially. For each:
1. Send request with configured method and timeout.
2. Check **status code** against `expect_status`. Mismatch -> FAIL.
3. If `expect_key` set, parse JSON and check key exists. Missing/invalid -> FAIL.
4. If `max_time` set and elapsed exceeds it -> SLOW.
5. On non-localhost URLs, check security headers (HSTS, CSP, X-Content-Type-Options, X-Frame-Options). Missing -> WARN (not FAIL). Skip HSTS on HTTP-only base URLs. Skip X-Frame-Options if CSP has `frame-ancestors`.

Failure handling: connection refused -> FAIL "Connection refused"; timeout -> FAIL "Timeout after Ns"; invalid JSON on `expect_key` -> FAIL "Invalid JSON response".

**Gate**: all endpoints tested, each has PASS/FAIL/SLOW verdict.

### Phase 3: REPORT

Format:

```
ENDPOINT VALIDATION REPORT
==========================
Base URL: http://localhost:8000
  /api/health                    200 OK      45ms
  /api/products                  500 FAIL   "Internal Server Error"
  /api/slow                      200 SLOW   3.2s > 2.0s threshold

SUMMARY: Passed 13/15 (86.7%), Failed 1, Slow 1
```

Exit 0 if all passed. Exit 1 if any failed.

## Error Handling

| Error | Cause | Fix |
|---|---|---|
| Base URL unreachable | Wrong port or service down | `ss -tlnp` to confirm port |
| All endpoints timeout | Wrong host or proxy issue | `curl -v` a single endpoint |
| JSON parse failure on `expect_key` | Non-JSON response (HTML/XML) | Remove `expect_key` or check Content-Type |
| FAIL on intentional 404 | Default expect_status is 200 | Set `"expect_status": 404` |
| 401 on auth endpoint | Missing/expired credentials | Add auth header; see `references/auth-endpoint-patterns.md` |

## CI Integration

```bash
# Pre-deployment gate with curl
jq -r '.endpoints[].path' endpoints.json | while read path; do
  curl -sf "http://localhost:8000$path" > /dev/null || { echo "FAIL: $path"; exit 1; }
done
```
