---
name: perses-plugin-pipeline
user-invocable: false
description: "End-to-end Perses plugin development pipeline."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
agent: perses-engineer
version: 2.0.0
routing:
  triggers:
    - perses plugin pipeline
    - full plugin development
    - perses plugin create and deploy
    - plugin end to end
  pairs_with:
    - perses-plugin-create
    - perses-dac-pipeline
  complexity: Complex
  category: devops
---

# Perses Plugin Development Pipeline

6-phase pipeline for complete Perses plugin development: from scaffold through deploy.

## Instructions

### Phase 1: SCAFFOLD

**Goal**: Generate plugin scaffold with correct structure.

**Why this phase first**: Always use `percli plugin generate` for scaffolding — never manually create directory structures. Manual approaches miss module federation config, package.json structure, and rsbuild setup.

1. Determine plugin parameters:
   - `--module.org`: Organization name (e.g., `my-org`)
   - `--module.name`: Module name (e.g., `my-plugin-module`)
   - `--plugin.type`: One of Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore
   - `--plugin.name`: Plugin name (e.g., `MyCustomPanel`)

2. Run scaffold:
```bash
percli plugin generate \
  --module.org=<org> \
  --module.name=<module> \
  --plugin.type=<type> \
  --plugin.name=<name>
```

3. Verify generated structure: package.json, rsbuild.config.ts, src/, schemas/ directories exist.

**Gate**: Scaffold generated, directory structure verified. Phase gates enforced — do not proceed to Phase 2 until this gate passes.

### Phase 2: SCHEMA

**Goal**: Author CUE schema defining the plugin's data model.

**Why this phase before React**: CUE before React always — author and validate schemas before implementing React components. Components lack type safety and validation contracts if schema comes later. Schema errors surface late during build if skipped.

1. Create CUE schema at `schemas/<type>/<name>/<name>.cue`
   - Declare correct package: `package model` (mandatory — Perses requires this in all plugin schemas)
   - Define the plugin's spec structure with CUE types and constraints
   - Import common Perses schema packages as needed

2. Create JSON example at `schemas/<type>/<name>/<name>.json`
   - Generate JSON examples alongside every CUE schema for validation
   - Must validate against the CUE schema
   - Serves as documentation and test fixture

3. Optional: Write Grafana migration schema at `schemas/<type>/<name>/migrate/migrate.cue`

4. Validate: `percli plugin test-schemas`
   - Visual inspection misses CUE's subtle type rules — always run test-schemas
   - Re-run after every schema change, no matter how small

**Gate**: `percli plugin test-schemas` passes with zero errors. Do not proceed to Phase 3 until this gate passes.

### Phase 3: IMPLEMENT

**Goal**: Build React component implementing the plugin UI.

**Why this phase after SCHEMA**: Schema validation gates this phase — you have type safety and a validation contract before writing React code.

1. Implement component in `src/<type>/<name>/`
   - Use `@perses-dev/plugin-system` hooks (e.g., `useDataQueries`, `useTimeRange`)
   - Use `@perses-dev/components` for shared UI elements
   - Never import from `@perses-dev/internal` — use only public API packages
   - Follow Perses component patterns from existing plugins

2. Register plugin in module's plugin registration file

3. Use `percli plugin start` for hot-reload development against a running Perses server
   - Default behavior: hot-reload development is ON

**Gate**: Component renders correctly in dev mode. Do not proceed to Phase 4 until this gate passes.

### Phase 4: TEST

**Goal**: Validate schemas and component behavior.

**Constraint**: Test before build always — `percli plugin test-schemas` must pass before running `percli plugin build`. Build success does not guarantee complete archive contents.

1. Run `percli plugin test-schemas` — must pass (re-validate after any IMPLEMENT changes)
   - Build exit code 0 does not guarantee complete archive contents — validation catches what exit codes miss
2. Run component unit tests if present (`npm test` or framework-specific runner)
3. Test with `percli plugin start` against a running Perses server — verify plugin appears and functions

**Gate**: All schema tests pass, component renders and functions correctly. Do not proceed to Phase 5 until this gate passes.

### Phase 5: BUILD

**Goal**: Create distribution archive.

**Why this phase gated on TEST**: Test before build ensures schema validity. Build without test validation produces archives with invalid schemas that fail silently in Perses server.

1. Run `percli plugin build`
   - Never manually construct plugin archives (zip/tar) — always use `percli plugin build`
   - Default format: .tar.gz for distribution archives

2. Verify archive contents include:
   - `package.json` — plugin metadata
   - `mf-manifest.json` — module federation manifest
   - `schemas/` — compiled CUE schemas as JSON
   - `__mf/` — module federation runtime chunks

```bash
# Verify archive contents (adjust filename)
tar -tzf <archive>.tar.gz | head -20
# Always list and verify archive contents — don't trust exit code 0
```

**Gate**: Archive built, contents verified with all required files present. Do not proceed to Phase 6 until this gate passes.

### Phase 6: DEPLOY

**Goal**: Install plugin in Perses server and verify.

**Constraint**: Test the actual deployed plugin — hot-reload dev mode bypasses plugin loading path; deploy uses archive loading.

1. Copy archive to Perses server's `plugins-archive/` directory
2. Restart Perses (or wait for hot-reload if enabled in server config)
3. Verify plugin loaded:
```bash
percli get plugin
# Or via MCP tool: perses_list_plugins
```
4. Create a test dashboard using the new plugin to confirm end-to-end functionality

**Gate**: Plugin loaded in Perses server, functional in a dashboard. Pipeline complete.

---

## Error Handling

### `percli plugin generate` fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| "invalid plugin type" | Unrecognized `--plugin.type` value | Use one of: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore |
| "directory already exists" | Target directory conflicts with existing scaffold | Remove or rename existing directory, or use a different `--module.name` |
| "percli: command not found" | percli not installed | Install via `brew install perses/tap/percli` or download from GitHub releases |
| Non-zero exit with no message | Wrong percli version | Check `percli version` and upgrade if below required minimum |

### CUE schema compilation errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| "package name mismatch" | CUE file uses wrong package name — Perses requires `package model` for all plugin schemas | Change the first line of the .cue file to `package model` |
| "cannot find package" / missing imports | Required CUE modules not imported | Add missing imports — common ones: `github.com/perses/shared/cue/common` for shared types |
| "conflicting values" | JSON example does not conform to CUE constraints | Fix JSON to match CUE type definitions, or relax CUE constraints |
| "cannot convert incomplete value" | CUE schema uses unresolved references | Ensure all referenced definitions are imported or defined locally |

### React component build errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Cannot find module '@perses-dev/...'" | Missing Perses npm dependencies | Run `npm install @perses-dev/plugin-system @perses-dev/components` |
| "Node.js version mismatch" | Node version too old for rsbuild | Upgrade to Node 18+ (check with `node --version`) |
| TypeScript type errors | Component props don't match plugin spec types | Align component props with the generated spec types from CUE schema |
| rsbuild config errors | Invalid rsbuild.config.ts | Compare against percli-generated default; do not modify module federation settings |

### `percli plugin build` archive incomplete

| Symptom | Cause | Fix |
|---------|-------|-----|
| Missing mf-manifest.json | Build did not complete successfully | Re-run `percli plugin build` and check for earlier errors in build output |
| Missing schemas/ directory | CUE schemas not compiled to JSON | Run `percli plugin test-schemas` first, then rebuild |
| Wrong archive structure | Manual archive creation instead of percli | Always use `percli plugin build` — never manually zip |
| Archive too large | node_modules or build artifacts included | Check .npmignore or build config; only dist output should be archived |

### Error: Plugin scaffold generation failure
**Cause**: Invalid `--plugin.type` value, directory name conflict, or `percli` not installed / version too old
**Solution**: Verify `percli version` meets minimum requirements. Use one of the valid plugin types: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore. Remove or rename conflicting directories.

### Error: CUE schema compilation failure
**Cause**: Wrong package name (must be `package model`), missing CUE module imports, or JSON example does not conform to CUE constraints
**Solution**: Ensure every plugin `.cue` schema file declares `package model`. Add missing imports from `github.com/perses/shared/cue/common`. Fix JSON examples to match CUE type definitions. Run `percli plugin test-schemas` to validate.

### Error: Build archive incomplete
**Cause**: `percli plugin build` succeeded but archive is missing `mf-manifest.json`, `schemas/`, or `__mf/` directory
**Solution**: Re-run `percli plugin build` and check for build errors in output. Ensure `percli plugin test-schemas` passes before building. Always use `percli plugin build` — never manually construct archives. List archive contents with `tar -tzf <archive>.tar.gz` to verify.

---

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/development/)
- [percli CLI Reference](https://perses.dev/docs/cli/percli/)
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/)
- [Perses Plugin System (@perses-dev/plugin-system)](https://github.com/perses/perses/tree/main/ui/plugin-system)
- [Official Perses Plugins Repository](https://github.com/perses/plugins)
- [rsbuild Documentation](https://rsbuild.dev/)
