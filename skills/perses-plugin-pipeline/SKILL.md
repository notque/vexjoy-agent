---
name: perses-plugin-pipeline
user-invocable: false
description: |
  End-to-end Perses plugin development pipeline: SCAFFOLD, SCHEMA, IMPLEMENT, TEST,
  BUILD, DEPLOY. From percli plugin generate through CUE schema authoring, React
  component implementation, testing, and archive deployment. Use for comprehensive
  plugin development workflows. Use for "perses plugin pipeline", "full plugin
  development". Do NOT use for quick scaffolding only (use perses-plugin-create).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
agent: perses-plugin-engineer
version: 2.0.0
---

# Perses Plugin Development Pipeline

6-phase pipeline for complete Perses plugin development: from scaffold through deploy.

## Operator Context

This skill operates as an end-to-end plugin development guide, enforcing phase gates between SCAFFOLD, SCHEMA, IMPLEMENT, TEST, BUILD, and DEPLOY.

### Hardcoded Behaviors (Always Apply)
- **Phase gates enforced**: Do not proceed to next phase until current phase passes its gate criteria
- **Test before build**: `percli plugin test-schemas` must pass before running `percli plugin build`
- **Schema + component required**: Both CUE schema and React component must be implemented before BUILD
- **Verify archive contents**: After build, confirm archive contains package.json, mf-manifest.json, schemas/, and __mf/
- **Use percli for all scaffolding**: Never manually create plugin directory structures — always use `percli plugin generate`

### Default Behaviors (ON unless disabled)
- **CUE before React**: Author and validate schemas before implementing React components
- **JSON example creation**: Generate a JSON example alongside every CUE schema for validation
- **Hot-reload development**: Use `percli plugin start` during IMPLEMENT phase for live preview
- **Archive format**: Default to .tar.gz for distribution archives

### Optional Behaviors (OFF unless enabled)
- **Grafana migration schema**: Write `migrate/migrate.cue` for Grafana panel/datasource migration
- **Multiple plugin types**: Scaffold multiple plugins in a single module (e.g., Panel + Datasource)
- **CI pipeline generation**: Create GitHub Actions or GitLab CI config for automated build/test

## What This Skill CAN Do
- Scaffold new Perses plugins via `percli plugin generate` for all plugin types
- Author CUE schemas defining plugin data models and validation rules
- Implement React components using `@perses-dev/plugin-system` hooks and patterns
- Run schema validation via `percli plugin test-schemas`
- Build distribution archives via `percli plugin build`
- Deploy plugin archives to a running Perses server

## What This Skill CANNOT Do
- Deploy or configure Perses servers (use perses-deploy)
- Create or manage dashboards (use perses-dashboard-create)
- Manage Kubernetes infrastructure (use kubernetes-helm-engineer)
- Debug Perses server-side issues (use perses-deploy or systematic-debugging)

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

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|-------------|------------------|
| **Skipping SCHEMA phase** — jumping from scaffold to React implementation | Components lack type safety; no validation contract; schema errors surface late during build | Always complete SCHEMA and validate with `percli plugin test-schemas` before writing React code |
| **Building without testing schemas** — running `percli plugin build` before `percli plugin test-schemas` | Build may succeed but produce invalid schemas that fail at runtime in Perses server | Run `percli plugin test-schemas` and fix all CUE errors before building |
| **Not verifying archive contents** — trusting build output without inspection | Archive may be missing mf-manifest.json or schemas, causing silent failures on deploy | After every build, list archive contents and confirm required files exist |
| **Manually creating directory structure** — instead of using `percli plugin generate` | Missing module federation config, incorrect package.json, no rsbuild setup | Always start with `percli plugin generate` even if you plan to customize later |

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|---------------|-----------------|
| "The CUE schema looks correct, skip test-schemas" | CUE has subtle type rules; visual inspection misses constraint errors | **Run `percli plugin test-schemas`** — it catches what reading cannot |
| "Build succeeded so the archive is fine" | Build exit code 0 does not guarantee complete archive contents | **List and verify archive contents** — check for mf-manifest.json, schemas/, __mf/ |
| "Schema changes are small, no need to re-test" | Small CUE changes can cascade into type mismatches across the schema | **Re-run test-schemas after every schema change**, no matter how small |
| "The component renders in dev, skip deploy verification" | Hot-reload dev mode bypasses plugin loading path; deploy uses archive loading | **Test the actual deployed plugin** in a Perses server instance |

## FORBIDDEN Patterns
- **NEVER** modify percli-generated rsbuild.config.ts module federation settings — this breaks plugin loading
- **NEVER** manually construct plugin archives (zip/tar) — always use `percli plugin build`
- **NEVER** skip CUE package declaration — every plugin .cue schema file must declare `package model`
- **NEVER** import from `@perses-dev/internal` — use only public API packages (`@perses-dev/plugin-system`, `@perses-dev/components`)
- **NEVER** hardcode Perses server URLs in plugin source — plugins receive context via the plugin system

## Blocker Criteria

Stop and ask the user before proceeding if:
- Plugin type is ambiguous (e.g., could be Panel or Variable)
- Target Perses server version is unknown (schema compatibility varies)
- No Perses server is available for DEPLOY phase testing
- Required `@perses-dev/*` package versions conflict with existing node_modules
- CUE schema requires imports from packages not present in the module

---

## Instructions

### Phase 1: SCAFFOLD

**Goal**: Generate plugin scaffold with correct structure.

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

**Gate**: Scaffold generated, directory structure verified. Proceed to Phase 2.

### Phase 2: SCHEMA

**Goal**: Author CUE schema defining the plugin's data model.

1. Create CUE schema at `schemas/<type>/<name>/<name>.cue`
   - Declare correct package: `package model`
   - Define the plugin's spec structure with CUE types and constraints
   - Import common Perses schema packages as needed

2. Create JSON example at `schemas/<type>/<name>/<name>.json`
   - Must validate against the CUE schema
   - Serves as documentation and test fixture

3. Optional: Write Grafana migration schema at `schemas/<type>/<name>/migrate/migrate.cue`

4. Validate: `percli plugin test-schemas`

**Gate**: `percli plugin test-schemas` passes with zero errors. Proceed to Phase 3.

### Phase 3: IMPLEMENT

**Goal**: Build React component implementing the plugin UI.

1. Implement component in `src/<type>/<name>/`
   - Use `@perses-dev/plugin-system` hooks (e.g., `useDataQueries`, `useTimeRange`)
   - Use `@perses-dev/components` for shared UI elements
   - Follow Perses component patterns from existing plugins

2. Register plugin in module's plugin registration file

3. Use `percli plugin start` for hot-reload development against a running Perses server

**Gate**: Component renders correctly in dev mode. Proceed to Phase 4.

### Phase 4: TEST

**Goal**: Validate schemas and component behavior.

1. Run `percli plugin test-schemas` — must pass (re-validate after any IMPLEMENT changes)
2. Run component unit tests if present (`npm test` or framework-specific runner)
3. Test with `percli plugin start` against a running Perses server — verify plugin appears and functions

**Gate**: All schema tests pass, component renders and functions correctly. Proceed to Phase 5.

### Phase 5: BUILD

**Goal**: Create distribution archive.

1. Run `percli plugin build`
2. Verify archive contents include:
   - `package.json` — plugin metadata
   - `mf-manifest.json` — module federation manifest
   - `schemas/` — compiled CUE schemas as JSON
   - `__mf/` — module federation runtime chunks

```bash
# Verify archive contents (adjust filename)
tar -tzf <archive>.tar.gz | head -20
```

**Gate**: Archive built, contents verified with all required files present. Proceed to Phase 6.

### Phase 6: DEPLOY

**Goal**: Install plugin in Perses server and verify.

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

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/development/)
- [percli CLI Reference](https://perses.dev/docs/cli/percli/)
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/)
- [Perses Plugin System (@perses-dev/plugin-system)](https://github.com/perses/perses/tree/main/ui/plugin-system)
- [Official Perses Plugins Repository](https://github.com/perses/plugins)
- [rsbuild Documentation](https://rsbuild.dev/)
