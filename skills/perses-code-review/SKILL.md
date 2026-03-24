---
name: perses-code-review
user-invocable: false
description: |
  Perses-aware code review: check Go backend against Perses patterns, React components
  against Perses UI conventions, CUE schemas against plugin spec, and dashboard
  definitions against best practices. Dispatches appropriate sub-reviewers. Use for
  "review perses", "perses pr", "perses code review". Do NOT use for general Go/React
  review without Perses context.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - Agent
agent: perses-core-engineer
version: 2.0.0
routing:
  triggers:
    - "review Perses code"
    - "Perses PR review"
  category: code-review
---

# Perses Code Review

Review code changes in Perses repositories for domain-specific patterns, API conventions, plugin system compliance, and dashboard correctness. This is not a general-purpose code reviewer — it enforces Perses-specific invariants across Go backend, React frontend, CUE schemas, and dashboard definitions.

## Operator Context

This skill operates as a Perses-domain code reviewer. It understands the project layout (`/cmd`, `/pkg`, `/internal`), the plugin system (`@perses-dev/*`), CUE schema conventions, and dashboard definition structure. It dispatches sub-reviewers per file type and aggregates findings.

### Hardcoded Behaviors (Always Apply)
- **Perses-specific focus**: Review against Perses patterns, not generic Go/React/CUE style guides. A passing `golangci-lint` does not mean the code follows Perses conventions.
- **CUE schema validation**: Every CUE schema must be in `package model`, use `close({})` for specs, and include a JSON example alongside the schema definition.
- **Dashboard definition validation**: Validate `$ref` panel references resolve, variable chains are acyclic, and datasource scopes (`global`, `project`, `dashboard`) are correct.
- **Project-scoped API compliance**: All CRUD API handlers must be project-scoped at `/api/v1/projects/{project}/...` unless the resource is explicitly global (e.g., `GlobalDatasource`, `GlobalSecret`).
- **percli lint gate**: Run `percli lint` on any dashboard JSON/YAML definitions touched in the PR. Lint failures are blockers.

### Default Behaviors (ON unless disabled)
- **Multi-domain dispatch**: Route `.go` files to Go sub-reviewer, `.tsx`/`.ts` to React sub-reviewer, `.cue` to CUE sub-reviewer, dashboard JSON/YAML to dashboard sub-reviewer.
- **Cross-domain correlation**: When a PR touches both CUE schemas and plugin code, verify the schema changes match the plugin's expected input/output types.
- **Storage interface check**: Verify new resources implement the storage interface (`dao.go`) with all required CRUD methods including `List` with pagination support.

### Optional Behaviors (OFF unless enabled)
- **Migration review**: Check `migrate/migrate.cue` for backward-compatible schema evolution when CUE schemas change.
- **E2E test coverage**: Verify that new API endpoints have corresponding E2E tests in the test suite.
- **Performance review**: Flag N+1 queries in storage implementations and unbounded list operations.

## What This Skill CAN Do
- Review Go backend code for Perses API patterns, storage interface compliance, and auth middleware usage
- Review React frontend code for `@perses-dev/plugin-system` hook usage and component conventions
- Review CUE schemas for `package model` compliance, closed specs, and JSON examples
- Validate dashboard definitions for panel references, variable chains, and datasource scoping
- Run `percli lint` on dashboard definitions and report failures
- Correlate cross-domain changes (schema + plugin, API + frontend)

## What This Skill CANNOT Do
- Deploy Perses instances (use `perses-deploy`)
- Create dashboards from scratch (use `perses-dashboard-create`)
- Develop new plugins (use `perses-plugin-create`)
- Perform general Go or React code review without Perses context (use `golang-general-engineer` or `typescript-frontend-engineer`)
- Run the full Perses test suite (use CI/CD)

---

## Error Handling

| Cause | Symptom | Solution |
|-------|---------|----------|
| Go API handler doesn't follow Perses CRUD patterns | Missing pagination on `List` endpoint, wrong HTTP status codes (e.g., 200 instead of 201 on create), no project-scoping | Flag as blocker. Perses `List` handlers must accept `?page=N&size=M` query params and return paginated results. Create returns 201, Update returns 200, Delete returns 204. All non-global resources must be under `/api/v1/projects/{project}/`. |
| React component doesn't use `@perses-dev/plugin-system` hooks | Component uses raw `fetch()` or direct state for time range instead of `usePlugin`, `useTimeRange`, `useDataQueries` from the plugin system | Flag as blocker. Perses plugins MUST use the plugin system hooks to participate in the dashboard lifecycle (time range sync, variable interpolation, refresh). Direct data fetching bypasses the plugin contract. |
| CUE schema not in `package model` or spec not closed | Schema declares `package foo` instead of `package model`, uses open struct `{}` instead of `close({})`, no JSON example file alongside | Flag as blocker. All Perses CUE schemas must be `package model` to be discoverable by the schema registry. Specs must use `close({})` to prevent unexpected fields. A `_example.json` must accompany each schema for documentation and validation. |
| Dashboard definition has invalid `$ref` panel references | Layout references `$ref: #/spec/panels/myPanel` but panel key is `my-panel` or doesn't exist, causing render failures | Flag as blocker. Panel keys in `$ref` must exactly match keys in `spec.panels`. Run `percli lint` to catch these. Check for typos and naming convention mismatches (camelCase vs kebab-case). |
| Broken variable chains in dashboard | Variable B depends on variable A via `$A` in its query, but A is defined after B in the variables list, or A doesn't exist | Flag as blocker. Variable evaluation order follows list order. Dependees must appear before dependents. Missing variables cause silent empty interpolation. |
| Wrong datasource scope | Dashboard uses `datasource: {name: "prom"}` without specifying scope, or references a project datasource from a different project | Flag as warning. Datasources have three scopes: `global` (cluster-wide), `project` (project-level), `dashboard` (inline). The scope must be explicit. Cross-project references are invalid. |

---

## Anti-Patterns

### 1. Reviewing Perses code with a general Go/React reviewer
**Why it fails**: A general Go reviewer will approve an API handler that returns a flat list without pagination, uses generic error responses, or doesn't enforce project-scoping. These are all Perses-specific requirements that generic linters and reviewers miss entirely.
**What to do instead**: Always route through this skill when the changed code lives in a Perses repository.

### 2. Not running `percli lint` on dashboard definitions in the PR
**Why it fails**: Dashboard JSON can have structurally valid YAML/JSON but semantically broken panel references, invalid plugin kinds, or malformed variable expressions. Manual review catches some of these, but `percli lint` catches all of them deterministically.
**What to do instead**: Run `percli lint` on every dashboard file changed in the PR. Treat lint failures as blockers.

### 3. Ignoring CUE schema changes when reviewing plugin PRs
**Why it fails**: A plugin PR that adds new configuration options without updating the corresponding CUE schema means the schema registry is out of sync. Users will be able to set options in the UI that fail CUE validation, or the UI won't expose options that the backend accepts.
**What to do instead**: When a plugin PR touches TypeScript types or Go structs, check that the corresponding `.cue` schema file is also updated and that the JSON example reflects the new fields.

### 4. Approving storage implementations without pagination
**Why it fails**: Perses projects can contain hundreds of dashboards. A `List` endpoint that returns all results without pagination will cause memory issues and slow API responses at scale. The frontend `useListResource` hook expects paginated responses.
**What to do instead**: Verify every `List` method in the storage layer accepts `page` and `size` parameters and returns a paginated response with total count.

---

## Anti-Rationalization

| Rationalization | Reality | Required Action |
|-----------------|---------|-----------------|
| "It's just a small dashboard JSON change, no need to lint" | Small JSON changes are where typos in `$ref` paths hide. A single wrong character breaks panel rendering silently. | **Run `percli lint`. Always.** |
| "The Go handler works, it just doesn't paginate yet" | "Yet" means never once it ships. Unpaginated list endpoints are tech debt that causes production incidents at scale. | **Block the PR until pagination is implemented.** |
| "The CUE schema is fine without `close()`, it still validates" | Open schemas accept any field, defeating the purpose of schema validation. Users will send garbage fields that silently pass validation. | **Require `close({})` on all spec structs.** |
| "This React component doesn't need `useTimeRange`, it manages its own time" | Components that manage their own time range break dashboard-level time sync. Users change the time picker and this panel doesn't update. | **Use `useTimeRange` from `@perses-dev/plugin-system`.** |
| "The variable ordering doesn't matter, the engine resolves dependencies" | The Perses variable engine evaluates in list order, not dependency order. Out-of-order variables produce empty interpolation with no error. | **Verify variable dependency order matches list order.** |

---

## FORBIDDEN Patterns

These are hard stops. If encountered, block the PR immediately.

- **Hardcoded datasource URLs in dashboard definitions** — Datasources must be referenced by name and scope, never by direct URL. Hardcoded URLs break when Perses is deployed in different environments.
- **`package main` in CUE schema files** — CUE schemas must be `package model`. Using `package main` makes the schema invisible to the Perses schema registry.
- **Raw HTTP calls in plugin React components** — Plugins must use the Perses plugin system (`useDataQueries`, `usePlugin`) for data fetching. Raw `fetch()` or `axios` calls bypass caching, auth token injection, and datasource proxy routing.
- **Global resource endpoints without admin auth middleware** — `GlobalDatasource`, `GlobalSecret`, and `GlobalVariable` endpoints must enforce admin-level authorization. Missing auth middleware is a security vulnerability.
- **Dashboard definitions without a `kind` field** — Every Perses resource must have a `kind` field. Dashboard definitions without `kind: Dashboard` will fail API validation on import.

---

## Blocker Criteria

A finding is a **blocker** (must fix before merge) if any of these apply:

1. `percli lint` fails on any dashboard definition in the PR
2. CUE schema is not in `package model` or uses open structs for spec types
3. API handler is missing project-scoping for a non-global resource
4. Plugin component uses raw HTTP instead of plugin system hooks
5. `$ref` panel references don't resolve to existing panel keys
6. Variable dependency chain is circular or out of order
7. Any FORBIDDEN pattern is present

A finding is a **warning** (should fix, not blocking) if:

1. Missing JSON example alongside new CUE schema (documentation gap)
2. Datasource scope is implicit rather than explicit
3. Missing error handling for specific edge cases
4. Test coverage gaps for new functionality

---

## Instructions

### Phase 1: CLASSIFY

**Goal**: Determine the review domains for this PR.

1. List all changed files and categorize: Go backend (`.go`), React frontend (`.ts`, `.tsx`), CUE schemas (`.cue`), dashboard definitions (`.json`, `.yaml` with `kind: Dashboard`)
2. Identify cross-domain changes — does the PR touch both schema and plugin? Both API and frontend?
3. Check for dashboard definition files that need `percli lint`

**Gate**: File classification complete. Domains identified.

### Phase 2: REVIEW

**Goal**: Apply Perses-specific review checks per domain.

**Go backend** (`/cmd`, `/pkg`, `/internal`):
- API handlers at `/api/v1/*` follow RESTful CRUD with project scoping
- Storage interfaces implement all required methods including paginated `List`
- Auth middleware is applied to global resource endpoints
- Error responses use Perses error types, not raw HTTP status codes

**React frontend** (`@perses-dev/*` packages):
- Components use `usePlugin`, `useTimeRange`, `useDataQueries` from `@perses-dev/plugin-system`
- No raw `fetch()` or `axios` calls in plugin components
- Component props follow `@perses-dev/dashboards` type conventions
- UI components use `@perses-dev/components` rather than raw MUI

**CUE schemas**:
- Schema is `package model`
- Spec structs use `close({})`
- JSON example file exists alongside schema
- If schema changed, check `migrate/migrate.cue` for migration path

**Dashboard definitions**:
- Run `percli lint` on all dashboard files
- Validate `$ref` panel references resolve
- Check variable chains for circular dependencies and ordering
- Verify datasource references use name + explicit scope

**Gate**: All domains reviewed. Findings collected.

### Phase 3: REPORT

**Goal**: Deliver structured review findings.

Report format:
1. **Summary**: One-line verdict (approve, request changes, blocker found)
2. **Blockers**: Issues that must be fixed before merge (with file path and line)
3. **Warnings**: Issues that should be fixed but are not blocking
4. **Notes**: Observations and suggestions for improvement
5. **percli lint output**: Raw output if dashboard definitions were linted

**Gate**: Review report delivered. Task complete.

---

## References

- [Perses GitHub Repository](https://github.com/perses/perses) — canonical source for patterns
- [Perses Plugin System Docs](https://perses.dev/docs/plugins/) — plugin development conventions
- [CUE Schema Guide](https://perses.dev/docs/cue/) — schema authoring requirements
- [Perses API Reference](https://perses.dev/docs/api/) — REST API patterns and scoping
- [percli Documentation](https://perses.dev/docs/percli/) — CLI tool including `percli lint`
- [Dashboard Specification](https://perses.dev/docs/dashboards/) — panel references, variables, layouts
