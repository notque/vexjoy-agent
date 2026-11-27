# Mutation Testing: `jev_limits.py` and `jev_router_common.py`

Local-only on-request mutation testing via `cosmic-ray` for load-bearing deterministic Jev scripts (`scripts/jev_limits.py` for split/budget math and `scripts/jev_router_common.py` for retry/backoff logic). For `hooks/` and `scripts/validate-*.py`, use `python3 scripts/mutation-check.py --hook hooks/<name>.py` instead.

## Tool choice: cosmic-ray over mutmut

`mutmut` 3.x copies mutated source into a sandboxed `mutants/` tree, which breaks `scripts/tests/conftest.py`'s flat `sys.path` import convention (`import jev_limits`). `cosmic-ray` mutates the real file in place, runs the configured test command, and restores it cleanly.

## Run (disposable venv, kept untracked)

```bash
python3 -m venv .venv && ./.venv/bin/python -m pip install cosmic-ray
./.venv/bin/cosmic-ray init scripts/cosmic-ray-jev-limits.toml /tmp/jev-limits-mutation.sqlite
./.venv/bin/cr-filter-operators /tmp/jev-limits-mutation.sqlite scripts/cosmic-ray-jev-limits.toml
./.venv/bin/cosmic-ray exec scripts/cosmic-ray-jev-limits.toml /tmp/jev-limits-mutation.sqlite
./.venv/bin/cr-report /tmp/jev-limits-mutation.sqlite

./.venv/bin/cosmic-ray init scripts/cosmic-ray-jev-router-common.toml /tmp/jev-router-common-mutation.sqlite
./.venv/bin/cr-filter-operators /tmp/jev-router-common-mutation.sqlite scripts/cosmic-ray-jev-router-common.toml
./.venv/bin/cosmic-ray exec scripts/cosmic-ray-jev-router-common.toml /tmp/jev-router-common-mutation.sqlite
./.venv/bin/cr-report /tmp/jev-router-common-mutation.sqlite
```

Each config's `[cosmic-ray.filters.operators-filter]` trims the pairwise operator-swap matrix down to one mutant per operator family (skipping unevaluated PEP 604 `X | None` `BitOr` annotations under `from __future__ import annotations`). Compute score as `killed / (killed + survived)` over the mutants that actually ran (203 for `jev_limits.py`, 435 for `jev_router_common.py`).

## Baseline (2026-10-30, cosmic-ray 8.7.0)

| File | Ran | Killed | Survived | Other | Score |
|---|---|---|---|---|---|
| `jev_limits.py` | 203 | 90 | 113 | -- | 44% |
| `jev_router_common.py` | 435 | 188 | 245 | 2 incompetent | 43% |

The 2 incompetent `jev_router_common.py` mutants stem from a cosmic-ray 8.7.0 `ExceptionReplacer` bug on `except (A, B, ...)` tuples and are excluded from the score. Most survivors are `NumberReplacer` hits on relational policy constants (`REQUEST_TOKEN_LIMIT`, `SAFE_FRACTION`, cache TTLs), `check_run` boundary comparisons, and `call_jev` telemetry branches. Investigate any re-run dropping below 35% before merging.
