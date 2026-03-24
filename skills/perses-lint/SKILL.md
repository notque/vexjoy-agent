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

## Operator Context

This skill operates as a validation gate for Perses resources. It runs `percli lint` against JSON/YAML resource files, interprets errors, applies fixes, and re-validates until all issues are resolved.

### Hardcoded Behaviors (Always Apply)
- **Show full output**: Always display complete lint output, never summarize or truncate
- **Online when possible**: Prefer `--online` mode when a Perses server is reachable
- **Fix-then-revalidate loop**: Never claim fixes are correct without re-running lint
- **Report every error**: Surface all lint errors, not just the first one encountered
- **Preserve user intent**: When fixing invalid plugin kinds, ask user which plugin they intended rather than guessing

### Default Behaviors (ON unless disabled)
- **Batch mode for directories**: When pointed at a directory, validate all `.json` and `.yaml` files
- **Error grouping**: Group lint errors by category (plugin, datasource, variable, layout) in output
- **Suggest online mode**: If local lint passes but user has a server configured, suggest online re-check

### Optional Behaviors (OFF unless enabled)
- **Auto-fix mode**: Automatically apply fixes for unambiguous errors (e.g., typo in plugin kind)
- **CI integration**: Output lint results in machine-parseable format for CI pipelines
- **Strict mode**: Treat warnings as errors (fail on any non-clean lint output)

## What This Skill CAN Do
- Run local structural validation with `percli lint -f <file>`
- Run server-side validation with `percli lint -f <file> --online` (checks plugin schemas, datasource existence)
- Validate individual files or batch-validate entire directories
- Diagnose and fix invalid panel plugin kinds, missing datasource references, broken variable references, and layout mismatches
- Re-validate after fixes to confirm resolution

## What This Skill CANNOT Do
- Create dashboards from scratch (use perses-dashboard-create)
- Deploy or configure Perses servers (use perses-deploy)
- Develop or test custom plugins (use perses-plugin-create or perses-plugin-test)
- Fix PromQL/TraceQL query logic errors (lint validates structure, not query semantics)

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

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|-------------|------------------|
| **Running `percli apply` without `percli lint` first** | Applies a broken resource to the server, then you discover errors at runtime or in the UI | Always run `percli lint -f <file>` before `percli apply -f <file>`. Lint is the gate before deploy. |
| **Only validating locally when a server is available** | Local lint checks structure only. Online mode validates against actual plugin schemas, existing datasources, and variable resolution. Many errors only surface with `--online`. | Use `percli lint -f <file> --online` whenever a Perses server is reachable. |
| **Ignoring lint warnings (only fixing errors)** | Warnings often indicate deprecated fields, unused variables, or schema drift that will become errors in future Perses versions | Fix all warnings. Use strict mode (`--strict` if available) in CI to enforce zero-warning policy. |
| **Fixing one error at a time and re-running** | Wastes cycles. Multiple errors are often related (e.g., renamed datasource breaks 5 panels) | Read ALL lint errors first, identify root causes, batch-fix related errors, then re-validate once. |

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "Lint passed locally, so the dashboard is correct" | Local lint only checks structure. Plugin schemas, datasource existence, and variable resolution require online mode. | Run `--online` against a server before declaring the resource valid. |
| "I fixed the error, no need to re-run lint" | Fixes can introduce new errors (e.g., fixing a panel kind may reveal a previously-masked datasource error) | Always re-run `percli lint` after every fix. The loop is: lint -> fix -> lint -> confirm clean. |
| "That warning is not important" | Warnings in Perses often indicate fields that will be removed or required in the next version. Ignoring them creates upgrade debt. | Fix warnings now. They cost minutes today and hours during upgrades. |

---

## FORBIDDEN Patterns

- **NEVER** mark lint as passing when there are unresolved errors or warnings
- **NEVER** modify `percli` output to hide errors from the user
- **NEVER** skip re-validation after applying fixes
- **NEVER** guess a plugin kind without checking the official 27-plugin list
- **NEVER** run `percli apply` as a substitute for `percli lint` ("it will tell us if it fails")

---

## Blocker Criteria

Do NOT proceed past validation if any of these are true:
- `percli lint` reports any errors (warnings in strict mode)
- Online validation was requested but the server is unreachable and no fallback was acknowledged
- A plugin kind is used that is not in the official 27-plugin list and the user has not confirmed it is a custom plugin
- Any `$ref` in the layout or variables section points to a non-existent target

---

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

If online mode fails with connection errors, fall back to local mode and note the limitation.

**Gate**: All lint output captured. Proceed to Phase 2.

### Phase 2: FIX

**Goal**: Resolve every reported error.

For each error, identify the root cause and apply the fix:

1. **Invalid panel plugin kind** -- Check the `kind` field against the 27 official plugins listed above. Correct typos or capitalization.
2. **Missing datasource reference** -- Add the missing datasource to `spec.datasources` or fix the name to match an existing datasource.
3. **Invalid variable reference** -- Verify `$ref` values match keys in `spec.variables`. Fix typos or add missing variable definitions.
4. **Layout $ref mismatch** -- Ensure every panel ID in `spec.layouts[].spec.display.panels` has a corresponding entry in `spec.panels`.
5. **Unknown field errors** -- Check Perses API version. Field may have been renamed or removed in a newer version.

When multiple errors share a root cause (e.g., a renamed datasource), fix the root cause once rather than patching each symptom individually.

**Gate**: All identified errors addressed. Proceed to Phase 3.

### Phase 3: RE-VALIDATE

**Goal**: Confirm all fixes are correct.

```bash
# Re-run the same lint command used in Phase 1
percli lint -f <file>
# or
percli lint -f <file> --online
```

- If new errors appear, return to Phase 2.
- Maximum 3 fix-revalidate cycles. If errors persist after 3 cycles, report remaining errors to the user with full context.

**Gate**: Lint returns zero errors. Validation complete.

---

## References

- Perses documentation: https://perses.dev/docs/
- percli CLI reference: https://perses.dev/docs/cli/percli/
- Perses plugin list: https://perses.dev/docs/plugins/
- Perses GitHub repository: https://github.com/perses/perses
- percli lint usage: `percli lint --help`
