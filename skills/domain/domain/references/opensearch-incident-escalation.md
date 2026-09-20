# SOC escalation contract

Severity sets the initial-response / maximum-processing SLA:

| Severity | Initial | Maximum |
|---|---:|---:|
| Very High | 15 min | 1 h |
| High | 30 min | 2 h |
| Medium | 1 h | 8 h |
| Low | 2 h | 24 h |

Escalate for high/critical impact, suspected CIA impact, correlated multi-vector activity, SLA breach, unresolved scope, or forensic/legal need.

Every handoff contains all nine fields:

1. ticket ID/link;
2. alert ID and Dashboards link;
3. MITRE technique ID, tactic, and kill-chain phase;
4. chronological timeline;
5. investigation actions;
6. impact and blast radius;
7. evidence artifacts;
8. concrete containment recommendation;
9. who/what/when/where/how.

Very High pages incident response immediately; after hours use the on-call path and record acknowledgment. Tier 1 triages/enriches and decides close/monitor/escalate; Tier 2 investigates, attributes, scopes, and proposes containment.

Track TTD (first event to alert), TTR (alert to first mitigation), MTTR (alert to closure), false-positive rate, and nine-field completeness. Local targets are FP ≤10% per use case and escalation completeness ≥90%.
