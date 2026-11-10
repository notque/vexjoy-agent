# Implementation plans

Written by the improve skill on 2026-11-09 at commit `c0f87bbf`. Execute in the
order below unless dependencies say otherwise. Read a plan fully before
starting, honor its STOP conditions, and update your row when done.

Selection: default top 4 by leverage, no user present (AFK mode). Mode: bare,
`standard` depth.

## Execution order and status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---|---|---|---|
| [001](001-redact-indexer-credentials.md) | The search-engine indexer never prints a credential | P1 | S | none | DONE (owner-gated rotation pending) |
| [002](002-atomic-index-writes.md) | Index generators write INDEX.json atomically | P2 | S | none | DONE (revised: see Revision 2 in the plan) |
| [003](003-pin-ci-pyyaml.md) | CI installs PyYAML at the locked version, and a test keeps it so | P3 | S | none | DONE |
| [004](004-local-ci-script.md) | One command runs the CI lint job locally | P2 | S | none | DONE |

Status values: TODO, IN PROGRESS, DONE, BLOCKED (one-line reason), REJECTED
(one-line rationale), STALE (superseded by plan NNN).

## Dependency notes

- No plan depends on another. Each touches a separate set of files.
- 003 and 004 both read `.github/workflows/test.yml`; only 003 edits it. If
  004 runs second, its drift check shows the 003 change, which is expected.
- Plan 001 step 5 is OWNER-GATED: rotate the Baidu push token and IndexNow key
  if dry-run or error output was ever logged.

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
