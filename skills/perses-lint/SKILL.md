---
name: perses-lint
user-invocable: false
description: |
  Validate Perses resources: run percli lint locally or with --online against a server.
  Check dashboard definitions, datasource configs, variable schemas. Report errors with
  actionable fixes. Use for "perses lint", "validate perses", "check dashboard",
  "perses validate". Do NOT use for plugin schema testing (use perses-plugin-test).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
routing:
  triggers:
    - "lint Perses"
    - "validate Perses resources"
  category: perses
---

# Perses Lint

Validate Perses resource definitions using `percli lint`. Supports local structural validation and online server-side validation that checks plugin schemas, datasource existence, and variable resolution.

## Instructions

### Phase 1: VALIDATE

**Goal**: Run lint and capture all errors.

```bash
# Local validation (structural checks only)
percli lint -f <file>

# Online validation (includes plugin schema checks, datasource existence)
percli lint -f <file> --online

# Batch validation — all JSON files in current directory
for f in *.json; do percli lint -f "$f"; done

# Batch validation — all YAML files
for f in *.yaml; do percli lint -f "$f"; done
```

Always display the complete lint output without summarizing or truncating (provides full context for diagnosis). If online mode fails with connection errors, fall back to local mode and note the limitation.

When pointed at a directory, validate all `.json` and `.yaml` files. After validation completes, group lint errors by category (plugin, datasource, variable, layout) in the report for clarity. If local lint passes but a Perses server is configured and reachable, also suggest running online validation because local mode only checks structure—plugin schemas, datasource existence, and variable resolution require server-side checking.

**Gate**: All lint output captured. Proceed to Phase 2.

### Phase 2: FIX

**Goal**: Resolve every reported error.

Read all lint errors first, identify common root causes, then batch-fix related errors together (because multiple errors are often related, e.g., a renamed datasource breaks 5 panels at once). This is more efficient than fixing one error and re-running.

For each error category, apply the fix:

1. **Invalid panel plugin kind** — Check the `kind` field against the 27 official plugins listed in Error Handling below. Correct typos or capitalization (common typos: `TimeseriesChart` → `TimeSeriesChart`, `Stat` → `StatChart`, `Gauge` → `GaugeChart`). When fixing invalid plugin kinds, ask the user which plugin they intended rather than guessing (to preserve their intent).

2. **Missing datasource reference** — Add the missing datasource to `spec.datasources` or fix the name to match an existing datasource. Online validation catches this more reliably because local mode only checks structure.

3. **Invalid variable reference** — Verify all `$ref` values match keys in `spec.variables`. Fix typos or add missing variable definitions.

4. **Layout $ref mismatch** — Ensure every panel ID in `spec.layouts[].spec.display.panels` has a corresponding entry in `spec.panels`. Remove stale layout references or add missing panels.

5. **Unknown field errors** — Check the Perses API version, since fields may have been renamed or removed in newer versions. Fix all warnings, not just errors (because warnings often indicate deprecated fields or schema drift that will become errors in future Perses versions, creating upgrade debt).

When multiple errors share a root cause, fix the root cause once rather than patching each symptom individually.

**Gate**: All identified errors addressed. Proceed to Phase 3.

### Phase 3: RE-VALIDATE

**Goal**: Confirm all fixes are correct.

```bash
# Re-run the same lint command used in Phase 1
percli lint -f <file>
# or
percli lint -f <file> --online
```

Always re-run `percli lint` after every fix (because fixes can introduce new errors—e.g., fixing a panel kind may reveal a previously-masked datasource error). The loop is: lint → fix → lint → confirm clean. Never skip re-validation after applying fixes.

If new errors appear, return to Phase 2 for another fix cycle. Maximum 3 fix-revalidate cycles: if errors persist after 3 cycles, report remaining errors to the user with full context. Do not claim fixes are correct without re-running lint.

**Gate**: Lint returns zero errors. Validation complete.

---

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| **Invalid panel plugin kind** | `unknown kind "TimeseriesChart"` — plugin name not in the 27 official plugins | Check against official list below. Common typos: `TimeseriesChart` -> `TimeSeriesChart`, `Stat` -> `StatChart`, `Gauge` -> `GaugeChart`. Fix the `kind` field in the panel spec. |
| **Missing datasource reference** | `datasource "myPrometheus" not found` — panel references a datasource not defined in the dashboard | Add the datasource to the dashboard's `spec.datasources` map, or correct the datasource name to match an existing one. Online mode catches this more reliably. |
| **Invalid variable reference** | `variable "cluter" not found` — `$ref` points to a variable name that does not exist in `spec.variables` | Check all `$ref` values against the keys in `spec.variables`. Fix the typo or add the missing variable definition. |
| **Layout $ref mismatch** | `panel "panel-3" referenced in layout but not found in panels` — a panel ID in `spec.layouts[].spec.display.panels` does not match any key in `spec.panels` | Ensure every panel ID referenced in layout sections exists as a key in `spec.panels`. Remove stale layout references or add the missing panel. |
| **Connection refused (online mode)** | `connection refused` or `dial tcp: connect: connection refused` when using `--online` | Perses server is not running or URL is wrong. Verify server is up with `curl <server-url>/api/v1/health`. Fall back to local lint with `percli lint -f <file>` (no `--online` flag). |
| **Authentication failure (online mode)** | `401 Unauthorized` or `403 Forbidden` when using `--online` | Login first with `percli login <server-url> --username <user> --password <pass>`. Check that the token has not expired. |

### Official Plugin Kinds (27 total)

**Chart plugins**: TimeSeriesChart, BarChart, GaugeChart, HeatmapChart, HistogramChart, PieChart, ScatterChart, StatChart, StatusHistoryChart, FlameChart

**Table plugins**: Table, TimeSeriesTable, LogsTable, TraceTable

**Display plugins**: Markdown, TracingGanttChart

**Variable plugins**: DatasourceVariable, StaticListVariable

**Datasource plugins**: PrometheusDatasource, TempoDatasource, and additional community datasource types

---

## References

- Perses documentation: https://perses.dev/docs/
- percli CLI reference: https://perses.dev/docs/cli/percli/
- Perses plugin list: https://perses.dev/docs/plugins/
- Perses GitHub repository: https://github.com/perses/perses
- percli lint usage: `percli lint --help`
