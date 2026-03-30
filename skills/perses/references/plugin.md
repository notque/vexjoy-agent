# Plugin Development

## Plugin Create

Scaffold and implement Perses plugins with CUE schemas and React components.

### Phase 1: SCAFFOLD (Default to Panel type if unspecified)

**Goal**: Generate the plugin directory structure with percli.

1. Determine plugin type (default: Panel)
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

**Goal**: Define the CUE schema and JSON example together.

1. Edit CUE schema at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.cue`. **Must declare `package model`**.

```cue
package model

import "github.com/perses/shared/cue/common"

kind: "<PluginName>"
spec: close({
    field1: string
    field2?: int
    format?: common.#format
})
```

2. Create JSON example at `schemas/<plugin-type>/<plugin-name>/<plugin-name>.json`.

3. If Grafana equivalent exists, create migration schema at `schemas/<plugin-type>/<plugin-name>/migrate/migrate.cue`.

4. Validate: `percli plugin test-schemas`

**Gate**: `percli plugin test-schemas` passes. Proceed to Phase 3.

### Phase 3: IMPLEMENT (Reference the 27 official plugins before building from scratch)

**Goal**: Build the React component.

1. Implement at `src/<type>/<name>/`
2. Follow rsbuild-based build system conventions
3. Check 27 official plugins for similar implementations first

**Gate**: React component builds without errors. Proceed to Phase 4.

### Phase 4: TEST

```bash
percli plugin test-schemas
percli plugin start
```

**Gate**: All schema tests pass. Proceed to Phase 5.

### Phase 5: BUILD (Never build without passing schema tests)

```bash
percli plugin build
```

Verify archive contains: package.json, mf-manifest.json, schemas/, __mf/

**Gate**: Archive created and verified. Proceed to Phase 6.

### Phase 6: DEPLOY

Install archive in Perses server's `plugins-archive/` directory.

**Gate**: Plugin installed and loading. Task complete.

### Create Error Handling

| Cause | Symptom | Solution |
|-------|---------|---------|
| Directory exists | "directory already exists" | Remove/rename or use different path |
| Invalid type | Unrecognized plugin type | Use: Panel, Datasource, TimeSeriesQuery, TraceQuery, ProfileQuery, LogQuery, Variable, Explore |
| Missing flags | Missing required flag | All four flags required: `--module.org`, `--module.name`, `--plugin.type`, `--plugin.name` |
| Missing package | "cannot determine package name" | Add `package model` as first line |
| Unclosed close() | Syntax error | Ensure matching braces in `close({...})` |
| Bad import path | Import not found | Use exact path `"github.com/perses/shared/cue/common"` |
| Extra fields in JSON | `close()` rejects unknown fields | Remove from JSON or add to schema |
| Empty archive | Missing mf-manifest.json | Run `rsbuild build` first |

---

## Plugin Pipeline

6-phase pipeline for complete Perses plugin development: from scaffold through deploy.

### Phase 1: SCAFFOLD

Always use `percli plugin generate` -- never manually create directory structures.

```bash
percli plugin generate \
  --module.org=<org> \
  --module.name=<module> \
  --plugin.type=<type> \
  --plugin.name=<name>
```

Verify: package.json, rsbuild.config.ts, src/, schemas/ exist.

**Gate**: Scaffold generated, structure verified.

### Phase 2: SCHEMA

CUE before React always.

1. Create CUE schema: `schemas/<type>/<name>/<name>.cue` with `package model`
2. Create JSON example: `schemas/<type>/<name>/<name>.json`
3. Optional: Migration schema at `schemas/<type>/<name>/migrate/migrate.cue`
4. Validate: `percli plugin test-schemas`

**Gate**: `percli plugin test-schemas` passes with zero errors.

### Phase 3: IMPLEMENT

1. Implement component in `src/<type>/<name>/`
   - Use `@perses-dev/plugin-system` hooks
   - Use `@perses-dev/components` for shared UI
   - Never import from `@perses-dev/internal`
2. Register plugin in module
3. Use `percli plugin start` for hot-reload

**Gate**: Component renders correctly.

### Phase 4: TEST

1. `percli plugin test-schemas` -- must pass
2. Component unit tests (`npm test`)
3. Test with `percli plugin start` against running Perses

**Gate**: All tests pass, component functions correctly.

### Phase 5: BUILD

```bash
percli plugin build
tar -tzf <archive>.tar.gz | head -20
```

Verify: package.json, mf-manifest.json, schemas/, __mf/ present.

**Gate**: Archive built, contents verified.

### Phase 6: DEPLOY

1. Copy archive to `plugins-archive/`
2. Restart Perses
3. Verify: `percli get plugin`
4. Test in a dashboard

**Gate**: Plugin loaded and functional. Pipeline complete.

### Pipeline Error Handling

| Symptom | Cause | Fix |
|---------|-------|-----|
| "invalid plugin type" | Bad `--plugin.type` | Use valid type name |
| "directory already exists" | Conflict | Rename or remove |
| "percli: command not found" | Not installed | `brew install perses/tap/percli` |
| "package name mismatch" | Wrong CUE package | Use `package model` |
| "Cannot find module '@perses-dev/...'" | Missing npm deps | `npm install @perses-dev/plugin-system @perses-dev/components` |
| Missing mf-manifest.json | Incomplete build | Re-run `percli plugin build` |

---

## Plugin Testing

Test across four layers: CUE schema, React components, integration, and Grafana migration.

Testing follows strict order: each layer depends on the previous passing.

### Phase 1: SCHEMA TESTS

1. Verify: `package model` at top, `close({...})` for strict validation
2. Check JSON examples exist for every schema
3. Run: `percli plugin test-schemas`
4. Fix errors before proceeding

**Gate**: All schema tests pass.

### Phase 2: COMPONENT TESTS

1. Mock `@perses-dev/plugin-system` hooks with realistic values
2. Run: `npm test -- --watchAll=false`
3. Create multiple JSON examples: minimal, full, edge cases

**Gate**: All component tests pass.

### Phase 3: INTEGRATION TESTS

1. Start local Perses: `docker run --name perses-test -d -p 127.0.0.1:8080:8080 persesdev/perses`
2. Start plugin dev server: `percli plugin start`
3. Verify plugin appears in UI panel type selector
4. Test with real data

**Gate**: Plugin loads and renders in local Perses.

### Phase 4: MIGRATION TESTS (if applicable)

1. Locate `migrate/migrate.cue`
2. Prepare Grafana test fixtures
3. Run: `percli migrate --input grafana-dashboard.json --output perses-dashboard.json`
4. Validate output against Perses schema

**Gate**: Migration produces valid output. Task complete.

### Test Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "cannot find package" | Missing `package model` | Add as first line |
| Parse error | Unclosed `close({...})` | Fix braces |
| Extra fields | JSON has undeclared fields | Add to schema or remove from JSON |
| "Cannot find module" | Missing mock | Add `jest.mock('@perses-dev/plugin-system')` |
| Connection refused | Perses not running | Start with Docker |
| Unexpected panel type | Unhandled Grafana panel | Add migration case |

---

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/)
- [percli CLI Reference](https://perses.dev/docs/cli/percli/)
- [CUE Language Specification](https://cuelang.org/docs/reference/spec/)
- [Official Perses Plugins (27)](https://github.com/perses/plugins)
- [@perses-dev/plugin-system](https://github.com/perses/perses/tree/main/ui/plugin-system)
- [rsbuild Documentation](https://rsbuild.dev/)
- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)
