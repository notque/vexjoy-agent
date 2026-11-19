# Financial Resilience Reference — DORA & German Banking IT Compliance

Requirements for systems in financial services, banking, insurance, and payment processing. Code-level checks for PR reviews.

## DORA (Digital Operational Resilience Act)

EU regulation for the financial sector. In force **January 17, 2025**. Supersedes German BAIT. Applies to 21 entity categories including banks, insurers, payment providers, crypto-asset service providers, and ICT third-party providers.

**Five Pillars**: ICT Risk Management (board accountability) → Incident Reporting (4h after major classification) → Resilience Testing (annual + TLPT/3y) → Third-Party Risk (provider register + SLAs) → Information Sharing (threat intelligence)

### Testing Requirements

| Test | Frequency | Scope |
|------|-----------|-------|
| Vulnerability scans | Annual | All systems |
| Penetration testing | Annual | Critical systems |
| Scenario-based | Annual | Threat simulation |
| TLPT (Red Team) | Every 3 years | Live production, TIBER-EU framework |
| Source code analysis | Part of resilience testing | Key applications |

### Penalties

DORA Art. 50 delegates penalty-setting to member states. Maximum penalties vary by jurisdiction:

- **Entity (typical member state cap)**: up to EUR 10M or 2% of annual turnover (varies by member state; verify applicable jurisdiction)
- **Critical ICT third-party providers**: periodic penalty up to 1% of average daily worldwide turnover (Art. 35)
- **Individual manager**: up to EUR 1M (varies by member state)

> **Note**: Verify the specific penalty regime in the applicable member state. The figures above are representative caps, not harmonized EU-wide amounts.

### Code-Level Checks

| # | Check | DORA Article |
|---|-------|-------------|
| DO-01 | ICT risk management framework with board-level accountability | Art. 5-6 |
| DO-02 | ICT asset inventory maintained and classified | Art. 8 |
| DO-03 | ICT incident detection and classification; initial notification within 4 hours of classifying as major (or 24h from detection, whichever earlier) | Art. 17-19 |
| DO-04 | Vulnerability scanning at minimum annually | Art. 24-25 |
| DO-05 | Penetration testing at minimum annually | Art. 24-25 |
| DO-06 | TLPT on live production every 3 years (significant entities) | Art. 26 |
| DO-07 | Source code review as part of resilience testing | Art. 25 |
| DO-08 | ICT third-party register with SLAs, audit rights, exit strategies | Art. 28-30 |
| DO-09 | ICT service continuity and recovery plans tested | Art. 11-12 |
| DO-10 | Cyber threat intelligence sharing mechanism | Art. 45 |

## KWG / MaRisk (Post-BAIT Transition)

### Regulatory Stack (2025)

| Regulation | Status |
|-----------|--------|
| KWG (Banking Act) | In force — organizational requirements (§25a) |
| MaRisk | In force — non-ICT risk management remains |
| BAIT | Repealed Jan 17, 2025 for DORA-subject entities |
| DORA | In force — supersedes BAIT for ICT risk |

**Exception**: BAIT remains applicable for leasing/factoring companies until **December 31, 2026**.

MaRisk still governs: AT 7.2 (tech/org resources, supplemented by DORA for ICT), AT 7.3 (business continuity), overall risk strategy/governance.

### Residual Checks (Post-DORA)

| # | Check | Regulation |
|---|-------|-----------|
| BF-01 | User authorization management with regular access reviews | MaRisk AT 7.2 |
| BF-02 | IT emergency management documented and tested | MaRisk AT 7.3 |
| BF-03 | Change management process for all ICT systems | MaRisk/DORA overlap |

## DORA ↔ NIS2 Interaction

Both apply to the financial sector. DORA is **lex specialis** — it takes precedence for financial entities. If an entity is both NIS2-subject and financial, DORA's ICT requirements apply instead of NIS2's cybersecurity requirements. NIS2 incident reporting still applies in parallel.

## How to Use in Reviews

1. Identify financial services context (banking, insurance, payment, crypto)
2. Apply DORA checks (DO-01 through DO-10) for all financial entities
3. Apply MaRisk residual checks (BF-01 through BF-03) for non-ICT risk areas
4. Check both application code AND infrastructure config
5. Report violations with specific check IDs and article references
6. Note: DORA requires source code review as part of formal resilience testing (DO-07)

## Cross-References

- [german-it-security.md](german-it-security.md) — NIS2UmsuCG checks (DORA is lex specialis for financial entities; NIS2 incident reporting still applies in parallel)
- [sovereign-cloud-data-residency.md](sovereign-cloud-data-residency.md) — BSI C5 and data residency for sovereign cloud deployments
- [compliance-checklists.md](compliance-checklists.md) — GDPR, SOC 2, PCI-DSS, HIPAA overlay checks

## Common Violations in Reviews

| Violation | Where It Hides | Detection |
|-----------|---------------|-----------|
| No ICT asset inventory | Missing CMDB or asset register | Check for asset management config |
| Missing incident classification | No severity taxonomy in alerting | Check alerting rules and runbooks |
| No third-party register | Vendor/SaaS list not maintained | Check procurement/vendor configs |
| Source code not in scope of resilience testing | Testing only covers infrastructure | Check test plans for code analysis |
| No exit strategy for ICT providers | Vendor contracts without exit clauses | Review vendor agreement templates |
