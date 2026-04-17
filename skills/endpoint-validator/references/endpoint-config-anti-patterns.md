# Endpoint Config Anti-Patterns Reference

> **Scope**: Anti-patterns in `endpoints.json` configuration and common validation mistakes.
> **Version range**: All versions of endpoint-validator
> **Generated**: 2026-04-17

---

## Overview

Most endpoint validation failures trace to configuration errors, not actual API bugs. This
reference covers the most common `endpoints.json` mistakes: hardcoded values that break CI,
mutating endpoints run against production, and timeout values that mask real problems.

---

## Correct Configuration Patterns

### Standard endpoints.json Structure

```json
{
  "base_url": "http://localhost:8000",
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

**Why**: Environment variables in header values (`${API_TOKEN}`) keep secrets out of config
files. The validator expands them at runtime — never commit actual tokens.

---

### Environment-Variable Base URL

```json
{
  "base_url": "${BASE_URL:-http://localhost:8000}",
  "endpoints": [...]
}
```

**Why**: `${VAR:-default}` allows CI to override the base URL without maintaining separate
config files per environment. Local dev falls back to localhost automatically.

---

## Anti-Pattern Catalog

### ❌ Hardcoded IP Address in base_url

**Detection**:
```bash
grep -rn '"base_url"' . --include="*.json" | grep -E '"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
rg '"base_url".*[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' --type json
```

**What it looks like**:
```json
{"base_url": "http://192.168.1.42:8000"}
```

**Why wrong**: IP addresses are machine-local. The config breaks on every other developer
machine, in CI, and after any network reconfiguration.

**Fix**:
```json
{"base_url": "http://localhost:8000"}
```
Or use an environment variable: `{"base_url": "${API_URL}"}`

---

### ❌ Write Endpoints Against Production base_url

**Detection**:
```bash
grep -rn '"method"' . --include="*.json" | grep -iE '"POST"|"PUT"|"DELETE"|"PATCH"'
```

**What it looks like**:
```json
{
  "base_url": "https://api.example.com",
  "endpoints": [
    {"path": "/api/v1/users", "method": "POST", "body": {"name": "test"}}
  ]
}
```

**Why wrong**: POST/PUT/DELETE against a production URL creates/mutates/deletes real data.
A smoke test that runs pre-deploy will insert test records, trigger webhooks, or bill users.

**Fix**: Use staging for mutating endpoints. Reserve production config for GET-only health
checks. The validator warns when it detects write methods with a non-localhost `base_url`.

---

### ❌ Zero or Very High Timeout

**Detection**:
```bash
grep -rn '"timeout"' . --include="*.json" | grep -E '"timeout":\s*0\b'
grep -rn '"timeout"' . --include="*.json" | grep -E '"timeout":\s*[6-9][0-9]|[1-9][0-9]{2,}'
```

**What it looks like**:
```json
{"path": "/api/slow", "timeout": 0}
{"path": "/api/upload", "timeout": 300}
```

**Why wrong**: `timeout: 0` means no timeout — a hung connection blocks the entire validation
suite forever. `timeout: 300` hides performance regressions; an endpoint that starts taking
60 seconds is clearly degraded but passes validation.

**Fix**: Use `timeout: 5` (default) for health checks. For legitimately slow endpoints, set
`timeout: 15` and `max_time: 5.0` to distinguish "too slow" from "timed out completely":
```json
{"path": "/api/report", "timeout": 15, "max_time": 5.0}
```

---

### ❌ expect_key on Non-JSON Endpoint

**Detection**:
```bash
grep -B2 '"expect_key"' endpoints.json | grep -E '"path".*\.(html|xml|csv|txt|pdf)'
```

**What it looks like**:
```json
{"path": "/sitemap.xml", "expect_key": "urlset"}
```

**Why wrong**: `expect_key` parses the response as JSON and checks for a top-level key.
XML, HTML, and CSV responses will always fail JSON parsing, generating "Invalid JSON response"
errors that obscure the real issue.

**Fix**: For non-JSON endpoints, only check `expect_status`:
```json
{"path": "/sitemap.xml", "expect_status": 200}
```

---

### ❌ Missing expect_status on Non-200 Endpoints

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

**What it looks like**:
```json
{"path": "/api/v1/nonexistent-resource"}
```

**Why wrong**: Default `expect_status` is 200. An endpoint that intentionally returns 404
(e.g., validating your 404 handler) will report FAIL when it should PASS.

**Fix**:
```json
{"path": "/api/v1/nonexistent-resource", "expect_status": 404}
```

---

### ❌ Credentials in Config File

**Detection**:
```bash
grep -rn '"Authorization"\|"X-Api-Key"\|"api_key"\|"token"' endpoints.json | grep -v '\${[A-Z_]*}'
rg '"Bearer [A-Za-z0-9+/=._-]{20,}"' --type json
```

**What it looks like**:
```json
{"headers": {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.actual-token-here"}}
```

**Why wrong**: Tokens committed to config files end up in git history permanently. Even if
rotated, the old token may be valid elsewhere or extractable from history. GitHub secret
scanning will flag this.

**Fix**: Use environment variable interpolation:
```json
{"headers": {"Authorization": "Bearer ${API_TOKEN}"}}
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
