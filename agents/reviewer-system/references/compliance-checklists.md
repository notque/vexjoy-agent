# Compliance Checklists Reference

Quick-reference checklists for regulatory compliance reviews. Code-level checks — not full compliance audits. Catches the most common violations in pull requests.

## GDPR (General Data Protection Regulation)

Applies to: any system processing EU resident personal data.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Lawful basis for processing | Consent collected before processing? Purpose documented? |
| 2 | Data minimization | Collecting only fields actually used? |
| 3 | Right to erasure | User data deletable? Cascading deletes handled? |
| 4 | Right to export | User data exportable (JSON/CSV)? |
| 5 | Data retention limits | Records auto-deleted after retention period? TTL? |
| 6 | Encryption at rest | PII encrypted in DB? Keys rotated? |
| 7 | Encryption in transit | TLS enforced? Internal calls encrypted? |
| 8 | Access logging | Personal data access logged with who/when/why? |
| 9 | Cross-border transfer | Data leave EU? Transfer mechanisms documented? |
| 10 | Breach notification | Affected users identifiable within 72 hours? |

## SOC 2 (Service Organization Control)

Applies to: SaaS providers, cloud services, data processors.

| # | Trust Principle | Code-Level Check |
|---|----------------|-----------------|
| 1 | Security — Access control | RBAC with least privilege? No shared credentials? |
| 2 | Security — Authentication | MFA? Password policy? Session timeouts? |
| 3 | Security — Encryption | At rest and in transit? Key management documented? |
| 4 | Security — Logging | Security events logged? Tamper-evident? Retention policy? |
| 5 | Availability — Monitoring | Health checks? Alerting? SLOs defined? |
| 6 | Availability — Backup | Automated backups? Tested restore? |
| 7 | Availability — Redundancy | SPOFs identified? Failover tested? |
| 8 | Confidentiality — Classification | Data classified (public/internal/confidential/restricted)? |
| 9 | Confidentiality — Access | Need-to-know enforced? Data masking for non-prod? |
| 10 | Processing integrity | Input validation? Output verification? Error handling? |

## PCI-DSS (Payment Card Industry)

Applies to: any system storing, processing, or transmitting cardholder data.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | No plaintext card storage | Card numbers never stored plaintext. Never logged. |
| 2 | Tokenization | Raw card numbers replaced with tokens? |
| 3 | Encryption of stored data | If stored, encrypted with AES-256+? |
| 4 | TLS 1.2+ | All cardholder data over TLS 1.2+? |
| 5 | No card data in logs | Grep logs for card patterns (4/5/6xxx-xxxx-xxxx-xxxx). |
| 6 | Access control | Restricted to need-to-know roles? |
| 7 | Unique IDs | Each user has unique credentials? |
| 8 | Input validation | Payment inputs validated and sanitized? |
| 9 | Error handling | Payment errors don't leak card data? |
| 10 | Key management | Keys rotated? Split knowledge for custodians? |

## HIPAA (Health Insurance Portability)

Applies to: systems handling Protected Health Information (PHI).

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | PHI encryption at rest | All PHI fields encrypted? |
| 2 | PHI encryption in transit | TLS enforced for all PHI? |
| 3 | Access controls | RBAC with audit trail? |
| 4 | Audit logging | All PHI access logged (user, timestamp, action)? |
| 5 | Minimum necessary | Only minimum PHI accessed for the function? |
| 6 | De-identification | PHI de-identifiable for analytics/testing? |
| 7 | Backup and recovery | Backups encrypted? Recovery tested? |
| 8 | Business associate agreements | Third-party PHI handlers have BAAs? |
| 9 | Breach notification | Affected individuals identifiable? |
| 10 | Disposal | PHI purged when no longer needed? |

## How to Use in Reviews

1. Identify which frameworks apply (from project context or ADR)
2. Scan relevant checklist against changed code
3. Report violations with specific requirement number
4. Distinguish hard violations (must fix) from gaps (should address)

Not every item applies to every PR. Focus on items relevant to the specific changes.
