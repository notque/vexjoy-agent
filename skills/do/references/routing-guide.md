# Routing System

The `/do` command routes requests to appropriate agents and skills.

## How Routing Works

1. **Parse request** - Identify domain, action, complexity
2. **Select agent** - Match domain triggers (e.g., "Go" → `golang-general-engineer`)
3. **Select skill** - Match task verb (e.g., "debug" → `systematic-debugging`)
4. **Execute** - Agent runs with skill methodology

## Agent Selection Triggers

| Triggers | Agent |
|----------|-------|
| go, golang, .go files | `golang-general-engineer` |
| python, .py, pip, pytest | `python-general-engineer` |
| kubernetes, helm, k8s | `kubernetes-helm-engineer` |
| react, next.js | `typescript-frontend-engineer` |

## Force-Routed Skills

These skills **MUST** be invoked when their triggers appear:

| Triggers | Skill |
|----------|-------|
| Go test, _test.go, table-driven, goroutine, channel, error handling, fmt.Errorf, sapcc, make check | `go-patterns` |

> For full routing tables with all agents and skills, see `skills/do/references/routing-tables.md`.
