# German IT Security Compliance Reference

Code-level checks for BSI IT-Grundschutz, KRITIS, and NIS2UmsuCG. Complements `sovereign-cloud-data-residency.md` (BSI C5, BDSG/DSGVO) and `compliance-checklists.md` (GDPR, SOC 2). Not a full compliance audit — catches the most common violations in pull requests.

---

## BSI IT-Grundschutz

Germany's comprehensive IT security methodology. The BSI Kompendium contains 113 modules across 10 subject areas. Achieving Standard-Absicherung qualifies for ISO 27001 certification via BSI.

### Module Categories

| Code | Domain | Examples |
|------|--------|----------|
| ISMS | Security Management | ISMS.1 Security Management |
| ORP | Organization & Personnel | ORP.1 Organization, ORP.4 Identity Management |
| CON | Concepts & Procedures | CON.1 Cryptography, CON.3 Backup |
| OPS | Operations | OPS.1.1.3 Patch Management, OPS.1.2.5 Remote Maintenance |
| DER | Detection & Response | DER.1 Detection, DER.2.1 Incident Management |
| APP | Applications | APP.1.1 Office Products, APP.5.3 Email |
| SYS | IT Systems | SYS.1.1 General Server, SYS.2.1 General Client |
| IND | Industrial IT | IND.1 Process Control & Automation |
| NET | Networks & Communication | NET.1.1 Network Architecture, NET.3.2 Firewall |
| INF | Infrastructure | INF.1 General Building, INF.2 Data Center |

### Protection Levels

| Level | Name | Description |
|-------|------|-------------|
| Basis | Basis-Absicherung | Minimum baseline. Attestation only. |
| Standard | Standard-Absicherung | Base + standard controls. Qualifies for ISO 27001 via BSI. |
| Core | Kern-Absicherung | Highest security for critical "crown jewel" assets. |

### BSI Standards

| Standard | Topic |
|----------|-------|
| BSI 200-1 | ISMS construction |
| BSI 200-2 | IT-Grundschutz methodology |
| BSI 200-3 | Risk analysis |
| BSI 200-4 | Business continuity management |

### Certification Phases

Strukturanalyse > Schutzbedarfsfeststellung > Modellierung > IT-Grundschutz-Check > Risikoanalyse > Umsetzung

### Grundschutz vs BSI C5

C5 is already covered in `sovereign-cloud-data-residency.md`. Key differences:

| Dimension | IT-Grundschutz | BSI C5 |
|-----------|---------------|--------|
| Scope | All institutional IT | Cloud services only |
| Type | Certification framework | Audit standard (attestation) |
| Focus | Organization's own info protection | Cloud provider offerings |
| Output | ISO 27001 certificate (via BSI) | C5 Type 1/2 attestation |
| Relationship | Foundation framework | Built on Grundschutz + ISO 27001 + CSA CCM |

### Grundschutz++ (2026 Evolution)

Published April 1, 2026. Mandatory ~2028. Available on GitHub: `BSI-Bund/Stand-der-Technik-Bibliothek`.

| Dimension | Classic Grundschutz | Grundschutz++ |
|-----------|-------------------|---------------|
| Format | Static PDF | Machine-readable JSON (OSCAL 1.1.3) |
| Requirements | 6,567 sub-requirements | 985 consolidated (85% reduction) |
| Modules | 113 modules | 19 process practices |
| Release cycle | Annual | Agile/continuous via GitHub |
| Cross-references | Manual | Automated ISO 27001:2022 + NIS2 mappings |
| Coverage | Traditional IT | + Cloud, containers, Zero Trust, AI |

### Code-Level Checks

| # | Check | Module Ref |
|---|-------|------------|
| GS-01 | Patch management process documented and automated | OPS.1.1.3 |
| GS-02 | Cryptographic algorithms meet BSI TR-02102 standards | CON.1 |
| GS-03 | Backup concept with tested restore procedures | CON.3 |
| GS-04 | Network segmentation with firewall rules documented | NET.3.2 |
| GS-05 | Remote maintenance secured (VPN, MFA, logging) | OPS.1.2.5 |
| GS-06 | Incident detection and response procedures implemented | DER.1, DER.2.1 |
| GS-07 | Identity management with RBAC and least privilege | ORP.4 |
| GS-08 | Server hardening per SYS.1.1 baseline | SYS.1.1 |
| GS-09 | Client hardening per SYS.2.1 baseline | SYS.2.1 |
| GS-10 | Application security requirements for deployed software | APP.* |
| GS-11 | Protection needs classification applied to all assets | ISMS.1 |
| GS-12 | Grundschutz++ OSCAL catalog consumption for automated compliance | Grundschutz++ |

---

## KRITIS (Critical Infrastructure)

German IT Security Act 2.0 for critical infrastructure operators. Applies to operators exceeding sector-specific thresholds. Retained under NIS2UmsuCG as "critical facilities" with additional obligations.

### Sector Classification

| Sector | Threshold | Metric |
|--------|-----------|--------|
| Energy | 500,000 | People served |
| Water | 500,000 | People served |
| Food | 500,000 | People served |
| IT & Telecom | 500,000 | People served |
| Health | 30,000 | Full inpatient cases/year |
| Finance | 500,000 | Accounts or transactions |
| Transport | 500,000 | Passengers/year or cargo volume |
| Government | N/A | Federal administration facilities |

### Code-Level Checks

| # | Check | Requirement |
|---|-------|-------------|
| KR-01 | Attack detection systems (IDS/IPS) with security event correlation | SS8a(1a) BSIG |
| KR-02 | Incident reporting to BSI within 24 hours, automated alerting pipeline | SS8b BSIG |
| KR-03 | Documentation sufficient for BSI audit at any time | SS8a |
| KR-04 | Trusted sources verified, SBOM generated for all deployments | Supply chain |
| KR-05 | CVE scanning automated with documented patch timelines | Vulnerability mgmt |
| KR-06 | KRITIS systems isolated via network segmentation, micro-segmentation | Network |
| KR-07 | Air-gapped or immutable backups, ransomware-resistant | Backup isolation |
| KR-08 | Least privilege service accounts, no shared admin credentials | Minimum privilege |
| KR-09 | SBOM generation and maintenance for all deployed software | Supply chain security |
| KR-10 | Registered security contact with BSI, verified annually | SS8b(3) BSIG |
| KR-11 | Biennial security audit per SS8a, results reported to BSI | SS8a(3) BSIG |
| KR-12 | KRITIS sector registration and threshold verification completed | SS8d BSIG |

---

## NIS2UmsuCG (German NIS2 Transposition)

In force December 6, 2025. No transition period. Dramatically expands scope from ~4,500 to ~29,000 entities.

### Scope Expansion

| Dimension | KRITIS (old) | NIS2UmsuCG (new) |
|-----------|-------------|-------------------|
| Entities | ~4,500 | ~29,000 |
| Sectors | 7 | 14 |
| Threshold | Infrastructure-based | Size-based (50 FTE or EUR 10M) |

### 14 Sectors

**Annex 1 (Sectors of High Criticality):** Energy, Transport, Finance, Health, Water, Digital Infrastructure, Space

**Annex 2 (Other Critical Sectors):** Postal, Waste, Chemicals, Food, Manufacturing, Digital Services, Research

### Entity Types

| Type | Size Threshold | Penalty Cap |
|------|---------------|-------------|
| Essential | >= 250 FTE or > EUR 50M turnover | EUR 10M or 2% global turnover |
| Important | >= 50 FTE or > EUR 10M turnover | EUR 7M or 1.4% global turnover |
| Critical facility | KRITIS thresholds (retained) | KRITIS + NIS2 obligations combined |

### Incident Reporting Timeline

| Phase | Deadline | Content |
|-------|----------|---------|
| Initial notification | 24 hours | Incident detected, basic facts |
| Follow-up report | 72 hours | Initial assessment, severity, cross-border impact |
| Final report | 1 month | Root cause, mitigation, lessons learned |

### Registration

BSI registration required within 3 months. Portal opened January 6, 2026.

### Code-Level Checks

| # | Check | NIS2 Ref |
|---|-------|----------|
| N2-01 | Risk analysis and security policies for information systems | SS30(2) |
| N2-02 | Incident handling with 24h initial reporting capability | SS32 |
| N2-03 | Business continuity and crisis management plans | SS30(2) |
| N2-04 | Supply chain security with vendor assessment | SS30(2) |
| N2-05 | Vulnerability management and disclosure procedures | SS30(2) |
| N2-06 | Cybersecurity hygiene training documented | SS30(2) |
| N2-07 | Encryption and cryptography policies implemented | SS30(2) |
| N2-08 | Multi-factor authentication and secure communications | SS30(2) |
| N2-09 | Attack detection system deployed (KRITIS operators only) | BSI Act |

---

## Framework Interaction Matrix

| Pair | Relationship |
|------|-------------|
| Grundschutz <> NIS2 | Grundschutz accepted as NIS2 implementation methodology |
| Grundschutz <> C5 | C5 built on Grundschutz; Grundschutz is broader foundation (C5 in `sovereign-cloud-data-residency.md`) |
| NIS2 <> KRITIS | NIS2 expands scope; KRITIS retained for critical facilities with additional obligations |
| All three <> ISO 27001 | Grundschutz certification path to ISO 27001; NIS2 recognizes ISO 27001 as implementation evidence |
| NIS2 <> DORA | DORA is lex specialis for financial entities; see [financial-resilience-de-eu.md](financial-resilience-de-eu.md) |

---

## Common Violations in Reviews

| Violation | Where It Hides | Detection |
|-----------|---------------|-----------|
| Missing SBOM | Build pipeline, no CycloneDX/SPDX output | Check CI/CD configs for SBOM generation step |
| No incident reporting endpoint | Missing BSI notification webhook/integration | Grep for BSI reporting URLs or alerting pipelines |
| Shared admin credentials | Terraform/helm secrets, service accounts | Check for `shared-*` or generic admin usernames |
| Unpatched dependencies | No automated CVE scanning in CI | Check for Trivy/Grype/Snyk in pipeline |
| No network segmentation | Flat network, no firewall rules | Check network policies, security groups, firewall configs |
| Missing Grundschutz classification | Assets without Schutzbedarf rating | Check asset inventory for protection needs tags |
| No MFA on remote maintenance | VPN or bastion without second factor | Check auth configs for remote access paths |
| Missing backup restore tests | Backup jobs exist but no restore verification | Check for restore test schedules or runbooks |
| No 24h alerting pipeline | Incident detection without timed escalation | Check alerting rules for SLA-based routing |
| Unregistered BSI contact | No security contact on file with BSI | Verify organizational BSI registration status |

---

## How to Use in Reviews

1. **Identify German/sovereign context** — SAP CC, German government, EU critical infrastructure, or entity meeting NIS2 size thresholds
2. **Apply Grundschutz baseline** for organizational security posture (all German institutional IT)
3. **Apply KRITIS checks** for critical infrastructure operators exceeding sector thresholds
4. **Apply NIS2 checks** for any entity with >= 50 FTE or >= EUR 10M turnover in covered sectors
5. **Report violations with specific check IDs** (GS-XX, KR-XX, N2-XX) for traceability
6. **Check application code AND infrastructure config** — Terraform, Helm, Docker Compose, CI/CD pipelines, network policies
7. **Cross-reference** `sovereign-cloud-data-residency.md` for BSI C5 and data residency checks
8. **Cross-reference** `compliance-checklists.md` for GDPR overlay requirements
