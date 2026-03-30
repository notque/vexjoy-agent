# Quality: Lint, Code Review, and CUE Schemas

## Perses Lint

Validate Perses resource definitions using `percli lint`. Supports local structural validation and online server-side validation.

### Phase 1: VALIDATE

```bash
# Local validation (structural checks only)
percli lint -f <file>

# Online validation (plugin schema checks, datasource existence)
percli lint -f <file> --online

# Batch validation
for f in *.json; do percli lint -f "$f"; done
for f in *.yaml; do percli lint -f "$f"; done
```

Display complete lint output. If online mode fails, fall back to local mode. When pointed at a directory, validate all `.json` and `.yaml` files. Group errors by category.

**Gate**: All lint output captured. Proceed to Phase 2.

### Phase 2: FIX

Read all errors first, identify root causes, batch-fix related errors.

1. **Invalid panel plugin kind** -- Check against 27 official plugins. Common typos: `TimeseriesChart` -> `TimeSeriesChart`, `Stat` -> `StatChart`, `Gauge` -> `GaugeChart`. Ask user which plugin intended.
2. **Missing datasource reference** -- Add to `spec.datasources` or fix name.
3. **Invalid variable reference** -- Fix typos or add missing definitions.
4. **Layout $ref mismatch** -- Ensure panel IDs in layouts match `spec.panels`.
5. **Unknown field errors** -- Check API version for renamed/removed fields.

**Gate**: All errors addressed. Proceed to Phase 3.

### Phase 3: RE-VALIDATE

```bash
percli lint -f <file>
```

Always re-run after every fix. Maximum 3 fix-revalidate cycles.

**Gate**: Zero errors. Validation complete.

### Official Plugin Kinds (27 total)

**Chart**: TimeSeriesChart, BarChart, GaugeChart, HeatmapChart, HistogramChart, PieChart, ScatterChart, StatChart, StatusHistoryChart, FlameChart

**Table**: Table, TimeSeriesTable, LogsTable, TraceTable

**Display**: Markdown, TracingGanttChart

**Variable**: DatasourceVariable, StaticListVariable

**Datasource**: PrometheusDatasource, TempoDatasource, and community types

### Lint Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Invalid plugin kind | `unknown kind` | Check official list above |
| Missing datasource | `datasource not found` | Add to `spec.datasources` or fix name |
| Invalid variable | `variable not found` | Fix typo or add definition |
| Layout mismatch | `panel referenced but not found` | Sync layout refs with `spec.panels` |
| Connection refused (online) | Cannot reach server | Fall back to local lint |
| Auth failure (online) | 401/403 | Run `percli login` first |

---

## Perses Code Review

Review code changes in Perses repositories for domain-specific patterns, API conventions, plugin system compliance, and dashboard correctness.

### Phase 1: CLASSIFY

Categorize changed files:
- Go backend (`.go`) -- `/cmd`, `/pkg`, `/internal`
- React frontend (`.ts`, `.tsx`) -- `@perses-dev/*` packages
- CUE schemas (`.cue`)
- Dashboard definitions (`.json`, `.yaml` with `kind: Dashboard`)

Identify cross-domain changes (schema + plugin must stay synchronized). Flag dashboard files for `percli lint`.

**Gate**: Classification complete.

### Phase 2: REVIEW

#### Go backend
- **Project-scoped API compliance**: CRUD handlers at `/api/v1/projects/{project}/...` unless explicitly global. Blocker if missing.
- **Paginated List endpoints**: Accept `page` and `size` params. Blocker if missing.
- **Storage interface**: New resources implement `dao.go` CRUD methods.
- **Auth middleware on global endpoints**: Admin-level auth on GlobalDatasource, GlobalSecret, GlobalVariable. Security blocker.
- **RESTful status codes**: Create=201, Update=200, Delete=204.

#### React frontend
- **Plugin system hooks**: Must use `usePlugin`, `useTimeRange`, `useDataQueries` from `@perses-dev/plugin-system`. Raw `fetch()` is a blocker.
- **Component conventions**: Use `@perses-dev/components` not raw MUI.

#### CUE schemas
- **`package model` required**: `package main` is a blocker.
- **Closed specs**: Use `close({})`. Open schemas are blockers.
- **JSON example**: `_example.json` alongside each schema.
- **Migration path**: Check `migrate/migrate.cue` for backward compatibility.

#### Dashboard definitions
- **Run `percli lint`**: Lint failures are blockers.
- **Panel reference validation**: `$ref` keys must match `spec.panels`.
- **Variable chain ordering**: Dependees before dependents. Circular deps are blockers.
- **Datasource references**: By name and explicit scope. Hardcoded URLs are blockers.
- **`kind` field required**: Missing `kind` is a blocker.

**Gate**: All domains reviewed. Findings collected.

### Phase 3: REPORT

1. **Summary**: One-line verdict
2. **Blockers**: Must fix before merge
3. **Warnings**: Should fix
4. **Notes**: Observations
5. **percli lint output**: If dashboards were linted

**Gate**: Report delivered. Task complete.

### Code Review Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Missing pagination/project-scoping | Go API doesn't follow CRUD patterns | Blocker |
| Raw fetch() in React | Not using plugin system hooks | Blocker |
| Wrong CUE package | Not `package model` | Blocker |
| Invalid `$ref` | Panel references don't match | Blocker -- run `percli lint` |
| Broken variable chains | Out-of-order dependencies | Blocker |

---

## CUE Schema Authoring

Write CUE schemas for Perses plugin data models, validation constraints, JSON examples, and Grafana migration logic.

### Pre-Flight Check

Stop and ask if:
- Plugin type is not panel, variable, or datasource
- User wants to modify shared types in `github.com/perses/shared`
- `percli` is not installed
- Target directory already contains schemas

### Phase 1: Define Data Model

**File placement**: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`

**Requirements**: `package model` first line. `close({...})` around spec. CUE v0.12.0+.

```cue
package model

import "github.com/perses/shared/cue/common"

kind: "<PluginKind>"
spec: close({
    requiredField: string
    optionalField?: int
    format?: common.#format
    thresholds?: common.#thresholds
    calculation?: common.#calculation
    items: [...#item]
    #item: {
        name: string
        value: number
    }
})
```

Run `percli plugin test-schemas` immediately after writing.

**Gate**: Schema written, tests pass.

### Phase 2: Create JSON Example

**File placement**: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`

Include all required fields and valid constrained values. Run `percli plugin test-schemas`.

**Gate**: Example written, tests pass.

### Phase 3: Write Migration (optional)

**File placement**: `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`

```cue
package migrate

import "github.com/perses/shared/cue/migrate"

#grafanaType: "<GrafanaPluginType>"
#mapping: {
    perses_field: #panel.grafana_field
}
```

`#grafanaType` must match Grafana plugin `type` exactly. Test against real Grafana panel JSON.

**Gate**: Migration written, tests pass.

### Phase 4: Validate

```bash
percli plugin test-schemas
```

**Gate**: All tests pass. Task complete.

### CUE Schema Error Handling

| Symptom | Cause | Fix |
|---------|-------|-----|
| `package is "foo", want "model"` | Wrong package | Use `package model` |
| `expected '}' found EOF` | Unclosed `close()` | Fix braces |
| `field not allowed` | JSON has extra fields | Add to schema or remove from JSON |
| `#grafanaType` not matching | Wrong Grafana ID | Use exact plugin `type` value |
| `no schema found` | Wrong directory | Use `schemas/<type>/<name>/<name>.cue` |

---

## References

- [Perses Documentation](https://perses.dev/docs/)
- [percli CLI Reference](https://perses.dev/docs/cli/percli/)
- [Perses Plugin List](https://perses.dev/docs/plugins/)
- [Perses GitHub](https://github.com/perses/perses)
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/)
- [Perses Shared CUE Types](https://github.com/perses/perses/tree/main/cue/schemas)
- [Perses API Reference](https://perses.dev/docs/api/)
