#!/usr/bin/env bash
# One-command entry point for the 5-task dry run.
#
# Usage:
#   ANTHROPIC_API_KEY=sk-... ./run_dry_run.sh
#
# The script is idempotent: re-running it creates a new timestamped
# results directory and leaves previous runs alone.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="$here/results/$timestamp"
mkdir -p "$out_dir/raw"

# --- Preflight ------------------------------------------------------------
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set in the environment." >&2
  echo "       Export it before running: export ANTHROPIC_API_KEY=sk-..." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found on PATH." >&2
  echo "       Harbor's local runtime requires Docker. Install it or" >&2
  echo "       switch environment.runtime in job.yaml to daytona/modal/e2b." >&2
  exit 3
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; attempting to install via the official script." >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # The installer prints the path it added; fall back to the default.
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v harbor >/dev/null 2>&1; then
  echo "harbor not found; installing via uv." >&2
  uv tool install harbor
  export PATH="$HOME/.local/bin:$PATH"
fi

# --- Build the image ------------------------------------------------------
docker build -t do-router-benchmark:latest -f "$here/Dockerfile" "$here"

# --- Run ------------------------------------------------------------------
# Harbor writes trial artifacts under output_dir. The job.yaml points at
# results/_pending; move that into results/<timestamp>/raw after the run.
rm -rf "$here/results/_pending"

set +e
harbor run -c "$here/job.yaml" 2>&1 | tee "$out_dir/harbor-run.log"
harbor_exit=${PIPESTATUS[0]}
set -e

if [[ -d "$here/results/_pending" ]]; then
  mv "$here/results/_pending"/* "$out_dir/raw/" 2>/dev/null || true
  rmdir "$here/results/_pending" 2>/dev/null || true
fi

# --- Report ---------------------------------------------------------------
python3 "$here/scripts/build_report.py" \
  --run-dir "$out_dir" \
  --output "$out_dir/report.md"

echo
echo "Harbor exit code: $harbor_exit"
echo "Results: $out_dir"
echo "Report:  $out_dir/report.md"
exit "$harbor_exit"
