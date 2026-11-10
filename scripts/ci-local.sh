#!/usr/bin/env bash
# ci-local.sh - run the CI lint job (.github/workflows/test.yml, job "lint")
# locally, in workflow order.
#
# Usage:
#   bash scripts/ci-local.sh            # lint job only
#   bash scripts/ci-local.sh --tests    # lint job, then the fast pytest tier
#
# Exit: 0 when every step passes, 1 on the first failure.
# tests/test_ci_local_script.py fails when this list and the workflow differ.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
PY="${PYTHON:-$(command -v python || command -v python3)}"

RUN_TESTS=0
if [[ $# -gt 0 ]]; then
    case "$1" in
        --tests) RUN_TESTS=1 ;;
        *)
            echo "Usage:"
            echo "  bash scripts/ci-local.sh            # lint job only"
            echo "  bash scripts/ci-local.sh --tests    # lint job, then the fast pytest tier"
            exit 2
            ;;
    esac
fi

COUNT=0
step() {
    COUNT=$((COUNT + 1))
    echo "==> $1"
    if ! eval "$1"; then
        echo "ci-local: FAILED at step $COUNT: $1" >&2
        exit 1
    fi
}

# --- ruff version check ---
CI_RUFF_VERSION="$(grep -o 'ruff==[0-9.]*' .github/workflows/test.yml | head -1 | cut -d= -f3)"
LOCAL_RUFF_VERSION="$(ruff --version 2>/dev/null | awk '{print $2}' || true)"
if [[ -n "$CI_RUFF_VERSION" && -n "$LOCAL_RUFF_VERSION" && "$CI_RUFF_VERSION" != "$LOCAL_RUFF_VERSION" ]]; then
    echo "warning: local ruff $LOCAL_RUFF_VERSION differs from CI pin $CI_RUFF_VERSION" >&2
fi

# --- routing-map uncommitted check ---
if [[ -n "$(git status --porcelain -- docs/routing-map.md)" ]]; then
    echo "warning: docs/routing-map.md has uncommitted changes; the regenerate step will report them" >&2
fi

# --- lint steps, in workflow order ---
step '"$PY" scripts/generate-skill-index.py && "$PY" scripts/generate-agent-index.py'
step '"$PY" scripts/add-companion-skills.py --check'
step 'ruff check . --config pyproject.toml'
step 'ruff format --check . --config pyproject.toml'
step '"$PY" scripts/validate-references.py --check-do-framing'
step '"$PY" scripts/validate-references.py --check-placeholders'
step '"$PY" scripts/validate-references.py --check-size'
step '"$PY" scripts/validate-references.py --check-skill-calls'
step '"$PY" scripts/validate_positive_instruction_docs.py --fleet'
step '"$PY" scripts/validate-doc-commands.py --check-sdir'
step '"$PY" scripts/validate-skill-frontmatter.py'
step '"$PY" scripts/validate-index-integrity.py'
step '"$PY" scripts/validate-promoted-successors.py'
step '"$PY" scripts/validate-pipeline-index.py'
step '"$PY" scripts/generate-routing-map.py --check'
step '"$PY" scripts/generate-skills-doc.py --check'
step '"$PY" scripts/validate-skill-names.py'

# No tracked INDEX.local.json
COUNT=$((COUNT + 1))
echo "==> no tracked INDEX.local.json"
if git ls-files | grep -E '(^|/)INDEX\.local\.json$'; then
    echo "tracked INDEX.local.json found (private-inclusive index must stay local)"
    echo "ci-local: FAILED at step $COUNT: no tracked INDEX.local.json" >&2
    exit 1
fi

step '"$PY" scripts/generate-routing-map.py && git diff --exit-code -- docs/routing-map.md'
step '"$PY" scripts/validate-negative-controls.py'
step '"$PY" scripts/validate-merged-index.py'
step '"$PY" scripts/validate-do-references.py'
step '"$PY" scripts/validate-doc-links.py'
step '"$PY" scripts/validate-doc-counts.py'
step '"$PY" scripts/validate-doc-commands.py'
step '"$PY" scripts/validate-doc-commands.py --scope toolkit'
step '"$PY" scripts/validate_component_models.py'
step '"$PY" scripts/validate-workflow-conformance.py'

# --- optional: fast pytest tier ---
if [[ "$RUN_TESTS" -eq 1 ]]; then
    COUNT=$((COUNT + 1))
    echo "==> pytest (fast tier)"
    if ! nice -n 10 "$PY" -m pytest --tb=short -q; then
        echo "ci-local: FAILED at step $COUNT: pytest" >&2
        exit 1
    fi
fi

echo "ci-local: all $COUNT steps passed"
