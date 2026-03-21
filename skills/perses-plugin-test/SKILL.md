---
name: perses-plugin-test
user-invocable: false
description: |
  Perses plugin testing: CUE schema unit tests with percli plugin test-schemas, React
  component tests, integration testing with local Perses server, and Grafana migration
  compatibility testing. Use for "test perses plugin", "perses plugin test",
  "perses schema test". Do NOT use for dashboard validation (use perses-lint).
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

# Perses Plugin Testing

Test Perses plugins across four layers: CUE schema validation, React component unit tests, integration testing against a live Perses server, and Grafana migration compatibility.

## Operator Context

This skill validates Perses plugin correctness from schemas through rendered components. Testing follows a strict order because each layer depends on the previous one passing.

### Hardcoded Behaviors (Always Apply)
- **Schema tests first**: Always run `percli plugin test-schemas` before any other test layer — component and integration tests are meaningless if schemas are invalid
- **JSON examples required**: Every CUE schema must have a matching JSON example at `schemas/<type>/<name>/<name>.json` for test coverage
- **`package model` declaration**: Every CUE schema file must declare `package model` — `percli plugin test-schemas` silently skips files without it
- **Local server only**: Integration tests must target a local Perses instance (`localhost`), never a shared or production server
- **Validate all 27 official plugins**: When testing a plugin that extends or wraps an official plugin, verify compatibility with the upstream schema

### Default Behaviors (ON unless disabled)
- **Run all four phases**: Execute schema, component, integration, and migration tests in order
- **Stop on phase failure**: If a phase fails, fix it before proceeding to the next phase
- **CUE `close({...})` validation**: Verify schemas use `close()` to reject unknown fields in JSON examples

### Optional Behaviors (OFF unless enabled)
- **Cross-plugin compatibility**: Test that this plugin's output works alongside other plugins in the same dashboard
- **Performance profiling**: Measure React component render time with React Profiler during integration tests
- **Snapshot testing**: Generate and compare React component snapshots across test runs

## What This Skill CAN Do
- Validate CUE schemas against JSON examples using `percli plugin test-schemas`
- Run React component unit tests with mocked `@perses-dev/plugin-system` hooks
- Start a hot-reload dev server with `percli plugin start` for integration testing
- Test Grafana dashboard migration logic against sample JSON fixtures
- Diagnose common CUE syntax errors (missing package declaration, unclosed specs, bad imports)

## What This Skill CANNOT Do
- Create new plugins from scratch (use perses-plugin-create)
- Validate full dashboards or datasource connectivity (use perses-lint)
- Deploy or configure a Perses server (use perses-deploy)
- Write CUE schemas — this skill only tests them

---

## Instructions

### Phase 1: SCHEMA TESTS

**Goal**: Validate all CUE schemas compile and match their JSON examples.

1. **Verify schema structure**: Each schema file must have `package model` at the top and use `close({...})` for strict validation
2. **Check JSON examples exist**: Every schema at `schemas/<type>/<name>/` must have a corresponding `<name>.json`
3. **Run schema tests**:
```bash
percli plugin test-schemas
```
4. **On failure**: Read the CUE error output carefully — common issues are missing imports, unclosed braces, or JSON examples with fields not in the schema

**Gate**: All schema tests pass. Proceed to Phase 2.

### Phase 2: COMPONENT TESTS

**Goal**: Run React component unit tests.

1. **Verify test setup**: Component tests must mock `@perses-dev/plugin-system` hooks (e.g., `useDataQueries`, `useTimeRange`)
2. **Run tests**:
```bash
npm test -- --watchAll=false
```
3. **Check coverage**: Ensure plugin component renders without errors and handles empty/error states

**Gate**: All component tests pass. Proceed to Phase 3.

### Phase 3: INTEGRATION TESTS

**Goal**: Verify the plugin works inside a running Perses instance.

1. **Start local Perses server** (if not already running):
```bash
docker run --name perses-test -d -p 127.0.0.1:8080:8080 persesdev/perses
```
2. **Start plugin dev server**:
```bash
percli plugin start
```
3. **Verify plugin loads**: Confirm the plugin appears in the Perses UI panel type selector
4. **Test with real data**: Create a dashboard using this plugin and verify it renders with a connected datasource

**Gate**: Plugin loads and renders in local Perses. Proceed to Phase 4.

### Phase 4: MIGRATION TESTS (if applicable)

**Goal**: Verify Grafana dashboard JSON converts correctly through migration logic.

1. **Locate migration schema**: Check for `migrate/migrate.cue`
2. **Prepare test fixtures**: Use sample Grafana dashboard JSON that exercises all panel types this plugin handles
3. **Run migration**:
```bash
percli migrate --input grafana-dashboard.json --output perses-dashboard.json
```
4. **Validate output**: Verify the migrated dashboard JSON matches expected Perses schema structure

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

## Anti-Patterns

| Anti-Pattern | Why It Fails | Do Instead |
|--------------|-------------|------------|
| Running component tests before schema tests pass | Components depend on valid schemas; testing components against broken schemas produces misleading failures | Always run `percli plugin test-schemas` first and fix all schema errors before touching component tests |
| Testing against a shared or production Perses server | Tests may corrupt real data, hit rate limits, or fail due to network latency; results are non-reproducible | Always use a local Perses instance via Docker or binary — disposable and isolated |
| JSON examples that only test the happy path | Schemas with optional fields, unions, or conditional logic have branches that never get exercised | Create multiple JSON examples per schema: minimal (required fields only), full (all fields), and edge cases (empty arrays, null values) |
| Skipping migration tests because "the schema didn't change" | Upstream Grafana panel JSON evolves independently; a working migration can break without any local changes | Run migration tests against current Grafana sample fixtures on every test cycle |
| Mocking the entire plugin-system module with empty stubs | Tests pass but don't verify that hooks are called correctly or return expected shapes | Mock individual hooks with realistic return values (e.g., `useTimeRange` returns `{ start, end }`) |

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "Schema tests pass so the plugin works" | Schema tests only validate CUE syntax and JSON conformance — they say nothing about whether the React component renders | **Run all four phases** |
| "I tested with one JSON example and it passed" | One example may only exercise the default branch of a union type; other branches remain untested | **Create JSON examples for every schema variant** |
| "Integration tests are slow, I'll skip them this time" | Integration tests catch issues that unit tests cannot: plugin registration, data binding, render lifecycle | **Always run integration tests against local Perses** |
| "The migration worked for my Grafana dashboard" | Your dashboard may only use a subset of panel types; other users' dashboards will have panels you didn't test | **Test migration with diverse Grafana fixtures covering all supported panel types** |

---

## FORBIDDEN Patterns

These are hard stops. If you encounter these, fix them before proceeding:

- **NEVER** run integration tests against a non-localhost Perses URL
- **NEVER** commit CUE schemas that lack `package model` — `percli` will silently ignore them
- **NEVER** skip schema tests and jump straight to component or integration tests
- **NEVER** use `percli plugin test-schemas` output as proof that React components work
- **NEVER** test migrations without validating the output against the Perses schema

---

## Blocker Criteria

Stop and ask the user before proceeding if:

- `percli` is not installed or not on PATH
- No CUE schemas exist in the plugin (nothing to test with `test-schemas`)
- The plugin has no JSON examples and you'd need to create them from scratch
- Integration testing is requested but no local Perses server is available and Docker is not installed
- Migration testing is requested but no `migrate/migrate.cue` file exists in the plugin
- Schema tests produce errors you cannot diagnose from the CUE output alone

---

## References

- [Perses Plugin Development Guide](https://perses.dev/docs/plugins/)
- [CUE Language Specification](https://cuelang.org/docs/references/spec/)
- [percli CLI Reference](https://perses.dev/docs/percli/)
- [Perses Official Plugins (27 plugins)](https://github.com/perses/plugins)
- [@perses-dev/plugin-system API](https://github.com/perses/perses/tree/main/ui/plugin-system)
- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)
