---
name: perses-cue-schema
user-invocable: false
description: "CUE schema authoring for Perses plugins: data models, validation."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-engineer
version: 2.0.0
routing:
  triggers:
    - "Perses CUE schema"
    - "plugin data model"
  category: perses
---

# Perses CUE Schema Authoring

Write CUE schemas for Perses plugin data models, validation constraints, JSON examples, and Grafana migration logic.

## Instructions

### Pre-Flight Check

Before starting, stop and ask the user if any of these apply:

- The plugin type is not panel, variable, or datasource (the standard Perses plugin types)
- The user wants to modify shared types in `github.com/perses/shared` (these are upstream and not ours to change)
- `percli` is not installed or `percli plugin test-schemas` is unavailable in the environment
- The target directory already contains schemas that would be overwritten

### Phase 1: Define Data Model

Create the CUE schema for the plugin spec.

**File placement**: Place the file at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`. The file name must match the plugin name exactly because `percli plugin test-schemas` discovers schemas by convention and skips misnamed files.

**Package and structure requirement**: Every schema file must use `package model` as its first line because any other package name causes a CUE loader error (`package is "foo", want "model"`). The only exception is migration files, which use `package migrate` instead.

Wrap all spec fields in `close({...})` because without it, CUE accepts any field name -- misspelled or unexpected fields pass validation silently, making the schema useless as a contract. Nested type definitions must live inside `close()` to be validated as part of the spec.

**Version requirement**: This skill requires CUE v0.12.0+. Earlier versions have incompatible syntax for Perses schemas.

```cue
package model

import "github.com/perses/shared/cue/common"

kind: "<PluginKind>"
spec: close({
    // Required fields
    requiredField: string

    // Optional fields (note the ?)
    optionalField?: int

    // Constrained fields -- import shared types from common rather than
    // redefining them locally, because local redefinitions diverge from
    // upstream and cause runtime incompatibility.
    format?: common.#format
    thresholds?: common.#thresholds
    calculation?: common.#calculation

    // Arrays of typed items
    items: [...#item]

    // Nested type definitions MUST live inside close() -- definitions
    // placed outside are not validated as part of the spec.
    #item: {
        name: string
        value: number
    }
})
```

Explain CUE syntax as you write: `close()` enforces strict field contracts, optional fields use `?`, arrays use `[...#type]`, and nested types use `#name`. This skill is educational by default.

**Validation gate**: After writing the schema file, run `percli plugin test-schemas` immediately. Do not wait until the end; validating incrementally catches errors before they compound.

**Gate**: Schema file written, `percli plugin test-schemas` passes on the schema alone. Proceed to Phase 2.

### Phase 2: Create JSON Example

Write a JSON example that validates against the schema.

**File placement**: Place it at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json` -- same directory, same base name as the `.cue` file. Every schema must have a corresponding JSON example because without one, `percli plugin test-schemas` has nothing to validate against and the schema's correctness is unverified.

Include all required fields and valid values for constrained types. Include optional fields to demonstrate their usage.

Run `percli plugin test-schemas` after writing the example.

**Gate**: JSON example file written, `percli plugin test-schemas` passes with both schema and example. Proceed to Phase 3.

### Phase 3: Write Migration (optional)

Only proceed if the user explicitly requests Grafana migration support.

**File placement**: Place the migration file at `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`. Migration files must live in the `migrate/` subdirectory and must never be placed elsewhere because the path structure is how `percli` discovers them.

```cue
package migrate

import "github.com/perses/shared/cue/migrate"

#grafanaType: "<GrafanaPluginType>"
#mapping: {
    // Map Grafana panel fields to Perses spec fields.
    // Always reference #panel field paths -- never hardcode values,
    // because Grafana field paths vary across plugin versions.
    perses_field: #panel.grafana_field
}
```

**Constraint 1 - Type matching**: `#grafanaType` must match the Grafana plugin `type` field exactly (e.g., `"timeseries"`, not `"time_series"`). A mismatch causes `#panel` lookups to resolve to `_|_` (bottom), breaking the entire migration.

**Constraint 2 - Field validation**: Test against real exported Grafana panel JSON. Guessed `#mapping` paths are silently wrong at runtime because there is no compile-time check on field existence. Actual data is essential for correctness.

Run `percli plugin test-schemas` after writing the migration file.

**Gate**: Migration file written, `percli plugin test-schemas` passes. Proceed to Phase 4.

### Phase 4: Validate

Confirm all schemas and examples pass validation together:

```bash
percli plugin test-schemas
```

If validation fails, return to the relevant phase and fix. Do not declare completion until tests pass -- a schema that "looks correct" is not correct until `percli` confirms it.

**Gate**: `percli plugin test-schemas` passes. Task complete.

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
**Cause**: `close({})` enforces a strict field set -- the JSON example contains fields the schema does not declare.
**Fix**: Either add the missing field to the CUE spec (with `?` if optional) or remove it from the JSON example. Also check for type mismatches (e.g., `string` in schema but `number` in JSON).

### Grafana Migration Schema Error
**Symptom**: `#grafanaType` value not matching, `#mapping` field path references fail, or `#panel` lookups resolve to `_|_` (bottom).
**Cause**: `#grafanaType` does not match the Grafana plugin ID exactly, or `#mapping` references a field path that does not exist on `#panel`.
**Fix**: Verify `#grafanaType` matches the Grafana plugin `type` field exactly (e.g., `"timeseries"`, not `"time_series"`). Check that `#mapping` field paths use `#panel.<field>` with the correct Grafana JSON structure.

### percli plugin test-schemas Failure: Schema/Example Not Found
**Symptom**: `no schema found` or `no example found` -- test runner skips or errors on the plugin.
**Cause**: Directory structure does not follow the expected convention, or files are misnamed.
**Fix**: Ensure files are at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue` and `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`. Names must match exactly.

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/) -- official plugin documentation
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/) -- CUE syntax and semantics
- [Perses Shared CUE Types](https://github.com/perses/perses/tree/main/cue/schemas) -- `common.#format`, `common.#thresholds`, etc.
- [percli CLI Reference](https://perses.dev/docs/tooling/percli/) -- `percli plugin test-schemas` and other commands
- [Grafana Panel Schema Reference](https://grafana.com/docs/grafana/latest/developers/plugins/) -- for migration `#grafanaType` values
