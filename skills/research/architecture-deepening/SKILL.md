---
name: architecture-deepening
version: "1.2.0"
description: "Improve architecture across modules by deepening interfaces."
user-invocable: true
command: architecture-deepening
context: fork
allowed-tools: [Agent, Bash, Read, Write, Edit, Glob, Grep]
routing:
  triggers: [improve architecture, improve codebase architecture, improve the codebase architecture, find architecture improvements, deepen architecture, find shallow modules, architecture improvement, module depth analysis, deepening opportunities, improve module interfaces, architecture deepening]
  not_for: "local cleanup/refactoring, vague complexity reduction, feature design, or architecture overview/explanation; requires cross-module interface or caller-burden evidence"
  pairs_with: [review, assessment]
  complexity: Medium
  category: analysis
---

# Architecture Deepening

Find module boundaries where callers must manage implementation detail or coordinate several components for one operation. This is read-only design work until the user selects a candidate and separately authorizes persistence or implementation.

Read `references/maintenance-lifecycle.md`; it owns scope, evidence, decision memory, terminal states, and handoff rules. The bundled scripts and schemas own serialization and path safety.

## Survey

Start with a user-named module or evidence from a review, feature, or completed fix. With no narrower evidence, use the lifecycle's bounded recent-change scan. Read prior decisions before ranking.

A candidate needs a specific interface, an observed caller burden, two affected callers or one high-impact caller, and a plausible seam that deletes or simplifies caller work. Useful burdens are leaked dependencies, repeated configuration, duplicated coordination, required source reading, temporal ordering, and implementation errors escaping the boundary. Recent change alone is not evidence.

Return at most five ranked candidates with interface/caller locations, seam (`data`, `protocol`, `temporal`, or `error`), deletion test, leverage, and prior-decision match. A no-findings result is valid; do not pad the list.

## Design

Stop for the user's selection. For a selected candidate, compare at least two concrete interfaces by what moves behind the boundary, caller code deleted, migration path, lost flexibility, escape hatch, testing seam, and second-order coupling. Limit the design conversation to three rounds, then select, defer, reject, or close as no-change.

Emit the lifecycle's complete typed handoff for every valid terminal result. Validate it with `scripts/handoff.py` before any successor acts. Persistence is separate from emission and requires authorization. Use only `decision_memory.py append` for durable decision memory; direct edits bypass its locking, containment, and atomic-write guarantees.
