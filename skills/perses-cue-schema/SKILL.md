---
name: perses-cue-schema
user-invocable: false
description: |
  CUE schema authoring for Perses plugins: define data models, write validation
  constraints, create JSON examples, implement Grafana migration schemas in
  migrate/migrate.cue. Educational skill that explains CUE patterns specific to
  Perses plugin development. Use for "perses cue schema", "perses model",
  "plugin schema", "cue validation perses". Do NOT use for dashboard CUE
  definitions (use perses-dac-pipeline).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-plugin-engineer
version: 2.0.0
---

# Perses CUE Schema Authoring

Write CUE schemas for Perses plugin data models, validation constraints, JSON examples, and Grafana migration logic.

## Operator Context

This skill operates as a CUE schema author for Perses plugins. It produces validated schema files, matching JSON examples, and optional migration definitions that pass `percli plugin test-schemas`.

### Hardcoded Behaviors (Always Apply)
- **Package model**: All plugin CUE schemas MUST use `package model` — any other package name causes compilation failure
- **Closed specs**: Use `close({...})` for all spec definitions — open specs allow invalid fields through validation silently
- **JSON example required**: Every schema MUST have a corresponding JSON example file at the same directory level
- **Test after write**: Run `percli plugin test-schemas` after creating or modifying any schema — never declare a schema complete without passing tests
- **CUE v0.12.0+**: Require CUE v0.12.0 or later; earlier versions have incompatible syntax for Perses schemas
- **Migration package**: Migration files MUST use `package migrate`, never `package model`

### Default Behaviors (ON unless disabled)
- **Educational mode**: Explain CUE syntax and Perses-specific patterns as schemas are created
- **Import common types**: Import `github.com/perses/shared/cue/common` for shared types (`#format`, `#thresholds`, `#calculation`) rather than redefining them
- **Validate incrementally**: Test after each schema file is written, not only at the end

### Optional Behaviors (OFF unless enabled)
- **Grafana migration**: Write `migrate/migrate.cue` with `#grafanaType` and `#mapping` for converting Grafana panels
- **Strict mode**: Treat all fields as required unless the user explicitly marks them optional

## What This Skill CAN Do
- Define CUE schemas for any Perses plugin type (panel, variable, datasource)
- Create matching JSON example files that validate against schemas
- Write Grafana migration schemas with field mappings via `#panel` references
- Explain CUE syntax: `close()`, optional fields (`?`), arrays (`[...#type]`), nested types (`#name`)
- Debug CUE compilation errors and schema/example mismatches
- Import and use shared Perses types from `common`

## What This Skill CANNOT Do
- Create Perses dashboards or layouts (use perses-dashboard-create)
- Scaffold full plugin projects with Go code (use perses-plugin-create)
- Deploy or configure Perses server instances (use perses-deploy)
- Write DaC pipeline CUE definitions (use perses-dac-pipeline)

---

## Error Handling

### CUE Compilation Error: Wrong Package Name
**Symptom**: `package is "foo", want "model"` or similar CUE loader error.
**Cause**: Schema file uses a package name other than `model`.
**Fix**: Change the first line of the `.cue` file to `package model`. Migration files use `package migrate` instead.

### CUE Compilation Error: Unclosed Spec or Bad Import
**Symptom**: `cannot find package`, `expected '}' found EOF`, or `import path not valid`.
**Cause**: Missing closing brace in `close({...})`, typo in import path, or missing import statement.
**Fix**: Verify braces are balanced in the `close({})` block. Confirm the import path is exactly `github.com/perses/shared/cue/common` (not shortened or aliased incorrectly).

### JSON Example Mismatch: close() Rejects Unknown Fields
**Symptom**: `percli plugin test-schemas` fails with `field not allowed` on a field present in the JSON but absent from the CUE schema.
**Cause**: `close({})` enforces a strict field set — the JSON example contains fields the schema does not declare.
**Fix**: Either add the missing field to the CUE spec (with `?` if optional) or remove it from the JSON example. Also check for type mismatches (e.g., `string` in schema but `number` in JSON).

### Grafana Migration Schema Error
**Symptom**: `#grafanaType` value not matching, `#mapping` field path references fail, or `#panel` lookups resolve to `_|_` (bottom).
**Cause**: `#grafanaType` does not match the Grafana plugin ID exactly, or `#mapping` references a field path that does not exist on `#panel`.
**Fix**: Verify `#grafanaType` matches the Grafana plugin `type` field exactly (e.g., `"timeseries"`, not `"time_series"`). Check that `#mapping` field paths use `#panel.<field>` with the correct Grafana JSON structure.

### percli plugin test-schemas Failure: Schema/Example Not Found
**Symptom**: `no schema found` or `no example found` — test runner skips or errors on the plugin.
**Cause**: Directory structure does not follow the expected convention, or files are misnamed.
**Fix**: Ensure files are at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue` and `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`. Names must match exactly.

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| **Open specs** (no `close({})`) | Allows any field through — invalid JSON passes validation silently | Always wrap spec fields in `close({...})` |
| **Not importing shared types** | Redefining `#format`, `#thresholds`, or `#calculation` locally diverges from upstream | Import from `github.com/perses/shared/cue/common` |
| **Schema without JSON example** | `percli plugin test-schemas` has nothing to validate against; schema correctness is unverified | Always create the `.json` example alongside the `.cue` schema |
| **Migration without real Grafana JSON** | `#mapping` paths are guessed and silently wrong at runtime | Test migration schemas against an actual exported Grafana panel JSON |
| **Using `package migrate` for schemas** | CUE loader expects `package model` for plugin schemas | Reserve `package migrate` only for files in the `migrate/` subdirectory |
| **Nested type defined outside close()** | Nested `#typeName` definitions placed outside `close({})` are not validated as part of the spec | Define nested types inside the `close({})` block |

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|---|---|---|
| "The schema looks correct" | CUE has subtle constraints — looking correct is not being correct | **Run `percli plugin test-schemas`** |
| "close() is optional for simple schemas" | Without close(), any misspelled field passes silently | **Always use close() — no exceptions** |
| "I'll add the JSON example later" | Schema without example is untested; bugs compound | **Write the JSON example before moving on** |
| "The migration mapping is straightforward" | Grafana field paths vary across plugin versions | **Test against real Grafana export JSON** |
| "Common types aren't needed for this schema" | Diverging from upstream types causes runtime incompatibility | **Import common types unless genuinely unused** |

---

## FORBIDDEN Patterns

- **NEVER** use `package` names other than `model` (schemas) or `migrate` (migration files)
- **NEVER** omit `close({})` around spec definitions
- **NEVER** declare a schema complete without a passing `percli plugin test-schemas` run
- **NEVER** hardcode values in migration `#mapping` — always reference `#panel` field paths
- **NEVER** place migration files outside the `migrate/` subdirectory

---

## Blocker Criteria

Stop and ask the user before proceeding if:
- The plugin type is not one of the standard Perses plugin types (panel, variable, datasource)
- The user wants to modify shared types in `github.com/perses/shared` — these are upstream
- `percli` is not installed or `percli plugin test-schemas` is unavailable in the environment
- The target directory already contains schemas that would be overwritten

---

## Instructions

### Phase 1: DEFINE DATA MODEL

**Goal**: Create the CUE schema for the plugin spec.

Location: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`

```cue
package model

import "github.com/perses/shared/cue/common"

kind: "<PluginKind>"
spec: close({
    // Required fields
    requiredField: string

    // Optional fields (note the ?)
    optionalField?: int

    // Constrained fields using shared types
    format?: common.#format
    thresholds?: common.#thresholds
    calculation?: common.#calculation

    // Arrays of typed items
    items: [...#item]

    // Nested type definitions (inside close)
    #item: {
        name: string
        value: number
    }
})
```

**Gate**: Schema file written and syntactically valid. Proceed to Phase 2.

### Phase 2: CREATE JSON EXAMPLE

**Goal**: Write a JSON example that validates against the schema.

Location: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`

The JSON must include all required fields and valid values for any constrained types. Optional fields should be included to demonstrate their usage.

**Gate**: JSON example file written. Proceed to Phase 3.

### Phase 3: WRITE MIGRATION (optional)

**Goal**: Define Grafana-to-Perses field mapping.

Location: `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`

```cue
package migrate

import "github.com/perses/shared/cue/migrate"

#grafanaType: "<GrafanaPluginType>"
#mapping: {
    // Map Grafana panel fields to Perses spec fields
    perses_field: #panel.grafana_field
}
```

Only proceed if the user requests migration support.

**Gate**: Migration file written. Proceed to Phase 4.

### Phase 4: VALIDATE

**Goal**: Confirm all schemas and examples pass validation.

```bash
percli plugin test-schemas
```

If validation fails, return to the relevant phase and fix. Do not declare completion until tests pass.

**Gate**: `percli plugin test-schemas` passes. Task complete.

---

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/) — official plugin documentation
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/) — CUE syntax and semantics
- [Perses Shared CUE Types](https://github.com/perses/perses/tree/main/cue/schemas) — `common.#format`, `common.#thresholds`, etc.
- [percli CLI Reference](https://perses.dev/docs/tooling/percli/) — `percli plugin test-schemas` and other commands
- [Grafana Panel Schema Reference](https://grafana.com/docs/grafana/latest/developers/plugins/) — for migration `#grafanaType` values
