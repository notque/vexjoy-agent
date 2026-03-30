# Dashboard-as-Code Pipeline

Set up and manage Dashboard-as-Code workflows with CUE or Go SDK.

## Phase 1: INITIALIZE

**Goal**: Set up the DaC module.

**CUE SDK** (default):
```bash
mkdir -p dac && cd dac
cue mod init my-dashboards
percli dac setup
cue mod tidy
```

Requirements: `percli` >= v0.51.0, `cue` >= v0.12.0. CUE is the default unless the user explicitly requests Go.

**Go SDK**:
```bash
mkdir -p dac && cd dac
go mod init my-dashboards
percli dac setup --language go
go mod tidy
```

Requirements: `percli` >= v0.44.0, Go installed. Use when team prefers Go or needs programmatic features beyond CUE.

**Gate**: Module initialized, `cue mod tidy` or `go mod tidy` succeeds. Proceed to Phase 2.

## Phase 2: DEFINE

**Goal**: Write dashboard definitions. One dashboard per file.

```
dac/
  cue.mod/
  dashboards/
    cpu-monitoring.cue
    network-overview.cue
  shared/
    datasources.cue
    variables.cue
```

- **One dashboard per file**: Enables per-dashboard CI and clean diffs
- **Shared definitions**: Use `dac/shared/` for common datasources, templates, variables

CUE imports from `github.com/perses/perses/cue/dac-utils/*`.
Go imports from `github.com/perses/perses/go-sdk`.

**Gate**: Definitions written, `cue vet` passes. Proceed to Phase 3.

## Phase 3: BUILD

```bash
# Single file
percli dac build -f dashboards/cpu-monitoring.cue -ojson

# Directory
percli dac build -d dashboards/ -ojson

# Go SDK
percli dac build -f main.go -ojson
```

Output in `built/`. Always build before apply. Never commit `built/`.

**Gate**: Build succeeds, JSON/YAML output in `built/`. Proceed to Phase 4.

## Phase 4: VALIDATE

```bash
percli lint -f built/cpu-monitoring.json
percli lint -f built/cpu-monitoring.json --online
```

Build success does not equal valid dashboard. Always lint.

**Gate**: Validation passes. Proceed to Phase 5.

## Phase 5: DEPLOY

```bash
percli apply -f built/cpu-monitoring.json --project <project>
percli get dashboard --project <project>
```

**Gate**: Dashboards deployed and accessible. Proceed to Phase 6 if CI/CD requested.

## Phase 6: CI/CD INTEGRATION (optional)

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

Never hardcode credentials. Use GitHub repo Settings > Variables and Secrets.

**Gate**: CI/CD configured and tested. Pipeline complete.

## Error Handling

| Symptom | Cause | Solution |
|---------|-------|----------|
| `cue mod tidy` fails | CUE module not initialized | Run `cue mod init` first |
| Version errors | CUE < 0.12.0 | Upgrade CUE |
| Empty `built/` | CUE doesn't evaluate to dashboard | Check file path and CUE expression |
| Non-JSON output (Go) | Stdout prints in Go code | **CRITICAL**: Remove all stdout prints, use stderr |
| CI/CD 401/403 | Missing secrets | Add to GitHub Settings > Secrets |
| CI/CD connection refused | Wrong URL or unreachable server | Verify URL is public, not localhost |
| `percli lint` fails | Dashboard violates Perses schema | Fix definition and rebuild |

## References

- [Perses DaC documentation](https://perses.dev/docs/dac/)
- [CUE SDK setup](https://perses.dev/docs/dac/cue/setup/)
- [Go SDK setup](https://perses.dev/docs/dac/go/setup/)
- [CUE DaC utils](https://github.com/perses/perses/tree/main/cue/dac-utils)
- [Go SDK](https://github.com/perses/perses/tree/main/go-sdk)
- [CI/CD GitHub Actions](https://github.com/perses/cli-actions)
- [percli CLI](https://perses.dev/docs/cli/)
- [Perses GitHub](https://github.com/perses/perses)
- [CUE language docs](https://cuelang.org/docs/)
