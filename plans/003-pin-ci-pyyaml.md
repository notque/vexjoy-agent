# Plan 003: CI installs PyYAML at the locked version, and a test keeps it so

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c0f87bbf..HEAD -- .github/workflows/test.yml tests/test_ci_dependency_pins.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: deps
- **Kind**: fix
- **Planned at**: commit `c0f87bbf`, 2026-11-09

## Why this matters

`requirements.lock` pins `PyYAML==6.0.3`, but seven CI jobs run
`pip install pyyaml` with no version. Those jobs, the lint job among them, take
whatever PyPI serves that day, so a new PyYAML release can change or break
gates on a PR that touched nothing related, and the validators run against a
version nobody tested. The workflow already pins `ruff` for this reason
(`test.yml:21-24`). After this plan, every CI install of PyYAML names the
locked version, and a test fails when a new unpinned install appears.

## Current state

`.github/workflows/test.yml` is the only workflow with `pip install` lines.
All ten, at the planned commit:

```text
24:      - run: pip install ruff==0.15.12 pyyaml
100:      - run: pip install -r requirements.lock pytest pytest-xdist pillow numpy
123:      - run: pip install -r requirements.lock pytest pytest-xdist pillow numpy
137:      - run: pip install pyyaml
149:      - run: pip install pyyaml
161:      - run: pip install pyyaml pytest
184:      - run: pip install pyyaml
217:      - run: pip install -r requirements.lock pytest
241:      - run: pip install pyyaml
258:      - run: pip install pyyaml
```

`requirements.lock` (repo root, 20 lines, `name==version`, no hashes) holds
`PyYAML==6.0.3` and `pillow==12.2.0`. It does not hold `pytest`,
`pytest-xdist`, `numpy`, or `ruff`.

Conventions:

- Repo-config contract tests live in `tests/`. Exemplar:
  `tests/test_pytest_config.py` (module docstring, `_REPO_ROOT =
  Path(__file__).resolve().parents[1]`, plain `assert` with a message that
  says why the rule exists). Match it.
- Package names compare case-insensitively, with `-` and `_` equal
  (`PyYAML` equals `pyyaml`).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| New test | `python3 -m pytest tests/test_ci_dependency_pins.py -n 0 -q` | all pass |
| Lint | `ruff check . --config pyproject.toml` | `All checks passed!` |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Negative-control gate | `python3 scripts/validate-negative-controls.py` | exit 0 |
| Workflow parses | `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml'))"` | exit 0, no output |

## Scope

**In scope** (the only files to modify):
- `.github/workflows/test.yml`: the seven `pip install` lines that name
  `pyyaml` (24, 137, 149, 161, 184, 241, 258). No other line.
- `tests/test_ci_dependency_pins.py` (create)

**Out of scope** (do not touch):
- `requirements.lock`: do not add or change a pin.
- Pinning `pytest`, `pytest-xdist`, or `numpy`. A correct pin needs a version
  checked against Python 3.10 and 3.12 on PyPI. That is a network lookup the
  owner has not approved. See Maintenance notes.
- `actions/checkout@v6` and `actions/setup-python@v6` SHA pinning: same
  reason.
- `ruff==0.15.12`: pinned on purpose (`test.yml:21-23`).
- Every other workflow file.

## Git workflow

- Branch: `fix/advisor-003-pin-ci-pyyaml`.
- One commit. Message style: one lowercase past-tense sentence, no type
  prefix, no trailing period. Example from `CONTRIBUTING.md`:
  `moved the hook timeouts to seconds so a stuck hook stops holding the session`.
- No `Co-Authored-By` or "Generated with" lines.
- Do not push, open a PR, merge, deploy, or tag. Do not run `pip install`.

## Steps

### Step 1: Write the failing test

Create `tests/test_ci_dependency_pins.py`. It reads files only; no network, no
`pip`.

1. Collect every `pip install` command from each `.github/workflows/*.yml`
   with a line regex (`^\s*-?\s*(?:run:\s*)?pip install (.+)$`), keeping
   `file:line` for messages.
2. Parse `requirements.lock` into `{normalized_name: version}`. Normalize
   with `re.sub(r"[-_.]+", "-", name).lower()`.
3. Define `KNOWN_UNPINNED = {"pytest", "pytest-xdist", "numpy"}` with a
   comment: "debt: not in requirements.lock; shrink this set, never grow it".
4. Tokenize each command. Skip `-r <file>` pairs, recording whether the
   command has `-r requirements.lock`.
5. Test `test_ci_installs_are_pinned`: every remaining token is one of:
   - `name==version`;
   - a bare name pinned in the lock, in a command that has
     `-r requirements.lock` (covers `pillow` on lines 100 and 123);
   - a bare name in `KNOWN_UNPINNED`.
   The failure message names `file:line`, the token, and the fix ("pin it to
   the requirements.lock version").
6. Test `test_ci_pins_match_lockfile`: for every `name==version` token whose
   name is in the lock, the version equals the lock version.
7. Test `test_known_unpinned_is_not_stale`: every name in `KNOWN_UNPINNED`
   still appears bare in some command, so the set shrinks when a pin lands.
8. Test `test_parser_finds_installs`: at least one command was collected, so
   a broken regex cannot pass the file vacuously.

**Verify**: `python3 -m pytest tests/test_ci_dependency_pins.py -n 0 -q` →
`test_ci_installs_are_pinned` fails and its output names 7 lines; the other
three tests pass.

### Step 2: Pin the seven lines

In `.github/workflows/test.yml`, replace the token `pyyaml` with
`pyyaml==6.0.3` on lines 24, 137, 149, 161, 184, 241, and 258. Results:

```text
24:      - run: pip install ruff==0.15.12 pyyaml==6.0.3
137, 149, 184, 241, 258:      - run: pip install pyyaml==6.0.3
161:      - run: pip install pyyaml==6.0.3 pytest
```

**Verify**:
- `grep -c "pyyaml==6.0.3" .github/workflows/test.yml` → `7`
- `grep -nE "pip install.*pyyaml( |$)" .github/workflows/test.yml` → no matches
- `python3 -m pytest tests/test_ci_dependency_pins.py -n 0 -q` → 4 passed

### Step 3: Run the gates

**Verify**: Lint, Format, Negative-control gate, and Workflow parses commands
from the table → all succeed.

## Test plan

- New: `tests/test_ci_dependency_pins.py`, 4 tests (step 1). The regression
  is test 5 failing before step 2 and passing after.
- Structure model: `tests/test_pytest_config.py`.
- Verification: `python3 -m pytest tests/test_ci_dependency_pins.py -n 0 -q` → 4 passed.

## Done criteria

- [ ] `python3 -m pytest tests/test_ci_dependency_pins.py -n 0 -q` exits 0, 4 passed
- [ ] `grep -c "pyyaml==6.0.3" .github/workflows/test.yml` prints `7`
- [ ] `git diff --stat -- .github/workflows/test.yml` shows 7 insertions and 7 deletions
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `python3 scripts/validate-negative-controls.py` exits 0
- [ ] `git status --short` shows only the two in-scope files (plus `plans/README.md` if you maintain the index)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The `pip install` lines do not match the "Current state" list.
- `requirements.lock` no longer pins `PyYAML==6.0.3`. Use the lock's version
  only after reporting; do not guess.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- `scripts/validate-negative-controls.py` fails after step 2: it reads this
  workflow, and a changed `run:` line may need a matching control.
- A step would need `pip install`, a PyPI lookup, a deploy, a credential, or
  any request to a third party.

## Maintenance notes

- CI is the real proof. The executor cannot run GitHub Actions; the owner
  sees the result on the first PR that carries this change.
- When `requirements.lock` bumps PyYAML, `test_ci_pins_match_lockfile` fails
  until the seven lines follow. That is the intended coupling.
- Deferred, owner decision (needs network): pin `pytest`, `pytest-xdist`, and
  `numpy` in a dev lock file and empty `KNOWN_UNPINNED`; add `--hash` entries
  to `requirements.lock`; pin the two GitHub actions to commit SHAs.
- A reviewer should check that only the seven lines changed in `test.yml`.
