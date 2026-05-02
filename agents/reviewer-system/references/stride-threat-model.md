# STRIDE Threat Modeling Reference

Proactive threat identification methodology. Use when reviewing code that handles authentication, authorization, data storage, or external communication.

## When to Apply

- New service or API endpoint
- Auth logic changes
- Data storage or transmission changes
- External service integration
- User input handling modified

## The STRIDE Framework

For each component or data flow, check all 6 categories:

### S — Spoofing (Identity)

| Check | What to Look For |
|-------|-----------------|
| Authentication bypass | Missing auth on endpoints, default credentials |
| Token forgery | Weak JWT signing, no signature verification |
| Session hijacking | Session IDs in URLs, missing secure/httponly flags |
| Certificate spoofing | Missing TLS validation, self-signed cert acceptance |

### T — Tampering (Data Integrity)

| Check | What to Look For |
|-------|-----------------|
| Input manipulation | Missing validation on bodies, params, headers |
| Database tampering | SQL injection, mass assignment, unparameterized queries |
| File tampering | Path traversal, arbitrary file write, symlink attacks |
| Message tampering | Missing HMAC/signature on webhooks |

### R — Repudiation (Accountability)

| Check | What to Look For |
|-------|-----------------|
| Missing audit logs | State-changing ops without who/what/when |
| Log tampering | Logs writable by app user, no integrity checks |
| Unsigned transactions | Financial/permission changes without audit trail |
| Missing request IDs | No correlation ID across services |

### I — Information Disclosure

| Check | What to Look For |
|-------|-----------------|
| Error message leakage | Stack traces, SQL errors, internal paths |
| Verbose logging | PII, tokens, passwords in logs |
| Insecure storage | Plaintext passwords, unencrypted PII at rest |
| Side channels | Timing differences in auth |
| Directory listing | Exposed .git/, .env, backup files |

### D — Denial of Service

| Check | What to Look For |
|-------|-----------------|
| Resource exhaustion | Unbounded queries, missing pagination, no size limits |
| Algorithmic complexity | ReDoS, quadratic parsing, hash collision attacks |
| Connection exhaustion | Missing pool limits, no timeouts on external calls |
| Storage exhaustion | Unbounded uploads, log flooding, cache poisoning |

### E — Elevation of Privilege

| Check | What to Look For |
|-------|-----------------|
| Broken access control | IDOR, missing ownership checks |
| Role escalation | User modifies own role, missing role validation |
| Privilege inheritance | Child resources inheriting permissions incorrectly |
| Default permissions | New resources with overly permissive defaults |

## Threat Assessment Output

```
Threat: [description]
Category: [S/T/R/I/D/E]
Asset: [what's at risk]
Attack Vector: [exploitation method]
Impact: [1-5]
Likelihood: [1-5]
Risk Score: Impact x Likelihood [1-25]
Mitigation: [specific fix]
```

## Risk Scoring

| Score | Classification | Action |
|-------|---------------|--------|
| 15-25 | Critical | Block PR, fix immediately |
| 10-14 | High | Fix before merge |
| 5-9 | Medium | Track, fix in next sprint |
| 1-4 | Low | Accept or defer |
