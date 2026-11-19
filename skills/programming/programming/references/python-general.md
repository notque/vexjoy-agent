---
description: "General Python development: features, debugging, code review, performance, tests. Modern Python 3.12+ rules bounded by requires-python, verification STOP blocks, ruff/pytest/mypy gates."
type: reference
---

# General Python Development

Rules for idiomatic, production-ready Python for the project's Python version
(3.12 or newer; `requires-python` sets the floor). Covers features, debugging,
review, performance, and tests.

Not for: OpenStack services and Oslo libraries (load `python-openstack.md`);
SQLite and Peewee ORM work (use the `data` skill); PHP (load `php-general.md`).
Final replies use the Implementation Schema in
[output-schemas.md](../../../shared-patterns/output-schemas.md). Source files
contain only code, never a summary.

## Expertise areas

- **Modern Python:** 3.11 features (TaskGroup, `asyncio.timeout`, exception
  groups, `Self`), 3.12 PEP 695 generics and `type` aliases, 3.13 and 3.14
  additions only when `requires-python` allows them.
- **Type safety:** mypy strict mode, generics, Protocols, TypedDict, Literal
  types, type narrowing.
- **Async:** asyncio, async context managers, TaskGroups, structured
  concurrency, async generators, rate limiting.
- **Testing:** pytest fixtures, parametrize, `unittest.mock`, coverage,
  property-based testing, async tests.
- **Code quality:** ruff (lint and format), mypy, bandit, pre-commit, uv.
- **Production readiness:** error handling, structured logging, configuration,
  dependency management, graceful shutdown, health checks.

## Baseline practices

- Type hints on public functions and class attributes.
- `pathlib` over `os.path`.
- Dataclasses or Pydantic models for structured data.
- Custom exception types for error handling.
- Clear test names and good coverage.
- Context managers for resource management.
- PEP 8 with line length 120.
- Only language and library features at or below the `requires-python` floor.

## Review priorities

1. Correctness and edge cases
2. Type safety and type hints
3. Security (SQL injection, XSS, insecure dependencies)
4. Error handling with proper exception types
5. Resource management (file handles, connections, locks)
6. Performance (comprehensions, generators, unnecessary allocations)
7. Modern features (pattern matching, exception groups, TaskGroups)
8. Test coverage and quality

## Hard rules

- **Write modern Python.** Before you write or edit Python code, load
  [python-modern-code.md](python-general/python-modern-code.md) and follow it.
  Code that passes its tests still fails review when it breaks these rules. The
  rules most often missed:
  - Read `requires-python` (or `python3 --version`) first and use no feature
    newer than that floor.
  - `build-backend` is exactly `hatchling.build` or `setuptools.build_meta`;
    invented backends break `pip install .`.
  - Builtin generics, `X | None`, and `collections.abc` imports; PEP 695
    `class Box[T]` on 3.12+; no bare generics; narrow `Any` from JSON before
    returning it.
  - A docstring on every public module, class, function, and method.
  - `raise ... from err` inside `except`; no `assert` outside tests; `Decimal`
    input checked with `is_finite()`.
  - `asyncio.TaskGroup` + `asyncio.timeout` + `Semaphore`; never swallow
    `CancelledError`.
  - SQL through `?` placeholders only, escaped `LIKE`,
    `PRAGMA foreign_keys = ON`, `with conn:` transactions.
- **Pre-handoff checklist.** Before you report done, run the commands and tick
  the checklist in python-modern-code.md section 14. Without tools, check the
  code against each checklist line.
- **Run ruff after every Python edit.** After editing any `.py` file, run
  `ruff check --fix <changed files> && ruff format <changed files>` before
  committing; ruff picks up the project's `pyproject.toml` or `ruff.toml`. CI
  rejects unsorted imports and unformatted code. Limit ruff to the changed
  files: formatting the whole tree rewrites code outside the request. Do not
  rely on humans to catch lint failures.
- **Before handoff, run** `ruff check --fix`, `ruff format`, `mypy --strict`,
  and `pytest` (python-modern-code.md section 14).
- **Type hints on all public functions**, parameters and return values.
- **Show complete command output.** Never summarize as "tests pass"; show actual
  pytest, ruff, and mypy output.
- **pytest** for all test code.
- **`pathlib.Path`** for all file operations.

## Defaults (on unless disabled)

- Run `pytest -v` after code changes; show full output.
- Run `ruff check <changed files>`; show any issues.
- Google-style docstrings on public functions and classes.
- Dataclasses over plain classes for data structures.
- Run mypy when type hints are present.

## Off unless requested

- Aggressive refactoring beyond the immediate task.
- New third-party dependencies.
- Converting sync code to async (only when concurrency is needed).
- Micro-optimizations before profiling confirms need.

## Verification STOP blocks

Mandatory. Do not skip them even when confident.

- **After writing code:** STOP. Run `pytest -v` and show the output. Untested
  code is an assumption, not a fact.
- **After claiming a fix:** STOP. Confirm the fix addresses the root cause, not
  the symptom. Re-read the original error and confirm it cannot recur.
- **After completing the task:** STOP. Run
  `ruff check --fix <changed files> && ruff format <changed files>` and
  `pytest -v` before reporting. Show the actual output.
- **Before editing a file:** read it first. Blind edits cause regressions.
- **Before committing:** do not commit to main. Create a feature branch.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Any task that writes or edits Python code: package, CLI, service, async worker, repository, tests, `pyproject.toml` | [python-modern-code.md](python-general/python-modern-code.md) | Measured failure patterns with before/after code: version floor, build backend, typing, docstrings, errors, Decimal, resources, asyncio, HTTP clients, sqlite3, FastAPI, CLIs, tests, ruff codes, pre-handoff checklist |
| flask, jinja, gunicorn, blueprint, CSRF exempt, static 403, SESSION_COOKIE_SECURE, StrictUndefined, systemctl restart | [flask-jinja-webapp.md](python-general/flask-jinja-webapp.md) | mmr-ratings production incidents: worker template cache, mode-600 static 403, CSRF blueprint exemptions, error-fix map |
| except OSError, type: ignore, E712, Peewee, venv, pip mismatch, uv install, reddit_mod, stdin JSON, LLM prompt fields, tarfile, yaml.load, pickle, extra="allow", SSRF | [python-local-gates.md](python-general/python-local-gates.md) | Host incidents (reddit_mod silent failures), Peewee E712 suppression, host venv/uv rules, CLI pipeline conventions, CVE-pinned gotchas |
| Cleanup, linting, formatting, quality gates | the `code-quality` skill | Shared quality-gate workflow |

## Error handling

Exception rules (chaining, narrow `except`, one base exception per package, no
`assert` in library code) are in python-modern-code.md section 5. Host-incident
fixes and version-pinned gotchas live in
[python-local-gates.md](python-general/python-local-gates.md).

## Hard gates

Before writing Python code, check the hard-gate table in
[python-local-gates.md](python-general/python-local-gates.md) (STOP / REPORT /
FIX with detection commands). Framework:
[forbidden-patterns-template.md](../../../shared-patterns/forbidden-patterns-template.md).

## Blockers and death-loop prevention

For fundamental design choices (async vs sync, ORM, framework, error-handling
strategy, new dependencies, breaking API changes), follow the project's existing
choice. Otherwise decide, record the assumption in the report, and ask Jev when
genuinely unsure. Ask only when a choice leaves a material decision uncovered.
After 3 failed attempts at the same fix, stop and reassess the diagnosis instead
of iterating.
