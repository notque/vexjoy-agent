# Architecture Maintenance Lifecycle

## Safe Entry Moments

Use a named interface/caller concern, 3+ concrete boundary signals from an artifact, a cross-module feature, a completed fix that exposed coupling, or an explicit repository-wide survey. A generic architecture label, defect review, one-file cleanup, or mapping request stays with its primary route.

## Scope and Recent-Change Bias

Priority: user scope; artifact-named modules; otherwise the five busiest module boundaries from the last 50 commits. Exclude generated, vendor, fixture, snapshot, lock, and build files. Widen once only for an explicitly repository-wide request. Recent change prioritizes inspection; it does not prove shallowness.

## Prior-Decision Read

Search `adr/`, `docs/`, and `.local/architecture-decisions.md`. Create and query canonical fingerprints only with:

```bash
python3 skills/research/architecture-deepening/scripts/decision_memory.py fingerprint --module '<path>' --symbol '<symbol>' --burden-kind '<kind>'
python3 skills/research/architecture-deepening/scripts/decision_memory.py find --repo-root . --store '<store>' --fingerprint '<fingerprint>'
```

Suppress a matching rejection while its assumptions hold. Changed callers, dependencies, constraints, or feature direction may reopen it through a superseding record.

## Candidate Evidence Floor

Require one public boundary, one observed caller burden, 2+ callers or one high-impact caller, a plausible seam, a caller deletion/simplification, and no still-valid matching rejection. Rank by severity, leverage, change likelihood, and deletion value using HIGH/MEDIUM/LOW.

## No-Findings Result

Report inspected paths/callers, evidence source, prior decisions, candidates considered, why each failed the floor, and a concrete revisit condition. Validate the corresponding inline `no-findings` handoff using `scripts/handoff.py validate --stdin --repo-root .`; validation writes nothing.

## Durable Decision Memory

Persist only when the user approves and the outcome is stable, surprising, costly to rediscover, and involved at least two credible options. The only stores are `docs/architecture-decisions.md` (`shared`) and `.local/architecture-decisions.md` (`local`). Create a record valid against `decision-memory-record.schema.json`, then run:

```bash
python3 skills/research/architecture-deepening/scripts/decision_memory.py append --repo-root . --store '<store>' --record '<record.json>'
```

The helper owns canonicalization, containment, symlink rejection, locking, re-read, fsync, and atomic replacement. Preserve history through `supersedes`.

## Terminal States

- `selected`: non-empty module and caller paths, current/proposed interfaces, migration, and 2+ measurable criteria (3+ for feature work).
- `rejected` / `deferred`: action, migration, criteria, consultation ADR, and successors are null/empty.
- `no-change`: current-interface rationale; no proposal or successor. HIGH risk requires a registered ADR path/hash.
- `no-findings`: null candidate/artifacts/interfaces/successors, LOW risk, empty criteria, and non-empty inspected modules.

## Architecture Change Handoff

Emit exactly one object valid against `skills/shared-patterns/schemas/architecture-change-handoff.schema.json`, with exact `"origin": "architecture-deepening"`. Invalid fingerprints, unsafe paths, symlink/containment failures, candidate-scope contradictions, or stale ADR provenance produce no handoff and no dispatch.

Authorized writes use only:

```bash
python3 scripts/handoff.py write --stdin --repo-root . --handoff 'adr/handoffs/<name>.json'
```

Change-class successors:

- `close`: no skill or pipeline.
- `behavior-preserving-refactor`: `next_skill: workflow`, `next_pipeline: systematic-refactoring`; MEDIUM/HIGH risk requires a registered and validated consultation ADR.
- `interface-migration` or `new-behavior`: `next_skill: workflow`, null pipeline and ADR fields; workflow DESIGN creates the canonical ADR and its pre-IMPLEMENT gate consults it.

All action paths are repository-relative. Every consumer reruns neutral handoff validation with its expected successor before acting. The user approves any successor dispatch.
