# Jev composition patterns

Use the smallest topology whose answers change policy:

| Need | Topology | Local example |
|---|---|---|
| route many candidates | cheap wide Choice, code shortlist, detailed Choice | `jev-route.py` |
| choose and reject | Choice winner plus per-candidate fitness Nouls | `jev-route.py` |
| reusable dimensions | parallel Nouls, combined by named code policy | review gates |
| evidence created by first judgment | request 1, code derives evidence, request 2 | taxonomy walk |
| inspect output | action, then post-judge over actual output | `jev-browser-verify.py` |
| bounded residual | rules decide extremes, Jev middle, optional frozen-evidence reviewer | evidence pipelines |

Do not serialize independent heads, multiply same-state probabilities, or use a composite Score when individual dimensions drive different actions. A cascade must log every attempt and cap retries. A verifier judges supplied evidence; code still checks schema, operation, target, and permissions.

When inventing a pattern, identify its position from `composition-positions.md`, define failure behavior and cost, then falsify it on labels and judge-variance repeats before adding it here.
