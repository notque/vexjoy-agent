# Sovereign Cloud & Data Residency Reference

Requirements for systems operating in sovereign cloud environments, particularly
German/EU data residency regulations. Relevant for SAP Converged Cloud and
similar sovereign infrastructure.

## German Federal Data Protection (BDSG / DSGVO)

The BDSG (Bundesdatenschutzgesetz) supplements GDPR with German-specific requirements.
DSGVO is the German implementation of GDPR.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Data processing in Germany/EU | No data leaves German/EU data centers. Check API endpoints, CDN configs, analytics services. |
| 2 | German DPO (Datenschutzbeauftragter) | Contact information accessible. Privacy policy in German. |
| 3 | Employee data protection (§26 BDSG) | Employee PII has stricter handling than customer data. Separate access controls. |
| 4 | Automated decision-making (Art. 22 DSGVO) | If automated decisions affect individuals, is there a human override mechanism? |
| 5 | Data processing agreements | Third-party processors have Auftragsverarbeitungsvertrag (AVV)? |
| 6 | Technical-organizational measures (TOMs) | Encryption, pseudonymization, access controls documented per §64 BDSG? |

## BSI C5 (Cloud Computing Compliance Criteria Catalogue)

German Federal Office for Information Security standard for cloud providers.
Required for German government cloud usage.

| # | Domain | Code-Level Check |
|---|--------|-----------------|
| 1 | Identity & Access (IDM) | MFA enforced? Role separation between tenant admin and provider admin? |
| 2 | Cryptography (CRY) | German-approved algorithms? Key management within EU boundaries? |
| 3 | Communication Security (COS) | Inter-service encryption? No unencrypted internal traffic? |
| 4 | Asset Management (AM) | Data classification implemented? Asset inventory automated? |
| 5 | Physical Security (PS) | Data centers in Germany? Geo-redundancy within German borders? |
| 6 | Operations Security (OPS) | Change management documented? Deployment audit trails? |
| 7 | Logging & Monitoring (LOG) | Security events logged immutably? Retention per BSI requirements? |
| 8 | Business Continuity (BCM) | DR within German data centers? No failover outside jurisdiction? |
| 9 | Supply Chain (SSO) | Subprocessors evaluated? No non-EU subprocessors for sovereign data? |
| 10 | Portability (PI) | Data exportable in open formats? No vendor lock-in for sovereign data? |

## EU Data Residency Requirements

For systems that must keep data within EU boundaries.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | No transatlantic data transfer | Check all external API calls — do any hit US endpoints? |
| 2 | EU-based DNS resolution | DNS queries stay within EU? No US-based DNS providers? |
| 3 | EU-based logging/monitoring | Log aggregation services hosted in EU? Sentry, Datadog, etc. — check region config. |
| 4 | EU-based CDN nodes | Static assets served from EU edge nodes only? |
| 5 | EU-based CI/CD | Build systems in EU? GitHub Actions runners in EU? |
| 6 | EU-based error tracking | Exception reporting (Sentry, Bugsnag) configured for EU region? |
| 7 | EU-based email services | Transactional email (SendGrid, SES) in EU region? |
| 8 | Backup residency | Backups stored in EU? Cross-region replication stays within EU? |

## IT-Sicherheitsgesetz (IT Security Act) & KRITIS

German IT Security Act 2.0 requirements for critical infrastructure operators
and their suppliers. Applies to energy, water, food, IT/telecom, health,
finance, transport, and government sectors.

| # | Requirement | Code-Level Check |
|---|------------|-----------------|
| 1 | Attack detection systems | IDS/IPS deployed? Security event correlation implemented? |
| 2 | Incident reporting (BSI) | Can security incidents be reported to BSI within 24 hours? Automated alerting? |
| 3 | Security audit readiness | System documentation sufficient for BSI audit? Architecture diagrams current? |
| 4 | Supply chain security | Dependencies from trusted sources? SBOM (Software Bill of Materials) generated? |
| 5 | Vulnerability management | CVE scanning automated? Patch timeline documented? |
| 6 | Network segmentation | KRITIS systems isolated from general IT? Micro-segmentation? |
| 7 | Backup isolation | Backups air-gapped or immutable? Ransomware-resistant? |
| 8 | Minimum privilege | Service accounts with least privilege? No shared admin credentials? |

## Personnel Security (SÜG — Sicherheitsüberprüfungsgesetz)

German security clearance requirements for personnel working on sovereign
and classified systems. The Sicherheitsüberprüfung (security vetting) requires
EU/EEA nationality for access to certain infrastructure tiers.

| Level | Name | Applies To |
|-------|------|-----------|
| Ü1 | Einfache Sicherheitsüberprüfung | Access to classified information (VS-NfD) |
| Ü2 | Erweiterte Sicherheitsüberprüfung | Access to SECRET-classified systems |
| Ü3 | Erweiterte mit Sicherheitsermittlungen | Access to TOP SECRET systems |

**Code-level implications:**

| # | Requirement | What It Means for Development |
|---|------------|------------------------------|
| 1 | EU/EEA national requirement | Non-EU personnel cannot access production sovereign systems. CI/CD pipelines must not expose sovereign secrets to non-cleared contexts. |
| 2 | Need-to-know access | Code repos for sovereign components may require separate access groups. No blanket org-wide read access. |
| 3 | Cleared environment only | Development of sovereign components on cleared workstations. No personal devices, no coffee-shop coding. |
| 4 | Audit trail on personnel access | Who accessed what sovereign system when — logged and reviewable. |
| 5 | Separation of duties | No single person can deploy AND approve sovereign system changes. Dual-control enforcement. |

## BSI Technical Guidelines (TR)

Specific technical standards referenced by BSI C5 and KRITIS:

| Guideline | Topic | Relevance |
|-----------|-------|-----------|
| BSI TR-02102 | Cryptographic algorithms | Which ciphers/key lengths are approved for German government use |
| BSI TR-03116 | TLS configurations | Minimum TLS versions, cipher suites for sovereign systems |
| BSI TR-03107 | eID and authentication | Electronic identity card integration requirements |
| BSI TR-03125 | Trusted archiving (TR-ESOR) | Long-term data preservation with integrity guarantees |

## Sovereign Cloud Architecture Patterns

| Pattern | Description | When to Apply |
|---------|------------|---------------|
| Data boundary enforcement | API gateway validates that requests carrying PII route only to EU services | Any multi-region architecture |
| Encryption key residency | HSM/KMS located within sovereign jurisdiction, keys never exported | Whenever encryption at rest is required |
| Audit log immutability | Append-only audit logs with cryptographic chaining | Any system processing regulated data |
| Tenant isolation | Hard tenant boundaries — no shared compute for sensitive workloads | Multi-tenant sovereign platforms |
| Geo-fenced failover | DR stays within jurisdiction even during outages | Business continuity planning |

## Common Violations in Code Reviews

| Violation | Where It Hides | How to Detect |
|-----------|---------------|---------------|
| US-region SaaS in production code | Hardcoded `us-east-1`, `.com` endpoints without EU equivalent | Grep for region identifiers in config |
| Analytics sending data abroad | Google Analytics, Mixpanel without EU data residency config | Check analytics SDK initialization |
| Error tracking to US | Default Sentry DSN pointing to US ingest | Verify Sentry DSN uses EU endpoint |
| Cloud storage in US | S3 bucket without explicit EU region | Check bucket creation / terraform configs |
| Third-party JS loading from US CDNs | Script tags pointing to US-hosted libraries | Audit external script sources |

## How to Use in Reviews

1. Identify if the system operates in sovereign context (SAP CC, German government, EU-only)
2. Apply BDSG + BSI C5 checks for German sovereign cloud
3. Apply EU data residency for general EU compliance
4. Report violations with specific requirement numbers
5. Check both application code AND infrastructure config (terraform, helm values, docker compose)
