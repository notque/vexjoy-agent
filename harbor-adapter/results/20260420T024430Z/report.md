# /do Router Dry Run: Blocker Report

Run date: 2026-04-19 (UTC timestamp 20260420T024430Z)
Status: NOT EXECUTED - host prerequisites missing
Branch: feat/harbor-do-router-benchmark

This directory marks the run attempt and hosts the blocker report. No trials
ran; no tokens were consumed; no pass/fail numbers are claimed. When the
prerequisites below are satisfied, run_dry_run.sh will overwrite
results/<new-timestamp>/ with real output.

## Blockers Encountered

Three host-side prerequisites are missing. All three are resolvable by the
user; none can be worked around silently without falsifying the measurement,
which is the point of the exercise.

### 1. No container runtime on the host

Harbor's local runtime requires Docker. The PyPI description is explicit:
"This will launch the benchmark locally using Docker."

Verified absent on this host: docker and podman are both not on PATH; neither
/var/run/docker.sock nor /run/docker.sock exists; systemctl status docker
reports the unit is unknown.

Options to resolve:
- Install Docker Engine (sudo apt install docker.io, add feedgen to the
  docker group, re-log). Passwordless sudo is available on this host, so this
  is a one-command fix after authorization.
- Switch job.yaml's environment.runtime to daytona, modal, e2b, or runloop
  and supply the matching cloud API key.

### 2. ANTHROPIC_API_KEY not set

The current shell session is authenticated via Claude Code OAuth
(~/.claude.json contains oauthAccount). Harbor's Claude Code agent path
requires an API key env var; the env grep showed no ANTHROPIC_API_KEY in
scope.

### 3. uv not installed

Harbor installs via `uv tool install harbor`. uv is not on PATH.
run_dry_run.sh auto-installs it on first run via the official installer
script, so this is only a blocker in the sense that the first run will touch
~/.local/bin/ and require a PATH refresh.

## What Was Delivered

All adapter code is shipped and reviewable on the feature branch. The
scaffold is complete enough that once the three prerequisites above are met,
the dry run is a single ./run_dry_run.sh invocation.

- harbor-adapter/harbor_adapter/claude_code_do_agent.py - the
  BaseInstalledAgent subclass with install(), @with_prompt_template run(),
  and populate_context_post_run() populated. Token usage is parsed from
  claude -p --output-format json rather than scraped from stderr.
- harbor-adapter/Dockerfile - minimal Ubuntu 24.04 base with the agent user
  and /logs + /workspace volumes wired. Node / Claude Code / toolkit are
  layered by the adapter's install() method so image rebuilds are not needed
  for toolkit updates.
- harbor-adapter/job.yaml - terminal-bench-2.0 dataset, task_filter: limit:
  5, env_passthrough: [ANTHROPIC_API_KEY], n_concurrent: 1.
- harbor-adapter/run_dry_run.sh - single-command entry point with preflight
  checks for the three blockers above.
- harbor-adapter/scripts/build_report.py - assembles this report (or the
  real one) from Harbor's trial outputs.
- harbor-adapter/.gitignore - keeps report.md out of ignore rules but
  excludes raw transcripts under raw/ so task content does not leak.
- adr/benchmark-do-router-dry-run.md - decision rationale, alternatives,
  risks, and the prerequisite gap.

## Next Action

One of:

1. Authorize sudo apt install docker.io on this host, export
   ANTHROPIC_API_KEY, and re-run ./run_dry_run.sh. Expected outcome: 5
   trials, per-task token numbers, aggregate cost.
2. Provide Daytona (or Modal / E2B / Runloop) credentials and switch
   job.yaml's environment.runtime to the cloud runtime.
