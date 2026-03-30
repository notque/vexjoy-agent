---
name: perses-plugin-test
user-invocable: false
description: "Perses plugin testing: CUE schema tests, React tests, integration tests."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-plugin-engineer
version: 2.0.0
routing:
  triggers:
    - "test Perses plugin"
    - "plugin testing"
  category: perses
---

# Perses Plugin Testing

Test Perses plugins across four layers: CUE schema validation, React component unit tests, integration testing against a live Perses server, and Grafana migration compatibility.

## Overview

This skill validates Perses plugin correctness from schemas through rendered components. Testing follows a strict four-phase order because each layer depends on the previous one passing — schema tests must succeed before component tests, which must succeed before integration tests, which must succeed before migration tests.

**STOP before proceeding if**:
- `percli` is not installed or not on PATH
- No CUE schemas exist in the plugin (nothing to test with `test-schemas`)
- The plugin has no JSON examples and you'd need to create them from scratch
- Integration testing is requested but no local Perses server is available and Docker is not installed
- Migration testing is requested but no `migrate/migrate.cue` file exists in the plugin
- Schema tests produce errors you cannot diagnose from the CUE output alone

---

## Instructions

### Phase 1: SCHEMA TESTS

**Goal**: Validate all CUE schemas compile and match their JSON examples.

1. **Verify schema structure**: Each schema file must have `package model` at the top (because `percli plugin test-schemas` silently skips files without this declaration) and use `close({...})` for strict field validation (because this rejects JSON examples with unknown fields).

2. **Check JSON examples exist**: Every schema at `schemas/<type>/<name>/` must have a corresponding `<name>.json` file (because every CUE schema needs matching JSON example for test coverage).

3. **Run schema tests**:
```bash
percli plugin test-schemas
```

4. **On failure**: Read the CUE error output carefully — common issues are missing `package model` declarations, unclosed braces in `close({...})` specs, or JSON examples with fields not defined in the schema. Fix errors in this phase before proceeding to Phase 2 (because component and integration tests are meaningless if schemas are invalid).

**Gate**: All schema tests pass. Proceed to Phase 2.

### Phase 2: COMPONENT TESTS

**Goal**: Run React component unit tests.

1. **Verify test setup**: Component tests must mock `@perses-dev/plugin-system` hooks (e.g., `useDataQueries`, `useTimeRange`) with realistic return values (because tests pass but don't verify correctness if hooks return empty stubs).

2. **Run tests**:
```bash
npm test -- --watchAll=false
```

3. **Check coverage**: Ensure plugin component renders without errors and handles empty/error states. Create multiple JSON examples per schema — minimal (required fields only), full (all fields), and edge cases (empty arrays, null values) (because one example may only exercise the default branch of a union type; other branches remain untested).

**Gate**: All component tests pass. Proceed to Phase 3.

### Phase 3: INTEGRATION TESTS

**Goal**: Verify the plugin works inside a running Perses instance.

1. **Start local Perses server** (if not already running; use `localhost` only, never a shared or production server, because tests may corrupt real data, hit rate limits, or produce non-reproducible results):
```bash
docker run --name perses-test -d -p 127.0.0.1:8080:8080 persesdev/perses
```

2. **Start plugin dev server**:
```bash
percli plugin start
```

3. **Verify plugin loads**: Confirm the plugin appears in the Perses UI panel type selector.

4. **Test with real data**: Create a dashboard using this plugin and verify it renders with a connected datasource (because integration tests catch issues that unit tests cannot: plugin registration, data binding, and render lifecycle).

**Gate**: Plugin loads and renders in local Perses. Proceed to Phase 4.

### Phase 4: MIGRATION TESTS (if applicable)

**Goal**: Verify Grafana dashboard JSON converts correctly through migration logic.

1. **Locate migration schema**: Check for `migrate/migrate.cue`.

2. **Prepare test fixtures**: Use sample Grafana dashboard JSON that exercises all panel types this plugin handles. Test migration with diverse Grafana fixtures covering all supported panel types (because your dashboard may only use a subset of panel types; other users' dashboards will have panels you didn't test).

3. **Run migration**:
```bash
percli migrate --input grafana-dashboard.json --output perses-dashboard.json
```

4. **Validate output**: Verify the migrated dashboard JSON matches expected Perses schema structure and test the output against the Perses schema (because upstream Grafana panel JSON evolves independently; a working migration can break without any local changes).

**Gate**: Migration produces valid Perses dashboard JSON. Task complete.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `percli plugin test-schemas` fails with "cannot find package" | CUE file missing `package model` declaration at top of file | Add `package model` as the first line of every CUE schema file |
| `percli plugin test-schemas` fails with parse error | Unclosed `close({...})` spec or mismatched braces in CUE | Count opening/closing braces; ensure every `close(` has matching `)` and every `{` has matching `}` |
| `percli plugin test-schemas` fails with import error | Wrong CUE import path (e.g., using Go-style paths instead of CUE module paths) | Check `cue.mod/module.cue` for the module name and use it as the import prefix |
| `percli plugin test-schemas` reports extra fields | JSON example contains fields not defined in the CUE schema | Either add the field to the CUE schema or remove it from the JSON example; `close()` rejects unknown fields |
| React test: "Cannot find module '@perses-dev/plugin-system'" | Missing mock setup for the plugin system dependency | Add `jest.mock('@perses-dev/plugin-system')` or create `__mocks__/@perses-dev/plugin-system.js` with stub hooks |
| React test: "Invalid hook call" | Using wrong test renderer or missing React context providers | Wrap component in `<PluginRegistry>` provider during tests; use `@testing-library/react` not `react-test-renderer` |
| Integration test: connection refused on port 8080 | Local Perses server not running or bound to a different port | Start server with `docker run -p 127.0.0.1:8080:8080 persesdev/perses` and verify with `curl http://localhost:8080/api/v1/health` |
| Integration test: 401 Unauthorized | Perses server has auth enabled but test is not authenticating | Run `percli login http://localhost:8080 --username admin --password <password>` before testing, or disable auth for local test instance |
| Migration test: unexpected panel type | Grafana dashboard JSON contains panel types not handled by `migrate/migrate.cue` | Add a migration case for the new panel type in `migrate.cue`, or filter unsupported panels before migration |
| Migration test: schema version mismatch | Grafana JSON structure changed between versions (e.g., v8 vs v10 panel format) | Check the Grafana version in the test fixture and ensure `migrate.cue` handles that version's structure |

---

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/)
- [CUE Language Specification](https://cuelang.org/docs/references/spec/)
- [percli CLI Reference](https://perses.dev/docs/percli/)
- [Perses Official Plugins (27 plugins)](https://github.com/perses/plugins)
- [@perses-dev/plugin-system API](https://github.com/perses/perses/tree/main/ui/plugin-system)
- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)
