# ADR-007: Security Improvements (bandit routing, security headers)

## Status

Implemented

## Date

2026-03-19

## Context

Research into external tooling (prompted by evaluating the FreeAgent repo) revealed
minor gaps in our security posture. We have LLM-based static analysis
(`reviewer-security`), dependency CVE scanning (`reviewer-dependency-audit`), and
Go SAST via golangci-lint (which already includes gosec). Two small improvements
were identified.

### What works today

```
STATIC REVIEW      → reviewer-security          ✅ (LLM reads code, checks OWASP Top 10)
CVE SCANNING       → reviewer-dependency-audit   ✅ (govulncheck, npm audit, pip-audit)
CONFIG SAFETY      → reviewer-config-safety      ✅ (hardcoded secrets, env var validation)
GO SAST            → golangci-lint (gosec)        ✅ (already runs via make check in CI)
```

### What's missing

| Gap | Impact |
|-----|--------|
| Bandit buried in python-quality-gate | Can't route "Python security scan" without knowing the skill name |
| No security header validation | endpoint-validator checks health but not CSP/HSTS/X-Frame-Options |

### Decision: gosec NOT added

gosec was initially considered for the go-pr-quality-gate but dropped after
investigation revealed all Go repos (log-router, go-bits, hermez) already run
gosec through golangci-lint in their `.golangci.yaml` configs. Adding standalone
gosec would be redundant — double-scanning the same code for the same patterns.

## Decision

Make two small, focused changes following existing patterns:

### 1. Add bandit force-route trigger

Bandit already runs inside python-quality-gate. Add force-route triggers
so "run bandit" or "Python security scan" routes to python-quality-gate
rather than requiring the user to know the skill name. The full quality
gate runs (not bandit standalone), which is the correct behavior — bandit
findings are more actionable in the context of the full quality report.

### 2. Add security header checks to endpoint-validator

Extend the existing HTTP validation to check response headers for common
security headers: Strict-Transport-Security, Content-Security-Policy,
X-Frame-Options, X-Content-Type-Options. Report missing headers as warnings
(not failures) since not all endpoints require all headers. Skip for
localhost/127.0.0.1 endpoints.

## Components

| Change | File | Type |
|--------|------|------|
| Bandit route | `skills/do/SKILL.md` | Routing edit |
| Security headers | `skills/endpoint-validator/SKILL.md` | Skill edit |

## Consequences

### Positive

- Python security scanning is accessible via natural language ("run bandit")
- Endpoint validation now covers basic security posture, not just availability

### Negative

- Security headers check may produce noise for internal/development endpoints
  (mitigated by localhost skip)

### Neutral

- No new skills, agents, or hooks created
- No changes to comprehensive-review pipeline
- No changes to Go quality gate (gosec already covered by golangci-lint)
