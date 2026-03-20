---
name: endpoint-validator
description: |
  Deterministic API endpoint validation with structured pass/fail reporting.
  Use when endpoints need smoke testing, health checks are required before
  deployment, or CI/CD pipelines need HTTP validation gates. Use for
  "validate endpoints", "check api health", "api smoke test", or
  "are endpoints working". Do NOT use for load testing, browser testing,
  full integration suites, or OAuth/complex authentication flows.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Edit
---

# Endpoint Validator Skill

## Operator Context

This skill operates as an operator for API endpoint validation workflows, configuring Claude's behavior for deterministic, structured health checking. It implements the **Discover, Validate, Report** pattern -- find endpoints, test each against expectations, produce machine-readable results with clear pass/fail verdicts.

### Hardcoded Behaviors (Always Apply)
- **Read-Only by Default**: Only makes GET requests unless explicitly configured otherwise
- **Timeout Safety**: Default 5-second timeout per request prevents hanging
- **Structured Output**: Always produces machine-parseable results with exit codes
- **No Data Mutation**: Never sends POST/PUT/DELETE without explicit user configuration
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before validation

### Default Behaviors (ON unless disabled)
- **Progress Display**: Show each endpoint result as it completes
- **Summary Statistics**: Pass/fail counts and percentages at end of run
- **Timing Information**: Response time in milliseconds for every endpoint
- **Threshold Enforcement**: Flag endpoints exceeding configured max_time
- **Sequential Execution**: Test endpoints one at a time for predictable output

### Optional Behaviors (OFF unless enabled)
- **POST/PUT/DELETE Testing**: Requires explicit method + body in configuration
- **Authentication Headers**: Bearer tokens or basic auth passed via config
- **Response Body Validation**: Deep JSON key checking beyond top-level
- **Custom Headers**: Additional headers per endpoint (e.g., Accept, Content-Type)
- **Parallel Requests**: Test multiple endpoints concurrently

## What This Skill CAN Do
- Validate HTTP GET endpoints for expected status codes
- Check JSON responses contain expected top-level keys
- Measure and report response times per endpoint
- Detect slow endpoints exceeding configured thresholds
- Produce CI/CD compatible exit codes (0 = all pass, 1 = any fail)
- Read endpoint definitions from JSON config files

## What This Skill CANNOT Do
- Perform load or stress testing (single request per endpoint only)
- Execute browser-based or JavaScript-rendered tests
- Handle OAuth flows or multi-step authentication chains
- Validate full JSON schemas (top-level key presence only)
- Test WebSocket or gRPC endpoints (HTTP only)

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Locate or receive endpoint definitions before making any requests.

**Step 1: Search for endpoint configuration**

Look for definitions in priority order:
1. `endpoints.json` in project root
2. `tests/endpoints.json`
3. Inline specification provided by user or calling agent

**Step 2: Parse and validate configuration**

Configuration must contain `base_url` and at least one endpoint:

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

Each endpoint supports these fields:
- `path` (required): URL path appended to base_url
- `expect_status` (default: 200): Expected HTTP status code
- `expect_key` (optional): Top-level JSON key that must exist in response
- `timeout` (default: 5): Request timeout in seconds
- `max_time` (optional): Fail if response exceeds this threshold in seconds

**Step 3: Confirm base URL is reachable**

Make a single request to `base_url` before running the full suite. If unreachable, report immediately rather than failing every endpoint individually.

**Gate**: Configuration parsed, base URL reachable, at least one endpoint defined. Proceed only when gate passes.

### Phase 2: VALIDATE

**Goal**: Test each endpoint against its expected criteria and collect structured results.

**Step 1: Execute requests sequentially**

For each endpoint:
1. Construct full URL from `base_url` + `path`
2. Send GET request with configured timeout
3. Record status code, response time, and body

**Step 2: Evaluate against expectations**

For each response, check in order:
1. **Status code**: Does it match `expect_status`? If not, mark FAIL.
2. **JSON key**: If `expect_key` set, parse JSON and check key exists. If missing or not valid JSON, mark FAIL.
3. **Response time**: If `max_time` set and elapsed exceeds it, mark SLOW.
4. **Security headers**: Check response headers for common security headers. Report missing headers as WARN (not FAIL):
   - `Strict-Transport-Security` — HSTS enforcement (expected on HTTPS endpoints)
   - `Content-Security-Policy` — XSS mitigation
   - `X-Content-Type-Options` — should be `nosniff`
   - `X-Frame-Options` — clickjacking prevention (or CSP `frame-ancestors`)

Skip security header checks for localhost/127.0.0.1 endpoints (development environments don't typically set these). Only check on non-localhost base URLs unless explicitly configured.

**Step 3: Handle failures gracefully**

- Connection refused: Record as FAIL with "Connection refused" error
- Timeout exceeded: Record as FAIL with "Timeout after Ns" error
- Invalid JSON when `expect_key` set: Record as FAIL with "Invalid JSON response"
- Unexpected exception: Record as FAIL with exception message

**Gate**: All endpoints tested. Every result has a clear PASS, FAIL, or SLOW verdict. Proceed only when gate passes.

### Phase 3: REPORT

**Goal**: Produce structured, machine-readable output with summary statistics.

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

- Exit 0 if all endpoints passed (SLOW counts as pass unless `max_time` was set)
- Exit 1 if any endpoint failed

**Gate**: Report printed, exit code set. Validation complete.

---

## Examples

### Example 1: Pre-Deployment Health Check
User says: "Validate all endpoints before we deploy"
Actions:
1. Find `endpoints.json` in project root (DISCOVER)
2. Test each endpoint, collect status codes and times (VALIDATE)
3. Print report, exit 0 if all pass (REPORT)
Result: Structured pass/fail report with CI-compatible exit code

### Example 2: Smoke Test After Migration
User says: "Check if the API is still working after the database migration"
Actions:
1. Read endpoint config, confirm base URL reachable (DISCOVER)
2. Hit each endpoint, check status and expected keys (VALIDATE)
3. Surface any failures with error details (REPORT)
Result: Quick verification that migration did not break API contracts

---

## Error Handling

### Error: "Base URL Unreachable"
Cause: Service not running, wrong port, or network issue
Solution:
1. Verify service is running (`ps aux`, `docker ps`, or equivalent)
2. Confirm port matches config (`netstat -tlnp` or `ss -tlnp`)
3. Check for firewall rules or container networking issues

### Error: "All Endpoints Timeout"
Cause: Service overwhelmed, wrong host, or proxy misconfiguration
Solution:
1. Test a single endpoint manually with `curl -v`
2. Increase timeout values in config if service is legitimately slow
3. Check if a reverse proxy or load balancer is intercepting requests

### Error: "JSON Parse Failure on expect_key Check"
Cause: Endpoint returns HTML, XML, or empty body instead of JSON
Solution:
1. Verify endpoint actually returns JSON (check Content-Type header)
2. Remove `expect_key` if endpoint legitimately returns non-JSON
3. Check if authentication is required (HTML login page returned)

---

## Anti-Patterns

### Anti-Pattern 1: Testing Against Production Without Safeguards
**What it looks like**: Pointing base_url at production with POST/DELETE endpoints
**Why wrong**: Can mutate production data, cause outages, or trigger rate limits
**Do instead**: Use staging environments for write operations; production only for GET health checks

### Anti-Pattern 2: Ignoring Slow Endpoints
**What it looks like**: "All status codes are 200, ship it!" while ignoring 8-second response times
**Why wrong**: Slow endpoints indicate degradation that will become failures under load
**Do instead**: Set `max_time` thresholds and treat SLOW as actionable warnings

### Anti-Pattern 3: Hardcoding Base URLs
**What it looks like**: `"base_url": "http://192.168.1.42:8000"` in checked-in config
**Why wrong**: Breaks on every other machine, CI environment, and deployment target
**Do instead**: Use environment variables or localhost with configurable port

### Anti-Pattern 4: No Endpoint Config in Repository
**What it looks like**: Manually listing endpoints every time validation runs
**Why wrong**: Endpoints drift, new ones get missed, no single source of truth
**Do instead**: Maintain `endpoints.json` in version control alongside the API code

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

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
