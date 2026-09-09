# Vision

VexJoy Agent is a toolkit — agents, skills, hooks, and scripts — that absorbs complexity so users don't have to. It is not an app, not a harness, not a model. It sits between the user's intent and the agent runtime, supplying domain knowledge, methodology, enforcement, and determinism that the runtime alone does not provide.

## First principles

### Route, don't guess

Semantic dispatch to domain specialists beats a generalist trying everything. The `/do` router reads intent, selects an agent for domain knowledge and a skill for methodology, and hands off. A user who says "debug this Go test" gets a Go engineer and a debugging skill without naming either. Evidence: the 9-cycle pre-router failure (`docs/what-didnt-work.md`) shows what happens when routing changes lack a standing baseline.

### Measure, don't assume

Routing telemetry, A/B testing, and a negative-results registry (`docs/what-didnt-work.md`) record what works and what doesn't. Retire what doesn't work. Activity metrics (activation counts, skip rates) are not value metrics — a hint that fires 238 times proves nothing about whether it helped. The learning-capture system was removed after measurement found no link between what it stored and what it delivered (`docs/what-didnt-work.md`, 2026-08-28). That retirement is evidence of the principle, not a failure of it.

### Enforce, don't hope

Hooks that deny tool use are stronger than instructions that can be ignored. Exit gates require test output, not confidence. Branch-safety hooks block commits to protected branches. Anti-rationalization checks demand evidence rather than assertions. Instructions can be rationalized around; exit codes cannot.

### Scripts own determinism, agents own judgment

Don't spend LLM tokens on what grep can do. Scripts (136) handle indexing, validation, linting, and testing — deterministic operations with no model cost. Agents (43) and skills (122) handle interpretation, diagnosis, design, and synthesis. The boundary is strict: if it involves reasoning, it is an agent or skill; if it doesn't, it is a script. See [PHILOSOPHY.md](docs/PHILOSOPHY.md) for the full treatment.

### Complexity is the enemy

Every new skill must justify its existence against consolidation. Overlapping entrypoints get merged. Default injections that don't justify their cost get removed. The stale-skill scanner (`scripts/stale-skill-scan.py`) ranks pruning candidates quarterly. The learning-capture retirement removed an entire subsystem — capture, confidence lifecycle, injection, graduation — when measurement showed it delivered no value. Keeping dead machinery is more expensive than building it was.

## What we don't do

- **Fleet supervision across sessions.** The toolkit operates within one session. It does not coordinate multiple concurrent agent sessions or recover stuck siblings in other processes.
- **Own the harness.** VexJoy runs on Claude Code, Codex, Factory, and Reasonix. It supplies knowledge and enforcement on top of those runtimes but does not replace or fork them.
- **Replace the user's judgment on high-stakes decisions.** Destructive operations, public exposure, secret access, and live infrastructure changes require explicit owner authorization. The toolkit blocks by default and asks.

## What we want to become

- **Durable state across sessions.** Today, session context dies when the session ends. Routing telemetry persists in `learning.db`, but working context does not. Cross-session memory that actually delivers value — unlike the retired learning-capture system — requires proving the retrieval→injection→outcome chain before shipping it.
- **Supervision with stuck-recovery.** Long-running agent work stalls. Detecting stuck states and recovering (retry, escalate, abort) without human polling would make multi-step workflows reliable enough to run unattended.
- **Measured self-improvement that works.** The toolkit has tried and failed at automated self-improvement (learning capture, evolution loops). The discipline is to measure before shipping, retire what fails, and try smaller scopes. The next attempt must start with a defined value metric, not an activity metric.

## Relationship to PHILOSOPHY.md

This document is the "why" — what the toolkit believes and where it's going. [PHILOSOPHY.md](docs/PHILOSOPHY.md) is the "how" — operational principles that govern daily work. Both are authoritative; PHILOSOPHY.md is more granular and closer to implementation.
