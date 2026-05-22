---
description: Severity tier framework, escalation criteria, 9-field escalation package, handoff protocol, after-hours procedure, 6-section use case lifecycle template, KPI definitions
---

# Incident Escalation

SOC incident response framework: severity tiers and SLAs, escalation criteria, 9-field package gate, handoff RACI, use case lifecycle, KPI definitions. Vendor-neutral; SLA defaults are configurable per organization.

> **Scope**: SOC escalation procedures, use case documentation, KPI measurement. Source basis: SOC incident response best practices.
> **Binding**: SLAs are organizational commitments tracked as KPIs.

---

## Severity Tiers and SLAs

Default tier framework. Configure SLA values per organizational commitments; the four-tier structure and escalation logic are stable.

| Severity | Description | Default Initial Response | Default Max Processing |
|----------|-------------|--------------------------|------------------------|
| Very High | Catastrophic / immediate / long-term damage. Suspected TP. Immediate IR notification. | 15 minutes | 1 hour |
| High | High-profile, immediate + mid-term damage to multiple services. Coordinate with security manager. | 30 minutes | 2 hours |
| Medium | Immediate damage to single service; potential to spread. Managed by service owner. | 1 hour | 8 hours |
| Low | Lower risk / impact. Follow runbooks at analyst discretion. | 2 hours | 24 hours |

**SLA breach is itself an escalation trigger**: delayed triage time or sustained high FP rate both meet escalation criteria.

---

## Escalation Criteria

Escalate when ANY of these conditions is met:

| Trigger | Description |
|---------|-------------|
| High or Critical severity | Business impact, data exfiltration, ransomware behavior, or known threat-actor TTPs |
| Confirmed/suspected CIA impact | Confidentiality, Integrity, or Availability threatened or compromised |
| Correlated multi-vector alerts | Lateral movement + privilege escalation indicators from multiple sources |
| SLA / KPI breach | Delayed triage, sustained high FP rate, failed containment within SLA window |
| Unresolvable / ambiguous scope | Analyst cannot determine impact, scope, or attribution without internal context |
| Forensic or legal requirement | HR, legal, or regulatory disclosure may be required |

**Alert becomes incident** when: confirmed CIA impact OR multiple correlated indicators suggest coordinated attack.

---

## 9-Field Escalation Package (Required)

All 9 fields are mandatory. Missing fields fail the QA gate and reduce escalation quality score.

| # | Field | Format / Notes |
|---|-------|----------------|
| 1 | Ticket ID + link | Ticket system URL |
| 2 | Alert summary + link | SIEM alert ID and OpenSearch Dashboards link |
| 3 | MITRE ATT&CK mapping | Technique ID (T####.###) + tactic + kill chain phase |
| 4 | Timeline of events | Chronological; first event → detection → current state |
| 5 | Investigation actions taken | Commands run, systems queried, remediation attempted |
| 6 | Initial impact analysis | Services affected, data potentially exposed, blast radius |
| 7 | Evidence artifacts | Log snippets, IPs, hashes, screenshots, query results |
| 8 | Containment recommendation | Specific action (block IP, revoke credential, isolate host) |
| 9 | 5 Ws | Who (actor), What (action), When (timestamp), Where (target), How (vector) |

### Validation checklist

```
[ ] Ticket ID present and linked
[ ] Alert ID + dashboard link present
[ ] MITRE technique ID (T####.###) specified
[ ] MITRE tactic category specified
[ ] Timeline spans first event → now
[ ] At least 2 investigation actions documented
[ ] Impact: affected service(s) named
[ ] At least 1 evidence artifact (log line, IP, hash)
[ ] Containment action specified or "no action recommended" stated
[ ] Who / What / When / Where / How all answered
```

Run this checklist mechanically before escalation submission — every field, every time.

---

## Handoff Protocol

Once escalation is accepted by internal stakeholders:

1. Internal incident manager **assumes ownership** of the case
2. Source SOC **continues supporting investigation** unless explicitly released
3. All updates documented in agreed system (ticketing platform)
4. Closure requires **formal confirmation from internal cybersecurity teams** — source SOC remains in support role

**Communication channels** are organization-specific. Document the on-call channel, the alert channel, and the case-management system in your runbook.

### RACI for escalation

| Activity | SOC Analyst | SOC IM | Internal Cybersecurity | Service Owner |
|----------|-------------|--------|------------------------|---------------|
| Alert Triage | R | S | A/C | I |
| Escalation | R | A | S/I | C |
| IR Coordination | I | R/A | C | C |
| KPI Reporting | S | R | A/C | I |

---

## After-Hours Escalation Procedure

For escalations outside standard hours:

1. Escalate via designated on-call channel (phone, ticketing system, chat)
2. Log the escalation attempt with timestamp
3. If no acknowledgement: retry until confirmation received
4. Owner of on-call list keeps contacts current

---

## Use Case Lifecycle Template (6 Sections)

Produce use case documentation in this structure for every new detection.

### Section 1: General Info

| Field | Value |
|-------|-------|
| Title | `{Attack Category} - {Specific Scenario}` |
| Unique ID | `{CATEGORY}-{SUBCATEGORY}-{TARGET}-{NNN}` (e.g., BRUTE-PWD-AUTH-001) |
| Version | Semver (1.0, 1.1, etc.) |
| Owner | Name + team |
| Status | Active / Under Review / Deprecated / Planned |
| Severity | Very High / High / Medium / Low |
| Tags | MITRE tactic, attack vector keywords |

### Section 2: Context

| Field | Value |
|-------|-------|
| Business Relevance | Why this detection matters to operations |
| MITRE Mapping | Tactic name (link to ATT&CK) |
| MITRE Technique | T-ID (link to specific technique) |
| Risk Mapping | Internal risk register item |
| Compliance Mapping | NIST CSF / ISO 27001 / regulatory control |

### Section 3: Outcomes

| Field | Value |
|-------|-------|
| Goal | What the detection prevents or detects |
| Link to Playbook | Runbook link (analysis + IR steps for Tier-1) |

### Section 4: Detection Logic

| Field | Value |
|-------|-------|
| Necessary Logs | Log sources required |
| Detection Methodology | Rule-based / Threshold-based / Anomaly-based / Correlation |
| Frequency | Monitor interval (e.g., every 5 minutes) |
| Link to Detection Rule | SIEM rule ID or repository link |
| Link to Filters | Allowlist / suppression filter links |

### Section 5: Continuous Improvement

| Field | Value |
|-------|-------|
| Expected KPIs | FP rate target, response-time link to SLA tier, re-run threshold |
| Last Review Date | ISO date |
| Next Review Date | ISO date (max 1 year out) |
| Retirement Criteria | Conditions under which this use case is deprecated |

### Section 6: Analyst Support

| Field | Value |
|-------|-------|
| Timeline Link | OpenSearch Dashboards link showing historical alerts |
| Case Links | Links to past incidents triggered by this detection |
| Vendor Documentation | Links to source / OS docs for affected log fields |

---

## Tier-1 vs Tier-2 SOC Workflow

| Activity | Tier-1 | Tier-2 |
|----------|--------|--------|
| Approach | Runbook-driven, structured | Deep-dive, unstructured |
| Scope | Triage, enrichment, initial categorization | Investigation, attribution, scoping |
| Output | Triaged alert (escalate / close / monitor) | Containment plan, root-cause analysis |
| Tools | Dashboards, runbook commands | Raw queries, forensic tools, threat intel |

A use case fails if its runbook does not give Tier-1 a clear escalate-or-close decision in <30 minutes.

---

## KPI Definitions and Measurement

| KPI | Definition | Measurement | Default Target |
|-----|-----------|-------------|----------------|
| Time to Detect (TTD) | Event occurrence → alert detection | `alert.triggered_at - event.first_seen` | Tier-dependent |
| Time to Respond (TTR) | Alert detection → first mitigation action | `first_action.timestamp - alert.triggered_at` | Within SLA window |
| Mean Time to Resolution (MTTR) | Detection → case closure | Mean of `(case.closed_at - alert.triggered_at)` | Track trend, reduce |
| False Positive Rate | % alerts closed as FP | `FP_count / total_alerts` per period | ≤ 10% per use case |
| Escalation Quality Score | % escalations meeting all 9-field QA standard | `complete_escalations / total_escalations` | ≥ 90% |
| Log Source Onboarding Rate | New log sources added per period | Count per sprint/month | Track vs. coverage roadmap |
| Use Case Improvement Rate | Rules created/improved per period | Count from rule change log | Track vs. gap analysis |

### KPI dashboard query (MTTR example)

```json
POST /siem-cases-*/_search
{
  "size": 0,
  "query": {
    "range": { "@timestamp": { "gte": "now-30d" } }
  },
  "aggs": {
    "mttr_stats": {
      "stats": {
        "script": {
          "source": "(doc['closed_at'].value.toInstant().toEpochMilli() - doc['detected_at'].value.toInstant().toEpochMilli()) / 60000",
          "lang": "painless"
        }
      }
    }
  }
}
```

---

## See Also

- `detection-engineering.md`: SIGMA authoring, detector creation, MITRE mapping
- `detection-safety-patterns.md`: Mapping errors and detector failure modes
