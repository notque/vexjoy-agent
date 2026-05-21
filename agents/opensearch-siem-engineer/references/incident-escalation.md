---
description: Severity tier table, escalation criteria, required escalation content, handoff protocol, after-hours procedure, use case lifecycle template, KPI definitions
---

# OpenSearch SIEM Incident Escalation

> **Scope**: SOC incident escalation procedures, severity SLAs, use case lifecycle documentation, and KPI measurement for SAP Cloud Infrastructure cyber defense operations. Source: SAP Cyber Defense Operations Concept (input-e.md).
> **Binding**: SLAs are contractual requirements, not guidelines.
> **Generated**: 2026-05-22

---

## Severity Tiers and SLAs

| Severity | Description | Initial Response | Max Processing |
|----------|-------------|------------------|----------------|
| Very High | Catastrophic/immediate/long-term damage. Suspected TP. Report to global IR immediately. | **15 minutes** | 1 hour |
| High | High-profile, immediate + mid-term damage to multiple services. Coordinate with SCI security manager. | **30 minutes** | 2 hours |
| Medium | Immediate damage to single service; potential to spread. Managed by supplier + service owner. No SCI SM notification required. | **1 hour** | 8 hours |
| Low | Lower risk/impact. Follow runbooks at analyst discretion. | **2 hours** | 24 hours |

**SLA breach is an escalation trigger**: delayed triage time or high FP rate both trigger escalation criteria.

---

## Escalation Criteria

Escalate when ANY of these conditions is met:

| Trigger | Description |
|---------|-------------|
| High or Critical severity | Business impact, data exfiltration, ransomware behavior, or known threat actor TTPs |
| Confirmed/suspected CIA triad impact | Confidentiality, Integrity, or Availability threatened or compromised |
| Correlated multi-vector alerts | Lateral movement + privilege escalation indicators from multiple sources |
| SLA/KPI breach | Delayed triage, high FP rate, failed containment within SLA window |
| Unresolvable/ambiguous scope | Analyst cannot determine impact, scope, or attribution without internal context |
| Forensic or legal requirement | HR, legal, or regulatory disclosure may be required |

**Alert becomes incident** when: confirmed CIA triad impact OR multiple correlated indicators suggest coordinated attack.

---

## Required Escalation Content (9 Fields)

All 9 fields are mandatory. Missing fields fail the QA gate and reduce escalation quality score.

| # | Field | Format / Notes |
|---|-------|----------------|
| 1 | Ticket ID + link | ServiceNow or Jira ticket URL |
| 2 | Alert summary + link | SIEM alert ID and OpenSearch Dashboards link |
| 3 | MITRE ATT&CK mapping | Technique ID (T1xxx.xxx) + tactic + kill chain phase |
| 4 | Timeline of events | Chronological; first event to detection to current state |
| 5 | Investigation actions taken | Commands run, systems queried, remediation attempted |
| 6 | Initial impact analysis | Services affected, data potentially exposed, blast radius |
| 7 | Evidence artifacts | Log snippets, IPs, hashes, screenshots, query results |
| 8 | Containment recommendation | Specific action (block IP, revoke credential, isolate host) |
| 9 | 5 Ws | Who (actor), What (action), When (timestamp), Where (target), How (vector) |

**Validation checklist before escalating:**

```
[ ] Ticket ID present and linked
[ ] Alert ID + dashboard link present
[ ] MITRE technique ID (T####.###) specified
[ ] MITRE tactic category specified
[ ] Timeline spans from first event to now
[ ] At least 2 investigation actions documented
[ ] Impact: affected service(s) named
[ ] At least 1 evidence artifact (log line, IP, hash)
[ ] Containment action specified or "no action recommended" stated
[ ] Who/What/When/Where/How all answered
```

---

## Handoff Protocol

Once escalation is accepted by internal stakeholders:

1. Internal incident manager **assumes ownership**
2. Supplier **continues supporting investigation** unless explicitly released by incident manager
3. All updates documented in agreed system (ServiceNow or Jira)
4. Closure requires **formal confirmation from internal cybersecurity teams**. Supplier does not self-close

**Support groups**: Defined in SNOW. Slack channel `#cc-user-sync-notifications` syncs current on-call person.

**RACI for escalation:**

| Activity | Supplier SOC Analyst | Supplier IM | Internal Cybersecurity | Service Owner |
|----------|---------------------|-------------|----------------------|---------------|
| Alert Triage | R | S | A/C | I |
| Escalation | R | A | S/I | C |
| IR Coordination | I | R/A | C | C |
| KPI Reporting | S | R | A/C | I |

---

## After-Hours Escalation Procedure

For escalations outside standard hours (09:00-17:00 CET):

1. Escalate via designated on-call channel (phone, ticketing system, Slack)
2. Log the escalation attempt with timestamp
3. If no acknowledgement: retry until confirmation received. Keep retrying until acknowledged
4. SAP is responsible for keeping on-call contact lists current

**After-hours channels**: `#cc-security-event-alerts`, on-call defined in `#cc-user-sync-notifications`

---

## Use Case Lifecycle Template (6 Sections)

Produce use case documentation in this structure for every new detection.

### Section 1: General Info

| Field | Value |
|-------|-------|
| Title | `{Attack Category} - {Specific Scenario}` |
| Unique ID | `{CATEGORY}-{SUBCATEGORY}-{TARGET}-{NNN}` (e.g., BRUTE-PWD-KEYSTONE-001) |
| Version | Semver (1.0, 1.1, etc.) |
| Owner | Name + team |
| Status | Active / Under Review / Deprecated / Planned |
| Severity | Very High / High / Medium / Low |
| Tags | MITRE tactic, attack vector keywords |

### Section 2: Context

| Field | Value |
|-------|-------|
| Business Relevance | Why this detection matters to SCI operations |
| MITRE Mapping | Tactic name (link to ATT&CK) |
| MITRE Technique | T-ID (link to specific technique) |
| Risk Mapping | Internal risk register item (e.g., R-IT-XX) |
| Compliance Mapping | NIST CSF / ISO 27001 / VS-NfD control |

### Section 3: Outcomes

| Field | Value |
|-------|-------|
| Goal | What the detection prevents or detects |
| Link to Playbook | Runbook link (analysis steps + IR steps for Tier-1) |

### Section 4: Detection Logic

| Field | Value |
|-------|-------|
| Necessary Logs | Log sources required (e.g., Keystone WSGI logs, network flow) |
| Detection Methodology | Rule-based / Threshold-based / Anomaly-based |
| Frequency | Monitor interval (e.g., every 5 minutes) |
| Link to Detection Rule | SIEM rule ID or GitHub link |
| Link to Filters | Allowlist/suppression filter links |

### Section 5: Continuous Improvement

| Field | Value |
|-------|-------|
| Expected KPIs | FP rate target, response time link to SLA tier, re-run threshold |
| Last Review Date | ISO date |
| Next Review Date | ISO date (max 1 year) |
| Retirement Criteria | Conditions under which this use case is deprecated |

### Section 6: Analyst Support

| Field | Value |
|-------|-------|
| Timeline Link | OpenSearch Dashboards link showing historical alerts |
| Case Links | Links to past incidents triggered by this detection |
| Vendor Documentation | Links to Keystone/OS docs for affected log fields |

---

## KPI Definitions and Measurement

| KPI | Definition | Measurement | Target |
|-----|-----------|-------------|--------|
| Time to Detect (TTD) | Event occurrence → alert detection | `alert.triggered_at - event.first_seen` | Depends on severity tier |
| Time to Respond (TTR) | Alert detection → first mitigation action | `first_action.timestamp - alert.triggered_at` | Within SLA window |
| Mean Time to Resolution (MTTR) | Detection → case closure | Mean of `(case.closed_at - alert.triggered_at)` | Track trend, reduce over time |
| False Positive Rate | % alerts closed as FP | `FP_count / total_alerts` per period | <= 10% per use case |
| Escalation Quality Score | % escalations meeting all 9-field QA standard | `complete_escalations / total_escalations` | >= 90% |
| Log Source Onboarding Rate | New log sources added to SIEM per period | Count per sprint/month | Track vs. coverage roadmap |
| Alert Use Case Improvement Rate | Rules improved or created per period | Count from rule change log | Track vs. detection gap analysis |

**KPI dashboard query (MTTR example):**

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
- `mapping-troubleshooting.md`: Mapping errors that block detector creation
