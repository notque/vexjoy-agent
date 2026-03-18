# Anti-Rationalization: Security

Security-specific patterns to prevent rationalized security shortcuts.

## Base Patterns

See [anti-rationalization-core.md](./anti-rationalization-core.md) for universal patterns.

## Security-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Internal network only" | Networks get breached | **Secure anyway** |
| "Trusted input" | Trust is a vulnerability | **Validate anyway** |
| "Only admins use this" | Admin credentials get stolen | **Secure anyway** |
| "We'll fix before launch" | Launch deadlines slip | **Fix now** |
| "Low-value target" | Attackers are opportunistic | **Secure anyway** |
| "Behind firewall" | Firewalls fail | **Defense in depth** |
| "Encrypted transport" | Encryption ≠ Authorization | **Still validate** |
| "Framework handles it" | Frameworks have vulnerabilities | **Verify** |
| "Small user base" | One breach is too many | **Secure anyway** |
| "Penetration test passed" | Tests can miss things | **Defense in depth** |
| "Authentication exists" | Auth ≠ Authorization | **Check both** |
| "Data isn't sensitive" | All data has value | **Protect anyway** |

## OWASP Top 10 Checklist

Never skip these checks:

| # | Category | Must Verify |
|---|----------|-------------|
| 1 | Broken Access Control | Authorization on every endpoint |
| 2 | Cryptographic Failures | Proper encryption, no hardcoded secrets |
| 3 | Injection | Parameterized queries, input validation |
| 4 | Insecure Design | Threat model, secure by default |
| 5 | Security Misconfiguration | Hardened defaults, no debug in prod |
| 6 | Vulnerable Components | Dependencies updated, CVE checks |
| 7 | Authentication Failures | Strong auth, secure session management |
| 8 | Integrity Failures | Signed updates, verified sources |
| 9 | Logging Failures | Audit logs, no sensitive data in logs |
| 10 | SSRF | URL validation, allowlists |

## "Trust" Rationalizations

Trust is not a security control:

| "Trusted" Thing | Why Not Trusted |
|-----------------|-----------------|
| Internal users | Credentials can be stolen |
| Admin users | Admins make mistakes |
| Partner APIs | Partners get breached |
| Your own frontend | Frontend can be bypassed |
| Database | SQL injection exists |
| Environment variables | Can be leaked |

## Security Review Requirements

Before approving security-relevant code:

| Area | Verified? |
|------|-----------|
| Input validation on ALL inputs | [ ] |
| Output encoding for context | [ ] |
| Authentication on protected routes | [ ] |
| Authorization checks in handlers | [ ] |
| Secrets not in code or logs | [ ] |
| Dependencies checked for CVEs | [ ] |
| Error messages don't leak info | [ ] |
| HTTPS/TLS configured properly | [ ] |

## Severity Classification for Security

Security issues are rarely LOW:

| Finding | Minimum Severity |
|---------|-----------------|
| SQL injection | CRITICAL |
| Auth bypass | CRITICAL |
| SSRF | HIGH-CRITICAL |
| XSS (stored) | HIGH |
| XSS (reflected) | MEDIUM-HIGH |
| Info disclosure | MEDIUM |
| Missing headers | LOW-MEDIUM |

When in doubt, classify higher.
