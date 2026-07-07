# Agent Evidence Queries

The agent evidence layer is a local SQLite read model inside `learning.db`. It
records compact, queryable facts from existing hooks so the agent can answer
questions such as:

- Which route has worked or failed recently?
- What happened in this session?
- Which tool or file target failed most recently?
- Is there enough local evidence to keep using a route, watch it, or investigate it?

It is intentionally data-only. There is no server, dashboard, proxy, or external
sync path.

## Tables

- `evidence_sessions`: one row per observed session, with project path and last
  seen time.
- `evidence_events`: append-style events for route decisions, route outcomes,
  skill invocations, agent invocations, and tool failures.
- `evidence_route_decisions`: normalized route decision rows with agent, skill,
  model, health-gate inputs, stack, and eventual outcome.

Text fields are bounded before storage. Metadata is stored as JSON text and
returned as decoded JSON by the Python API and CLI JSON views.

## CLI

```bash
python3 scripts/learning-db.py evidence-recent --json --limit 20
python3 scripts/learning-db.py evidence-route-context python-general-engineer:test-driven-development --json
python3 scripts/learning-db.py evidence-file-history hooks/lib/learning_db_v2.py --json
python3 scripts/learning-db.py evidence-failures --json
python3 scripts/learning-db.py evidence-decide python-general-engineer:test-driven-development --json
```

The `evidence-decide` command returns an advisory value only:

- `keep`: recent local evidence does not show a meaningful failure signal.
- `watch`: failures exist at a rate worth watching, especially on low sample
  counts.
- `investigate`: failures dominate the local evidence.
- `no_data`: the route has no local evidence yet.

These commands are safe for scripts and agent context assembly because JSON
output does not require parsing prose.
