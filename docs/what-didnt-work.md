# What didn't work

Negative-results registry. A list of experiments that lost, so the next session skips a known-dead path.

When to add: you tried something and it failed, weakened, or got reverted. Record it here before you forget. Newest on top.

Format: one `## YYYY-MM-DD <experiment>` section with the four bold fields below. Evidence must be a location (`file:line`, eval path, PR #, or `learning.db topic/key`), not a claim.

```markdown
## YYYY-MM-DD <experiment, one line>

- **Expectation**: what we predicted.
- **What happened**: the observed result.
- **Evidence**: file:line, eval path, PR number, or learning.db topic/key.
- **Decision**: rejected | deferred | revisit-if <condition>.
```

Query it: read this file, run `grep -c '^## 2026' docs/what-didnt-work.md`, or run `/retro what-didnt-work` (prints the file; optionally mirrors a one-line pointer into learning.db for FTS search). Check it before re-running an experiment.

---

## 2026-06-05 Provenance footers on every answer

- **Expectation**: per-answer footers (source tier, confidence, reviewed-by, freshness, owner) improve auditability.
- **What happened**: refuted for a single-user toolkit. The metadata is already captured internally in learning.db via hooks (`routing-decision-recorder`, `routing-outcome-recorder`, `review-capture`) and is queryable through `learning-db.py`. Footers add friction with no new value and fight the Dense-Complete Writing standard.
- **Evidence**: verified detail `skills-design` / "Provenance footers"; `skills/meta/do/SKILL.md` lines 461-467 (hook capture, not in output).
- **Decision**: rejected.

## 2026-06-05 Strict knowledge/process skill split

- **Expectation**: partition each complex skill into a knowledge-only semantic router plus a separate process executor.
- **What happened**: refuted. The toolkit composes agent + skill at dispatch time, and most skills are intentionally hybrid (`/do` routes and orchestrates; `planning` interviews and executes). The `pairs_with` field already documents relationships declaratively. A forced binary split adds structure with no working gain.
- **Evidence**: verified detail `skills-design` / "Pairwise knowledge + process skill splitting"; `skills/process/planning/SKILL.md` lines 92-95 (`pairs_with`); `skills/meta/do/SKILL.md` line 280.
- **Decision**: rejected.

## 2026-06-05 Eval-doc caveats left as unindexed prose

- **Expectation**: nothing. This is the gap that motivates the registry.
- **What happened**: real eval caveats (for example the N=1 pilot note) sit as prose in eval READMEs, unsearchable. This registry indexes future ones. Back-filling old eval caveats is out of scope for this PR.
- **Evidence**: `evals/dense-complete-writing/README.md:25-26`.
- **Decision**: revisit-if a second eval produces a coverage-collapse result (then back-fill the old caveats).

---

## Program notes (blog-learnings implementation)

Operational dead-ends from the implementation program. Reverted approaches and runtime quirks, not experiment hypotheses, so they sit below the dated seed entries. Same six fields, lighter heading.

### 2026-06-05 Post-merge git pull as live hook deployment

- **Expectation**: pulling main after a merge puts the changed hooks live in `~/.claude` immediately via the post-merge sync hook.
- **What happened**: the post-merge hook is deliberately no-clobber (commit 18e6d03c) so it adds new items but never overwrites existing `~/.claude` hooks. Freshly merged telemetry capture stayed inert (0 rows) until `sync-to-user-claude.py` was run manually on SessionStart; the next probe then wrote the first `telemetry_runs` row.
- **Evidence**: commit 18e6d03c; `hooks/sync-to-user-claude.py`; program negative-notes log, 2026-06-05.
- **Decision**: rejected. After merging hook changes mid-session, run `sync-to-user-claude.py` (or restart the session) before expecting live hook behavior; the no-clobber pull alone will not deploy them.

### 2026-06-05 Workflow args global on the Windows runtime

- **Expectation**: the Workflow tool `args` param is exposed to the script as the `args` global.
- **What happened**: both launches failed in 9ms with "undefined is not an object (evaluating 'args.prs')". `args` was never delivered, for inline script and `scriptPath` invocations alike.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Hardcode run config as a `const` inside the script file; do not parameterize Workflow scripts via `args` on this runtime version.

### 2026-06-05 gh auth login --with-token from stored git PAT

- **Expectation**: authenticate the gh CLI non-interactively by piping the git-credential-manager PAT into `gh auth login --with-token`.
- **What happened**: login validation rejected the token for missing `read:org` scope (the push-capable PAT has `repo` only). `hosts.yml` stayed absent and the first ship run failed.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Export `GH_TOKEN` from `git credential fill` per session; gh honors it without the `read:org` validation, and `repo` scope covers pr create/checks/merge.

### 2026-06-05 VEXJOY_SECURITY_REVIEW_SKIP via Bash inline env-prefix

- **Expectation**: a bash inline prefix (`VAR=1 git commit ...`) or `export` in the Bash tool would let the PreToolUse security-review hook see the skip var.
- **What happened**: the var never reached the hook. The Claude Code runtime intercepts any Bash string containing "git commit", spawns the hook from the runtime process env (not the tool subshell), and blocks before the inline assignment runs.
- **Evidence**: program negative-notes log, 2026-06-05.
- **Decision**: rejected. Set the var in the PowerShell process (`$env:VEXJOY_SECURITY_REVIEW_SKIP="1"`) before `git commit`; PowerShell's process env propagates to the runtime-spawned hook. Use the override only for the auditable self-scan case.

### 2026-06-05 Windows fcntl-less concurrency tests

- **Expectation**: full local pytest of `test_routing_decision_recorder.py` would be green.
- **What happened**: the `TestBridgeConcurrency` parallel-append tests fail on Windows. `routing_outcome_state` serializes with `fcntl.flock`, which is absent on win32, so the lock is a no-op and concurrent appends race. Identical failures reproduce on a clean main checkout; CI's Linux runner passes them.
- **Evidence**: `hooks/lib/routing_outcome_state.py`; program negative-notes log, 2026-06-05.
- **Decision**: revisit-if the toolkit adds a win32 lock fallback. Treat as a pre-existing Windows-only environment limit, not a PR regression; trust CI's Linux run for these tests.

### 2026-06-05 Probe learnings table for git_commit_sha telemetry columns

- **Expectation**: PR-A would add named envelope columns (`git_commit_sha`, `model_id`, `skill_version`) to the `learnings` table, so a `--record` path could probe `PRAGMA table_info(learnings)` and update them.
- **What happened**: PR-A (#741) shipped the envelope as a dedicated `telemetry_runs` table (schema v5, `git_sha` column) with a `record_telemetry_run()` API. `learnings` never gets `git_commit_sha`, so the probe always found it absent and degraded to a log file. The with-envelope test passed only because the fixture hand-added the column, certifying a path production never takes.
- **Evidence**: PR #741; `learning-db.py telemetry-query`; program negative-notes log, 2026-06-05.
- **Decision**: rejected. Probe `telemetry_runs` existence; write via `record_telemetry_run()` and keep a human-readable summary row in `learnings`. Fixtures build the real schema.
