# Endpoint Configuration Patterns Guide

<!-- no-pair-required: document title block, not a pattern description -->

> **Scope**: Correct patterns for `endpoints.json` configuration and common validation mistakes to detect.
> **Version range**: All versions of endpoint-validator
> **Generated**: 2026-04-17

---

## Overview

Most endpoint validation failures trace to configuration errors, not actual API bugs. This
reference covers the correct approach for `endpoints.json`: environment-variable base URLs,
proper timeout values, secret management, and response type matching.

---

## Configuration Patterns

### Use Environment-Variable Base URLs

Configure `base_url` with `${VAR:-default}` syntax so CI can override the URL without maintaining separate config files per environment. Local dev falls back to localhost automatically.

```json
{
  "base_url": "${BASE_URL:-http://localhost:8000}",
  "endpoints": [
    {"path": "/health", "expect_status": 200},
    {"path": "/api/v1/users", "expect_key": "data", "timeout": 10},
    {"path": "/api/v1/search?q=test", "expect_status": 200, "max_time": 2.0},
    {
      "path": "/api/v1/protected",
      "headers": {"Authorization": "Bearer ${API_TOKEN}"},
      "expect_status": 200
    }
  ]
}
```

**Why this matters**: Environment variables in header values (`${API_TOKEN}`) keep secrets out of config files. The validator expands them at runtime — never commit actual tokens. Hardcoded IP addresses break on every other developer machine, in CI, and after any network reconfiguration.

**Detection**:
```bash
grep -rn '"base_url"' . --include="*.json" | grep -E '"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
```

---

### Restrict Write Methods to Non-Production URLs

Reserve production config for GET-only health checks. Use staging for mutating endpoints (POST, PUT, DELETE, PATCH). The validator warns when it detects write methods with a non-localhost `base_url`.

```json
{
  "base_url": "${STAGING_URL:-http://localhost:8000}",
  "endpoints": [
    {"path": "/api/v1/users", "method": "POST", "body": {"name": "test"}}
  ]
}
```

**Why this matters**: POST/PUT/DELETE against a production URL creates/mutates/deletes real data. A smoke test that runs pre-deploy will insert test records, trigger webhooks, or bill users.

**Detection**:
```bash
grep -rn '"method"' . --include="*.json" | grep -iE '"POST"|"PUT"|"DELETE"|"PATCH"'
```

---

### Set Meaningful Timeouts With Performance Ceilings

Use `timeout: 5` (default) for health checks. For legitimately slow endpoints, set `timeout: 15` and `max_time: 5.0` to distinguish "too slow" from "timed out completely." Never use `timeout: 0` (no timeout) or values above 60 seconds.

```json
{"path": "/api/report", "timeout": 15, "max_time": 5.0}
```

**Why this matters**: `timeout: 0` means no timeout — a hung connection blocks the entire validation suite forever. `timeout: 300` hides performance regressions; an endpoint taking 60 seconds is clearly degraded but passes validation.

**Detection**:
```bash
grep -rn '"timeout"' . --include="*.json" | grep -E '"timeout":\s*0\b'
grep -rn '"timeout"' . --include="*.json" | grep -E '"timeout":\s*[6-9][0-9]|[1-9][0-9]{2,}'
```

---

### Use `expect_status` Only for Non-JSON Endpoints

For XML, HTML, CSV, and other non-JSON responses, check `expect_status` only. Reserve `expect_key` for endpoints that return JSON — it parses the response as JSON and checks for a top-level key.

```json
{"path": "/sitemap.xml", "expect_status": 200}
{"path": "/api/v1/users", "expect_key": "data"}
```

**Why this matters**: `expect_key` on a non-JSON endpoint always fails JSON parsing, generating "Invalid JSON response" errors that obscure the real issue.

**Detection**:
```bash
grep -B2 '"expect_key"' endpoints.json | grep -E '"path".*\.(html|xml|csv|txt|pdf)'
```

---

### Set `expect_status` for Non-200 Endpoints

When validating endpoints that intentionally return non-200 status codes (e.g., 404 handlers, rate limiters), set `expect_status` explicitly. The default is 200.

```json
{"path": "/api/v1/nonexistent-resource", "expect_status": 404}
```

**Why this matters**: An endpoint that intentionally returns 404 (validating your 404 handler) will report FAIL when it should PASS if no `expect_status` is set.

**Detection**:
```bash
python3 -c "
import json
with open('endpoints.json') as f: cfg = json.load(f)
for ep in cfg.get('endpoints', []):
    path = ep.get('path', '')
    if ('404' in path or 'error' in path.lower() or 'missing' in path.lower()):
        if 'expect_status' not in ep:
            print('WARN missing expect_status:', path)
"
```

---

### Use Environment Variable Interpolation for Credentials

Reference secrets via `${ENV_VAR}` in header values. Never commit Bearer tokens, API keys, or passwords directly in config files — they end up in git history permanently.

```json
{"headers": {"Authorization": "Bearer ${API_TOKEN}"}}
```

**Why this matters**: Tokens committed to config files persist in git history even after rotation. GitHub secret scanning will flag hardcoded tokens, and the old token may be valid elsewhere or extractable from history.

**Detection**:
```bash
grep -rn '"Authorization"\|"X-Api-Key"\|"api_key"\|"token"' endpoints.json | grep -v '\${[A-Z_]*}'
rg '"Bearer [A-Za-z0-9+/=._-]{20,}"' --type json
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Connection refused` on every endpoint | Wrong port in `base_url` | Check service with `ss -tlnp` or `docker ps` |
| `Invalid JSON response` on XML/HTML path | `expect_key` set on non-JSON endpoint | Remove `expect_key`, only check `expect_status` |
| `Timeout after 5s` on one slow endpoint | Default timeout too low | Set `"timeout": 15` on that endpoint specifically |
| FAIL on intentional 404 endpoint | Default `expect_status: 200` | Add `"expect_status": 404` |
| Auth endpoint returns 401 | Missing `Authorization` header | Add `"headers": {"Authorization": "Bearer ${TOKEN}"}` |
| CI fails but local passes | `base_url` hardcoded to local IP | Use `localhost` or `${BASE_URL}` env var |

---

## Detection Commands Reference

```bash
# Find hardcoded IPs in any endpoints config
grep -rn '"base_url"' . --include="*.json" | grep -E "[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"

# Find write methods in config files
grep -rn '"method"' . --include="*.json" | grep -iE "post|put|patch|delete"

# Find suspiciously high timeouts (> 59 seconds)
grep -rn '"timeout"' . --include="*.json" | grep -E '"timeout":\s*[6-9][0-9]|[1-9][0-9]{2,}'

# Detect potential committed credentials
grep -rn '"Authorization"\|"X-Api-Key"\|"api_key"' . --include="*.json" | grep -v '\${[A-Z_]*}'
```

---

## See Also

- `security-headers.md` — HSTS, CSP, and other response header validation
- `auth-endpoint-patterns.md` — configuring authenticated endpoint validation
