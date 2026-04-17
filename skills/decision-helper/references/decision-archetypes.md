# Decision Archetypes Reference

> **Scope**: Common tech decision categories with domain-specific criteria weight adjustments and hard-constraint checklists. Does not cover non-technical decisions (hiring, content strategy).
> **Version range**: All versions of decision-helper skill
> **Generated**: 2026-04-16

---

## Overview

Most tech decisions fall into one of six archetypes. Default criteria weights (Correctness 5, Complexity 3, Maintainability 3, Risk 3, Effort 2, Familiarity 2, Ecosystem 1) are calibrated for general architectural choices. Each archetype below adjusts weights to reflect what actually drives outcome quality for that decision type.

Apply these adjustments BEFORE scoring — weight changes after seeing scores are confirmation bias.

---

## Archetype Table

| Archetype | Boost Weights | Lower Weights | Primary Eliminator |
|-----------|--------------|---------------|-------------------|
| Build vs. Buy | Risk +1, Maintainability +1 | Effort -1, Familiarity -1 | License compatibility |
| Database selection | Risk +1, Ecosystem +1 | Effort -1, Familiarity -1 | Data model fit |
| Cloud/Infra provider | Risk +2, Ecosystem +1 | Complexity -1, Maintainability -1 | Compliance requirements |
| Framework/library | Maintainability +1, Ecosystem +1 | Effort -1 | Last commit >2yr or archived |
| API design | Correctness +1, Maintainability +1 | Familiarity -1, Ecosystem -0 | Breaking change risk to consumers |
| Operational tooling | Familiarity +1, Risk +1 | Ecosystem -1 | Team operational capacity |

---

## Build vs. Buy

**When it applies**: Replacing or adding a capability that vendors sell as products (auth, search, email, monitoring, billing).

**Hard constraints — apply first, eliminate non-starters**:
- Does the vendor support your data residency requirements?
- Is the vendor's license compatible with your distribution model?
- Is the vendor's pricing sustainable at your projected scale?

**Adjusted criteria**:

| Criterion | Default | Build-vs-Buy | Rationale |
|-----------|---------|-------------|-----------|
| Correctness | 5 | 5 | Unchanged |
| Risk | 3 | 4 | Vendor lock-in and service reliability are long-term risks |
| Maintainability | 3 | 4 | Ownership cost is the central question |
| Complexity | 3 | 3 | Unchanged |
| Ecosystem | 1 | 2 | Vendor community health predicts longevity |
| Familiarity | 2 | 1 | Team can learn a tool; they can't easily escape a vendor |
| Effort | 2 | 1 | One-time cost; less important than ongoing ownership |

**Scoring note**: For "Buy" options, score Maintainability based on what happens when the vendor changes pricing or API. Score Risk based on migration path if vendor is acquired or discontinued.

---

## Database Selection

**When it applies**: Choosing a primary data store, adding a secondary store, or replacing an existing one.

**Hard constraints — apply first**:
- Does the workload require transactions across multiple entities? (eliminates most eventually-consistent stores)
- What's the required query pattern: key-value lookups, graph traversal, full-text search, time-series?
- Does the team have operational capacity for this engine in production?

**Adjusted criteria**:

| Criterion | Default | DB-Selection | Rationale |
|-----------|---------|-------------|-----------|
| Correctness | 5 | 5 | Data model fit is non-negotiable |
| Risk | 3 | 4 | Data loss scenarios carry outsized consequence |
| Complexity | 3 | 3 | Operational complexity matters long-term |
| Maintainability | 3 | 3 | Unchanged |
| Ecosystem | 1 | 2 | Driver quality, backup tooling, observability integrations matter |
| Effort | 2 | 2 | Unchanged |
| Familiarity | 2 | 1 | Database expertise transfers; don't over-weight team comfort |

**Scoring note**: Score Correctness specifically on data model fit, not just whether data can be stored. Forcing relational data into a document store scores 4 at best, not 7.

---

## Cloud / Infrastructure Provider

**When it applies**: Choosing a cloud provider, managed service, or infrastructure platform.

**Hard constraints — apply first**:
```bash
# Check compliance requirements that may eliminate providers immediately
# (SOC2, HIPAA, FedRAMP, GDPR residency)
# Verify against provider compliance pages before scoring
```

**Adjusted criteria**:

| Criterion | Default | Cloud | Rationale |
|-----------|---------|-------|-----------|
| Correctness | 5 | 5 | Feature availability (managed services needed) |
| Risk | 3 | 5 | Egress costs, lock-in, and regional outage exposure are critical |
| Familiarity | 2 | 3 | Migration from a known platform has a real productivity floor |
| Ecosystem | 1 | 2 | Managed service breadth reduces operational burden |
| Maintainability | 3 | 2 | Managed services shift maintenance to provider |
| Complexity | 3 | 2 | Cloud providers abstract operational complexity by design |
| Effort | 2 | 2 | Unchanged |

---

## Framework / Library Selection

**When it applies**: Choosing a web framework, ORM, testing library, or major dependency.

**Hard constraints — apply first**:
```bash
# Check project activity — last commit >2 years is a yellow flag, archived = eliminate
gh repo view {org}/{repo} --json pushedAt,isArchived,stargazerCount

# Check license compatibility with your project
cat {candidate}/LICENSE 2>/dev/null || grep -i license {candidate}/package.json {candidate}/go.mod 2>/dev/null
```

**Adjusted criteria**:

| Criterion | Default | Framework | Rationale |
|-----------|---------|-----------|-----------|
| Correctness | 5 | 5 | Must actually solve the problem |
| Maintainability | 3 | 4 | Framework-imposed patterns lock in for years |
| Ecosystem | 1 | 2 | Active contributors, plugins, community answers predict longevity |
| Risk | 3 | 3 | Unchanged |
| Complexity | 3 | 3 | Unchanged |
| Familiarity | 2 | 2 | Unchanged |
| Effort | 2 | 1 | One-time learning cost; deprioritize |

---

## API Design

**When it applies**: Choosing between REST/GraphQL/gRPC, versioning strategies, or auth schemes for a new or evolving API.

**Hard constraints — apply first**:
- Who are the consumers? External third-party developers, internal mobile clients, and internal services have different requirements.
- Is this replacing an existing API? Breaking changes need explicit migration paths before scoring begins.

**Adjusted criteria**:

| Criterion | Default | API-Design | Rationale |
|-----------|---------|-----------|-----------|
| Correctness | 5 | 6 | Getting the contract wrong requires breaking changes to fix |
| Maintainability | 3 | 4 | API surface area grows; backward compatibility is costly to retrofit |
| Risk | 3 | 3 | Unchanged |
| Complexity | 3 | 3 | Unchanged |
| Effort | 2 | 2 | Unchanged |
| Ecosystem | 1 | 1 | Unchanged |
| Familiarity | 2 | 1 | API consumers span teams; internal familiarity matters less |

---

## Sensitivity Analysis Pattern

When top two options are within 0.5 weighted score, run sensitivity analysis before declaring a close call:

```
1. Identify the two highest-weight criteria (typically Correctness + one other)
2. Ask: "If I'm wrong about {winner}'s score on {top criterion} — what if it's 6 instead of 8?"
3. Recalculate. If winner changes: genuinely close, more investigation needed.
4. If winner holds under pessimistic scoring: high-confidence recommendation despite close scores.
```

**When NOT to apply**: Sensitivity analysis is for close calls, not fishing for a preferred outcome. If the winner is already clear (margin >0.5), skip this step.

---

## See Also

- `decision-anti-patterns.md` — Behavioral failure modes in scoring and framing
