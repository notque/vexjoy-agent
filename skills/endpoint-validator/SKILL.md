---
name: endpoint-validator
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
  pairs_with:
    - service-health-check
    - e2e-testing
---

# Endpoint Validator Skill

Deterministic HTTP validation: Discover, Validate, Report. Tests endpoints against expectations, produces machine-readable results with pass/fail verdicts and CI-compatible exit codes.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Security header WARNs, HSTS/CSP/X-Frame issues | `security-headers.md` | Routes to the matching deep reference |
| Config errors, hardcoded IPs, timeout problems | `endpoint-config-preferred-patterns.md` | Routes to the matching deep reference |
| 401/403 failures, Bearer/API-key/cookie auth | `auth-endpoint-patterns.md` | Routes to the matching deep reference |

## Instructions

### Phase 1: DISCOVER

**Goal**: Locate or receive endpoint definitions before making requests.

**Step 1: Read repository CLAUDE.md**

Check for base URL conventions, environment variable names, or endpoint paths.

**Step 2: Search for endpoint configuration**

Priority order:
1. `endpoints.json` in project root
2. `tests/endpoints.json`
3. Inline specification from user or calling agent

Prefer config files in version control over ad-hoc lists.

**Step 3: Parse and validate configuration**

Must contain `base_url` and at least one endpoint:

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

Supported fields:
- `path` (required): URL path appended to base_url
- `expect_status` (default: 200): Expected HTTP status code
- `expect_key` (optional): Top-level JSON key that must exist. Full JSON schema validation is out of scope.
- `timeout` (default: 5): Request timeout in seconds
- `max_time` (optional): Fail if response exceeds this threshold
- `method` (optional): HTTP method, default GET. POST/PUT/DELETE require explicit config with request body.
- `headers` (optional): Per-endpoint headers (Accept, Content-Type, Authorization)

If `base_url` is production and config includes POST/PUT/DELETE, warn before proceeding. Use staging for write operations; reserve production for GET-only health checks.

Use hostnames or environment variables in `base_url`, not hardcoded IPs. `http://192.168.1.42:8000` breaks on every other machine.

**Step 4: Confirm base URL is reachable**

Single request to `base_url` before running full suite. If unreachable, report immediately.

**Gate**: Configuration parsed, base URL reachable, at least one endpoint defined.

### Phase 2: VALIDATE

> **Opus 4.7 override:** Run the command. Do not reason about whether it would pass. Execute the check, paste the exit code and output. A verdict without observed tool output is a guess.

**Goal**: Test each endpoint against expected criteria and collect structured results.

**Step 1: Execute requests sequentially**

One at a time for predictable, reproducible output. Per endpoint:
1. Construct full URL from `base_url` + `path`
2. Send request with configured method and timeout
3. Record status code, response time, body
4. Display each result as it completes

This is contract validation, not load testing.

**Step 2: Evaluate against expectations**

Per response, check in order:
1. **Status code**: Match `expect_status`? If not, FAIL.
2. **JSON key**: If `expect_key` set, parse JSON, check key exists. If missing or invalid JSON, FAIL.
3. **Response time**: If `max_time` set and exceeded, SLOW.
4. **Security headers**: Check for common headers, report missing as WARN (not FAIL):
   - `Strict-Transport-Security` (HTTPS endpoints)
   - `Content-Security-Policy`
   - `X-Content-Type-Options` (should be `nosniff`)
   - `X-Frame-Options` (or CSP `frame-ancestors`)

Skip security header checks for localhost/127.0.0.1. Only check non-localhost unless explicitly configured.

**Step 3: Handle failures gracefully**

- Connection refused: FAIL with "Connection refused"
- Timeout: FAIL with "Timeout after Ns"
- Invalid JSON when `expect_key` set: FAIL with "Invalid JSON response"
- Unexpected exception: FAIL with exception message

**Gate**: All endpoints tested. Every result has PASS, FAIL, or SLOW verdict.

### Phase 3: REPORT

**Goal**: Structured, machine-readable output with summary statistics.

**Step 1: Format individual results**

```
ENDPOINT VALIDATION REPORT
==========================
Base URL: http://localhost:8000
Endpoints: 15 tested

RESULTS:
  /api/health                    200 OK      45ms
  /api/users                     200 OK     123ms
  /api/products                  500 FAIL   "Internal Server Error"
  /api/slow                      200 SLOW   3.2s > 2.0s threshold

SECURITY HEADERS (non-localhost only):
  /api/health                    WARN  Missing: Content-Security-Policy, X-Frame-Options
  /api/users                     OK    All security headers present
  /api/products                  SKIP  (endpoint failed)
```

**Step 2: Produce summary**

```
SUMMARY:
  Passed: 13/15 (86.7%)
  Failed: 1 (status error)
  Slow: 1 (exceeded threshold)
  Security header warnings: 3 endpoints missing headers
```

**Step 3: Set exit code**

- Exit 0 if all passed (SLOW counts as pass unless `max_time` was set)
- Exit 1 if any failed

**Gate**: Report printed, exit code set.

### Examples

#### Example 1: Pre-Deployment Health Check
User: "Validate all endpoints before we deploy"
1. Find `endpoints.json` (DISCOVER)
2. Test each endpoint (VALIDATE)
3. Print report, exit 0 if all pass (REPORT)

#### Example 2: Smoke Test After Migration
User: "Check if the API still works after the database migration"
1. Read config, confirm base URL reachable (DISCOVER)
2. Hit each endpoint, check status and expected keys (VALIDATE)
3. Surface failures with error details (REPORT)

---

## Error Handling

### Error: "Base URL Unreachable"
Cause: Service not running, wrong port, or network issue
Solution:
1. Verify service is running (`ps aux`, `docker ps`)
2. Confirm port matches config (`ss -tlnp`)
3. Check firewall rules or container networking

### Error: "All Endpoints Timeout"
Cause: Service overwhelmed, wrong host, or proxy misconfiguration
Solution:
1. Test manually with `curl -v`
2. Increase timeout values if service is legitimately slow
3. Check for reverse proxy or load balancer intercepting requests

### Error: "JSON Parse Failure on expect_key Check"
Cause: Endpoint returns HTML, XML, or empty body instead of JSON
Solution:
1. Verify endpoint returns JSON (check Content-Type header)
2. Remove `expect_key` if endpoint legitimately returns non-JSON
3. Check if authentication is required (HTML login page returned)

---

## Reference Loading

| Task Type | Load This Reference |
|-----------|-------------------|
| Security header WARNs, HSTS/CSP/X-Frame issues | `references/security-headers.md` |
| Config errors, hardcoded IPs, timeout problems | `references/endpoint-config-preferred-patterns.md` |
| 401/403 failures, Bearer/API-key/cookie auth | `references/auth-endpoint-patterns.md` |

---

## References

### CI/CD Integration

```yaml
# GitHub Actions example
# TODO: scripts/validate_endpoints.py not yet implemented
# Manual alternative: use curl to validate endpoints from endpoints.json
- name: Validate API endpoints
  run: |
    jq -r '.endpoints[].path' endpoints.json | while read path; do
      curl -sf "$BASE_URL$path" > /dev/null && echo "PASS: $path" || echo "FAIL: $path"
    done
```

```bash
# Pre-deployment gate
# TODO: scripts/validate_endpoints.py not yet implemented
# Manual alternative: iterate endpoints.json with curl
jq -r '.endpoints[].path' endpoints.json | while read path; do
  curl -sf "http://localhost:8000$path" > /dev/null || { echo "FAIL: $path"; exit 1; }
done
```
