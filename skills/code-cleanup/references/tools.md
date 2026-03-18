# Code Cleanup Tools Reference

## Python Tools

| Tool | Purpose | Install |
|------|---------|---------|
| `ruff` | Fast linter and formatter (replaces flake8, isort, black) | `pip install ruff` |
| `vulture` | Dead code detection | `pip install vulture` |
| `radon` | Cyclomatic complexity and maintainability metrics | `pip install radon` |
| `mypy` | Static type checker | `pip install mypy` |
| `pylint` | Comprehensive linting, duplicate detection | `pip install pylint` |

### Ruff Rule Categories

| Select | Detects |
|--------|---------|
| `F401` | Unused imports |
| `F811` | Redefined unused variables |
| `I001` | Import sorting violations |
| `ANN` | Missing type annotations |
| `D` | Missing docstrings |

## Go Tools

| Tool | Purpose | Install |
|------|---------|---------|
| `goimports` | Import management and formatting | `go install golang.org/x/tools/cmd/goimports@latest` |
| `gocyclo` | Cyclomatic complexity analyzer | `go install github.com/fzipp/gocyclo/cmd/gocyclo@latest` |
| `golangci-lint` | Comprehensive linter aggregator | `brew install golangci-lint` or `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest` |
| `staticcheck` | Advanced static analysis, deprecation detection | `go install honnef.co/go/tools/cmd/staticcheck@latest` |

## Universal Tools (Always Available)

| Tool | Purpose |
|------|---------|
| `grep` | Pattern searching (TODOs, naming violations, magic numbers) |
| `git blame` | Code history and age detection for TODO triage |
| `wc -l` | Line counting for function length |

## Tool Availability Check Script

```bash
echo "=== Python Tools ==="
command -v ruff && ruff --version || echo "ruff: NOT INSTALLED (pip install ruff)"
command -v vulture && vulture --version || echo "vulture: NOT INSTALLED (pip install vulture)"
command -v radon && radon --version || echo "radon: NOT INSTALLED (pip install radon)"
command -v mypy && mypy --version || echo "mypy: NOT INSTALLED (pip install mypy)"

echo "=== Go Tools ==="
command -v goimports && echo "goimports: available" || echo "goimports: NOT INSTALLED"
command -v gocyclo && echo "gocyclo: available" || echo "gocyclo: NOT INSTALLED"
command -v golangci-lint && golangci-lint --version || echo "golangci-lint: NOT INSTALLED"
command -v staticcheck && staticcheck --version || echo "staticcheck: NOT INSTALLED"
```
