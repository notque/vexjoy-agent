# Routing System

The `/do` command routes requests to appropriate agents and skills.

## How Routing Works

1. **Classify** - Determine request complexity (Trivial, Simple, Medium, Complex)
2. **Route** - Run `scripts/index-router.py` for trigger matching, apply force-routes or select from scored candidates, override skill based on task verb
3. **Enhance** - Stack additional skills based on request signals (e.g., "with tests" adds test-driven-development)
4. **Execute** - Create plan (Simple+), invoke agent with skill methodology
5. **Learn** - Record routing outcome and session insights to `learning.db`

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
| Typo, one-line fix, trivial mechanical change | `fast` |
| Small self-contained change, add CLI flag, extract helper | `quick` |
| Go test, _test.go, table-driven, goroutine, channel, error handling, fmt.Errorf, sapcc, make check | `go-patterns` |
| Push branch, create PR, open pull request, PR status, fix PR comments | `pr-workflow` |
| Stage files, commit, save work, checkpoint | `git-commit-flow` |
| CI passed, GitHub Actions status, build results | `github-actions-check` |
| New feature design, plan, implement, validate, release | `feature-lifecycle` |
| Scan and fix AI patterns across docs/content | `de-ai-pipeline` |
| Improve toolkit, evaluate repo, audit system, self-improvement | `toolkit-improvement` |
| Perses dashboards, plugins, deployment, migration | `perses` |

> For full routing tables with all agents and skills, see `skills/do/references/routing-tables.md`.
