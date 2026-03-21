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
---

# Perses Grafana Migration

Convert Grafana dashboards to Perses format with validation and deployment.

## Operator Context

This skill operates as a migration pipeline for converting Grafana dashboards to Perses format, handling export, conversion, validation, and deployment.

### Hardcoded Behaviors (Always Apply)
- **Validate after conversion**: Always run `percli lint` on migrated dashboards — conversion may produce structurally valid but semantically broken output
- **Preserve originals**: Never modify or delete Grafana source JSON files — migration is a one-way copy operation, originals are the rollback path
- **Report incompatibilities**: List all plugins/panels that couldn't be migrated — unsupported Grafana plugins become StaticListVariable placeholders that need manual attention
- **Extract `.dashboard` key**: When exporting from Grafana API, always extract the `.dashboard` key from the response — the raw API response wraps the dashboard in metadata that `percli migrate` cannot parse
- **Verify Grafana version**: Confirm source Grafana instance is 9.0.0+ before migration — older versions use dashboard JSON schemas that `percli` does not support
- **Review placeholders before deploy**: Never deploy migrated dashboards without first searching for and documenting all `StaticListVariable` placeholders — these represent broken functionality that will confuse end users

### Default Behaviors (ON unless disabled)
- **Online mode**: Use `percli migrate --online` when connected to a Perses server (recommended — uses latest plugin migration logic)
- **JSON output**: Default to JSON format for migrated dashboards
- **Batch processing**: Process multiple dashboards in parallel when given a directory
- **Lint after convert**: Run `percli lint` on every converted file before proceeding to deploy

### Optional Behaviors (OFF unless enabled)
- **K8s CR output**: Generate Kubernetes CustomResource format with `--format cr`
- **Auto-deploy**: Apply migrated dashboards immediately after validation
- **Dry-run deploy**: Validate deployment with `percli apply --dry-run` before committing

## What This Skill CAN Do
- Convert Grafana dashboard JSON to Perses format
- Handle bulk migration of multiple dashboards
- Validate migrated output and report incompatibilities
- Deploy migrated dashboards to Perses
- Map supported panel types: Graph to TimeSeriesChart, Stat to StatChart, Table to Table

## What This Skill CANNOT Do
- Migrate Grafana annotations, alerting rules, or notification channels
- Convert unsupported Grafana plugins (they become StaticListVariable placeholders)
- Migrate Grafana users, teams, or datasource configurations
- Create dashboards from scratch (use perses-dashboard-create)
- Convert custom Grafana-only plugins that have no Perses equivalent

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

## Anti-Patterns

| Anti-Pattern | Why It's Wrong | Do Instead |
|--------------|----------------|------------|
| Deploying migrated dashboards without reviewing StaticListVariable placeholders | Users see broken panels with placeholder values, lose trust in the migration | Search all migrated files for `StaticListVariable` placeholders, document each, fix or remove before deploy |
| Running migration in offline mode when online mode is available | Offline mode uses bundled plugin migration logic which may be outdated — misses latest panel type mappings | Always prefer `--online` when a Perses server is reachable; offline is a fallback, not a default |
| Deleting original Grafana JSON files after migration | No rollback path if migration output is wrong, no way to re-run with updated `percli` version | Keep originals in a `grafana-originals/` directory alongside migrated output — storage is cheap, re-migration is not |
| Batch migrating everything at once without prioritization | Critical dashboards get the same attention as abandoned test dashboards, errors pile up | Prioritize by usage: migrate the top 5-10 most-viewed dashboards first, validate thoroughly, then batch the rest |
| Migrating dashboards without first checking Grafana version | Wasted effort — older Grafana JSON schemas produce broken or empty Perses output | Run `curl /api/health` or check `version` in the Grafana API response before starting any migration |

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "The migration completed without errors so it's correct" | `percli migrate` succeeds even when panels are replaced with StaticListVariable placeholders — zero errors does not mean zero data loss | **Diff panel counts**: compare number of panels in Grafana source vs Perses output, search for all placeholder values |
| "Online mode isn't necessary, offline is fine" | Offline mode bundles a snapshot of plugin migration logic that may be weeks or months behind — new panel type mappings are added to the server continuously | **Use online mode** whenever a Perses server is available, verify server version is current |
| "We can fix the placeholders later after deployment" | Users will see broken dashboards immediately, file bugs, lose confidence in the migration — fixing in production is always harder than fixing before deploy | **Fix or document every placeholder** before deploying, even if it delays the migration timeline |
| "The layout looks close enough" | Grafana's 24-column grid and Perses's Grid layout have different coordinate systems — "close enough" means overlapping panels or wasted whitespace that makes dashboards unusable | **Visually verify** every migrated dashboard in the Perses UI before declaring migration complete |

## FORBIDDEN Patterns

These patterns MUST NOT appear in migration workflows:

- **NEVER** pipe raw Grafana API response directly to `percli migrate` without extracting `.dashboard` — the envelope metadata will cause parse failures
- **NEVER** use `percli migrate` on Grafana JSON from versions below 9.0.0 — the output will be silently wrong or empty
- **NEVER** deploy migrated dashboards to production without running `percli lint` — structural errors will break the Perses UI
- **NEVER** delete Grafana source dashboards or disable them before confirming the Perses migration is complete and validated by dashboard owners
- **NEVER** assume all Grafana panel types have Perses equivalents — annotations, alerting rules, and custom Grafana-only plugins have no mapping

## Blocker Criteria

STOP and escalate to the user if any of these conditions are met:

- **Grafana version < 9.0.0**: Migration will produce broken output. User must upgrade Grafana or manually convert dashboard JSON.
- **More than 30% of panels are unsupported**: Migration value is too low — more manual work than automated. Recommend building Perses dashboards from scratch instead.
- **No Perses server available and online mode required**: If the user specifically needs online mode features (latest plugin mappings) but has no server, the migration cannot proceed at the expected quality level.
- **Grafana API authentication unavailable**: Cannot export dashboards without API access. User must provide a service account token or admin credentials.
- **Target Perses project does not exist and user lacks create permissions**: Cannot deploy. User must create the project or get permissions first.

---

## Instructions

### Phase 1: EXPORT

**Goal**: Export Grafana dashboards as JSON files. If user has JSON files already, skip to Phase 2.

Verify Grafana version first:
```bash
curl -s https://grafana.example.com/api/health | jq '.version'
# Must be 9.0.0+
```

Export a single dashboard:
```bash
# Export from Grafana API — MUST extract .dashboard key
curl -H "Authorization: Bearer <token>" \
  https://grafana.example.com/api/dashboards/uid/<uid> \
  | jq '.dashboard' > grafana-dashboard.json
```

For bulk export, iterate over all dashboards:
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

**Goal**: Convert Grafana JSON to Perses format.

```bash
# Single dashboard (online mode - recommended)
percli migrate -f grafana-dashboard.json --online -o json > perses-dashboard.json

# Bulk migration
for f in grafana-*.json; do
  percli migrate -f "$f" --online -o json > "perses-${f#grafana-}"
done

# K8s CR format
percli migrate -f grafana-dashboard.json --online --format cr -o json > perses-cr.json

# Offline fallback (when no Perses server available)
percli migrate -f grafana-dashboard.json -o json > perses-dashboard.json
```

**Migration notes**:
- Requires Perses server connection for online mode (uses latest plugin migration logic)
- Compatible with Grafana 9.0.0+, latest version recommended
- Unsupported variables become `StaticListVariable` with values `["grafana", "migration", "not", "supported"]`
- Panel type mapping: Graph to TimeSeriesChart, Stat to StatChart, Table to Table
- Panels with no Perses equivalent need manual replacement after migration

**Gate**: Conversion complete. All files produced without errors. Proceed to Phase 3.

### Phase 3: VALIDATE

**Goal**: Validate converted dashboards and report incompatibilities.

```bash
# Lint every migrated file
percli lint -f perses-dashboard.json

# Search for unsupported plugin placeholders
grep -r '"grafana","migration","not","supported"' perses-*.json

# Count panels: compare source vs migrated
jq '.panels | length' grafana-dashboard.json
jq '.spec.panels | length' perses-dashboard.json
```

Check for:
- Panel types that weren't converted (search for StaticListVariable placeholders)
- Missing datasource references
- Variable references that didn't translate
- Layout issues (overlapping or mis-sized panels in Grid layout)

**Gate**: Validation passes. All StaticListVariable placeholders documented with remediation plan. Proceed to Phase 4.

### Phase 4: DEPLOY

**Goal**: Deploy migrated dashboards to Perses.

```bash
# Ensure project exists
percli apply -f - <<EOF
kind: Project
metadata:
  name: <project>
spec: {}
EOF

# Deploy dashboards
percli apply -f perses-dashboard.json --project <project>
```

Verify migration:
```bash
percli get dashboard --project <project>
```

Open Perses UI and visually confirm each migrated dashboard renders correctly.

**Gate**: Dashboards deployed and accessible. Visual verification complete. Migration complete.

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
