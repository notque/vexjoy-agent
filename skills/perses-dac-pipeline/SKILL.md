---
name: perses-dac-pipeline
user-invocable: false
description: |
  Dashboard-as-Code pipeline: initialize CUE or Go module with percli dac setup,
  write dashboard definitions, build with percli dac build, validate, apply, and
  integrate with CI/CD via GitHub Actions (perses/cli-actions). Use for "dashboard
  as code", "perses dac", "perses cue", "perses gitops", "perses ci/cd". Do NOT
  use for one-off dashboard creation (use perses-dashboard-create) or Grafana
  migration (use perses-grafana-migrate).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
---

# Perses Dashboard-as-Code Pipeline

Set up and manage Dashboard-as-Code workflows with CUE or Go SDK.

## Operator Context

This skill operates as a pipeline for Dashboard-as-Code workflows, from module initialization through CI/CD integration.

### Hardcoded Behaviors (Always Apply)
- **One dashboard per file**: Follow Perses convention of one dashboard definition per file — keeps diffs clean and enables per-dashboard CI validation
- **Build before apply**: Always run `percli dac build` before `percli apply` — raw CUE/Go files cannot be applied directly
- **Validate built output**: Always run `percli lint` on built JSON/YAML before deploying — build success does not guarantee valid dashboard spec
- **Go SDK stdout warning**: Never log/print to stdout in Go DaC programs — `dac build` captures stdout as the dashboard definition, so any stray output corrupts it

### Default Behaviors (ON unless disabled)
- **CUE SDK**: Default to CUE SDK unless user requests Go
- **JSON output**: Build to JSON format by default
- **Git-friendly**: Organize files for version control (one dashboard per file, clear naming)

### Optional Behaviors (OFF unless enabled)
- **Go SDK**: Use Go SDK instead of CUE for teams more comfortable with Go
- **YAML output**: Build to YAML format instead of JSON

## What This Skill CAN Do
- Initialize CUE or Go DaC modules
- Write dashboard definitions using SDK builders
- Build definitions to JSON/YAML
- Set up CI/CD with GitHub Actions
- Manage multi-dashboard repositories

## What This Skill CANNOT Do
- Create custom plugins (use perses-plugin-create)
- Deploy Perses server (use perses-deploy)
- Migrate Grafana dashboards (use perses-grafana-migrate)

---

## Instructions

### Phase 1: INITIALIZE

**Goal**: Set up the DaC module.

**CUE SDK** (default):
```bash
mkdir -p dac && cd dac
cue mod init my-dashboards
percli dac setup
cue mod tidy
```
Requirements: `percli` >= v0.51.0, `cue` >= v0.12.0

**Go SDK**:
```bash
mkdir -p dac && cd dac
go mod init my-dashboards
percli dac setup --language go
go mod tidy
```
Requirements: `percli` >= v0.44.0, Go installed

**Gate**: Module initialized, dependencies resolved. `cue mod tidy` or `go mod tidy` succeeds without errors. Proceed to Phase 2.

### Phase 2: DEFINE

**Goal**: Write dashboard definitions using SDK builders.

CUE example structure:
```
dac/
├── cue.mod/
├── dashboards/
│   ├── cpu-monitoring.cue
│   └── network-overview.cue
└── shared/
    ├── datasources.cue
    └── variables.cue
```

CUE DaC imports from `github.com/perses/perses/cue/dac-utils/*`.
Go DaC imports from `github.com/perses/perses/go-sdk`.

**Gate**: Dashboard definitions written. Files parse without syntax errors. Proceed to Phase 3.

### Phase 3: BUILD

**Goal**: Build definitions to deployable format.

```bash
# Single file
percli dac build -f dashboards/cpu-monitoring.cue -ojson

# Directory (all dashboards)
percli dac build -d dashboards/ -ojson

# Go SDK
percli dac build -f main.go -ojson
```

Output appears in `built/` directory.

**Gate**: Build succeeds, JSON/YAML output in `built/`. Proceed to Phase 4.

### Phase 4: VALIDATE

**Goal**: Ensure built dashboards are valid.

```bash
percli lint -f built/cpu-monitoring.json
# Or with server validation
percli lint -f built/cpu-monitoring.json --online
```

**Gate**: Validation passes. Proceed to Phase 5.

### Phase 5: DEPLOY

**Goal**: Apply dashboards to Perses.

```bash
percli apply -f built/cpu-monitoring.json --project <project>
```

Verify deployment:
```bash
percli get dashboard --project <project>
```

**Gate**: Dashboards deployed and accessible. Proceed to Phase 6 if CI/CD is requested.

### Phase 6: CI/CD INTEGRATION (optional)

**Goal**: Set up GitHub Actions for automated DaC pipeline.

```yaml
name: Dashboard-as-Code
on:
  push:
    paths: ['dac/**']
jobs:
  dac:
    uses: perses/cli-actions/.github/workflows/dac.yaml@v0.1.0
    with:
      url: ${{ vars.PERSES_URL }}
      directory: ./dac
      server-validation: true
    secrets:
      username: ${{ secrets.PERSES_USERNAME }}
      password: ${{ secrets.PERSES_PASSWORD }}
```

**Gate**: CI/CD pipeline configured and tested. Pipeline complete.

---

## Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| `cue mod tidy` fails with "no CUE module found" | CUE module not initialized — `cue mod init` was skipped or ran in wrong directory | Run `cue mod init <module-name>` in the `dac/` directory before running `percli dac setup` |
| `cue mod tidy` fails with version/dependency errors | CUE version too old (< 0.12.0) or incompatible with `percli dac setup` output | Verify `cue version` shows >= 0.12.0. Upgrade CUE if needed. Run `percli dac setup` again after upgrade |
| `percli dac build` produces empty `built/` directory | CUE expression does not evaluate to a valid dashboard object, or the entry file path is wrong | Verify the file path passed to `-f` is correct. Ensure the CUE file evaluates to a Perses dashboard (imports `dac-utils` and uses dashboard builder). Check for CUE evaluation errors in stderr |
| `percli dac build` output contains non-JSON lines (Go SDK) | Go program prints to stdout via `fmt.Println`, `log.Println`, or similar — `dac build` captures all stdout as the dashboard definition | Remove ALL stdout prints from Go DaC code. Use `fmt.Fprintln(os.Stderr, ...)` for debug output. Check imported libraries for stray stdout writes |
| CI/CD pipeline fails with 401/403 | `PERSES_USERNAME` / `PERSES_PASSWORD` secrets not configured in GitHub repository, or credentials are wrong | Add secrets in GitHub repo Settings > Secrets. Verify credentials work locally with `percli login` first |
| CI/CD pipeline fails with connection refused | `PERSES_URL` variable points to wrong server or server is not reachable from GitHub Actions runner | Verify the URL is publicly accessible (not localhost). Check `vars.PERSES_URL` is set in GitHub repo Settings > Variables |
| `percli lint` fails on valid-looking JSON | Dashboard JSON is structurally valid but violates Perses schema (e.g., unknown panel type, missing required field) | This is the system working correctly — fix the dashboard definition and rebuild. Run `percli lint --online` against a live server for detailed validation errors |

---

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|-------------|-------------|-----------------|
| **Multiple dashboards in one CUE file** | Makes diffs noisy, CI runs everything on any change, harder to review | One dashboard per file in `dac/dashboards/`. Use `dac/shared/` for common definitions |
| **Running `percli apply` directly on CUE/Go files** | `percli apply` expects built JSON/YAML, not raw source files — will fail or produce garbage | Always run `percli dac build` first, then `percli apply -f built/<file>.json` |
| **Skipping `percli lint` after successful build** | Build success means valid CUE/Go syntax, NOT valid Perses dashboard — panels, datasources, variables can still be wrong | Always lint built output: `percli lint -f built/<file>.json` |
| **Using `fmt.Println` / `log.Println` in Go SDK** | `percli dac build` captures stdout as dashboard JSON — any print statement corrupts the output with non-JSON text | Use `fmt.Fprintln(os.Stderr, ...)` for debug output. Remove all stdout writes before building |
| **Hardcoding Perses URL in CI workflow** | URL changes break the pipeline, credentials leak if URL contains auth | Use `vars.PERSES_URL` variable and `secrets.PERSES_USERNAME` / `secrets.PERSES_PASSWORD` secrets |
| **Committing the `built/` directory to git** | Built artifacts are derived output — committing them causes merge conflicts and staleness | Add `built/` to `.gitignore`. Let CI/CD rebuild from source on every push |

---

## Anti-Rationalization

These are common justifications for skipping steps. Each one leads to real failures.

| Rationalization | Why It Fails | Required Action |
|----------------|-------------|-----------------|
| "Build succeeded, so the dashboard is valid" | `percli dac build` only validates CUE/Go syntax, not Perses dashboard semantics — panels can reference nonexistent datasources, variables can have wrong types | **Run `percli lint` on every built artifact before deploying** |
| "I tested locally, CI/CD will be fine" | Local environment has different `percli` version, different CUE cache, different auth context — CI runner starts fresh | **Verify CI pipeline succeeds end-to-end in a real push before declaring done** |
| "One file with all dashboards is simpler" | Simpler to write, nightmare to maintain — every change triggers full rebuild, diffs are unreadable, code review is impossible | **Split into one dashboard per file, always** |
| "I'll add linting to the pipeline later" | Later never comes. Invalid dashboards get deployed, break monitoring, cause incidents | **Add `percli lint` to the pipeline now, in the same PR that sets up CI** |
| "The Go SDK print statement is just for debugging" | `dac build` does not distinguish "debug" stdout from "dashboard" stdout — the print will ship to production in the JSON output | **Remove the print. Use stderr. Verify with `percli dac build` before committing** |

---

## FORBIDDEN Patterns

These patterns MUST NOT appear in any DaC pipeline output. Violation is a blocker.

- **NEVER** run `percli apply` on raw `.cue` or `.go` source files — always build first
- **NEVER** print to stdout in Go SDK dashboard programs — this corrupts `dac build` output
- **NEVER** hardcode credentials in workflow YAML — use GitHub secrets
- **NEVER** skip the lint step between build and deploy — build success is not validation
- **NEVER** put multiple dashboard definitions in a single file — one dashboard per file, always
- **NEVER** commit the `built/` directory to version control — it is a derived artifact

---

## Blocker Criteria

Do NOT mark a phase as complete if any of these conditions exist:

| Phase | Blocker |
|-------|---------|
| INITIALIZE | `cue mod tidy` or `go mod tidy` exits with non-zero status |
| INITIALIZE | `percli` version does not meet minimum requirement (CUE: v0.51.0+, Go: v0.44.0+) |
| DEFINE | CUE files have syntax errors (`cue vet` fails) |
| DEFINE | Multiple dashboards defined in a single file |
| BUILD | `percli dac build` produces no output in `built/` directory |
| BUILD | Built JSON contains non-JSON content (Go SDK stdout contamination) |
| VALIDATE | `percli lint` reports errors on any built artifact |
| DEPLOY | `percli apply` returns non-zero exit status |
| DEPLOY | Dashboard not visible via `percli get dashboard --project <project>` |
| CI/CD | Workflow YAML contains hardcoded credentials |
| CI/CD | Pipeline has not been tested with an actual push |

---

## References

| Resource | URL |
|----------|-----|
| Perses DaC documentation | https://perses.dev/docs/dac/ |
| CUE SDK setup guide | https://perses.dev/docs/dac/cue/setup/ |
| Go SDK setup guide | https://perses.dev/docs/dac/go/setup/ |
| CUE DaC utils package | `github.com/perses/perses/cue/dac-utils` |
| Go SDK package | `github.com/perses/perses/go-sdk` |
| CI/CD GitHub Actions | `perses/cli-actions/.github/workflows/dac.yaml@v0.1.0` |
| percli CLI reference | https://perses.dev/docs/cli/ |
| Perses GitHub repository | https://github.com/perses/perses |
| CUE language docs | https://cuelang.org/docs/ |
