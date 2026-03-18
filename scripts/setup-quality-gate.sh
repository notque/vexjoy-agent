#!/bin/bash
#
# Setup script for Universal Quality Gate
#
# Installs linting tools for supported languages.
# Run this once after cloning the repository.
#
# Usage: ./scripts/setup-quality-gate.sh [--all|--python|--node|--go]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Python tools
setup_python() {
    info "Setting up Python quality tools..."

    if command_exists pip3; then
        pip3 install --user ruff >/dev/null 2>&1 && \
            info "  Installed ruff (Python linter)" || \
            warn "  Failed to install ruff"
    elif command_exists pip; then
        pip install --user ruff >/dev/null 2>&1 && \
            info "  Installed ruff (Python linter)" || \
            warn "  Failed to install ruff"
    else
        warn "  pip not found, skipping Python tools"
        return 1
    fi

    # Verify installation
    if command_exists ruff; then
        info "  ruff $(ruff --version 2>/dev/null | head -1)"
    else
        # Check in user's local bin
        if [ -f "$HOME/.local/bin/ruff" ]; then
            info "  ruff installed to ~/.local/bin/ruff"
            info "  Add ~/.local/bin to your PATH if not already"
        fi
    fi
}

# Install Node.js tools
setup_node() {
    info "Setting up Node.js quality tools..."

    if ! command_exists npm; then
        warn "  npm not found, skipping Node.js tools"
        return 1
    fi

    # Install globally (or use npx which comes with npm)
    if command_exists npx; then
        info "  npx available - tools will be fetched on demand"

        # Pre-cache common tools
        info "  Pre-caching eslint..."
        npx --yes eslint --version >/dev/null 2>&1 && \
            info "    eslint ready" || \
            warn "    eslint cache failed (will work via npx)"
    fi
}

# Install Go tools
setup_go() {
    info "Setting up Go quality tools..."

    if ! command_exists go; then
        warn "  go not found, skipping Go tools"
        return 1
    fi

    # golangci-lint
    if ! command_exists golangci-lint; then
        info "  Installing golangci-lint..."
        go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest 2>/dev/null && \
            info "    golangci-lint installed" || \
            warn "    golangci-lint install failed"
    else
        info "  golangci-lint already installed"
    fi
}

# Setup Claude Code hooks integration
setup_hooks() {
    info "Setting up Claude Code hooks..."

    CLAUDE_SETTINGS="$HOME/.claude/settings.json"

    if [ ! -f "$CLAUDE_SETTINGS" ]; then
        warn "  ~/.claude/settings.json not found"
        warn "  Hooks will need manual configuration"
        return 1
    fi

    info "  Quality gate available via: /quality-gate skill"
    info "  See skills/universal-quality-gate/SKILL.md for usage"
}

# Show summary
show_summary() {
    echo ""
    info "=== Setup Summary ==="
    echo ""

    # Check each tool
    echo "Python tools:"
    command_exists ruff && echo "  [✓] ruff" || echo "  [✗] ruff"

    echo ""
    echo "Node.js tools:"
    command_exists npx && echo "  [✓] npx (eslint, biome via npx)" || echo "  [✗] npx"

    echo ""
    echo "Go tools:"
    command_exists gofmt && echo "  [✓] gofmt" || echo "  [✗] gofmt"
    command_exists golangci-lint && echo "  [✓] golangci-lint" || echo "  [✗] golangci-lint"

    echo ""
    info "Run quality gate with:"
    echo "  python3 \"$REPO_ROOT/skills/universal-quality-gate/scripts/run_quality_gate.py\""
    echo ""
}

# Main
main() {
    echo "========================================"
    echo " Universal Quality Gate Setup"
    echo "========================================"
    echo ""

    case "${1:-all}" in
        --python)
            setup_python
            ;;
        --node)
            setup_node
            ;;
        --go)
            setup_go
            ;;
        --hooks)
            setup_hooks
            ;;
        --all|*)
            setup_python
            setup_node
            setup_go
            setup_hooks
            ;;
    esac

    show_summary
}

main "$@"
