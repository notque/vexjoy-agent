# Auth Endpoint Patterns Reference

> **Scope**: Configuring and validating authenticated API endpoints in endpoint-validator.
> **Version range**: All HTTP auth schemes (Bearer, API key, Basic, session cookie)
> **Generated**: 2026-04-17

---

## Overview

Validating authenticated endpoints requires passing credentials without committing them to
config files. The four most common schemes — Bearer tokens, API keys, Basic auth, and session
cookies — each have distinct configuration patterns. The primary failure mode is a 401 that
masquerades as an API bug when it's actually a credential misconfiguration.

---

## Pattern Table

| Auth Scheme | Header | endpoints.json Pattern | Failure Signal |
|-------------|--------|----------------------|----------------|
| Bearer token | `Authorization: Bearer <token>` | `"Bearer ${BEARER_TOKEN}"` | 401 on otherwise valid endpoint |
| API key (header) | `X-Api-Key: <key>` | `"${API_KEY}"` | 403 or 401 with no `WWW-Authenticate` |
| Basic auth | `Authorization: Basic <b64>` | `"Basic ${BASIC_CREDS_B64}"` | 401 with `WWW-Authenticate: Basic` |
| Session cookie | `Cookie: session=<token>` | `"${SESSION_TOKEN}"` | 302 redirect to login page |

---

## Correct Patterns

### Bearer Token Authentication

Pass the token via environment variable interpolation. Never hardcode.

```json
{
  "base_url": "${API_BASE_URL}",
  "endpoints": [
    {
      "path": "/api/v1/users",
      "headers": {
        "Authorization": "Bearer ${API_BEARER_TOKEN}",
        "Accept": "application/json"
      },
      "expect_status": 200,
      "expect_key": "data"
    }
  ]
}
```

**Why**: `${API_BEARER_TOKEN}` is expanded from the shell environment at runtime. The same
config works locally (export the var) and in CI (set as a secret). The token never touches
the filesystem or git history.

---

### API Key in Custom Header

```json
{
  "path": "/api/v1/search",
  "headers": {
    "X-Api-Key": "${SEARCH_API_KEY}",
    "Accept": "application/json"
  },
  "expect_status": 200
}
```

**Why**: `X-Api-Key` is not standardized — different APIs use `X-API-Key`, `Api-Key`,
`X-Auth-Token`. HTTP headers are case-insensitive per RFC 7230, but match the API
documentation exactly for readability.

---

### Validating the Auth Rejection Path

Explicitly test that unauthenticated requests return 401, not 200.

```json
{
  "path": "/api/v1/admin/users",
  "expect_status": 401,
  "description": "no-auth should reject with 401"
}
```

**Why**: A misconfigured API may accidentally return 200 with empty data instead of 401
on unauthenticated requests. Validating the rejection path catches authorization middleware
that was accidentally disabled during a deploy.

---

### Verify Required Environment Variables Before Running

```bash
# Pre-flight check — run before endpoint-validator in CI
python3 -c "
import json, os, re, sys
cfg = json.load(open('endpoints.json'))
refs = re.findall(r'\\\${([A-Z_]+)}', json.dumps(cfg))
missing = [r for r in set(refs) if not os.environ.get(r)]
if missing:
    print('MISSING env vars:', missing)
    sys.exit(1)
print('All env vars present')
"
```

---

## Anti-Pattern Catalog

### ❌ Hardcoded Bearer Token in Config

**Detection**:
```bash
grep -rn '"Authorization"' endpoints.json | grep -v '\${[A-Z_]'
rg '"Authorization".*"Bearer [A-Za-z0-9._-]{20,}"' --type json
```

**What it looks like**:
```json
{"headers": {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.actual.token"}}
```

**Why wrong**: JWT tokens in config files get committed to git history. Even after rotation,
the old token remains in every git clone. GitHub secret scanning flags base64-encoded JWTs.

**Fix**: `{"headers": {"Authorization": "Bearer ${API_TOKEN}"}}`

---

### ❌ Skipping expect_status on Protected Endpoint

**Detection**:
```bash
python3 -c "
import json
cfg = json.load(open('endpoints.json'))
for ep in cfg.get('endpoints', []):
    if 'Authorization' in str(ep.get('headers', {})):
        if 'expect_status' not in ep:
            print('WARN no expect_status on auth endpoint:', ep['path'])
"
```

**What it looks like**:
```json
{
  "path": "/api/v1/admin/users",
  "headers": {"Authorization": "Bearer ${TOKEN}"}
}
```

**Why wrong**: Without explicit `expect_status`, default is 200. If the token expires or
loses its scope, the endpoint returns 401 — the validator reports FAIL (expected 200, got 401)
with no context that it's an auth failure, not an API bug.

**Fix**: Always set `expect_status: 200` explicitly on auth-protected endpoints so the
failure message reads "expected 200, got 401" and the auth header is visible in the config.

---

### ❌ Using Admin Credentials for Smoke Tests

**Detection**:
```bash
grep -rn "ADMIN\|ROOT\|MASTER\|SUPERUSER\|SUPER_" endpoints.json
```

**What it looks like**:
```json
{"headers": {"Authorization": "Bearer ${PROD_ADMIN_TOKEN}"}}
```

**Why wrong**: A validation run with a compromised CI environment gets full admin access
to production. Blast radius is maximum. Use read-only service account tokens scoped to
the specific paths being validated.

**Fix**: Create a dedicated `endpoint-validator` service account with read-only access.
Rotate its token independently of admin credentials.

---

### ❌ Session Cookie Validation Without Expiry Handling

**Detection**:
```bash
grep -rn '"Cookie"' endpoints.json | grep -v '\${[A-Z_]'
```

**What it looks like**:
```json
{
  "path": "/dashboard",
  "headers": {"Cookie": "session=abc123fixed"},
  "expect_status": 200
}
```

**Why wrong**: Sessions expire. A hardcoded session value that worked during setup will
silently redirect to a login page (302), which the validator may follow and report 200
(the login page), masking the auth failure entirely.

**Fix**: Use env var for session token and add `expect_key` on JSON dashboard APIs:
```json
{
  "path": "/api/dashboard",
  "headers": {"Cookie": "session=${SESSION_TOKEN}"},
  "expect_status": 200,
  "expect_key": "user"
}
```

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|------------|-----|
| `FAIL: expected 200, got 401` | Missing or expired auth header | Add `headers.Authorization` with fresh env var token |
| `FAIL: expected 200, got 403` | Token lacks required scope/role | Use token with correct permissions or set `expect_status: 403` |
| `FAIL: expected 200, got 302` | Session expired, redirected to login | Refresh `${SESSION_TOKEN}` in environment |
| `FAIL: Invalid JSON` on auth endpoint | 401 returns HTML error page, not JSON | Catch the 401 first via `expect_status: 401` in a separate test |
| Token works in curl but fails in validator | Token contains `%`, `&`, or `+` requiring encoding | URL-encode token or verify env var expansion strips quotes |
| All auth endpoints fail in CI only | Env var not set in CI environment | Add token to CI secrets and export it before running validator |

---

## Detection Commands Reference

```bash
# Find all auth-related header configurations
grep -rn '"Authorization"\|"X-Api-Key"\|"Cookie"\|"X-Auth"' endpoints.json

# Detect hardcoded tokens (not env-var references)
rg '"Authorization".*"(Bearer|Basic) [A-Za-z0-9+/=._-]{10,}"' --type json

# Find admin/superuser tokens in config
grep -rn "ADMIN\|admin\|ROOT\|root\|MASTER\|master" endpoints.json | grep -i "token\|key\|auth"

# Check env vars required by endpoints.json are set
python3 -c "
import json, os, re
cfg = json.load(open('endpoints.json'))
refs = re.findall(r'\\\${([A-Z_]+)}', json.dumps(cfg))
for r in set(refs):
    print(('SET  ' if os.environ.get(r) else 'MISS '), r)
"
```

---

## See Also

- `security-headers.md` — HSTS, CSP, and other response header validation
- `endpoint-config-anti-patterns.md` — general configuration mistakes
