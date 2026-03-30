---
name: perses-code-review
user-invocable: false
description: "Perses-aware code review: Go backend, React UI, CUE schemas, dashboards."
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
    - "review Perses code"
    - "Perses PR review"
  category: code-review
---

# Perses Code Review

Review code changes in Perses repositories for domain-specific patterns, API conventions, plugin system compliance, and dashboard correctness. This skill enforces Perses-specific invariants across Go backend, React frontend, CUE schemas, and dashboard definitions — a passing `golangci-lint` or generic code review does not mean the code follows Perses conventions.

## Instructions

### Phase 1: CLASSIFY

**Goal**: Determine the review domains for this PR so you can apply the right checks to each file type.

1. List all changed files and categorize:
   - Go backend (`.go`) — files under `/cmd`, `/pkg`, `/internal`
   - React frontend (`.ts`, `.tsx`) — files in `@perses-dev/*` packages
   - CUE schemas (`.cue`)
   - Dashboard definitions (`.json`, `.yaml` with `kind: Dashboard`)

2. Identify cross-domain changes, because schema and plugin changes must stay synchronized. When a PR touches both CUE schemas and plugin code, the schema changes must match the plugin's expected input/output types — a plugin PR that adds configuration options without updating the corresponding CUE schema leaves the schema registry out of sync, causing UI options to fail CUE validation or the backend to accept options the UI cannot expose. Flag these for paired review.

3. Flag dashboard definition files for `percli lint` in Phase 2. Dashboard JSON can be structurally valid but semantically broken (invalid panel references, wrong plugin kinds, malformed variable expressions). Manual review catches some of these; `percli lint` catches all of them deterministically.

**Gate**: File classification complete. Domains identified.

### Phase 2: REVIEW

**Goal**: Apply Perses-specific review checks per domain. Route `.go` files to Go sub-reviewer, `.tsx`/`.ts` to React sub-reviewer, `.cue` to CUE sub-reviewer, and dashboard JSON/YAML to dashboard sub-reviewer.

#### Go backend (`/cmd`, `/pkg`, `/internal`)

- **Project-scoped API compliance**: All CRUD API handlers must be project-scoped at `/api/v1/projects/{project}/...` unless the resource is explicitly global (e.g., `GlobalDatasource`, `GlobalSecret`). This matters because projects provide multi-tenancy isolation — a handler that skips project-scoping for a non-global resource is a blocker and a security issue.

- **Paginated List endpoints**: Every `List` method in the storage layer must accept `page` and `size` query parameters and return a paginated response with total count, because Perses projects can contain hundreds of dashboards — an unpaginated `List` endpoint causes memory issues and slow API responses at scale. The frontend `useListResource` hook expects paginated responses. Block the PR until pagination is implemented.

- **Storage interface implementation**: New resources must implement the storage interface (`dao.go`) with all required CRUD methods including `List` with pagination support, so the API can expose all standard operations uniformly.

- **Auth middleware on global endpoints**: `GlobalDatasource`, `GlobalSecret`, and `GlobalVariable` endpoints must enforce admin-level authorization. Missing auth middleware on global resource endpoints is a security vulnerability — block immediately.

- **RESTful status codes**: Create returns 201, Update returns 200, Delete returns 204. Error responses must use Perses error types, not raw HTTP status codes, so clients can consistently parse API responses.

#### React frontend (`@perses-dev/*` packages)

- **Plugin system hooks required**: Components must use `usePlugin`, `useTimeRange`, `useDataQueries` from `@perses-dev/plugin-system`. Components that manage their own time range break dashboard-level time sync — users change the time picker and the panel does not update. Raw `fetch()` or `axios` calls in plugin components are a blocker because they bypass caching, auth token injection, datasource proxy routing, and the plugin contract for variable interpolation and refresh.

- **Component conventions**: Props must follow `@perses-dev/dashboards` type conventions. UI components must use `@perses-dev/components` rather than raw MUI, so the Perses design system stays consistent.

#### CUE schemas

- **`package model` required**: All Perses CUE schemas must be `package model` to be discoverable by the schema registry. `package main` in a CUE schema file makes it invisible to the registry — block immediately.

- **Closed specs**: Spec structs must use `close({})` because open schemas accept any field, defeating the purpose of schema validation — users can send garbage fields that silently pass validation.

- **JSON example file**: A `_example.json` must accompany each schema for documentation and validation. Missing examples are a warning (documentation gap).

- **Migration path**: When CUE schemas change, check `migrate/migrate.cue` for backward-compatible schema evolution, so existing dashboard definitions don't break.

#### Dashboard definitions

- **Run `percli lint`**: Execute `percli lint` on every dashboard file changed in the PR. Lint failures are blockers, because even small JSON changes can hide typos in `$ref` paths that break panel rendering silently.

- **Panel reference validation**: Panel keys in `$ref` must exactly match keys in `spec.panels`. Check for typos and naming convention mismatches (camelCase vs kebab-case), because unresolved `$ref` references cause render failures.

- **Variable chain ordering**: Variable evaluation order follows list order, not dependency order. Dependees must appear before dependents, because out-of-order variables produce empty interpolation with no error. Circular dependencies are blockers.

- **Datasource references**: Datasources must be referenced by name and explicit scope (`global`, `project`, `dashboard`). Cross-project references are invalid. Hardcoded datasource URLs in dashboard definitions are a blocker because they break when Perses is deployed in different environments.

- **`kind` field required**: Every Perses resource must have a `kind` field. Dashboard definitions without `kind: Dashboard` fail API validation on import — block immediately.

**Gate**: All domains reviewed. Findings collected.

### Phase 3: REPORT

**Goal**: Deliver structured review findings in a format that clearly distinguishes blockers (must fix) from warnings (should fix).

Report format:

1. **Summary**: One-line verdict (approve, request changes, blocker found)
2. **Blockers**: Issues that must be fixed before merge (with file path and line). A finding is a blocker if:
   - `percli lint` fails on any dashboard definition
   - CUE schema is not `package model` or uses open structs for spec types
   - API handler is missing project-scoping for a non-global resource
   - Plugin component uses raw HTTP instead of plugin system hooks
   - `$ref` panel references do not resolve to existing panel keys
   - Variable dependency chain is circular or out of order
   - Any forbidden pattern is present (hardcoded datasource URLs, `package main` in CUE, raw HTTP in plugins, global endpoints without admin auth, dashboards without `kind`)
3. **Warnings**: Issues that should be fixed but are not blocking (missing JSON example alongside CUE schema, implicit datasource scope, missing error handling for edge cases, test coverage gaps)
4. **Notes**: Observations and suggestions for improvement
5. **percli lint output**: Raw output if dashboard definitions were linted

**Gate**: Review report delivered. Task complete.

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Go API handler doesn't follow Perses CRUD patterns | Missing pagination on `List` endpoint, wrong HTTP status codes (e.g., 200 instead of 201 on create), no project-scoping | Flag as blocker. Perses `List` handlers must accept `?page=N&size=M` query params and return paginated results. Create returns 201, Update returns 200, Delete returns 204. All non-global resources must be under `/api/v1/projects/{project}/`. |
| React component doesn't use `@perses-dev/plugin-system` hooks | Component uses raw `fetch()` or direct state for time range instead of `usePlugin`, `useTimeRange`, `useDataQueries` from the plugin system | Flag as blocker. Perses plugins MUST use the plugin system hooks to participate in the dashboard lifecycle (time range sync, variable interpolation, refresh). Direct data fetching bypasses the plugin contract. |
| CUE schema not in `package model` or spec not closed | Schema declares `package foo` instead of `package model`, uses open struct `{}` instead of `close({})`, no JSON example file alongside | Flag as blocker. All Perses CUE schemas must be `package model` to be discoverable by the schema registry. Specs must use `close({})` to prevent unexpected fields. A `_example.json` must accompany each schema for documentation and validation. |
| Dashboard definition has invalid `$ref` panel references | Layout references `$ref: #/spec/panels/myPanel` but panel key is `my-panel` or doesn't exist, causing render failures | Flag as blocker. Panel keys in `$ref` must exactly match keys in `spec.panels`. Run `percli lint` to catch these. Check for typos and naming convention mismatches (camelCase vs kebab-case). |
| Broken variable chains in dashboard | Variable B depends on variable A via `$A` in its query, but A is defined after B in the variables list, or A doesn't exist | Flag as blocker. Variable evaluation order follows list order. Dependees must appear before dependents. Missing variables cause silent empty interpolation. |
| Wrong datasource scope | Dashboard uses `datasource: {name: "prom"}` without specifying scope, or references a project datasource from a different project | Flag as warning. Datasources have three scopes: `global` (cluster-wide), `project` (project-level), `dashboard` (inline). The scope must be explicit. Cross-project references are invalid. |

## References

- [Perses GitHub Repository](https://github.com/perses/perses) — canonical source for patterns
- [Perses Plugin System Docs](https://perses.dev/docs/plugins/) — plugin development conventions
- [CUE Schema Guide](https://perses.dev/docs/cue/) — schema authoring requirements
- [Perses API Reference](https://perses.dev/docs/api/) — REST API patterns and scoping
- [percli Documentation](https://perses.dev/docs/percli/) — CLI tool including `percli lint`
- [Dashboard Specification](https://perses.dev/docs/dashboards/) — panel references, variables, layouts
