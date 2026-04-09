---
title: Vendor Evaluation — Scorecards, RFP Criteria, Integration Complexity
domain: build-vs-buy
level: 3
skill: build-vs-buy
---

# Vendor Evaluation Reference

> **Scope**: Vendor evaluation scorecards, RFP criteria matrices, integration complexity scoring, and red flag detection for technology vendor decisions. Use when comparing 2+ vendors or when a buy decision has been made and vendor selection is the next step.
> **Version range**: Framework-agnostic — validate vendor-specific claims against current documentation.
> **Generated**: 2026-04-09 — SaaS market conditions change; re-run vendor evaluation annually for active contracts.

---

## Overview

Vendor evaluation fails most often by comparing features instead of evaluating fitness for a specific context. A vendor with 400 features that does not integrate with your existing auth stack is worse than one with 50 features that drops in cleanly. This reference structures evaluation around the dimensions that determine whether a vendor relationship succeeds over 2-3 years, not just at time of purchase.

---

## Vendor Evaluation Scorecard

Score each vendor 1-10 per dimension. Fill independently before comparing scores with the team.

| Dimension | Weight | Vendor A | Vendor B | Vendor C | Scoring Guide |
|-----------|--------|----------|----------|----------|---------------|
| Functional fit | 5× | ___ | ___ | ___ | Does it solve the actual problem without significant workarounds? |
| Integration complexity | 4× | ___ | ___ | ___ | Hours to connect to existing stack (10 = <8 hrs, 1 = weeks) |
| Support quality | 4× | ___ | ___ | ___ | Response time SLA, escalation path, community vs. dedicated |
| Pricing model fit | 3× | ___ | ___ | ___ | Predictability as usage grows; alignment with your cost model |
| Data ownership / portability | 3× | ___ | ___ | ___ | Can you export your data in a usable format? |
| Security / compliance | 3× | ___ | ___ | ___ | SOC 2, GDPR, HIPAA — do their certifications match your requirements? |
| Company stability | 3× | ___ | ___ | ___ | Funding, revenue growth, customer retention signals |
| API quality | 2× | ___ | ___ | ___ | REST/GraphQL maturity, rate limits, webhook reliability |
| Roadmap alignment | 2× | ___ | ___ | ___ | Are upcoming features useful to you? Direction of travel? |
| Onboarding quality | 1× | ___ | ___ | ___ | Docs, sandbox, getting-started experience |
| **Weighted Total** | **30×** | **___** | **___** | **___** | |

**Interpretation**: 80%+ of max (240+): strong fit. 60-79% (144-191): acceptable with known gaps. Below 60%: reconsider.

---

## RFP Criteria Matrix

Use this when issuing a formal RFP to 3+ vendors. Structure requirements as MUST/SHOULD/NICE for objective comparison.

### Requirements Classification

| Requirement | Priority | Vendor A | Vendor B | Vendor C | Notes |
|-------------|----------|----------|----------|----------|-------|
| **MUST HAVE (eliminators)** | | | | | |
| SSO/SAML support | MUST | Pass/Fail | Pass/Fail | Pass/Fail | |
| EU data residency | MUST | Pass/Fail | Pass/Fail | Pass/Fail | |
| 99.9% uptime SLA | MUST | Pass/Fail | Pass/Fail | Pass/Fail | |
| [Your hard requirement] | MUST | Pass/Fail | Pass/Fail | Pass/Fail | |
| **SHOULD HAVE (differentiators)** | | | | | |
| Webhook retry on failure | SHOULD | 1-5 | 1-5 | 1-5 | |
| Role-based access control | SHOULD | 1-5 | 1-5 | 1-5 | |
| Audit logging | SHOULD | 1-5 | 1-5 | 1-5 | |
| Custom domain support | SHOULD | 1-5 | 1-5 | 1-5 | |
| **NICE TO HAVE (tie-breakers)** | | | | | |
| Slack integration | NICE | Yes/No | Yes/No | Yes/No | |
| Mobile SDK | NICE | Yes/No | Yes/No | Yes/No | |

**Process**: Eliminate any vendor failing a MUST. Score SHOULD items 1-5. NICE items break ties only.

---

## Integration Complexity Scoring

Run this before scorecard scoring. Integration complexity is chronically underestimated and frequently causes "buy" decisions to cost as much as "build."

| Integration Point | Effort Level | Score (10=easy) | Notes |
|-------------------|-------------|-----------------|-------|
| Auth (SSO, OAuth2, SAML) | Low / Medium / High | ___ | Does vendor support your identity provider? |
| Data ingestion (API, ETL, webhook) | Low / Medium / High | ___ | Format compatibility, rate limits, batch support |
| Data export / sync | Low / Medium / High | ___ | Webhook vs. polling, data freshness requirements |
| User provisioning (SCIM, manual) | Low / Medium / High | ___ | Automated vs. manual user management |
| Billing / payment integration | Low / Medium / High | ___ | If applicable — does it plug into your billing system? |
| Reporting / BI integration | Low / Medium / High | ___ | Data warehouse export, native analytics gaps |
| Existing tools / workflow | Low / Medium / High | ___ | Slack, Jira, PagerDuty, internal tools |

**Effort level definitions**:
- **Low**: Works out of the box or < 8 engineering hours. Standard OAuth2, documented webhooks, stable API.
- **Medium**: 1-3 weeks of engineering time. Custom adapter needed, unstable API, limited documentation.
- **High**: 1+ months, may require professional services. Non-standard auth, batch-only data access, custom ETL.

**Integration total effort estimate**:
```
Low (×8 hrs each): ___ items × 8 = ___ hrs
Medium (×40 hrs each): ___ items × 40 = ___ hrs
High (×160 hrs each): ___ items × 160 = ___ hrs
Total: ___ hrs × $___/hr = $___
```

---

## Red Flag Detection

Run this against every finalist vendor. One critical flag = disqualify. Multiple moderate flags = negotiate contract protections.

### Critical Red Flags (disqualify immediately)

```
[ ] No data export capability (you cannot get your data back in a usable format)
[ ] Arbitration-only contract with no class action (legal risk)
[ ] No uptime SLA or SLA with credits that don't cover your actual downtime cost
[ ] "We'll add that feature" promises not in contract (vaporware negotiation)
[ ] Pricing not disclosed publicly — only available after sales call (predatory pricing)
[ ] No SOC 2 Type II when you have compliance requirements
```

### Moderate Red Flags (negotiate mitigations)

```
[ ] Single data center with no failover option
[ ] Support is email-only with 48-hour SLA (no phone/chat for critical issues)
[ ] Annual contract required at outset with no monthly trial
[ ] API rate limits that would be hit at your scale (check their public docs, not sales promises)
[ ] Changelog is sparse or months out of date (signals low development velocity)
[ ] LinkedIn shows large support/sales team but small engineering team (feature growth will stall)
[ ] G2/Capterra reviews mention recurring billing problems or difficult cancellation
[ ] GitHub issues (if OSS component) show months-old bugs unaddressed
```

### Vendor Stability Signals

| Signal | Positive | Negative |
|--------|----------|----------|
| Funding | Series B+ or profitable/bootstrapped | Seed-only with no clear path |
| Revenue transparency | Published ARR or customer count growth | No public metrics |
| Customer retention | Publicly cited NRR > 100% | Churn not discussed |
| Engineering velocity | Regular releases, active changelog | Releases monthly or less |
| Enterprise customers | Named enterprise customers in same industry | Only SMB references |

---

## Contract Negotiation Checklist

Before signing any vendor contract over $10K/year:

```
[ ] SLA with financial penalties (not just service credits)
[ ] Data portability clause: export in standard format within 30 days of termination
[ ] Price cap on renewals (e.g., "increases capped at CPI or 5%, whichever is lower")
[ ] Termination for convenience clause (can you leave with 30-day notice?)
[ ] Service level agreement for support response (not just "best effort")
[ ] Data deletion timeline after contract ends (GDPR-critical)
[ ] Audit rights if handling sensitive data
[ ] Subprocessor notification (you must be notified if they change data processors)
```

---

## Anti-Patterns

### Buying based on demo, not hands-on trial
**What it looks like**: Sales demo shows everything working perfectly, contract signed, integration begins, and a different reality emerges.
**Why wrong**: Demos are curated. Integration complexity, actual API reliability, and support quality only reveal themselves in practice.
**Fix**: Require a proof-of-concept (POC) period with a representative integration task before committing to annual contract. "We need to complete integration milestone X before we commit" is a reasonable ask for any serious vendor.

### Evaluating current feature set, not roadmap direction
**What it looks like**: Vendor has 9/10 of features needed today. Missing 1 feature is "on the roadmap."
**Why wrong**: "On the roadmap" has no SLA. Features promised in sales negotiations are not features in contracts.
**Fix**: Ask to see the public changelog and last 4 release notes. If the velocity is high and roadmap direction matches your needs, that is more reliable than verbal promises. Require a contract addendum for features that are decision-critical.

### Evaluating one vendor at a time (serial evaluation)
**What it looks like**: Full evaluation of Vendor A, then if not satisfied, evaluate Vendor B.
**Why wrong**: Serial evaluation introduces time pressure at Vendor B. You may sign with B because you are tired of evaluating, not because B is the best option.
**Fix**: Run parallel evaluations with 2-3 vendors simultaneously using the same RFP criteria. Takes more coordination but produces better decisions.

---

## Detection Commands Reference

```bash
# Check vendor API rate limits (if REST API)
curl -I https://api.vendor.com/v1/some-endpoint 2>&1 | grep -i "x-ratelimit"

# Check vendor uptime history
# (Manual: visit statuspage.io/<vendor> or status.<vendor>.com)

# Check GitHub activity for OSS components
curl -s "https://api.github.com/repos/{owner}/{repo}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Stars:', d['stargazers_count'])
print('Last push:', d['pushed_at'])
print('Open issues:', d['open_issues_count'])
"
```

---

## See Also

- `tco-framework.md` — TCO calculation templates and build vs buy decision scorecard
- `skills/build-vs-buy/SKILL.md` — full evaluation workflow with dimension weights
