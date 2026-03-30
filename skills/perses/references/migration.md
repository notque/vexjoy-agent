# Grafana Migration

Convert Grafana dashboards to Perses format with validation and deployment.

## Overview

Four-phase migration pipeline: EXPORT Grafana dashboards as JSON, CONVERT to Perses format, VALIDATE converted output and fix incompatibilities, then DEPLOY to a Perses instance.

**Key constraints**:
- Always validate after conversion because `percli migrate` succeeds even when panels become `StaticListVariable` placeholders
- Preserve originals (never delete Grafana source files)
- Extract `.dashboard` key when exporting from Grafana API
- Verify Grafana version is 9.0.0+ before migration
- Use online mode when a Perses server is available

## Phase 1: EXPORT

**Goal**: Export Grafana dashboards as JSON. If user has JSON files already, skip to Phase 2.

```bash
# Verify Grafana version (must be 9.0.0+)
curl -s https://grafana.example.com/api/health | jq '.version'

# Single dashboard -- extract .dashboard key
curl -H "Authorization: Bearer <token>" \
  https://grafana.example.com/api/dashboards/uid/<uid> \
  | jq '.dashboard' > grafana-dashboard.json

# Bulk export
curl -H "Authorization: Bearer <token>" \
  https://grafana.example.com/api/search?type=dash-db \
  | jq -r '.[].uid' | while read uid; do
    curl -s -H "Authorization: Bearer <token>" \
      "https://grafana.example.com/api/dashboards/uid/$uid" \
      | jq '.dashboard' > "grafana-$uid.json"
done
```

**Gate**: JSON files available, `.dashboard` key extracted, Grafana 9.0.0+ confirmed.

## Phase 2: CONVERT

**Goal**: Convert Grafana JSON to Perses format.

```bash
# Online mode (RECOMMENDED)
percli migrate -f grafana-dashboard.json --online -o json > perses-dashboard.json

# Bulk migration
for f in grafana-*.json; do
  percli migrate -f "$f" --online -o json > "perses-${f#grafana-}"
done

# K8s CR format
percli migrate -f grafana-dashboard.json --online --format cr -o json > perses-cr.json

# Offline fallback
percli migrate -f grafana-dashboard.json -o json > perses-dashboard.json
```

**Migration behavior**:
- Unsupported variables become `StaticListVariable` with `["grafana", "migration", "not", "supported"]`
- Panel mapping: Graph -> TimeSeriesChart, Stat -> StatChart, Table -> Table
- Layout coordinates may not map perfectly

**Gate**: Conversion complete. Proceed to Phase 3.

## Phase 3: VALIDATE

```bash
percli lint -f perses-dashboard.json

# Search for unsupported placeholders
grep -r '"grafana","migration","not","supported"' perses-*.json

# Compare panel counts
jq '.panels | length' grafana-dashboard.json
jq '.spec.panels | length' perses-dashboard.json
```

Also check: variable references, missing datasource references, layout issues.

**Critical gate**: Document ALL `StaticListVariable` placeholders with a remediation plan before deploying.

**Gate**: Validation passes. Placeholders documented.

## Phase 4: DEPLOY

```bash
# Ensure project exists
percli apply -f - <<EOF
kind: Project
metadata:
  name: <project>
spec: {}
EOF

# Deploy
percli apply -f perses-dashboard.json --project <project>

# Verify
percli get dashboard --project <project>
```

Visually verify in Perses UI.

**Gate**: Dashboards deployed and verified. Migration complete.

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Invalid Grafana JSON | Parse error | Verify with `jq .` -- ensure `.dashboard` key extracted |
| Grafana < 9.0.0 | Schema errors or empty output | Upgrade Grafana first |
| Unsupported plugin | `StaticListVariable` placeholders | Replace with closest Perses equivalent |
| Online mode connection failure | "connection refused" | Check Perses server URL and auth, fall back to offline |
| Layout lost | Overlapping or wrong-sized panels | Manually adjust Grid coordinates |
| Missing datasource refs | References to non-existent names | Create matching Perses datasources |

## References

| Resource | URL |
|----------|-----|
| Perses GitHub | https://github.com/perses/perses |
| percli documentation | https://perses.dev/docs/tooling/percli/ |
| Grafana API -- Get Dashboard | https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/#get-dashboard-by-uid |
| Grafana API -- Search | https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/#dashboard-search |
| Perses Plugin System | https://perses.dev/docs/plugins/ |
| Migration Guide | https://perses.dev/docs/tooling/percli/#migrate |
