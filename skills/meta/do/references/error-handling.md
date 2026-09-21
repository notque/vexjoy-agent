# Router error handling

Errors never authorize bypassing a required phase or the fresh actual-intent
check. Repair the decision and run the shared required-router protocol again
before invoking a worker or answering directly.

| Error | Required recovery |
|---|---|
| No agent matches | Recheck live domain/near-match descriptions; only then use `general-purpose` with a written reason and the closest methodology skill (`workflow` fallback). |
| Force-route conflict | Choose the most specific intent match within each slot; combine compatible skill/pipeline/stack selections; protected git/security guards remain authoritative. |
| Plan required | Create/update the task-owned `task_plan.md`, supply its path, and retry validation. |
| Classifier script failed | Report the actual failure and use the full `/do` semantic selection flow; retain originating router provenance and every remaining gate. |
| Builder or intent check failed | Correct missing evidence, changed scope, or invalid names; retry the builder. Never hand-assemble a dispatch. |
| Jev unavailable or errored | Report the diagnostic; keep dependent execution blocked until a fresh check succeeds. |
| Essential clarification | Obtain the missing material decision, update request context and intent, and revalidate. |
| Worker incomplete | Inventory missing scope/evidence, repair through a validated handoff, and verify again. |

A fallback is a route-selection recovery, not a successful intent receipt.
