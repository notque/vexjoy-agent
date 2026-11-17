# Implementation plans

Written by the improve skill on 2026-11-09 at commit `c0f87bbf`. Execute in the
order below unless dependencies say otherwise. Read a plan fully before
starting, honor its STOP conditions, and update your row when done.

Selection: default top 4 by leverage, no user present (AFK mode). Mode: bare,
`standard` depth.

Second run: 2026-11-16 at commit `871f6499`, plans 005-008. Same mode, depth,
and selection default. It audited what the first run listed under "Not
audited": hooks outside the churn hotspots, `skills/**` scripts, the account
and cron scripts, the workflows, and the private-name gate changed since the
first run. Its findings are in "Second run" at the end of this file.

## Execution order and status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---|---|---|---|
| [001](001-redact-indexer-credentials.md) | The search-engine indexer never prints a credential | P1 | S | none | DONE (owner-gated rotation pending) |
| [002](002-atomic-index-writes.md) | Index generators write INDEX.json atomically | P2 | S | none | DONE (revised: see Revision 2 in the plan) |
| [003](003-pin-ci-pyyaml.md) | CI installs PyYAML at the locked version, and a test keeps it so | P3 | S | none | DONE |
| [004](004-local-ci-script.md) | One command runs the CI lint job locally | P2 | S | none | DONE |
| [005](005-subagent-guard-block-format.md) | The subagent completion guard blocks in the format SubagentStop honors | P1 | S | none | DONE on branch `fix/hooks-audit-findings` (`9eeadedc`), not merged; step 6, install, is owner-gated |
| [006](006-routing-feedback-signal.md) | Find out why routing outcomes never record a real signal (investigate) | P2 | M | none | DONE: see [006-findings.md](006-findings.md) |
| [007](007-escape-wordpress-link-urls.md) | The WordPress converters escape link and image URLs | P2 | S | none | DONE on branch `fix/skills-script-findings` (`e2f60375`), not merged |
| [008](008-validate-account-names.md) | Account names and aliases are checked before they reach a shell file | P3 | S | none | DONE on branch `fix/scripts-docs-findings` (`6ea44104`), not merged |

Status values: TODO, IN PROGRESS, DONE, BLOCKED (one-line reason), REJECTED
(one-line rationale), STALE (superseded by plan NNN).

## Dependency notes

- No plan depends on another. Each touches a separate set of files.
- 003 and 004 both read `.github/workflows/test.yml`; only 003 edits it. If
  004 runs second, its drift check shows the 003 change, which is expected.
- Plan 001 step 5 is OWNER-GATED: rotate the Baidu push token and IndexNow key
  if dry-run or error output was ever logged.
- Plans 005-008 do not depend on each other or on 001-004. Each touches a
  separate set of files.
- Plan 005 step 6 is OWNER-GATED: installing the fixed hook turns on
  enforcement that has never run.
- Plan 006 changes no code. Its output, `plans/006-findings.md`, feeds a
  follow-up fix plan.

## Findings not selected

Vetted and real, ranked below the four plans. Plan one with
`/improve plan <description>`.

| Finding | Category | Effort | Confidence | Evidence |
|---|---|---|---|---|
| `feature-state.py` ignores a failed `git branch` before `git worktree add`; `retro-record` reads, modifies, and writes state without a lock | bug | S-M | HIGH | `scripts/feature-state.py:870-886`, `:565-610` |
| mypy is configured and never run | dx | M | HIGH | `pyproject.toml:185`; no CI step |
| Learning DB mixes naive local and UTC timestamps (investigate: no reader that mixes them found yet) | bug | M | MED | `hooks/lib/learning_db_v2.py:885,1016,2211,2279,2299,2514,2646` vs `:1155,1645,1812` |
| `init_db` opens a second connection and runs the full schema in every hook process (measure first) | perf | M | MED | `hooks/lib/learning_db_v2.py:96-109,341-356` |
| 11 hard gates lack a CLI-level negative control | tests | M | MED | `scripts/negative-control-allowlist.txt`; `.github/workflows/test.yml:70` |
| Duplicate `finalize_`/`drain_pending_outcomes`; three timed-stdin readers; five `extract_frontmatter` variants | tech-debt | S-M | HIGH | `hooks/lib/routing_outcome_state.py:332,508`; `scripts/generate-index.py:44`, `generate-skill-index.py:50`, `generate-agent-index.py:35` |
| `validate-threat-model.py` and `validate-decomposition.py` have no tests and no CI step (agent claim, not re-verified) | tests | S | MED | `scripts/validate-threat-model.py`, `scripts/validate-decomposition.py` |
| AI review job holds `id-token: write`; the action may need it | security | S | MED | `.github/workflows/pr-ai-review.yml:35-40` |

## Direction options (owner decision)

- Empty the negative-control allowlist and switch the gate to `--strict`
  (`test.yml:70`). Cost: 11 small CLI exit tests. Gain: no gate can pass
  vacuously.
- Gate `validate-merged-index.py --strict` in the lint job (`test.yml:72-75`).
  Needs the current advisory findings cleared first.
- Adopt mypy on `hooks/lib` and `scripts/vexinstall` with a baseline file.
  Largest effort; highest long-term payoff for the shared libraries.
- `adr/handoff-context-plan.md` is still "proposed" (2026-08-29): accept,
  reject, or retire it.

## Findings considered and rejected

- Routing-outcome hooks untested: false. Tests exist in
  `tests/test_learning_db_and_routing_outcomes.py` and
  `hooks/tests/test_weak_positive.py`, `test_apply_outcome.py`,
  `test_routing_outcome_basis.py`, `test_acceptance_detector.py`.
- `pipeline-phase-gate.py` untested: false. `scripts/tests/test_pipeline_phase_gate.py` has 25 tests.
- `pre-route.py` swallows generator failures: by design, documented at `scripts/pre-route.py:77-81`.
- `defer_advisory` appends JSONL without a lock: one writer, small `O_APPEND` writes.
- `pretool-unified-gate.py` size: the consolidation is a settled decision.
- `shell=True` in `hooks/lib/quality_gate.py:253-262`: documented accepted risk; the command comes from tracked config.
- `shell=True` in `grade.py:95`: no external input reaches it.
- `jev_transport.py:58` loads dotenv at import: only one hook module imports it.
- `jev_router` daemon-thread cleanup and breaker clock math: minor, bounded by a 60 s TTL.
- Lock-file hashes, GitHub action SHA pins, and pins for `pytest`, `pytest-xdist`, `numpy`: need PyPI or GitHub lookups (third-party egress). Owner decision; noted in plan 003.
- Fail-open hooks, the ruff ignore list, untracked `INDEX.json`, advisory always-exit-0 CI jobs, the ruff pin: settled trade-offs.

## Not audited

- `skills/**` scripts, `agents/`, `plugins/`, `evals/`, `services/`: outside the `standard` hotspot scope.
- Hooks outside the churn hotspots, and most `hooks/lib` modules.
- `scripts/routing-benchmark.py`, `register-hook.py`, the cron scripts.
- `scripts/manage-accounts.py`: has uncommitted edits.
- Test assertion quality beyond a sample.
- Commands in `docs/REFERENCE.md`.
- Known-vulnerability scan: `pip-audit` is not installed, and installing it is out of bounds for this skill.
- `.gitignore`: a safety hook blocks agent access to it.

## Second run (2026-11-16, commit `871f6499`)

### Carried over from the first run, re-checked at this commit

Still open and unchanged: the `feature-state.py` branch and lock finding
(`scripts/feature-state.py:870-881`, `:565-610`), mypy configured and never
run (`pyproject.toml:185`), the 11-entry negative-control allowlist
(`scripts/negative-control-allowlist.txt`), and the untested
`validate-threat-model.py` and `validate-decomposition.py` (now verified: no
test names either script and no CI step runs them). The other first-run rows
were not re-opened.

### Findings not selected

| Finding | Category | Effort | Confidence | Evidence |
|---|---|---|---|---|
| `posttool-security-scan.py` prints plain text on PostToolUse, which the model never sees; it also duplicates `security-review-hook.py`, registered on the same `Write\|Edit` matcher with the same scanner. Owner decision: retire it or fix its output. Either edits a safety hook or its registration | bug | S | HIGH | `hooks/posttool-security-scan.py:143-151`; `hooks/security-review-hook.py:349-354`; `.claude/settings.json:394,430` |
| The unattended Reddit moderation script feeds modqueue text to a headless session with `--permission-mode auto` and no tool allowlist. Its prompt also names `skills/content/reddit-moderate/scripts/reddit-mod.py`, which does not exist; the script is at `skills/content/content/scripts/reddit-moderate/reddit-mod.py`. Owner decision: it is a scheduled job | security, bug | M | HIGH | `skills/content/content/scripts/reddit-moderate/reddit-automod-cron.sh:69-71,89-95` |
| Two cron scripts export a GitHub token into a headless session that runs without permission prompts. Owner decision: scheduled jobs and credential handling | security | M | HIGH | `scripts/reference-enrichment-cron.sh:24-29`, `scripts/toolkit-evolution-cron.sh:21-27` |
| The private-name gate reads the staged diff and commit messages with the inherited environment, while its visibility check uses a cleaned one; a failed or timed-out read scans nothing | security | S | HIGH | `hooks/pretool-private-name-leak-gate.py:553-567` vs `:793-803` |
| `usage_db.py` runs the full schema on every recorded Skill call (verified) and Agent call, and its tables are never pruned (agent claims, not re-verified) | perf | S | HIGH | `hooks/lib/usage_db.py:64,111,146` |
| `quality_gate.py` re-reads the language registry once per file | perf | S | HIGH | `hooks/lib/quality_gate.py:76-79` |
| `ci-merge-gate.py` looks for `--admin` and `--force` with `str.split()`, so quoted or chained text can cause a false block | bug | S | MED | `hooks/ci-merge-gate.py:120-138` |
| `wordpress-media-upload.py` builds a `Content-Disposition` header from a raw file name; `wordpress-scraper.py` writes post titles into frontmatter without stripping newlines and downloads images with no size cap | security | S | HIGH | `skills/content/content/scripts/publish/wordpress-media-upload.py:129`; `wordpress-scraper.py:383-385,524-525` |
| The three WordPress publish scripts duplicate their config and auth helpers, and their env loaders keep quotes that the game-dev loader strips | tech-debt | S | HIGH | `skills/content/content/scripts/publish/wordpress-upload.py:56-134`, `wordpress-edit-post.py:44-122`, `wordpress-media-upload.py:34-83` |
| `fal_queue_image_run.py` exits at import when its API key is unset, so its helpers cannot be tested or reused | bug | S | HIGH | `skills/game/game-dev/scripts/fal_queue_image_run.py:55-61` |
| 78 of 136 skill scripts have no test (agent count, not re-verified) | tests | L | MED | agent inventory of `skills/**` |
| Timing-based tests with thin margins (line 253 verified; the others are agent claims) | tests | S | MED | `scripts/tests/test_jev_router_common.py:253,340,949` |
| No pip cache in CI (agent claim, not re-verified); index generation repeated in five or more jobs | dx | S-M | MED | `.github/workflows/test.yml:26,102,124,139,151` |
| `CONTRIBUTING.md` install line omits `pillow` and `numpy`, so image tests skip silently | docs | S | HIGH | `CONTRIBUTING.md:84` vs `.github/workflows/test.yml:100` |
| Eleven hook files are on disk and not registered (some are adapters for other CLIs; agent claim, not re-verified) | tech-debt | S | MED | `hooks/` vs `.claude/settings.json` |
| Three untracked Jev output files dated 2026-10-21 sit in `scripts/` | dx | S | HIGH | `git status --short` |

### Direction options (owner decision)

- The four options from the first run are still open.
- Routing feedback: plan 006 measures why outcomes carry no signal. After it,
  choose between repairing the reaction detectors and adding an explicit
  correction channel (`scripts/learning-db.py:979,1078` report both rates as
  not instrumented).
- `route-health` now reports one routing-relevant failure, which is the
  re-propose condition in `docs/route-loop-validation.md`. With zero strong
  outcomes the actuator still has nothing to act on; decide after plan 006.
- Session pickup across account profiles: `process` Pickup mode
  (`skills/process/process/SKILL.md:96`) starts from a handoff package, and
  nothing reads another profile's session history.
  Option: a read-only script that lists the latest sessions for the current
  repo across registered profiles and prints the user turns and final replies.
- Retire one of the two PostToolUse security scanners (first row above).

### Findings considered and rejected

- `github.base_ref` interpolated into a `run:` step (`.github/workflows/test.yml:222`): the workflow runs only for pull requests into `main`, so the value is always `main`.
- Route state files under `/tmp` with no user scoping (`hooks/lib/routing_outcome_state.py:113`): single-user machine; entries expire within 24 hours.
- `ci-merge-gate.py` logs a crash line on empty stdin (agent claim, not re-verified): it still exits 0; noise only.
- `posttool-session-reads.py` rewrites its file on every event (agent claim, not re-verified): bounded by 7-day retention; no measured cost.
- The private-name gate rebuilds its term list on every gated command (agent claim, not re-verified): about 10 ms, and a cache could miss a new private name.
- `with_server.py` runs its command with `shell=True` (agent claim, not re-verified): running a caller-supplied command is the script's purpose.
- Private repos skip the private-name gate: owner decision, 2026-11-13.

### Not audited

- About 40 hooks, including every `SessionStart` hook, `pretool-branch-safety.py`, `pretool-config-protection.py`, `pretool-worktree-edit-guard.py`, and the `routing-outcome-*` hooks beyond the finalizer. Plan 006 reads the routing ones.
- `skills/**`: the sprite scripts, `frontend/scripts-html-artifact/`, the workflow `.js` references, `docs-sync-checker`, `image-gen`, and `pr-workflow` scripts.
- `install.sh` and `scripts/vexinstall/`; `scripts/register-hook.py` path handling; `scripts/routing-benchmark.py` internals.
- Commands in `docs/REFERENCE.md` beyond a file-exists check.
- `agents/`, `plugins/`, `evals/`, `services/`.
- Known-vulnerability scan: `pip-audit` is not installed.

### Fix pass (2026-11-16, same day)

The owner asked for every listed issue to be fixed. Work sits on local
branches cut from `871f6499`; none is merged, pushed, or installed.

| Branch | Holds |
|---|---|
| `fix/hooks-audit-findings` | Plan 005; `quality_gate.py` registry cache; `ci-merge-gate.py` shell-aware flag check; private-name gate reads git with a cleaned environment |
| `fix/skills-script-findings` | Plan 007; media-upload header file name; scraper title and image size cap; env loaders strip quotes; `fal_queue_image_run.py` imports without its key; dead paths in the Reddit moderation script |
| `fix/scripts-docs-findings` | Plan 008; `feature-state.py` checks the `git branch` result; tests for `validate-threat-model.py` and `validate-decomposition.py`; `CONTRIBUTING.md` and the `dev` extra gain `pillow` and `numpy`; two timing sleeps replaced with a patched clock |
| `feat/verification-layer` | `REVIEW.md` with a diff-triggered checklist, read from the base branch by the AI review workflow; `Verified-By:` trailer and an observe-mode gate; flaky-test and three-round policies |
| `feat/voice-triad-eval` | `scripts/voice-triad-eval.py`, its reference, and writing-skill edits |

`feat/verification-layer` and `feat/voice-triad-eval` both edit the counts in
the root `README.md`; the second one merged needs its counts regenerated.

Still open after this pass:

| Finding | Why it is open |
|---|---|
| Reddit moderation script permission mode | Changing an unattended job's flags cannot be verified without running it |
| GitHub token export in two cron scripts | Same reason; also credential handling |
| `usage_db.py` schema on every call | Rejected: each hook run is a new process, so a per-process flag saves nothing |
| `cmd_retro_record` lock in `feature-state.py` | No lock helper exists in the file; needs its own plan |
| One thread-timing sleep (`test_jev_router_common.py:949`) | No deterministic replacement without changing the code under test |
| Shared module for the WordPress publish scripts; 78 untested skill scripts; 11-entry negative-control allowlist; mypy; CI pip cache and repeated index generation; unregistered hook files | Larger than a small fix, or not verifiable without a push. Plan each with `/improve plan <description>` |
| Writing docs name `voice-validator.py` and `voice-analyzer.py`, which are not in the repo | Found while building the voice eval (`skills/content/writing/SKILL.md:126,150,153`; `references/cv-iteration-guide.md:19,30`). Needs a decision: restore the scripts or rewrite the passages |

Integration (2026-11-16): the five branches were merged into
`feature/audit-fixes-verification-voice-eval`, one merge per branch, so each
is one revert unit. Two changes were added there:

- The subagent guard's branch check blocks only a subagent whose own
  transcript holds a commit-making command. Without that, any subagent
  finishing in a checkout whose default branch is ahead of its upstream would
  be told to move commits it did not make.
- `posttool-security-scan.py` was removed on the owner's delegation. It ran the
  same scanner, rules, and matcher as the PostToolUse path of
  `security-review-hook.py`, on Claude Code and on Codex, and its plain stdout
  never reached the model.
