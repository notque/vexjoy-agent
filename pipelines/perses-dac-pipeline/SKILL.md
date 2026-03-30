---
name: perses-dac-pipeline
user-invocable: false
description: "Dashboard-as-Code pipeline for Perses with CUE and percli."
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
    - dashboard as code
    - perses dac
    - perses cue
    - perses gitops
    - perses ci/cd
  pairs_with:
    - perses-dashboard-create
    - perses-plugin-pipeline
  complexity: Complex
  category: devops
---

# Perses Dashboard-as-Code Pipeline

Set up and manage Dashboard-as-Code workflows with CUE or Go SDK.

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

- Requirements: `percli` >= v0.51.0, `cue` >= v0.12.0
- Why CUE first: CUE SDK is the default unless the user explicitly requests Go, as it requires less runtime overhead and is idiomatic for configuration-as-code patterns.

**Go SDK**:
```bash
mkdir -p dac && cd dac
go mod init my-dashboards
percli dac setup --language go
go mod tidy
```

- Requirements: `percli` >= v0.44.0, Go installed
- When to use: Use Go SDK only when the team is significantly more comfortable with Go or when dashboard logic requires programmatic features beyond CUE's data-transformation capabilities.

**Gate**: Module initialized, dependencies resolved. `cue mod tidy` or `go mod tidy` succeeds without errors. Verify `percli version` meets minimum requirement. Proceed to Phase 2.

---

### Phase 2: DEFINE

**Goal**: Write dashboard definitions using SDK builders. Keep one dashboard per file to enable per-dashboard CI validation and clean diffs — this is the Perses convention and prevents merge conflicts when multiple dashboards coexist.

CUE directory structure:
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

- **One dashboard per file**: Always split multiple dashboards into separate files in `dac/dashboards/`. A single file with all dashboards is simpler to write but impossible to maintain — every change triggers a full rebuild, diffs are unreadable, and code review becomes impossible.
- **Shared definitions**: Use `dac/shared/` for common datasources, panel templates, and variable definitions. Import them into your dashboard definitions via CUE's standard import syntax.

CUE DaC imports from `github.com/perses/perses/cue/dac-utils/*`.
Go DaC imports from `github.com/perses/perses/go-sdk`.

**Gate**: Dashboard definitions written. Files parse without syntax errors. Run `cue vet` (CUE) to validate structure. Proceed to Phase 3.

---

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

- **Always build before apply**: Raw `.cue` or `.go` files cannot be applied directly to Perses — `percli apply` requires the built JSON/YAML output. Running `percli apply` on source files will fail.
- **Never commit `built/`**: The `built/` directory is a derived artifact — add it to `.gitignore`. CI/CD will rebuild from source on every push, ensuring consistency.

**Gate**: Build succeeds, JSON/YAML output in `built/` directory. Proceed to Phase 4.

---

### Phase 4: VALIDATE

**Goal**: Ensure built dashboards are valid according to Perses schema.

```bash
percli lint -f built/cpu-monitoring.json
# Or with server validation
percli lint -f built/cpu-monitoring.json --online
```

- **Build success ≠ valid dashboard**: `percli dac build` only validates CUE/Go syntax, not Perses dashboard semantics. Panels can reference nonexistent datasources, variables can have wrong types, and fields can violate the schema — the build will still succeed.
- **Always lint**: Never skip this step. Invalid dashboards deployed to Perses break monitoring and cause incidents.

**Gate**: Validation passes with no errors reported. Proceed to Phase 5.

---

### Phase 5: DEPLOY

**Goal**: Apply dashboards to Perses.

```bash
percli apply -f built/cpu-monitoring.json --project <project>
```

Verify deployment:
```bash
percli get dashboard --project <project>
```

**Gate**: Dashboards deployed and accessible via `percli get`. Proceed to Phase 6 if CI/CD is requested.

---

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

- **Use secrets and variables**: Never hardcode `PERSES_URL`, `PERSES_USERNAME`, or `PERSES_PASSWORD` into workflow YAML. Use GitHub repo Settings > Variables for `vars.PERSES_URL` and Settings > Secrets for credentials. URL changes and secret leaks are prevented this way.
- **Verify CI/CD locally first**: Test the pipeline by pushing to a development branch and verifying the workflow succeeds before declaring the pipeline complete.

**Gate**: CI/CD pipeline configured, tested with a real push, and succeeds end-to-end. Pipeline complete.

---

## Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| `cue mod tidy` fails with "no CUE module found" | CUE module not initialized — `cue mod init` was skipped or ran in wrong directory | Run `cue mod init <module-name>` in the `dac/` directory before running `percli dac setup` |
| `cue mod tidy` fails with version/dependency errors | CUE version too old (< 0.12.0) or incompatible with `percli dac setup` output | Verify `cue version` shows >= 0.12.0. Upgrade CUE if needed. Run `percli dac setup` again after upgrade |
| `percli dac build` produces empty `built/` directory | CUE expression does not evaluate to a valid dashboard object, or the entry file path is wrong | Verify the file path passed to `-f` is correct. Ensure the CUE file evaluates to a Perses dashboard (imports `dac-utils` and uses dashboard builder). Check for CUE evaluation errors in stderr |
| `percli dac build` output contains non-JSON lines (Go SDK) | Go program prints to stdout via `fmt.Println`, `log.Println`, or similar — `dac build` captures all stdout as the dashboard definition | **CRITICAL**: Remove ALL stdout prints from Go DaC code. Use `fmt.Fprintln(os.Stderr, ...)` for debug output. Check imported libraries for stray stdout writes. Rebuild and verify output is valid JSON. This is a blocker. |
| CI/CD pipeline fails with 401/403 | `PERSES_USERNAME` / `PERSES_PASSWORD` secrets not configured in GitHub repository, or credentials are wrong | Add secrets in GitHub repo Settings > Secrets. Verify credentials work locally with `percli login` first |
| CI/CD pipeline fails with connection refused | `PERSES_URL` variable points to wrong server or server is not reachable from GitHub Actions runner | Verify the URL is publicly accessible (not localhost). Check `vars.PERSES_URL` is set in GitHub repo Settings > Variables |
| `percli lint` fails on valid-looking JSON | Dashboard JSON is structurally valid but violates Perses schema (e.g., unknown panel type, missing required field) | This is the system working correctly — fix the dashboard definition and rebuild. Run `percli lint --online` against a live server for detailed validation errors |

---

## References

- [Perses DaC documentation](https://perses.dev/docs/dac/) - Dashboard-as-Code overview and getting started guide
- [CUE SDK setup guide](https://perses.dev/docs/dac/cue/setup/) - CUE-based DaC module initialization
- [Go SDK setup guide](https://perses.dev/docs/dac/go/setup/) - Go-based DaC module initialization
- [CUE DaC utils package](https://github.com/perses/perses/tree/main/cue/dac-utils) - CUE helper utilities for dashboard definitions
- [Go SDK package](https://github.com/perses/perses/tree/main/go-sdk) - Go SDK for programmatic dashboard building
- [CI/CD GitHub Actions](https://github.com/perses/cli-actions) - Reusable GitHub Actions for DaC pipelines
- [percli CLI reference](https://perses.dev/docs/cli/) - Command-line tool for Perses operations
- [Perses GitHub repository](https://github.com/perses/perses) - Main Perses project repository
- [CUE language docs](https://cuelang.org/docs/) - CUE language specification and reference
