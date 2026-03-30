# STRIDE Threat Modeling Reference

Structured methodology for proactive threat identification. Use when reviewing
code that handles authentication, authorization, data storage, or external
communication — not just looking for bugs, but modeling what an attacker would target.

## When to Apply

- New service or API endpoint being added
- Authentication/authorization logic changes
- Data storage or transmission patterns change
- External service integration added
- User input handling modified

## The STRIDE Framework

For each component or data flow, check all 6 categories:

### S — Spoofing (Identity)

Can an attacker pretend to be someone else?

| Check | What to Look For |
|-------|-----------------|
| Authentication bypass | Missing auth checks on endpoints, default credentials |
| Token forgery | Weak JWT signing (HS256 with guessable secret), no signature verification |
| Session hijacking | Session IDs in URLs, missing secure/httponly cookie flags |
| Certificate spoofing | Missing TLS certificate validation, self-signed cert acceptance |

### T — Tampering (Data Integrity)

Can an attacker modify data they shouldn't?

| Check | What to Look For |
|-------|-----------------|
| Input manipulation | Missing validation on request bodies, query params, headers |
| Database tampering | SQL injection, mass assignment, unparameterized queries |
| File tampering | Path traversal, arbitrary file write, symlink attacks |
| Message tampering | Missing HMAC/signature on webhooks, unsigned API responses |

### R — Repudiation (Accountability)

Can an attacker deny they performed an action?

| Check | What to Look For |
|-------|-----------------|
| Missing audit logs | State-changing operations without logging who/what/when |
| Log tampering | Logs writable by application user, no log integrity checks |
| Unsigned transactions | Financial or permission changes without audit trail |
| Missing request IDs | No correlation ID for tracing actions across services |

### I — Information Disclosure

Can an attacker access data they shouldn't?

| Check | What to Look For |
|-------|-----------------|
| Error message leakage | Stack traces, SQL errors, internal paths in responses |
| Verbose logging | PII, tokens, passwords in log output |
| Insecure storage | Plaintext passwords, unencrypted PII at rest |
| Side channels | Timing differences in auth (valid vs invalid username) |
| Directory listing | Exposed .git/, .env, backup files, admin panels |

### D — Denial of Service

Can an attacker make the system unavailable?

| Check | What to Look For |
|-------|-----------------|
| Resource exhaustion | Unbounded queries, missing pagination, no request size limits |
| Algorithmic complexity | Regex DoS (ReDoS), quadratic parsing, hash collision attacks |
| Connection exhaustion | Missing connection pool limits, no timeouts on external calls |
| Storage exhaustion | Unbounded file uploads, log flooding, cache poisoning |

### E — Elevation of Privilege

Can an attacker gain permissions they shouldn't have?

| Check | What to Look For |
|-------|-----------------|
| Broken access control | IDOR (incrementing IDs), missing ownership checks |
| Role escalation | User can modify their own role, missing role validation |
| Privilege inheritance | Child resources inheriting parent permissions incorrectly |
| Default permissions | New resources created with overly permissive defaults |

## Threat Assessment Output

For each identified threat, document:

```
Threat: [description]
Category: [S/T/R/I/D/E]
Asset: [what's at risk]
Attack Vector: [how it could be exploited]
Impact: [1-5] — what happens if exploited
Likelihood: [1-5] — how easy to exploit
Risk Score: Impact x Likelihood [1-25]
Mitigation: [specific fix]
```

## Risk Scoring Guide

| Score Range | Classification | Action |
|-------------|---------------|--------|
| 15-25 | Critical | Block PR, fix immediately |
| 10-14 | High | Fix before merge |
| 5-9 | Medium | Track, fix in next sprint |
| 1-4 | Low | Accept or defer |
