# Harbor Adapter for the /do Router

A `BaseInstalledAgent` subclass that runs the claude-code-toolkit /do router
inside a Harbor container against terminal-bench-2.

## Prerequisites

- Docker (Harbor's local runtime launches tasks in containers)
- `uv` (Harbor is installed via `uv tool install harbor`)
- `ANTHROPIC_API_KEY` exported in the host shell

## Run the 5-task dry run

```bash
export ANTHROPIC_API_KEY=sk-...
./run_dry_run.sh
```

Results land in `results/<timestamp>/`:

- `report.md` — per-task pass/fail, tokens, estimated cost, aggregates
- `raw/` — full Harbor trial directories (gitignored; may contain transcripts)
- `harbor-run.log` — stdout/stderr of the `harbor run` invocation

## Switch to a cloud runtime

Edit `job.yaml`:

```yaml
environment:
  runtime: daytona
```

Set the matching API key on the host (`DAYTONA_API_KEY`, `MODAL_TOKEN_ID` +
`MODAL_TOKEN_SECRET`, `E2B_API_KEY`, or `RUNLOOP_API_KEY`).

## Files

- `harbor_adapter/claude_code_do_agent.py` — the adapter
- `Dockerfile` — base image; Node / Claude Code / toolkit land on top at install
- `job.yaml` — Harbor job config
- `run_dry_run.sh` — entry point
- `scripts/build_report.py` — assembles `report.md` from trial outputs
