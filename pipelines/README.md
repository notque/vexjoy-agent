# Pipelines

Pipelines are multi-phase structured workflows with explicit gates between phases. They live in `pipelines/` and are synced to `~/.claude/skills/` at install time, so Claude Code discovers them as regular skills.

Each pipeline has numbered phases (e.g., PHASE 1: GATHER → PHASE 2: COMPILE) and produces artifacts at each phase rather than relying on context memory.

---

## Core Orchestration

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `workflow-orchestrator` | 3 | BRAINSTORM → WRITE-PLAN → EXECUTE-PLAN for complex multi-step tasks |
| `auto-pipeline` | 2 | Automatic pipeline generation for unrouted tasks; crystallizes patterns into permanent pipelines |
| `explore-pipeline` | 1–8 | Systematic codebase exploration: Quick (1), Standard (4), or Deep (8) phases |
| `do-perspectives` | 1 | 10 analytical lenses applied sequentially for multi-angle pattern extraction |

---

## Feature & Code Development

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `pr-pipeline` | 7 | End-to-end PR creation: Classify → Stage → Review → Commit → Push → Fix Loop → Create → Verify |
| `comprehensive-review` | 3 | 3-wave code review: per-package deep analysis + 11 foundation reviewers + 10 deep-dive reviewers |
| `skill-creation-pipeline` | 5 | DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE for new skills with quality gates |
| `agent-upgrade` | 5 | AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE for improving existing agents/skills |
| `system-upgrade` | 6 | CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY for ecosystem-wide upgrades |

---

## Pipeline Meta-Pipelines

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `hook-development-pipeline` | 5 | SPEC → IMPLEMENT → TEST → REGISTER → DOCUMENT for production-quality hooks |
| `pipeline-scaffolder` | N | Scaffold pipeline components from a Pipeline Spec JSON produced by `chain-composer` |
| `pipeline-test-runner` | 3 | Discover targets → run subdomain skills in parallel → validate artifacts and report |
| `pipeline-retro` | 3 | Trace test failures to generator root causes; Three-Layer Pattern fix and re-test |
| `chain-composer` | 4 | Compose valid pipeline chains from the step menu for each subdomain in a Component Manifest |
| `domain-research` | 4 | Discover and classify subdomains for pipeline generation (4 parallel research agents) |

---

## Content & Voice

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `voice-writer` | 8 | LOAD → GROUND → GENERATE → VALIDATE → REFINE → JOY-CHECK → OUTPUT → CLEANUP |
| `voice-calibrator` | 4 | Analyze writing samples and extract voice patterns with deterministic metrics |
| `research-to-article` | 7 | Parallel research agents gather data, then voice pipeline generates a validated article |
| `article-evaluation-pipeline` | 4 | Fetch → Validate → Analyze → Report for wabi-sabi-aware voice quality evaluation |
| `de-ai-pipeline` | 3 | Scan-fix-verify loop to remove AI writing patterns from docs (max 3 iterations) |
| `doc-pipeline` | 5 | Research → Outline → Generate → Verify → Output for technical documentation |

---

## Research

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `research-pipeline` | 5 | SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER with parallel agents and artifact saving |

---

## MCP

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `mcp-pipeline-builder` | 6 | ANALYZE → DESIGN → GENERATE → VALIDATE → EVALUATE → REGISTER to convert a repo into an MCP server |

---

## Perses (Observability)

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `perses-dac-pipeline` | 4 | Dashboard-as-Code: initialize CUE/Go module → write definitions → build → validate → CI/CD |
| `perses-plugin-pipeline` | 6 | SCAFFOLD → SCHEMA → IMPLEMENT → TEST → BUILD → DEPLOY for full plugin development |

---

## Toolkit Governance

| Pipeline | Phases | Description |
|----------|--------|-------------|
| `github-profile-rules` | 4 | Extract programming rules from a GitHub user's public profile via API analysis |
