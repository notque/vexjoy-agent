# Sovereign Cloud & Data Residency Reference

Requirements for systems in sovereign cloud environments, particularly German/EU data residency. Relevant for SAP Converged Cloud and similar infrastructure.

## German Federal Data Protection (BDSG / DSGVO)

BDSG supplements GDPR with German-specific requirements. DSGVO is the German GDPR implementation.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Processing in Germany/EU | No data leaves German/EU data centers. Check API endpoints, CDN, analytics. |
| 2 | German DPO | Contact info accessible. Privacy policy in German. |
| 3 | Employee data (§26 BDSG) | Stricter handling than customer data. Separate access controls. |
| 4 | Automated decisions (Art. 22 DSGVO) | Human override mechanism for automated decisions affecting individuals? |
| 5 | Processing agreements | Third-party processors have AVV? |
| 6 | TOMs (§64 BDSG) | Encryption, pseudonymization, access controls documented? |

## BSI C5 (Cloud Computing Compliance Criteria)

German Federal Office for Information Security standard. Required for German government cloud.

| # | Domain | Code-Level Check |
|---|--------|-----------------|
| 1 | Identity & Access (IDM) | MFA? Role separation between tenant admin and provider admin? |
| 2 | Cryptography (CRY) | German-approved algorithms? Key management within EU? |
| 3 | Communication Security (COS) | Inter-service encryption? No unencrypted internal traffic? |
| 4 | Asset Management (AM) | Data classification? Automated asset inventory? |
| 5 | Physical Security (PS) | Data centers in Germany? Geo-redundancy within German borders? |
| 6 | Operations Security (OPS) | Change management documented? Deployment audit trails? |
| 7 | Logging & Monitoring (LOG) | Immutable security event logs? Retention per BSI? |
| 8 | Business Continuity (BCM) | DR within German data centers? No failover outside jurisdiction? |
| 9 | Supply Chain (SSO) | Subprocessors evaluated? No non-EU subprocessors for sovereign data? |
| 10 | Portability (PI) | Data exportable in open formats? No vendor lock-in? |

## EU Data Residency Requirements

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | No transatlantic transfer | All external API calls stay in EU? |
| 2 | EU-based DNS | No US-based DNS providers? |
| 3 | EU-based logging/monitoring | Log aggregation in EU? Check Sentry, Datadog region config. |
| 4 | EU-based CDN | Static assets from EU edge nodes only? |
| 5 | EU-based CI/CD | Build systems in EU? GitHub Actions runners in EU? |
| 6 | EU-based error tracking | Sentry/Bugsnag configured for EU region? |
| 7 | EU-based email | Transactional email (SendGrid, SES) in EU region? |
| 8 | Backup residency | Backups in EU? Cross-region replication stays within EU? |

## IT-Sicherheitsgesetz & KRITIS

German IT Security Act 2.0 for critical infrastructure and suppliers. Applies to energy, water, food, IT/telecom, health, finance, transport, government.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Attack detection | IDS/IPS? Security event correlation? |
| 2 | Incident reporting (BSI) | Report to BSI within 24 hours? Automated alerting? |
| 3 | Audit readiness | Documentation sufficient for BSI audit? |
| 4 | Supply chain security | Trusted sources? SBOM generated? |
| 5 | Vulnerability management | CVE scanning automated? Patch timeline documented? |
| 6 | Network segmentation | KRITIS systems isolated? Micro-segmentation? |
| 7 | Backup isolation | Air-gapped or immutable? Ransomware-resistant? |
| 8 | Minimum privilege | Least privilege service accounts? No shared admin credentials? |

> **Extended coverage**: See [german-it-security.md](german-it-security.md) for expanded KRITIS checks (KR-01 through KR-12), BSI IT-Grundschutz modules, and NIS2UmsuCG requirements.

## Personnel Security (SÜG)

German security clearance for sovereign and classified systems.

| Level | Name | Applies To |
|-------|------|-----------|
| Ü1 | Einfache Sicherheitsüberprüfung | VS-NfD classified info |
| Ü2 | Erweiterte Sicherheitsüberprüfung | SECRET systems |
| Ü3 | Erweiterte mit Sicherheitsermittlungen | TOP SECRET systems |

**Code-level implications:**

| # | Requirement | Impact |
|---|------------|--------|
| 1 | EU/EEA national requirement | CI/CD must not expose sovereign secrets to non-cleared contexts |
| 2 | Need-to-know access | Sovereign repos may require separate access groups |
| 3 | Cleared environment only | Development on cleared workstations only |
| 4 | Personnel access audit trail | Who accessed what sovereign system when |
| 5 | Separation of duties | No single person deploys AND approves sovereign changes |

## BSI Technical Guidelines

| Guideline | Topic | Relevance |
|-----------|-------|-----------|
| BSI TR-02102 | Cryptographic algorithms | Approved ciphers/key lengths for German government |
| BSI TR-03116 | TLS configurations | Minimum TLS versions, cipher suites |
| BSI TR-03107 | eID and authentication | Electronic identity card integration |
| BSI TR-03125 | Trusted archiving (TR-ESOR) | Long-term data preservation with integrity |

## Sovereign Cloud Architecture Patterns

| Pattern | Description | When to Apply |
|---------|------------|---------------|
| Data boundary enforcement | API gateway validates PII routes only to EU services | Multi-region architecture |
| Encryption key residency | HSM/KMS within jurisdiction, keys never exported | Encryption at rest required |
| Audit log immutability | Append-only logs with cryptographic chaining | Regulated data |
| Tenant isolation | Hard boundaries, no shared compute for sensitive workloads | Multi-tenant sovereign platforms |
| Geo-fenced failover | DR within jurisdiction during outages | Business continuity |

## Common Violations in Reviews

| Violation | Where It Hides | Detection |
|-----------|---------------|-----------|
| US-region SaaS | Hardcoded `us-east-1`, `.com` endpoints | Grep for region identifiers |
| Analytics abroad | Google Analytics without EU config | Check SDK initialization |
| Error tracking to US | Default Sentry DSN | Verify EU endpoint |
| Cloud storage in US | S3 without explicit EU region | Check bucket/terraform configs |
| Third-party JS from US CDNs | Script tags to US-hosted libraries | Audit external script sources |

## How to Use in Reviews

1. Identify sovereign context (SAP CC, German government, EU-only)
2. Apply BDSG + BSI C5 for German sovereign cloud
3. Apply EU data residency for general EU compliance
4. Report violations with specific requirement numbers
5. Check application code AND infrastructure config (terraform, helm, docker compose)
