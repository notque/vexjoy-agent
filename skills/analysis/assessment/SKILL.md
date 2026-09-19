---
name: assessment
description: "Assessment: read-only inspection, codebase overview, value analysis, health checks, ADR consultation, decision analysis, multi-perspective critique."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
  - Agent
routing:
  not_for: "code review with findings (use review), building or fixing (use workflow)"
  triggers:
    - "inspect without changing"
    - "read-only"
    - "audit current state"
    - "onboard to codebase"
    - "codebase structure"
    - "give me an overview"
    - "summarize this repo"
    - "repo value analysis"
    - "what can we learn from"
    - "service status"
    - "check health"
    - "is service running"
    - "validate endpoints"
    - "consult on ADR"
    - "architecture consultation"
    - "adr consultation"
    - "help me decide"
    - "decision matrix"
    - "pros and cons"
    - "trade-offs"
    - "critique these ideas"
    - "devil's advocate"
    - "stress test proposals"
    - "roast this"
    - "poke holes in this"
  category: analysis
  pairs_with:
    - review
    - workflow
    - security
---

# Assessment Skill

Seven modes for read-only analysis and decision support. Match the request to
a mode, then follow that mode's phases.

## Mode Selection

| Request pattern | Mode |
|---|---|
| Inspect, browse, explore without changing | [Read-Only Inspection](#read-only-inspection) |
| Onboard, overview, summarize repo, codebase structure | [Codebase Overview](#codebase-overview) |
| Repo value analysis, compare repos, what can we learn | [Repo Value Analysis](#repo-value-analysis) |
| Service status, health check, uptime, validate endpoints | [Service Health Check](#service-health-check) |
| Consult on ADR, challenge design, architecture consultation | [ADR Consultation](#adr-consultation) |
| Help me decide, decision matrix, pros/cons, trade-offs | [Decision Scoring](#decision-scoring) |
| Critique ideas, devil's advocate, stress test, roast | [Multi-Persona Critique](#multi-persona-critique) |

---

## Read-Only Inspection

Safe exploration without modifying files or system state.

### Phase 1: SCOPE

Parse the request. Determine target scope (file, directory, service,
system-wide). Clarify before proceeding if scope could match dozens of results.

### Phase 2: GATHER

Use read-only tools only.

**Allowed**: `ls`, `find`, `wc`, `du`, `df`, `file`, `stat`, `ps`, `top -bn1`,
`uptime`, `free`, `pgrep`, `git status/log/diff/show/branch`,
`sqlite3 "SELECT ..."`, `curl -s` (GET only), `date`, `env`.

**Forbidden**: `mkdir`, `rm`, `mv`, `cp`, `touch`, `chmod`, `chown`,
`git add/commit/push`, file writes, `INSERT/UPDATE/DELETE/DROP`,
`npm/pip/apt install`, `kill`, `systemctl restart`.

### Phase 3: REPORT

Lead with the answer. Show supporting evidence. List files examined. All
claims must cite evidence.

---

## Codebase Overview

4-phase exploration producing an evidence-backed onboarding report. Read-only.

Read any `.claude/CLAUDE.md` or `CLAUDE.md` in the repo root first. Skip
sensitive files (`.env`, `*.pem`, `*.key`, credentials) silently.

### Phase 1: DETECT

Examine root directory. Identify project type from config files (`package.json`,
`go.mod`, `pyproject.toml`, `pom.xml`, `Cargo.toml`). Document: language,
framework, build system, dependencies. Load `references/codebase-overview/exploration-strategies.md`
for language-specific discovery commands.

**Gate**: Project type identified. Tech stack documented.

### Phase 2: EXPLORE

Discover entry points, core modules, data models, API surfaces, configuration,
tests. Limit 20 files per category. Map directory structure (exclude
`node_modules/`, `venv/`, `vendor/`, `dist/`, `build/`, `__pycache__/`).

**Gate**: Entry points, core modules, data layer, API surface, config, tests documented.

### Phase 3: MAP

Identify design patterns with file evidence. Map 5-10 key abstractions. Trace
a typical request through the full stack. Analyze last 10 commits. All paths
absolute. All claims cite source files.

**Gate**: Patterns identified, abstractions mapped, data flow documented.

### Phase 4: SUMMARIZE

Generate report using `references/codebase-overview/report-template.md`.
Include "Where to Add New Code" section. Run post-exploration secret scan.

For deep-dive mode ("full picture"), launch 4 parallel domain agents via Task.
See `references/codebase-overview/examples-and-errors.md` for dispatch template.

**Scripts**: `scripts/cartographer.py` (quick), `scripts/cartographer_omni.py`
(100-metric), `scripts/cartographer_ultimate.py` (focused performance).

---

## Repo Value Analysis

6-phase pipeline analyzing external repositories for adoptable ideas.

### Phase 1: CLONE

Parse input (GitHub URL, local path, `org/repo`). `git clone --depth 1`.
Categorize files into zones (skills, agents, hooks, docs, tests, config, code,
other). Cap zones at ~100 files.

### Phase 2: DEEP-READ (parallel)

Dispatch 1 Agent per zone (up to 8). Each reads EVERY file and produces:
component inventory, key techniques, notable patterns, gaps. Output to
`/tmp/[REPO]-zone-[zone].md`.

**Gate**: 75%+ agents returned.

### Phase 3: INVENTORY (parallel with Phase 2)

Dispatch 1 Agent to catalog vexjoy-agent repo: agents, skills, hooks, scripts
with counts. Output to `/tmp/self-inventory.md`.

### Phase 4: SYNTHESIZE

Read all zone findings and inventory. Build comparison table. Rate gaps:
HIGH/MEDIUM/LOW. Save draft to `research-[REPO]-comparison.md`.

### Phase 5: AUDIT (parallel)

For each HIGH/MEDIUM recommendation, dispatch 1 audit Agent to verify: ALREADY
EXISTS, PARTIAL, or MISSING. Skip with `--quick`.

### Phase 6: REPORT

Adjust recommendations from audit. Write final report: executive summary,
comparison table, already-covered, recommendations, verdict, next steps. Clean
`/tmp/` files. Load `references/repo-value-analysis/phase7-implement-template.md`
for implementation dispatch.

---

## Service Health Check

Deterministic service monitoring: Discover-Check-Report. Never report healthy
without verifying process status independently.

### Phase 1: DISCOVER

Locate service definitions: `services.json`, docker-compose, systemd units, or
user input. Build manifest: process pattern, health file, port, stale threshold
per service.

### Phase 2: CHECK

Per service: (1) `pgrep -f "<pattern>"` for process status, (2) parse health
file JSON for staleness/status/connections, (3) `ss -tlnp "sport = :<port>"`
for port.

| Condition | Status |
|---|---|
| Process not running | DOWN |
| Running + health file missing/stale | WARNING |
| Running + status=error | ERROR |
| Running + disconnected >30min | WARNING |
| Running + port not listening | ERROR |
| Running + healthy | HEALTHY |

**Gate**: All services evaluated with evidence.

### Phase 3: REPORT

Output summary (X/N healthy), highlight services needing action, provide
copy-pasteable remediation. Never auto-restart without explicit flag.

For endpoint validation, load `references/service-health-check/endpoint-validator.md`.
For CVE source auditing, load `references/service-health-check/cve-source-check.md`.

---

## ADR Consultation

3-agent parallel architecture consultation producing PROCEED or BLOCKED.

### Phase 1: DISCOVER

Locate ADR (user path, `.adr-session.json`, or ask). Validate via
`adr-query.py`. Read full ADR. Create `adr/{adr-name}/` directory.

**Gate**: ADR read, path validated, consultation directory created.

### Phase 2: DISPATCH (parallel)

Launch all 3 agents in ONE message. Load `references/adr-consultation/agent-prompts.md`
for prompt templates:
1. **Contrarian** (reviewer-perspectives): challenge assumptions, simpler alternatives
2. **User advocate** (reviewer-perspectives): user impact, cognitive load
3. **Meta-process** (reviewer-perspectives): system health, coupling, SPOF

For complex decisions, add 2 more agents (see agent-prompts.md).

**Gate**: All agents returned and wrote to `adr/{adr-name}/`.

### Phase 3: SYNTHESIZE

Read agent files from disk. Extract concerns to `adr/{adr-name}/concerns.md`.
Determine verdict: all PROCEED = strong consensus, any BLOCK = hard block,
mixed = significant concerns. Write `adr/{adr-name}/synthesis.md`. Issue
verdict per `references/adr-consultation/consultation-patterns.md`.

---

## Decision Scoring

Weighted scoring for 2-4 options. Runs inline (no fork).

### Step 1: Frame

State decision in one sentence. List 2-4 options. Eliminate non-starters first.

### Step 2: Criteria

Default weights (adjust per domain -- load `references/decision-helper/decision-archetypes.md`
for build-vs-buy, database, cloud, framework, API, or operational tooling):

| Criterion | Weight | Measures |
|---|---|---|
| Correctness | 5 | Solves the actual problem |
| Complexity | 3 | Added complexity (lower = better) |
| Maintainability | 3 | Ease of change/debug |
| Risk | 3 | Failure mode severity |
| Effort | 2 | Implementation time |
| Familiarity | 2 | Team comfort |
| Ecosystem | 1 | Library/community support |

Lock weights before scoring. Do not adjust after seeing results.

### Step 3: Score

Rate each option 1-10 per criterion with one-sentence justification. Calculate
`sum(score * weight) / sum(weights)`.

### Step 4: Analyze

All scores <6.0: no good option -- explore alternatives. Top two within 0.5:
close call -- identify deciding criteria. Top leads by >0.5: recommend winner.
If matrix contradicts intuition, ask which criterion is missing.

### Step 5: Persist

Append to active ADR session (`.adr-session.json`) or task plan.

---

## Multi-Persona Critique

5-persona parallel critique with consensus synthesis.

### Phase 1: UNDERSTAND

Extract or generate numbered proposals. Each: what it does, why it matters,
how it differs from status quo (2-4 sentences). Research domain first if
generating.

### Phase 2: BRIEF

Load `references/multi-persona-critique/personas.md`. Build prompts for 5
personas, each receiving ALL proposals:
1. **The Logician**: coherence, assumptions, falsifiability
2. **The Pragmatic Builder**: build cost, maintenance, simpler alternatives
3. **The Systems Purist**: accidental complexity, separation of concerns
4. **The End User Advocate**: friction, delight, solved-problem test
5. **The Skeptical Philosopher**: human agency, dependency risk

Each produces: STRONG/PROMISING/WEAK/REJECT per proposal, ranked list,
cross-cutting observations.

### Phase 3: DISPATCH (parallel)

Launch all 5 via Agent. Wait for ALL to complete.

### Phase 4: SYNTHESIZE

Build consensus matrix (proposals x personas x ratings). Classify: CONSENSUS
(4+ agree), CONTESTED (2-3 split), OUTLIER (1 vs 4). Score: STRONG=3,
PROMISING=2, WEAK=1, REJECT=0. Sum per proposal (0-15).

### Phase 5: PRESENT

Generate report using `references/multi-persona-critique/synthesis-template.md`:
consensus matrix, features to build, worth investigating, disagreements,
shelve, cross-cutting insights.

For roast-style code critique with HN personas and file:line validation, load
`references/multi-persona-critique/roast.md`.

---

## Deep References

Load on demand when the corresponding phase needs detailed lookup data.

| Context | Reference | Content |
|---|---|---|
| Codebase overview: language commands | `references/codebase-overview/exploration-strategies.md` | Per-language discovery commands |
| Codebase overview: report format | `references/codebase-overview/report-template.md` | 12-section report template |
| Codebase overview: deep-dive dispatch | `references/codebase-overview/examples-and-errors.md` | Parallel agent template, worked examples |
| Codebase overview: statistical lenses | `references/codebase-overview/statistical-three-lenses.md` | Three-lens statistical analysis |
| Codebase overview: metrics catalog | `references/codebase-overview/statistical-metrics-catalog.md` | 100-metric catalog |
| Codebase overview: statistical phases | `references/codebase-overview/statistical-phase-details.md` | Phase banners and workflows |
| Codebase overview: statistical examples | `references/codebase-overview/statistical-analysis-examples.md` | Real-world statistical workflows |
| Value analysis: implementation | `references/repo-value-analysis/phase7-implement-template.md` | Agent dispatch template |
| Health check: endpoint validation | `references/service-health-check/endpoint-validator.md` | Full endpoint validation methodology |
| Health check: security headers | `references/service-health-check/security-headers.md` | HSTS, CSP reference |
| Health check: endpoint config | `references/service-health-check/endpoint-config-preferred-patterns.md` | Config patterns |
| Health check: auth endpoints | `references/service-health-check/auth-endpoint-patterns.md` | Auth endpoint patterns |
| Health check: CVE sources | `references/service-health-check/cve-source-check.md` | CVE source check methodology |
| ADR: agent prompts | `references/adr-consultation/agent-prompts.md` | 3-agent prompt templates |
| ADR: artifact patterns | `references/adr-consultation/consultation-patterns.md` | Verdict display, artifact templates |
| ADR: failure modes | `references/adr-consultation/consultation-preferred-patterns.md` | Dispatch and verdict fixes |
| ADR: error recovery | `references/adr-consultation/error-handling.md` | Error recovery by phase |
| Decision: archetypes | `references/decision-helper/decision-archetypes.md` | Archetype-specific criteria weights |
| Decision: failure modes | `references/decision-helper/decision-preferred-patterns.md` | Scoring discipline patterns |
| Critique: personas | `references/multi-persona-critique/personas.md` | 5 persona specifications |
| Critique: synthesis | `references/multi-persona-critique/synthesis-template.md` | Consensus matrix and report |
| Critique: examples | `references/multi-persona-critique/examples-and-errors.md` | Worked examples, failure modes |
| Critique: roast mode | `references/multi-persona-critique/roast.md` | HN persona evidence-based critique |
