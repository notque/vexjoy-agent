---
summary: "Record form a human fills when retiring a skill or agent."
read_when:
  - "retiring a skill or agent"
---

# Deprecation Template

A short record a human copies when retiring a skill or agent. The
`stale-skill-scan.py` report proposes candidates; a person owns the retirement
decision and writes this record.

## Record form

Copy this block, fill it in, and keep it with the change that removes the
component.

```markdown
# Deprecation: <component-name>

- **Kind:** skill | agent
- **Date:** YYYY-MM-DD
- **Reason:** <one line — model improved, redundant with X, never routed>
- **Replacement:** <skill/agent name, or "none — capability dropped">
- **Evidence:** stale-skill-scan score N (age Xd, routes Y) on YYYY-MM-DD
- **Action taken:** removed file + INDEX entry | marked redundant | merged into X
```

## Quarterly run

Run once per quarter, review the output, deprecate by hand:

```bash
python3 scripts/stale-skill-scan.py --top 20
```

The scan is report-only. It ranks skills and agents by a staleness score built
from git mtime, routing-row frequency, and orphaned INDEX entries. It never
edits, deletes, or blocks — every line is a candidate for review, not a
deletion.

## Automating the cadence (opt-in)

The quarterly run is human-initiated by design — a person reads the report
before anything is retired. To automate it later, point the existing
`/schedule` skill (cron-backed remote routine) at the command above. That is the
opt-in escalation path; no cron is created here.
