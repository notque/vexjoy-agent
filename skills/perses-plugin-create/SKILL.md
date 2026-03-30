---
name: perses-plugin-create
user-invocable: false
description: "Perses plugin scaffolding: select type, generate, implement CUE + React."
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
    - "create Perses plugin"
    - "scaffold plugin"
  category: perses
---

# Perses Plugin Create

Scaffold and implement Perses plugins with CUE schemas and React components.

## Overview

This skill guides the full lifecycle of creating a Perses plugin: scaffolding the directory structure with `percli`, defining the CUE schema and JSON example, implementing the React component, validating schemas, and building the distributable archive.

---

## Instructions

### Phase 1: SCAFFOLD (Default to Panel type if unspecified)

**Goal**: Generate the plugin directory structure with percli.

1. Determine plugin type from user request (default: Panel because most plugin requests are for panels)
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

### Phase 2: SCHEMA (Always pair schema with JSON example; use `close({...})` around spec)

**Goal**: Define the CUE schema and JSON example. These must be created together because schema validation requires examples to catch typos and type errors that are invisible at compile time.

1. Edit CUE schema at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`. **Must declare `package model` as the first line** (after any imports) so the CUE compiler can determine the package namespace.

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
    format?: common.#format
})
```

**Always wrap spec in `close({...})`** to reject unknown fields during validation—without it, garbage JSON passes and validation becomes meaningless.

2. Create JSON example at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`. Examples surface schema errors invisible at compile time (typos, wrong types, missing required fields).

```json
{
  "kind": "<PluginName>",
  "spec": {
    "field1": "example-value"
  }
}
```

3. If Grafana equivalent exists, create migration schema at `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue` (organizations migrating from Grafana are the primary adoption path—migration is not optional when equivalents exist).

4. Validate immediately (before moving to React):

```bash
percli plugin test-schemas
```

**Gate**: `percli plugin test-schemas` passes. Proceed to Phase 3.

### Phase 3: IMPLEMENT (Reference the 27 official plugins before building from scratch)

**Goal**: Build the React component.

1. Implement React component at `src/<type>/<name>/`
2. Follow the rsbuild-based build system conventions from the scaffolded template
3. Check the 27 official plugins across 6 categories for similar implementations before creating from scratch (saves time and ensures consistency)

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

### Phase 5: BUILD (Never build without passing schema tests; always validate archive structure)

**Goal**: Create the distributable archive. Never run `percli plugin build` without `percli plugin test-schemas` passing first—schema errors ship in the archive and cause runtime failures on the Perses server.

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

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|---------|
| `percli plugin generate` fails: directory exists | "directory already exists" error | Remove or rename the existing directory, or generate into a different path |
| `percli plugin generate` fails: invalid type | Unrecognized plugin type error | Use one of: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore |
| `percli plugin generate` fails: missing flags | Missing required flag error | All four flags are required: `--module.org`, `--module.name`, `--plugin.type`, `--plugin.name` |
| CUE schema compilation error: missing package | "cannot determine package name" | Add `package model` as the first line of the .cue file (after any imports) |
| CUE schema compilation error: unclosed close() | Syntax error in CUE | Ensure `close({...})` has matching braces—every `{` needs a `}` before the closing `)` |
| CUE schema compilation error: bad import path | Import not found for shared types | Use exact path `"github.com/perses/shared/cue/common"`—not shorthand or relative imports |
| JSON example does not match schema: extra fields | `close()` rejects unknown fields | Remove fields from JSON that are not defined in the CUE schema, or add them to the schema |
| JSON example does not match schema: wrong types | Type mismatch error | Ensure JSON values match CUE type declarations (string vs int vs bool) |
| JSON example does not match schema: missing required | Required field not present | Add all non-optional fields (those without `?` suffix in CUE) to the JSON example |
| `percli plugin build` produces empty archive | Archive missing mf-manifest.json | Run `rsbuild build` (or equivalent npm build) first—the React build must succeed before archive creation |
| `percli plugin build` fails: wrong directory | Build cannot find plugin config | Run `percli plugin build` from the module root directory (where package.json lives) |

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
