# Compliance Checklists Reference

Quick-reference checklists for regulatory compliance reviews. Use when
reviewing code that handles personal data, payment information, health
records, or operates in regulated environments.

These are code-level checks — not full compliance audits. They catch
the most common violations that appear in pull requests.

## GDPR (General Data Protection Regulation)

Applies to: any system processing EU resident personal data.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Lawful basis for processing | Is consent collected before data processing? Is the purpose documented? |
| 2 | Data minimization | Are you collecting only the fields you actually use? |
| 3 | Right to erasure | Can user data be deleted? Are cascading deletes handled? |
| 4 | Right to export | Can user data be exported in a portable format (JSON/CSV)? |
| 5 | Data retention limits | Are records auto-deleted after retention period? Is there a TTL? |
| 6 | Encryption at rest | Is PII encrypted in the database? Are encryption keys rotated? |
| 7 | Encryption in transit | Is TLS enforced? Are internal service calls encrypted? |
| 8 | Access logging | Are accesses to personal data logged with who/when/why? |
| 9 | Cross-border transfer | Does data leave the EU? Are transfer mechanisms documented? |
| 10 | Breach notification | Can affected users be identified within 72 hours? |

## SOC 2 (Service Organization Control)

Applies to: SaaS providers, cloud services, data processors.

| # | Trust Principle | Code-Level Check |
|---|----------------|-----------------|
| 1 | Security — Access control | Role-based access with least privilege? No shared credentials? |
| 2 | Security — Authentication | MFA available? Password policy enforced? Session timeouts? |
| 3 | Security — Encryption | Data encrypted at rest and in transit? Key management documented? |
| 4 | Security — Logging | Security events logged? Logs tamper-evident? Retention policy? |
| 5 | Availability — Monitoring | Health checks implemented? Alerting on failures? SLOs defined? |
| 6 | Availability — Backup | Automated backups? Tested restore procedures? |
| 7 | Availability — Redundancy | Single points of failure identified? Failover tested? |
| 8 | Confidentiality — Classification | Is data classified (public/internal/confidential/restricted)? |
| 9 | Confidentiality — Access | Need-to-know access enforced? Data masking for non-prod? |
| 10 | Processing integrity | Input validation? Output verification? Error handling? |

## PCI-DSS (Payment Card Industry)

Applies to: any system that stores, processes, or transmits cardholder data.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | No plaintext card storage | Card numbers never stored in plaintext. Never logged. |
| 2 | Tokenization | Raw card numbers replaced with tokens after initial processing? |
| 3 | Encryption of stored data | If card data must be stored, is it encrypted with AES-256+? |
| 4 | TLS 1.2+ | All cardholder data transmitted over TLS 1.2 or higher? |
| 5 | No card data in logs | Grep logs for card number patterns (4/5/6xxx-xxxx-xxxx-xxxx). |
| 6 | Access control | Cardholder data access restricted to need-to-know roles? |
| 7 | Unique IDs | Each user accessing cardholder data has unique credentials? |
| 8 | Input validation | All payment form inputs validated and sanitized? |
| 9 | Error handling | Payment errors don't leak card data or processing details? |
| 10 | Key management | Encryption keys rotated? Split knowledge for key custodians? |

## HIPAA (Health Insurance Portability)

Applies to: systems handling Protected Health Information (PHI).

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | PHI encryption at rest | All PHI fields encrypted in database? |
| 2 | PHI encryption in transit | TLS enforced for all PHI transmission? |
| 3 | Access controls | Role-based access to PHI with audit trail? |
| 4 | Audit logging | All PHI access logged with user, timestamp, action? |
| 5 | Minimum necessary | Only minimum PHI needed for the function is accessed? |
| 6 | De-identification | Can PHI be de-identified for analytics/testing? |
| 7 | Backup and recovery | PHI backups encrypted? Recovery procedures tested? |
| 8 | Business associate agreements | Third-party services handling PHI have BAAs? |
| 9 | Breach notification | Can affected individuals be identified for breach notification? |
| 10 | Disposal | PHI properly purged when no longer needed? |

## How to Use in Reviews

1. Identify which frameworks apply (usually from project context or ADR)
2. Scan the relevant checklist against the changed code
3. Report violations with the specific requirement number
4. Distinguish between hard violations (must fix) and gaps (should address)

Not every checklist item applies to every PR. Focus on items relevant to the specific code changes being reviewed.
