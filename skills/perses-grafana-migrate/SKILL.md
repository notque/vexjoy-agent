---
name: perses-grafana-migrate
user-invocable: false
description: |
  Grafana-to-Perses dashboard migration: export Grafana dashboards, convert with
  percli migrate, validate converted output, fix incompatibilities, deploy to Perses.
  Handles bulk migration with parallel processing. Use for "migrate grafana",
  "grafana to perses", "perses migrate", "convert grafana". Do NOT use for creating
  new dashboards from scratch (use perses-dashboard-create).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
agent: perses-dashboard-engineer
version: 2.0.0
routing:
  triggers:
    - "migrate Grafana"
    - "Grafana to Perses"
  category: perses
---

# Perses Grafana Migration

Convert Grafana dashboards to Perses format with validation and deployment.

## Overview

This skill orchestrates a four-phase migration pipeline: EXPORT Grafana dashboards as JSON, CONVERT to Perses format, VALIDATE converted output and fix incompatibilities, then DEPLOY to a Perses instance.

**Key constraints embedded in workflow**:
- Always validate after conversion because `percli migrate` succeeds even when panels become `StaticListVariable` placeholders — zero errors does not mean zero data loss
- Preserve originals (never delete Grafana source files) because migration is one-way; originals are the rollback path
- Extract `.dashboard` key when exporting from Grafana API because the raw API response wraps the dashboard in metadata that `percli migrate` cannot parse
- Verify Grafana version is 9.0.0+ before migration because older versions use dashboard JSON schemas that `percli` does not support
- Use online mode when a Perses server is available because offline mode bundles outdated plugin migration logic; online uses the latest logic from the server

---

## Instructions

### Phase 1: EXPORT

**Goal**: Export Grafana dashboards as JSON files. If user has JSON files already, skip to Phase 2.

Verify Grafana version first (required because older Grafana versions produce broken or empty output):
```bash
curl -s https://grafana.example.com/api/health | jq '.version'
# Must be 9.0.0+. If below 9.0.0, user must upgrade or manually update schemaVersion (risky).
```

Export a single dashboard (IMPORTANT: extract `.dashboard` key, not the full envelope, because `percli migrate` will fail on API metadata):
```bash
curl -H "Authorization: Bearer <token>" \
  https://grafana.example.com/api/dashboards/uid/<uid> \
  | jq '.dashboard' > grafana-dashboard.json
```

For bulk export, iterate over all dashboards (prioritize by usage; migrate top 5-10 most-viewed first, then batch the rest):
```bash
curl -H "Authorization: Bearer <token>" \
  https://grafana.example.com/api/search?type=dash-db \
  | jq -r '.[].uid' | while read uid; do
    curl -s -H "Authorization: Bearer <token>" \
      "https://grafana.example.com/api/dashboards/uid/$uid" \
      | jq '.dashboard' > "grafana-$uid.json"
done
```

**Gate**: Grafana dashboard JSON files available, `.dashboard` key extracted, Grafana version confirmed 9.0.0+. Proceed to Phase 2.

### Phase 2: CONVERT

**Goal**: Convert Grafana JSON to Perses format using `percli migrate`.

Prefer online mode (uses latest plugin migration logic from the server) over offline:
```bash
# Single dashboard (online mode - RECOMMENDED)
percli migrate -f grafana-dashboard.json --online -o json > perses-dashboard.json

# Bulk migration with online mode
for f in grafana-*.json; do
  percli migrate -f "$f" --online -o json > "perses-${f#grafana-}"
done

# K8s CR format (if needed for GitOps deployment)
percli migrate -f grafana-dashboard.json --online --format cr -o json > perses-cr.json

# Offline fallback (only if no Perses server is available)
percli migrate -f grafana-dashboard.json -o json > perses-dashboard.json
```

**Migration behavior** (awareness for downstream validation):
- Unsupported Grafana variables become `StaticListVariable` with marker values `["grafana", "migration", "not", "supported"]`
- Panel type mapping: Graph → TimeSeriesChart, Stat → StatChart, Table → Table
- Panels with no Perses equivalent need manual replacement after migration
- Layout coordinates may not map perfectly (Grafana's 24-column grid vs Perses Grid have different coordinate systems)

**Gate**: Conversion complete. All files produced without errors. Proceed to Phase 3.

### Phase 3: VALIDATE

**Goal**: Validate converted dashboards and report incompatibilities before deploy.

Lint every migrated file (required to catch structural errors that will break the Perses UI):
```bash
percli lint -f perses-dashboard.json
```

Search for unsupported plugin placeholders (these represent broken functionality that will confuse end users):
```bash
grep -r '"grafana","migration","not","supported"' perses-*.json
```

Count panels to detect data loss (compare source vs output; gaps indicate unsupported panels):
```bash
# Grafana panel count
jq '.panels | length' grafana-dashboard.json
# Perses panel count
jq '.spec.panels | length' perses-dashboard.json
```

Check for additional incompatibilities:
- Variable references that didn't translate (search for references to non-existent variables)
- Missing datasource references (migrated dashboard references names that don't exist in Perses)
- Layout issues (overlapping panels or wrong sizes in Grid layout — visually verify in UI later)

**Critical gate**: Before proceeding, find and document ALL `StaticListVariable` placeholders with a remediation plan (fix or remove). Never deploy migrated dashboards without first reviewing placeholders because users will see broken dashboards immediately and lose confidence in the migration.

**Gate**: Validation passes. All StaticListVariable placeholders documented with remediation plan. Proceed to Phase 4.

### Phase 4: DEPLOY

**Goal**: Deploy migrated dashboards to Perses.

Ensure the target project exists:
```bash
percli apply -f - <<EOF
kind: Project
metadata:
  name: <project>
spec: {}
EOF
```

Deploy dashboards:
```bash
percli apply -f perses-dashboard.json --project <project>
```

Verify deployment:
```bash
percli get dashboard --project <project>
```

Open Perses UI and visually verify each migrated dashboard renders correctly (because layout coordinates may have shifted, this is the final validation step).

**Gate**: Dashboards deployed and accessible. Visual verification complete. Migration complete.

---

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Invalid Grafana JSON format | `percli migrate` fails with parse error or "unexpected token" | Verify JSON is valid with `jq .` — ensure you extracted the `.dashboard` key from Grafana API response, not the full envelope |
| Grafana version < 9.0.0 | `percli migrate` fails with schema errors or produces empty output | Upgrade Grafana to 9.0.0+ before export, or manually update the dashboard JSON `schemaVersion` field (risky — structural differences may remain) |
| Unsupported plugin warning | Migration succeeds but panels contain `StaticListVariable` with values `["grafana","migration","not","supported"]` | Document each unsupported panel, then manually replace with the closest Perses equivalent (TimeSeriesChart, StatChart, Table, or Markdown panel) |
| Online mode connection failure | `percli migrate --online` fails with "connection refused" or timeout | Verify Perses server URL and port, check authentication (run `percli login` first), fall back to offline mode with `percli migrate -f <file> -o json` if server is unavailable |
| Panel layout lost in migration | Grafana grid coordinates don't map cleanly to Perses Grid layout — panels overlap or have wrong sizes | After migration, review the `spec.layouts` section and manually adjust Grid `x`, `y`, `w`, `h` values to match the original Grafana layout intent |
| Missing datasource references | Migrated dashboard references datasource names that don't exist in Perses | Create matching Perses datasources before deploying, or update the migrated JSON to reference existing Perses datasource names |

---

## References

| Resource | URL |
|----------|-----|
| Perses GitHub | https://github.com/perses/perses |
| percli documentation | https://perses.dev/docs/tooling/percli/ |
| Grafana API — Get Dashboard | https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/#get-dashboard-by-uid |
| Grafana API — Search | https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/#dashboard-search |
| Perses Plugin System | https://perses.dev/docs/plugins/ |
| Migration Guide | https://perses.dev/docs/tooling/percli/#migrate |
