---
title: TCO Framework — Total Cost of Ownership for Build vs Buy Decisions
domain: build-vs-buy
level: 3
skill: build-vs-buy
---

# TCO Framework

> **Scope**: Total cost of ownership calculation templates, build vs buy decision scorecards, and migration cost models. Covers the first 3 years of a technology decision — the window where build vs buy trade-offs are most sensitive to get right.
> **Version range**: Framework-agnostic — applies to any software/SaaS/OSS adoption decision.
> **Generated**: 2026-04-09 — validate vendor pricing against current public pricing pages.

---

## Overview

The most common mistake in build vs buy is comparing purchase price to build cost. A SaaS that costs $500/month looks expensive next to "free to build." The analysis should compare 3-year total cost of ownership, including all hidden costs: engineering time to build and maintain, support burden, training, and opportunity cost of capacity consumed. Build almost always wins year 1 and loses years 2-3. The crossover point determines the decision.

---

## TCO Calculation Template

Fill this out for each option before any scoring. Use fully-loaded engineering cost (salary + benefits + overhead), typically 1.5-2× base salary.

### Option: [Name]

```
## Year 1 Costs

### Acquisition / Build
- Vendor license or SaaS contract: $___/month × 12 = $___
  OR
- Engineering hours to build: ___ hours × $___/hour = $___
- External integrations (APIs, connectors): $___
- Infrastructure setup (servers, CI/CD, config): $___

### Onboarding
- Training / learning curve: ___ hours × $___/hour = $___
- Data migration from existing system: ___ hours × $___/hour = $___
- Documentation and runbooks: ___ hours × $___/hour = $___

Year 1 Total: $___

## Year 2-3 Costs (Annual)

### Vendor (if SaaS)
- License at expected usage tier: $___/year
- Usage overages (estimate 20% buffer): $___/year
- Upgrade / tier increase: $___/year (if usage grows)

### Build (if internal)
- Maintenance and bug fixes: ___ hours/month × 12 × $___/hour = $___
- Infrastructure (hosting, monitoring, backups): $___/year
- Security patches and dependency updates: ___ hours/quarter × 4 × $___/hour = $___
- Feature additions (roadmap items): ___ hours/year × $___/hour = $___

Annual Year 2-3 Total: $___

## 3-Year TCO Summary

| | Year 1 | Year 2 | Year 3 | 3-Year Total |
|-|--------|--------|--------|--------------|
| Vendor | $__ | $__ | $__ | $__ |
| Build | $__ | $__ | $__ | $__ |
| OSS + Customize | $__ | $__ | $__ | $__ |
```

---

## Worked Example: Authentication System

Real-but-anonymized: 8-person engineering team evaluating whether to build auth or adopt Auth0.

```
## Auth0 (Buy SaaS)

Year 1:
- Auth0 B2C plan (25K MAU): $23/month × 12 = $276
- Integration engineering: 40 hours × $150/hour = $6,000
- Documentation: 8 hours × $150/hour = $1,200
Year 1 Total: $7,476

Year 2-3 (annual):
- Auth0 at 75K MAU: $240/month × 12 = $2,880
- Maintenance: 2 hours/month × 12 × $150 = $3,600
Annual: $6,480

3-Year Total: $7,476 + $6,480 + $6,480 = $20,436

## Build from scratch

Year 1:
- JWT auth library integration: 80 hours × $150 = $12,000
- OAuth2 implementation: 120 hours × $150 = $18,000
- MFA, password reset flows: 60 hours × $150 = $9,000
- Security review: 20 hours × $150 = $3,000
Year 1 Total: $42,000

Year 2-3 (annual):
- Security patches: 8 hours/quarter × 4 × $150 = $4,800
- Feature maintenance: 4 hours/month × 12 × $150 = $7,200
- Incident response (1-2 per year estimated): 16 hours × $150 = $2,400
Annual: $14,400

3-Year Total: $42,000 + $14,400 + $14,400 = $70,800
```

**Decision**: Auth0 saves $50,364 over 3 years. Engineering team's 260 hours freed up for product differentiators. Unless data residency requirements or offline-first constraints prevent it, buy wins clearly.

---

## Build vs Buy Decision Scorecard

Score each dimension 1-10, then calculate weighted total. Customize weights for your context.

| Dimension | Weight | Build | OSS + Customize | Buy SaaS | Notes |
|-----------|--------|-------|-----------------|----------|-------|
| Fit to requirements | 5× | ___ | ___ | ___ | Does it solve the actual problem? |
| 3-Year TCO | 4× | ___ | ___ | ___ | From TCO template above |
| Operational burden | 4× | ___ | ___ | ___ | Who runs it at 3 AM? |
| Team capability | 3× | ___ | ___ | ___ | Can we build/operate it? |
| Lock-in risk | 3× | ___ | ___ | ___ | How hard to switch? |
| Time to value | 3× | ___ | ___ | ___ | Weeks until operational |
| Flexibility | 2× | ___ | ___ | ___ | Future extensibility |
| **Weighted Total** | **24×** | **___** | **___** | **___** | |

**Fit scoring guide**:
- 9-10: Solves the problem exactly, no meaningful gaps
- 7-8: Solves the problem with minor workarounds (< 5% of use cases affected)
- 5-6: Solves 70-80% of the problem, significant gaps need custom work
- 3-4: Covers the core but misses important edge cases
- 1-2: Wrong tool for the job

---

## Migration Cost Model

Run this when switching from existing solution to evaluate true total cost. Often reveals that migration cost exceeds the savings from the new option.

```
## Migration Cost Estimate

### Data Migration
- Schema mapping and transformation: ___ hours × $___/hour = $___
- Data validation and reconciliation: ___ hours × $___/hour = $___
- Historical data migration (one-time): ___ hours × $___/hour = $___

### Integration Rewiring
- API client updates (per integration): ___ integrations × ___ hours × $___/hour = $___
- Webhook reconfiguration: ___ hours × $___/hour = $___
- Auth/credential rotation: ___ hours × $___/hour = $___

### Risk and Buffer
- Rollback capability (maintain old system in parallel): ___ months × $___/month = $___
- Incident response during cutover: ___ hours × $___/hour = $___
- Buffer for unexpected complexity (add 30%): $___

Migration Total: $___
Months until break-even (savings from new system per month): ___
Break-even: ___ months
```

**Rule**: If break-even is over 24 months, the migration is marginal. If break-even is over 36 months, the migration likely destroys value — reconsider.

---

## Hidden Cost Checklist

Before finalizing TCO, confirm you have accounted for:

```
[ ] Vendor price escalation risk (SaaS prices increase 10-15% annually on average)
[ ] Usage overages (most SaaS tools have surprise usage-based tiers)
[ ] Security and compliance costs (SOC 2, GDPR compliance on vendor side — who bears audit costs?)
[ ] Contract lock-in (annual vs monthly pricing — is the discount worth the commitment?)
[ ] Support tier costs (enterprise support is often 20-25% of license cost)
[ ] Training time per new hire (ongoing, not just initial onboarding)
[ ] Integration maintenance (third-party integrations break when vendors change APIs)
[ ] Sunset risk (vendor acquisition, product discontinuation, pricing regime change)
[ ] Data export capability (can you get your data back in a usable format if you leave?)
[ ] Opportunity cost: what won't get built while this is under development/integration?
```

---

## Anti-Patterns

### Comparing development cost to license cost
**What it looks like**: "Auth0 costs $2,880/year. We can build it for free."
**Why wrong**: "Free to build" ignores 120+ engineering hours, security maintenance, incident response, and opportunity cost. The license is year 2+ maintenance savings, not just year 1 build savings.
**Fix**: Always run the 3-year TCO template. If the comparison is still in favor of building after year 2-3 costs are included, building may be right.

### Underestimating maintenance burden
**What it looks like**: Year 2 estimate shows zero hours for maintenance on custom-built system.
**Why wrong**: Every system has dependencies that release updates. Security vulnerabilities require patches. Load characteristics change. Features accumulate bugs over time. 10-20% of initial build effort per year is the historical baseline.
**Detection**: If Year 2 internal maintenance estimate is less than 10% of Year 1 build estimate, it is too optimistic.
**Fix**: Use 15% of Year 1 build cost as minimum Year 2-3 annual maintenance baseline. Adjust up if the system is complex.

### TCO without usage growth modeling
**What it looks like**: SaaS cost calculated at current usage (100 users), not at expected usage in year 3 (1,000 users).
**Why wrong**: Many SaaS platforms have non-linear pricing. What looks affordable at 100 users can be prohibitive at 1,000. The opposite is also true — build costs are largely fixed.
**Fix**: Model three usage scenarios: current, 3× growth, 10× growth. Pick the option that remains affordable across all three plausible scenarios.

---

## See Also

- `vendor-evaluation.md` — vendor scorecards, RFP criteria, integration complexity scoring
- `skills/project-evaluation/references/roi-frameworks.md` — ROI calculation and risk-adjusted analysis
