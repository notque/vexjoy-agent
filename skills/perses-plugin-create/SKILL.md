---
name: perses-plugin-create
user-invocable: false
description: |
  Perses plugin scaffolding and creation: select plugin type (Panel, Datasource, Query,
  Variable, Explore), generate with percli plugin generate, implement CUE schema and React
  component, test with percli plugin start, build archive with percli plugin build. Use for
  "create perses plugin", "new panel plugin", "new datasource plugin", "perses plugin scaffold".
  Do NOT use for dashboard creation (use perses-dashboard-create).
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

# Perses Plugin Create

Scaffold and implement Perses plugins with CUE schemas and React components.

## Operator Context

This skill guides the full lifecycle of creating a Perses plugin: scaffolding the directory structure with `percli`, defining the CUE schema and JSON example, implementing the React component, validating schemas, and building the distributable archive.

### Hardcoded Behaviors (Always Apply)
- **Schema + example together**: Always create both the CUE schema and a matching JSON example file -- never one without the other
- **Test before build**: Always run `percli plugin test-schemas` before `percli plugin build` -- a build without passing schema tests is forbidden
- **Model package**: CUE schemas must declare `package model` as the first line after imports
- **Close spec definitions**: Always wrap spec fields in `close({...})` to reject unknown fields during validation
- **Validate JSON against schema**: After creating the JSON example, run `percli plugin test-schemas` to confirm the example passes CUE validation before moving to React implementation

### Default Behaviors (ON unless disabled)
- **Panel type**: Default to Panel plugin type if the user does not specify a type
- **Include migration**: Generate Grafana migration scaffold (`schemas/<type>/<name>/migrate/migrate.cue`) if a Grafana equivalent panel exists
- **Reference official plugins**: Check the 27 official plugins across 6 categories for similar implementations before creating a new plugin from scratch

### Optional Behaviors (OFF unless enabled)
- **Multi-plugin module**: Create multiple related plugins within a single module (one module can contain multiple plugins)
- **Hot-reload dev server**: Start `percli plugin start` against a running Perses server for live development
- **Custom shared types**: Import shared CUE types from `github.com/perses/shared/cue/common` for format, thresholds, sorting, etc.

## What This Skill CAN Do
- Scaffold a new plugin directory with `percli plugin generate`
- Create CUE schema definitions for any plugin type: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore
- Create matching JSON example files for schema validation
- Generate Grafana migration schemas for plugins with Grafana equivalents
- Implement React components with the rsbuild-based build system
- Build distributable archives (.zip/.tar/.tar.gz) containing package.json, mf-manifest.json, schemas/, and __mf/

## What This Skill CANNOT Do
- Create or manage dashboards (use perses-dashboard-create)
- Deploy Perses server instances (use perses-deploy)
- Review existing plugin code for quality (use perses-code-review)
- Run the plugin test suite beyond schema validation (use perses-plugin-test)
- Manage datasource connections or variables at the project level (use perses-datasource-manage or perses-variable-manage)

---

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|---------|
| `percli plugin generate` fails: directory exists | "directory already exists" error | Remove or rename the existing directory, or generate into a different path |
| `percli plugin generate` fails: invalid type | Unrecognized plugin type error | Use one of: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore |
| `percli plugin generate` fails: missing flags | Missing required flag error | All four flags are required: `--module.org`, `--module.name`, `--plugin.type`, `--plugin.name` |
| CUE schema compilation error: missing package | "cannot determine package name" | Add `package model` as the first line of the .cue file (after any imports) |
| CUE schema compilation error: unclosed close() | Syntax error in CUE | Ensure `close({...})` has matching braces -- every `{` needs a `}` before the closing `)` |
| CUE schema compilation error: bad import path | Import not found for shared types | Use exact path `"github.com/perses/shared/cue/common"` -- not shorthand or relative imports |
| JSON example does not match schema: extra fields | `close()` rejects unknown fields | Remove fields from JSON that are not defined in the CUE schema, or add them to the schema |
| JSON example does not match schema: wrong types | Type mismatch error | Ensure JSON values match CUE type declarations (string vs int vs bool) |
| JSON example does not match schema: missing required | Required field not present | Add all non-optional fields (those without `?` suffix in CUE) to the JSON example |
| `percli plugin build` produces empty archive | Archive missing mf-manifest.json | Run `rsbuild build` (or equivalent npm build) first -- the React build must succeed before archive creation |
| `percli plugin build` fails: wrong directory | Build cannot find plugin config | Run `percli plugin build` from the module root directory (where package.json lives) |

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Do Instead |
|-------------|-------------|------------|
| Creating CUE schema without JSON example | `percli plugin test-schemas` has nothing to validate against -- schema errors are invisible until runtime | Always create both files together and run `percli plugin test-schemas` immediately |
| Not using `close({...})` for spec | Without `close()`, the schema accepts any unknown fields -- validation becomes meaningless | Always wrap spec in `close({...})` to enforce strict field validation |
| Skipping Grafana migration schema when equivalent exists | Users migrating from Grafana hit a dead end when no migration path exists for their panels | Check if a Grafana equivalent exists and create `migrate/migrate.cue` if so |
| Hard-coding default values in the React component | Users cannot configure the plugin's behavior through the dashboard JSON -- defaults are invisible | Define defaults as configurable fields in the CUE schema with sensible default values |
| Copying schema from another plugin without adjusting `kind` | The `kind` field identifies the plugin -- duplicates cause plugin resolution conflicts at runtime | Always set `kind` to match the unique plugin name |
| Building archive before running test-schemas | Schema errors ship in the archive and cause runtime failures on the Perses server | Run `percli plugin test-schemas` and fix all errors before `percli plugin build` |

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "The schema is simple, it doesn't need a JSON example" | Even simple schemas need validation -- typos in field names or types are invisible without a test | **Create the JSON example and run test-schemas** |
| "close() is too restrictive, I'll add it later" | Without close(), the schema validates nothing -- any garbage JSON passes | **Add close() now, relax specific fields with `...` only if needed** |
| "The React component compiles so the plugin works" | React compilation says nothing about schema correctness or plugin registration | **Run percli plugin test-schemas AND verify the archive structure** |
| "I'll skip migration since most users start fresh" | Organizations migrating from Grafana are the primary adoption path -- migration is not optional when equivalents exist | **Check for Grafana equivalent and create migration schema** |
| "One test run passed, the schema is correct" | A single JSON example may not cover optional fields, edge cases, or constraint boundaries | **Verify the example includes representative values for all fields** |

---

## FORBIDDEN Patterns

These are hard stops. Do NOT proceed past these.

- **NEVER** run `percli plugin build` without `percli plugin test-schemas` passing first
- **NEVER** create a CUE schema without a corresponding JSON example file
- **NEVER** omit `package model` from a CUE schema file
- **NEVER** omit `close({...})` around the spec definition
- **NEVER** use a `kind` value that duplicates an existing plugin in the same module

---

## Blocker Criteria

STOP and ask the user when:

- **Plugin type is ambiguous**: The user's description could map to multiple plugin types (e.g., "query plugin" could be TimeSeriesQuery, TraceQuery, ProfileQuery, or LogQuery)
- **Schema fields are unclear**: The user describes desired behavior but not the data model -- ask what fields the plugin should accept
- **Module context is missing**: You cannot determine if this is a new module or an addition to an existing module
- **Grafana equivalent is uncertain**: You are unsure whether a Grafana panel equivalent exists for migration purposes
- **Shared type usage**: The user references "thresholds", "format", or "sort" but you are unsure which shared CUE types from `github.com/perses/shared/cue/common` to import

---

## Instructions

### Phase 1: SCAFFOLD

**Goal**: Generate the plugin directory structure with percli.

1. Determine plugin type from user request (default: Panel)
2. Choose module organization: new module or add to existing
3. Run scaffolding:

```bash
percli plugin generate \
  --module.org=<org> \
  --module.name=<name> \
  --plugin.type=<Panel|Datasource|TimeSeriesQuery|TraceQuery|ProfileQuery|LogQuery|Variable|Explore> \
  --plugin.name=<PluginName> \
  <directory>
```

**Gate**: Directory structure generated. Proceed to Phase 2.

### Phase 2: SCHEMA

**Goal**: Define the CUE schema and JSON example.

1. Edit CUE schema at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`:

```cue
package model

import "github.com/perses/shared/cue/common"  // only if shared types needed

kind: "<PluginName>"
spec: close({
    // Required fields (no ? suffix)
    field1: string
    // Optional fields (? suffix)
    field2?: int
    // Shared types from common
    format?: common.#Format
})
```

2. Create JSON example at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`:

```json
{
  "kind": "<PluginName>",
  "spec": {
    "field1": "example-value"
  }
}
```

3. If Grafana equivalent exists, create migration schema at `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`

4. Validate immediately:

```bash
percli plugin test-schemas
```

**Gate**: `percli plugin test-schemas` passes. Proceed to Phase 3.

### Phase 3: IMPLEMENT

**Goal**: Build the React component.

1. Implement React component at `src/<type>/<name>/`
2. Follow the rsbuild-based build system conventions from the scaffolded template
3. Reference official plugins (27 across 6 categories) for similar implementations

**Gate**: React component builds without errors. Proceed to Phase 4.

### Phase 4: TEST

**Goal**: Validate the complete plugin.

```bash
# Validate schemas against JSON examples
percli plugin test-schemas

# Optional: hot-reload dev server against running Perses
percli plugin start
```

**Gate**: All schema tests pass. Proceed to Phase 5.

### Phase 5: BUILD

**Goal**: Create the distributable archive.

```bash
percli plugin build
```

Verify archive contains: package.json, mf-manifest.json, schemas/, __mf/

**Gate**: Archive created and structure verified. Proceed to Phase 6.

### Phase 6: DEPLOY

**Goal**: Install the plugin.

Install archive in Perses server's `plugins-archive/` directory, or embed via npm for bundled deployments.

**Gate**: Plugin installed and loading in Perses server. Task complete.

---

## References

- **Plugin types**: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore
- **Official plugins**: 27 plugins across 6 categories in [perses/plugins](https://github.com/perses/plugins)
- **CUE schema location**: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`
- **JSON example location**: `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`
- **Migration schema location**: `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`
- **React component location**: `src/<type>/<name>/`
- **Shared CUE types**: `github.com/perses/shared/cue/common` (format, thresholds, sorting)
- **Archive format**: .zip/.tar/.tar.gz containing package.json, mf-manifest.json, schemas/, __mf/
- **Related skills**: perses-plugin-test, perses-plugin-pipeline, perses-cue-schema, perses-deploy
