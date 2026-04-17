# Security Headers Reference

> **Scope**: The four HTTP security headers endpoint-validator checks on non-localhost endpoints.
> **Version range**: All HTTP/1.1+ servers
> **Generated**: 2026-04-17 — verify against OWASP Secure Headers Project

---

## Overview

The endpoint-validator checks four response headers for security compliance. These headers
are absent by default in most frameworks — they must be explicitly set. Missing headers are
reported as WARN (not FAIL): the API is reachable but misconfigured. Checks are skipped
on `localhost`/`127.0.0.1` because development environments routinely omit them.

---

## Pattern Table

| Header | Required Value | Skip Condition | Report Level |
|--------|---------------|----------------|--------------|
| `Strict-Transport-Security` | `max-age=...` (HTTPS only) | HTTP endpoints, localhost | WARN if absent on HTTPS |
| `Content-Security-Policy` | Any value | localhost | WARN if absent |
| `X-Content-Type-Options` | `nosniff` (exact) | localhost | WARN if absent or wrong value |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | localhost; if CSP has `frame-ancestors` | WARN if absent |

---

## Correct Patterns

### Strict-Transport-Security (HSTS)

Tells browsers to only access the site over HTTPS for the specified duration.

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

**Why**: Without HSTS, a user who visits `http://example.com` can be intercepted even if the
server redirects to HTTPS. HSTS eliminates the initial unprotected request.

**Validation note**: Only expected on HTTPS endpoints. If `base_url` starts with `http://`,
skip this check — HSTS on plain HTTP is meaningless and the browser ignores it.

---

### Content-Security-Policy (CSP)

Restricts which scripts, stylesheets, and resources the browser may load.

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-abc123'
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
```

**Why**: Absent CSP means a successful XSS attack can load arbitrary scripts. Even a restrictive
`default-src 'self'` is vastly better than nothing for API responses that might be rendered.

---

### X-Content-Type-Options

Prevents MIME-type sniffing — the browser must honor the `Content-Type` the server declares.

```http
X-Content-Type-Options: nosniff
```

**Why**: Without `nosniff`, a browser may execute a response with `Content-Type: text/plain`
as JavaScript if the content "looks like" a script. This is the primary defense against
MIME confusion attacks.

**Valid value**: Only `nosniff`. Any other value (empty, custom string) is treated as absent.

---

### X-Frame-Options

Prevents the page from being embedded in an iframe on another origin (clickjacking defense).

```http
X-Frame-Options: DENY
X-Frame-Options: SAMEORIGIN
```

**Why**: Clickjacking overlays a hidden iframe over a legitimate UI. DENY is safest for APIs.

**CSP alternative**: `Content-Security-Policy: frame-ancestors 'none'` is the modern replacement.
If CSP already contains `frame-ancestors`, skip the X-Frame-Options check to avoid false WARNs.

---

## Anti-Pattern Catalog

### ❌ Checking Security Headers on localhost

**Detection**:
```bash
grep -rn '"base_url".*localhost\|"base_url".*127\.0\.0\.1' endpoints.json
```

**What it looks like**:
```json
{
  "base_url": "http://localhost:8000",
  "check_security_headers": true
}
```

**Why wrong**: Development servers don't set these headers. Running the check against localhost
generates spurious WARNs on every local run, training developers to ignore warnings entirely.

**Fix**: The validator skips security header checks when `base_url` contains `localhost` or
`127.0.0.1` by default. Only override with `force_security_check: true` when explicitly needed.

---

### ❌ Treating WARN as PASS in CI

**Detection**:
```bash
grep -rn "|| true\|--allow-warn\|exit 0" .github/workflows/ .gitlab-ci.yml 2>/dev/null
```

**What it looks like**:
```yaml
- run: endpoint-validator || true  # suppress all failures
```

**Why wrong**: Suppressing exit codes means security header regressions (a deploy that removes
CSP) pass CI silently. Use `--fail-on-warn` in production validation runs so header removal
triggers a build failure.

**Fix**:
```yaml
- run: endpoint-validator --base-url $PROD_URL --fail-on-warn
  env:
    PROD_URL: ${{ secrets.PROD_URL }}
```

---

### ❌ HSTS Expected on HTTP Endpoint

**Detection**:
```bash
grep -rn '"base_url".*"http://' endpoints.json | grep -v "localhost\|127\.0\.0\.1"
```

**What it looks like**:
```json
{"base_url": "http://api.example.com"}
```

**Why wrong**: HSTS is only meaningful over HTTPS. Browsers ignore HSTS headers delivered
over HTTP (per RFC 6797 §8.1). Checking for it on HTTP endpoints always generates misleading WARNs.

**Fix**: Use `https://` base_url for production validation, or the validator should auto-skip
HSTS checks when base_url starts with `http://`.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `WARN: Missing Strict-Transport-Security` on all endpoints | Base URL is HTTP not HTTPS | Switch to `https://` in `base_url` or add HSTS in nginx config |
| `WARN: X-Content-Type-Options` but header appears present | Value is not exactly `nosniff` | Fix server config: only `nosniff` is valid |
| No security warnings on prod, failures on CI | CI `base_url` points to localhost | Point CI base_url to staging with real headers |
| CSP check warns despite `frame-ancestors` in CSP | Validator doesn't parse CSP directives | Verify validator treats CSP `frame-ancestors` as X-Frame-Options substitute |

---

## Detection Commands Reference

```bash
# Check all four headers for a live endpoint
curl -sI https://api.example.com/health | grep -iE "strict-transport|content-security|x-content-type|x-frame"

# Find endpoints.json files referencing non-localhost URLs
grep -rn '"base_url"' . --include="*.json" | grep -v "localhost\|127\.0\.0\.1"

# Detect CSP presence in nginx config
grep -rn "Content-Security-Policy\|add_header.*CSP" /etc/nginx/ 2>/dev/null
```

---

## See Also

- `endpoint-config-anti-patterns.md` — configuration mistakes in endpoints.json
- `auth-endpoint-patterns.md` — configuring authenticated endpoint validation
