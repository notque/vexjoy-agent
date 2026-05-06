# Industry-Specific Compliance Reference

Sector-specific security and data protection standards beyond general frameworks. Extensible per vertical.

## TISAX (Trusted Information Security Assessment Exchange)

Automotive industry information security standard managed by ENX Association, based on VDA ISA questionnaire. Required by German OEMs (VW, BMW, Mercedes-Benz) for all suppliers handling sensitive information.

**Assessment Levels:**

| Level | Audit Type | Applies To |
|-------|-----------|------------|
| AL1 | Self-assessment only | Administrative/commercial info |
| AL2 | Remote document review by auditor | Sensitive technical info, development docs |
| AL3 | On-site audit + physical security checks | Physical prototypes, strictly confidential data |

**VDA ISA 6.0 Labels (Since April 2024):**
Old "Info High"/"Info Very High" replaced by Confidential, Strictly Confidential, new Availability label. Prototype Protection retained. Main language switched to English.

**Key Standards Referenced:** ISO/IEC 27001:2022, BSI-Grundschutz, NIST CSF, IEC 62443 (for OT)

**Code-Level Checks:**

| # | Check | ISA Ref |
|---|-------|---------|
| TX-01 | Secure coding guidelines enforced (input validation, secure libs) | A.8.28 |
| TX-02 | Code reviews include security review for vulnerabilities | A.8.28 |
| TX-03 | Data classification labels applied to all shared data | Info Classification |
| TX-04 | DLP controls prevent unauthorized data exfiltration | Data Protection |
| TX-05 | SIEM/security monitoring active and alerting | Security Monitoring |
| TX-06 | Prototype data access restricted with enhanced monitoring | Prototype Protection |
| TX-07 | Business continuity plan for IT services documented and tested | Continuity |
| TX-08 | Third-party/supplier security assessment completed | Supply Chain |

## How to Use in Reviews

1. Identify automotive context (OEM integration, supplier portal, prototype handling)
2. Determine required TISAX assessment level (AL1/AL2/AL3)
3. Apply checks relevant to the assessment level
4. Focus on prototype protection for AL3 reviews
5. Report violations with check IDs (TX-01 through TX-08)

Not every check applies to every PR. Focus on items relevant to the specific changes.

## Common Violations in Reviews

| Violation | Where It Hides | Detection |
|-----------|---------------|-----------|
| No data classification | Files/APIs without sensitivity labels | Check metadata, headers, documentation |
| Prototype data exposed | Test fixtures, staging environments | Grep for prototype-related data |
| Missing DLP | No outbound data controls | Check egress rules, API gateways |
| No supplier assessment | Third-party libs without security review | Check vendor assessment records |
| Weak code review | No security-specific review checklist | Check PR templates, review workflows |

## [Future] Healthcare (DiGAV / MDR)

German Digital Health Applications regulation + EU Medical Device Regulation.
To be added when healthcare vertical is needed.

## [Future] Energy (EnWG / IT-SiKat)

German Energy Industry Act + IT Security Catalog for energy operators.
To be added when energy vertical is needed.
