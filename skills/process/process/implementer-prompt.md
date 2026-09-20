# Implementer dispatch contract

Supply the project context, conventions, branch, test command, `BASE_SHA`, complete task text, owned paths, and exact verification. The implementer must stay within those paths, run verification, self-review, and report edits and check results. Commit only when the parent task authorizes commits.

For executor-ready plans, also supply the plan-creation SHA, inlined context excerpts, in/out-of-scope paths, and per-step verify/expected pairs. Stop and return completed work plus the needed decision when ancestry or excerpts drift, verification fails twice, an out-of-scope path is required, a required step is ambiguous/missing, or a previously passing test regresses. Do not improvise past a stop condition.
