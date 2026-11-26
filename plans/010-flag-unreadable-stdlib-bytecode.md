# Plan 010: The installer flags an unreadable stdlib bytecode cache, and the owner repairs this host

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c68ac1fe..HEAD -- scripts/vexinstall/interp.py scripts/vexinstall/doctor.py scripts/vexinstall/apply.py scripts/tests/test_hook_python_pin.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Kind**: fix (steps 1-4) plus one OWNER-GATED host repair (step 5)
- **Planned at**: commit `c68ac1fe`, 2026-11-26

## Why this matters

Every toolkit hook is a fresh Python process, and Claude Code starts about 10
of them before each Bash, Write, or Edit call and 4 to 7 after. On this host,
four standard-library `__pycache__` directories are owned by root with mode
700: `/usr/lib/python3.12/{importlib,re,encodings,collections}/__pycache__`
(dated 2026-09-12 06:02, likely written by root under a 077 umask during a
package upgrade). User `feedgen` cannot read them, so every Python process
recompiles those four packages from source.

Measured on 2026-11-26 (medians, `nice -n 10`, isolated HOME):

| What | Today | With a readable bytecode cache |
|---|---|---|
| `python3 -c pass` | 30.9 ms | 17.5 ms |
| `python3 -c "import re, json"` | 53.1 ms | 25.7 ms |
| Smallest hook (`suggest-compact.py`) | 59 ms | 33 ms |
| 10 PreToolUse hooks on one Bash call: sum / slowest | 704 / 87 ms | 458 / 60 ms |
| 10 PreToolUse hooks on one Write call: sum / slowest | 690 / 80 ms | 409 / 50 ms |
| 7 PostToolUse hooks on one Edit call: sum / slowest | 460 / 83 ms | 280 / 53 ms |
| 8 UserPromptSubmit hooks: sum / slowest | 548 / 75 ms | 319 / 44 ms |

Claude Code runs an event's hooks in parallel, so "slowest" is the delay added
to each tool call and "sum" is the CPU spent. Repairing the four directories
removes about 35 percent of both. The repair needs root, so it is the owner's
step. The toolkit's part is to detect the condition and print the repair, so
this host and any other host with the same damage find out, including after a
future Python upgrade recreates it.

## Current state

- `scripts/vexinstall/interp.py`: interpreter pin helpers. `missing_modules`
  (lines 392-415) runs a probe snippet through the pinned hook interpreter and
  is the pattern to copy. Excerpt (lines 378-391):

  ```python
  REQUIRED_MODULES = ("yaml", "requests", "dotenv", "google.auth", "jsonschema", "PIL")

  # Runs without -I, as pyrun.sh runs hooks, so the user site (install.sh's pip --user fallback) counts.
  _MISSING_PROBE = (
      "import sys\n"
      "sys.path[:] = [p for p in sys.path if p not in ('', '.')]\n"
      "import importlib.util as u\n"
      ...
  )
  ```

  `missing_modules(home, modules=REQUIRED_MODULES, timeout=10.0)` resolves the
  interpreter with `link = link_path(home)` and
  `path = _probe_path(link, read_pin(link))`, returns `[]` when `path is None`,
  runs `subprocess.run([path, "-c", _MISSING_PROBE, *modules], capture_output=True, text=True, timeout=timeout, check=False)`,
  returns `[]` on `OSError` or `subprocess.SubprocessError`, and returns
  `out.stdout.split() if out.returncode == 0 else []`.
- `scripts/vexinstall/doctor.py:242-253`: `_check_python` adds a `WARN`
  finding `python-deps-missing` when `interp.missing_modules(ctx.home)` is not
  empty:

  ```python
  def _check_python(ctx: Context, findings: list[Finding]) -> None:
      """Interpreter drift: the hook python link is missing, dangling, or older than 3.10."""
      link = str(interp.link_path(ctx.home))
      for check, detail in interp.drift(ctx.home):
          findings.append(Finding(ERROR, check, "claude", link, detail))
      if not interp.drift(ctx.home):
          missing = interp.missing_modules(ctx.home)
          if missing:
              ...
              findings.append(Finding(WARN, "python-deps-missing", "claude", link, detail))
  ```
- `scripts/vexinstall/apply.py:115-130`: `_health_lines(ctx, label)` builds
  the `[sync] warning: ...` lines the SessionStart sync prints (stale source
  clone, registered hook files not deployed). Each line starts
  `f"[{label}] warning: "`.
- `scripts/tests/test_hook_python_pin.py:473-495`: the exemplar tests.
  `test_doctor_warns_when_hook_python_lacks_requirements` replaces the pinned
  interpreter link with a fake `python3` shell script that answers the probe,
  runs `world.run("doctor", "--target", "claude")`, and asserts one `warn`
  finding. `test_missing_modules_is_empty_for_a_python_with_the_stdlib_only`
  calls `interp.missing_modules` against the real interpreter. Match both.
- Convention: new probe code follows `missing_modules` exactly (same
  resolution, same timeout handling, same "unknown means empty" rule). Doctor
  findings use `Finding(level, check, target, path, detail)`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Targeted tests | `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q` | all pass |
| Doctor, live | `PYTHONPATH=scripts python3 -m vexinstall doctor --target claude --json` | exit 0 or 1; JSON whose `data.findings` is a list |
| Lint | `ruff check . --config pyproject.toml` | exit 0 |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Lint job | `bash scripts/ci-local.sh` | exit 0 |

The doctor is read-only. Local ruff may be newer than the CI pin (0.15.12);
`scripts/ci-local.sh` warns about that. A format complaint about a file you did
not touch is not yours: report it, do not fix it.

## Scope

**In scope** (the only files to modify):
- `scripts/vexinstall/interp.py`
- `scripts/vexinstall/doctor.py`
- `scripts/vexinstall/apply.py`
- `scripts/tests/test_hook_python_pin.py`

**Out of scope** (do not touch, though they look related):
- `hooks/lib/pyrun.sh`: no launcher change. Setting `PYTHONPYCACHEPREFIX`
  there was considered and rejected (see Maintenance notes).
- Anything under `/usr`: the repair is the owner's step 5.
- `hooks/*.py`: no hook changes.

## Git workflow

- Branch: `perf/flag-unreadable-stdlib-bytecode`.
- One commit. Message: one lowercase past-tense sentence, no type prefix, no
  trailing period, then a blank line and `Verified-By: tests`. Example from
  `git log`: `dropped the trivial intent skip so every /d route runs the intent check again, trivial ones included, at the owner's call`.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing tests

In `scripts/tests/test_hook_python_pin.py`, after
`test_missing_modules_is_empty_for_a_python_with_the_stdlib_only`, add:

1. `test_unreadable_bytecode_dirs_lists_what_the_probe_reports(world, tmp_path)`:
   run `apply --target claude`, replace the pinned link with a fake
   `python3` (copy the shell-script technique from
   `test_doctor_warns_when_hook_python_lacks_requirements`) that prints two
   lines, `/x/lib/python3.12/re/__pycache__` and
   `/x/lib/python3.12/collections/__pycache__`, when its `-c` argument
   contains `__pycache__`, and prints `3.12 0` otherwise. Assert
   `interp.unreadable_bytecode_dirs(world.home)` returns those two paths in
   order.
2. `test_doctor_warns_when_stdlib_bytecode_is_unreadable(world, tmp_path)`:
   same fake; run `doctor --target claude`; assert exactly one finding with
   `check == "python-bytecode-unreadable"` and `level == "warn"`, and that its
   `detail` contains `re/__pycache__` and `chmod`.
3. `test_unreadable_bytecode_dirs_is_empty_for_a_readable_stdlib(world)`:
   with the real interpreter after `apply`, assert the result is a list and
   that every entry ends with `__pycache__`. Do not assert it is empty: on the
   planning host it is not.
4. `test_sync_health_line_names_unreadable_bytecode(world, monkeypatch)`:
   run `apply --target claude`, then
   `monkeypatch.setattr(interp, "unreadable_bytecode_dirs", lambda home, timeout=10.0: ["/x/lib/python3.12/re/__pycache__"])`
   (sync may repair a fake interpreter link, so patch the function instead of
   faking python here); `res = world.run("sync", "--target", "claude")`; assert
   `any(line.startswith("[sync] warning:") and "bytecode" in line for line in res.out)`.
   `world` and `Result` come from `scripts/tests/vexinstall_support.py`
   (`Env.run`, line 169); sync appends `_health_lines` to `res.out` at
   `scripts/vexinstall/apply.py:646-648`.

**Verify**: `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q -k "bytecode"` → the 4 new tests fail (`AttributeError` or assertion), nothing else fails.

### Step 2: Add the probe to `interp.py`

Below `missing_modules`, add a probe constant and function. Target shape:

```python
# Lists stdlib __pycache__ dirs the hook python cannot read. Python then recompiles those modules in
# every process, which costs each hook 25-30 ms (measured 2026-11-26 on a host where root left four
# of them at mode 700). Checks the stdlib root and its direct subdirectories.
_BYTECODE_PROBE = (
    "import os, sysconfig\n"
    "root = sysconfig.get_paths()['stdlib']\n"
    "dirs = [root] + sorted(e.path for e in os.scandir(root) if e.is_dir(follow_symlinks=False))\n"
    "for d in dirs:\n"
    "    c = os.path.join(d, '__pycache__')\n"
    "    if os.path.isdir(c) and not os.access(c, os.R_OK | os.X_OK):\n"
    "        print(c)\n"
)


def unreadable_bytecode_dirs(home: Path, timeout: float = 10.0) -> list[str]:
    """Stdlib ``__pycache__`` dirs the pinned interpreter cannot read; [] when none or unknown."""
```

Resolve and run the interpreter exactly as `missing_modules` does, with
`[path, "-c", _BYTECODE_PROBE]`, and return
`out.stdout.split("\n")` filtered to non-empty lines when
`out.returncode == 0`, else `[]`. Keep the probe valid on Python 3.8 (no
`X | None`, no `match`).

**Verify**: `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q -k "unreadable_bytecode_dirs"` → 2 pass.

### Step 3: Report it from the doctor and the sync

- In `doctor.py` `_check_python`, inside the `if not interp.drift(ctx.home):`
  branch, after the `missing_modules` check, call
  `interp.unreadable_bytecode_dirs(ctx.home)`. When it is not empty, append
  `Finding(WARN, "python-bytecode-unreadable", "claude", link, interp.bytecode_repair_detail(dirs))`.
  `bytecode_repair_detail(dirs)` (new, in `interp.py`) returns exactly
  `f"{len(dirs)} stdlib bytecode dir(s) unreadable (first: {dirs[0]}), so every hook recompiles them (~25-30 ms per hook); repair as root: chmod -R go+rX {' '.join(dirs)}"`.
- In `apply.py` `_health_lines`, append one line with the same text, prefixed
  `f"[{label}] warning: "`. Call it as `interp.unreadable_bytecode_dirs(ctx.home)`
  (module attribute, so the step 1 monkeypatch reaches it), once per
  `_health_lines` call. Put the shared text in one helper in `interp.py`,
  `bytecode_repair_detail(dirs: list[str]) -> str`, used by both callers.

**Verify**: `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q` → all pass, including the 4 new tests.

### Step 4: Check the live doctor and the lint job

**Verify**:
- `PYTHONPATH=scripts python3 -m vexinstall doctor --target claude --json | python3 -c "import json,sys; d=json.load(sys.stdin); print([f['detail'] for f in d['data']['findings'] if f['check']=='python-bytecode-unreadable'])"` → on the planning host, one detail naming the four `/usr/lib/python3.12/.../__pycache__` dirs. On a host without the damage, `[]`. The doctor exits 1 when it has any finding; on the planning host it already reports three unrelated warnings, so do not read the exit code as failure.
- `bash scripts/ci-local.sh` → exit 0.

### Step 5 (OWNER-GATED: sudo on system files; root-owned paths under `/usr`): Repair this host's bytecode cache

For the owner. The executor skips this step and reports it as pending.

```bash
sudo chmod -R go+rX /usr/lib/python3.12/importlib/__pycache__ /usr/lib/python3.12/re/__pycache__ \
  /usr/lib/python3.12/encodings/__pycache__ /usr/lib/python3.12/collections/__pycache__
```

Check: `/usr/bin/python3 -X importtime -c pass 2>&1 | grep -E '\| +collections$'`
shows a self time (first number) under 2000 us; it was about 10,000 us. The
doctor stops reporting `python-bytecode-unreadable`. Rollback:
`sudo chmod -R go-rwx` on the same four dirs. To keep it from recurring, check
root's umask (`sudo sh -c umask`); a value of `0077` will recreate unreadable
caches on the next upgrade that runs Python as root.

## Test plan

- New tests in `scripts/tests/test_hook_python_pin.py` (step 1): probe output
  parsing, doctor finding, real-interpreter shape, sync health line.
- Model after `test_doctor_warns_when_hook_python_lacks_requirements` and
  `test_missing_modules_is_empty_for_a_python_with_the_stdlib_only` in the
  same file.
- Verification: `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q` → all pass, including 4 new tests.

## Done criteria

- [ ] `python3 -m pytest scripts/tests/test_hook_python_pin.py -n 0 -q` exits 0 with the 4 new tests passing
- [ ] `grep -n "def unreadable_bytecode_dirs" scripts/vexinstall/interp.py` returns 1 line
- [ ] `grep -n "python-bytecode-unreadable" scripts/vexinstall/doctor.py` returns at least 1 line
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` row for 010 updated; step 5 reported as pending owner action

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- The probe takes more than 1 s on the planning host (the sync prints these
  lines at every SessionStart in the toolkit checkout; it must stay cheap).
- Any step would need `sudo`, a write under `/usr`, or a change to root's
  umask. That is step 5 and belongs to the owner.

## Maintenance notes

- Rejected alternative: export `PYTHONPYCACHEPREFIX` in `hooks/lib/pyrun.sh`
  so hooks keep a user-owned bytecode cache. It removes the cost without root,
  but it changes how every hook runs on every host to work around one host's
  damage, duplicates the stdlib bytecode into the user's home, and leaves every
  other Python program on the host slow (the fast test tier saved 9 percent
  CPU with the prefix set). Revisit only if the owner declines step 5.
- The probe checks the stdlib root and one level of subdirectories. A damaged
  nested package (`concurrent/futures/__pycache__`) is not reported; add depth
  only if one shows up.
- Reviewer: check the probe parses on Python 3.8 and that the doctor and sync
  text name the dirs and the repair command.
