# Plan 002: Index generators write INDEX.json atomically

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c0f87bbf..HEAD -- scripts/generate-agent-index.py scripts/generate-skill-index.py scripts/generate-index.py scripts/lib/atomic_io.py scripts/tests/test_atomic_io.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Kind**: fix
- **Planned at**: commit `c0f87bbf`, 2026-11-09

## Why this matters

`skills/INDEX.json` and `agents/INDEX.json` are generated, untracked files that
the router, the dispatch builder, and session hooks read. Three generators
write them in place, so a reader that runs during a write sees a truncated
file. `scripts/build-dispatch.py:557-560` treats a JSON parse error as "no
names", which turns off agent-name validation for that call without any
message. Regeneration happens during sync and from other sessions, so reads
and writes do overlap. Writing to a temp file and renaming it over the target
means a reader sees the old file or the new file, never a partial one.

## Current state

`scripts/generate-agent-index.py:266-268` (inside `main`):

```python
    # Write index file
    with open(output_path, "w") as f:
        json.dump(index, f, indent=2)
```

Note: this writes no trailing newline and uses the platform default encoding.

`scripts/generate-skill-index.py:546-563` (`write_index`):

```python
    try:
        output_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        return True
    except PermissionError:
        print(f"Error: Permission denied writing to {output_path}", file=sys.stderr)
        return False
    except OSError as e:
        print(f"Error: Failed to write index file: {e}", file=sys.stderr)
        return False
```

`scripts/generate-index.py:553-555` (inside `main`, write mode):

```python
    # Write mode
    for label, (idx, path) in indexes.items():
        path.write_text(json.dumps(idx, indent=2) + "\n", encoding="utf-8")
```

The reader that fails silently, `scripts/build-dispatch.py:556-560`:

```python
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
```

Conventions:

- Shared script helpers live in `scripts/lib/` and are imported as
  `from scripts.lib.<module> import <name>`. All three generators already do
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` and then
  `from scripts.lib.frontmatter import extract_frontmatter_block`. Match it.
- An atomic writer exists at `scripts/vexinstall/fsops.py:124`
  (`atomic_write_bytes`), but it requires an installer `Guard` object. Do not
  import it; write the small helper below.
- Tests load hyphenated scripts with `importlib`; exemplar
  `scripts/tests/test_generate_skill_index.py:1-22`. Tests write under
  `tmp_path` only.
- Python floor is 3.10.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| New tests | `python3 -m pytest scripts/tests/test_atomic_io.py -n 0 -q` | all pass |
| Generator tests | `python3 -m pytest scripts/tests/test_generate_skill_index.py scripts/tests/test_generate_routing_map.py -n 0 -q` | all pass (27 in the first file at the planned commit) |
| Regenerate | `python3 scripts/generate-skill-index.py && python3 scripts/generate-agent-index.py` | exit 0 |
| Index gate | `python3 scripts/validate-index-integrity.py` | exit 0 |
| Lint | `ruff check . --config pyproject.toml` | `All checks passed!` |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |
| Fast suite | `nice -n 10 python3 -m pytest --tb=short -q` | all pass |

## Scope

**In scope** (the only files to modify):
- `scripts/lib/atomic_io.py` (create)
- `scripts/tests/test_atomic_io.py` (create)
- `scripts/generate-agent-index.py`
- `scripts/generate-skill-index.py`
- `scripts/generate-index.py`

**Out of scope** (do not touch):
- `scripts/build-dispatch.py`: its silent `continue` is a separate decision.
- `scripts/generate-routing-map.py`, `scripts/generate-skills-doc.py`,
  `scripts/add-companion-skills.py`: they write tracked docs that no runtime
  path parses.
- `scripts/vexinstall/`: the installer has its own guarded writer.
- The JSON content and byte layout of each index. Output must stay
  byte-identical.

## Git workflow

- Branch: `fix/advisor-002-atomic-index-writes`.
- One commit. Message style: one lowercase past-tense sentence, no type
  prefix, no trailing period. Example from `git log`:
  `made agent_input_hash reject a single bare path so a string like Makefile cannot hash per character and silently miss later edits`.
- No `Co-Authored-By` or "Generated with" lines.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Record the current output bytes

```bash
python3 scripts/generate-skill-index.py && python3 scripts/generate-agent-index.py
sha256sum skills/INDEX.json agents/INDEX.json > /tmp/advisor-002-before.sha
stat -c '%a %n' skills/INDEX.json agents/INDEX.json > /tmp/advisor-002-before.mode
```

**Verify**: `wc -l < /tmp/advisor-002-before.sha` → `2`

### Step 2: Add the helper with tests

Create `scripts/lib/atomic_io.py` with one public function:

```python
def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write *text* to *path* so a reader sees the old file or the new one."""
```

Required behavior:

1. Create the temp file in `path.parent` with `tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`.
2. Write the encoded text, `flush`, `os.fsync`, close.
3. Set the mode: the existing file's permission bits when `path` exists,
   otherwise `0o666 & ~umask`. `mkstemp` creates `0600`; without this step
   the index becomes unreadable to other users. Read the umask without
   changing it for longer than one call: `mask = os.umask(0); os.umask(mask)`.
4. `os.replace(tmp, path)`.
5. On any exception, remove the temp file and re-raise the original
   exception. `PermissionError` and other `OSError` must propagate unchanged,
   because `write_index` in `generate-skill-index.py` catches them by type.

Create `scripts/tests/test_atomic_io.py` with these cases, all under
`tmp_path`:

1. Writes new file; content matches.
2. Replaces an existing file; content matches; no `*.tmp` file remains in the
   directory.
3. Existing file with mode `0o640` keeps `0o640` after the write.
4. New file gets `0o666 & ~umask` (compute the expectation in the test).
5. Failure leaves the original intact: monkeypatch `os.replace` in the module
   to raise `OSError`; assert the call raises `OSError`, the original content
   is unchanged, and no temp file remains.
6. Missing parent directory raises `OSError` (`FileNotFoundError`).

**Verify**: `python3 -m pytest scripts/tests/test_atomic_io.py -n 0 -q` → 6 passed

### Step 3: Switch the three generators

Add `from scripts.lib.atomic_io import atomic_write_text` next to the existing
`from scripts.lib.frontmatter import ...` line in each file. Then:

- `scripts/generate-agent-index.py`: replace the `with open(...)`/`json.dump`
  block with `atomic_write_text(output_path, json.dumps(index, indent=2))`.
  No trailing newline, to keep the bytes identical.
- `scripts/generate-skill-index.py` `write_index`: replace the
  `output_path.write_text(...)` call with
  `atomic_write_text(output_path, json.dumps(index, indent=2) + "\n")`. Keep
  both `except` clauses as they are.
- `scripts/generate-index.py`: replace `path.write_text(...)` with
  `atomic_write_text(path, json.dumps(idx, indent=2) + "\n")`.

**Verify**:

```bash
python3 scripts/generate-skill-index.py && python3 scripts/generate-agent-index.py
sha256sum -c /tmp/advisor-002-before.sha
stat -c '%a %n' skills/INDEX.json agents/INDEX.json | diff - /tmp/advisor-002-before.mode
```

→ both files `OK`; `diff` prints nothing.

### Step 4: Run the gates

**Verify**: Generator tests, Index gate, Lint, Format, and Fast suite commands
from the table → all succeed.

### Step 5: Clean up

`rm /tmp/advisor-002-before.sha /tmp/advisor-002-before.mode`

**Verify**: `ls /tmp/advisor-002-before.* 2>/dev/null | wc -l` → `0`

## Test plan

- New: `scripts/tests/test_atomic_io.py`, 6 cases (step 2).
- Regression: the byte-identity and mode checks in step 3.
- Existing: `scripts/tests/test_generate_skill_index.py` must pass unchanged.

## Done criteria

- [ ] `python3 -m pytest scripts/tests/test_atomic_io.py -n 0 -q` exits 0, 6 passed
- [ ] `grep -nE 'write_text\(json\.dumps|open\(output_path, "w"\)' scripts/generate-agent-index.py scripts/generate-skill-index.py scripts/generate-index.py` returns no matches
- [ ] Step 3 byte-identity and mode checks passed
- [ ] `python3 scripts/validate-index-integrity.py` exits 0
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `nice -n 10 python3 -m pytest --tb=short -q` exits 0
- [ ] `git status --short` shows only the five in-scope files (plus `plans/README.md` if you maintain the index)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- The step 3 hash check fails: the output bytes changed, and a `--check` mode
  or CI comparison elsewhere may depend on them.
- `python3 scripts/validate-doc-counts.py` starts failing. It counts
  `scripts/*.py` at the top level only, so a file under `scripts/lib/` should
  not change the count. If it does, the assumption is false.
- A step would need a deploy, a credential, a public listener, a scheduled
  job, data deletion, or a request to a third party.

## Maintenance notes

- Run this plan's fast suite outside 01:00-04:00 local time and at `nice` 10
  or higher; this host reserves that window.
- New generators that write a file a runtime path parses should use
  `atomic_write_text`.
- Follow-up, not in this plan: `scripts/build-dispatch.py:557-560` skips an
  unreadable index without a message. With atomic writes the truncated-read
  cause is gone, but a warning on a present-but-unparseable index would make
  any other cause visible.
- A reviewer should check the mode handling in `atomic_write_text` and that
  the agent index still has no trailing newline.

## Revision 2 (2026-11-09, after a blocked first run)

The first run of this plan started an unbounded process chain. Read this
section before any step; where it differs from the text above, this section
wins.

### What went wrong

- `generate-skill-index.py:800-817` runs `check-routing-drift.py` after it
  writes. That script calls `ensure_fresh_indexes`
  (`scripts/lib/index_freshness.py`), which re-runs a generator when the index
  is older than any source. The `skills/` and `agents/` directories are
  sources.
- A temp file plus `os.replace` inside `skills/` sets the directory's mtime
  after the file's own mtime (the file's mtime is its last write, before the
  rename). The index is then always "older than a source", so generator and
  drift check start each other without end. An in-place write never touched
  the directory mtime.
- The same loop exists before this plan whenever a source has an mtime in the
  future. Nothing bounds it.
- `skills/INDEX.json` holds a `generated` timestamp
  (`generate-skill-index.py:365`), so two runs never hash the same. The step 1
  and step 3 sha256 check cannot pass for that file as written.

### Safety rule for every generator run in this plan

Until step R2 below is done and its tests pass, do not run
`generate-skill-index.py`, `generate-agent-index.py`, `generate-index.py`,
`check-routing-drift.py`, `router-self-audit.py`, or the full pytest suite.
After that, run each of them only inside a task-capped scope, so a loop fails
fast instead of filling memory:

```bash
systemd-run --user --scope -q -p TasksMax=40 -- <command>
```

After each such run: `pgrep -fc "$(git rev-parse --show-toplevel)/scripts/"`
must print `0`. If it does not, kill by that path prefix and STOP.

### Added scope

- `scripts/lib/index_freshness.py`
- `scripts/tests/test_index_freshness.py` (extend if it exists, else create;
  search `scripts/tests` and `tests` for an existing test of this module first)

### Step R1: the index must not predate its directory

In `atomic_write_text`, after `os.replace`, call `os.utime(path)` so the
file's mtime is not older than the directory mtime that the rename just set.
Add test 7 to `scripts/tests/test_atomic_io.py`: after a write that replaces
an existing file, and after a write that creates one,
`path.stat().st_mtime_ns >= path.parent.stat().st_mtime_ns`.

### Step R2: bound the generator/drift cycle

- In `index_freshness.ensure_fresh_indexes`, pass the generator subprocess an
  environment that adds `VEXJOY_INDEX_REGEN=1` (copy `os.environ`; add the
  key). Export the name as a module constant.
- In `generate-skill-index.py`, skip the post-generation drift gate when that
  variable is set: a consumer started this run and does its own check.
- Tests, all under `tmp_path`, none starting the real generator:
  1. `ensure_fresh_indexes` on a fixture root with a missing index and a stub
     generator script that writes the index and records `os.environ.get(...)`:
     the stub saw `VEXJOY_INDEX_REGEN=1`.
  2. Regression for the loop: a fixture root whose stub generator writes the
     index through `atomic_write_text`; afterwards
     `newer_source(root, surface)` is `None`.
  3. `generate-skill-index.py` with the variable set does not start
     `check-routing-drift.py`: load the module with `importlib`, monkeypatch
     its `subprocess.run` to record calls, run `main` against a small fixture
     tree the way `scripts/tests/test_generate_skill_index.py` does, and
     assert no recorded call names `check-routing-drift.py`. If `main` cannot
     run against a fixture without `--repo-root` (which already skips the
     gate), extract the gate's condition into a small function and test that
     function with the variable set and unset.

**Verify**: `python3 -m pytest scripts/tests/test_atomic_io.py <the freshness test file> -n 0 -q` → all pass.

### Step R3: replace the byte-identity check

Step 1 and step 3 compare content, not raw hashes:
`agents/INDEX.json` by sha256 as written; `skills/INDEX.json` by loading both
versions as JSON, deleting the top-level `generated` key, and comparing the
rest for equality. Also check the skills file still ends with one newline and
the agents file with none. Keep the mode comparison.

Then run, inside the scope from the safety rule:
`python3 scripts/generate-skill-index.py && python3 scripts/generate-agent-index.py`
and after it `python3 scripts/check-routing-drift.py` → exit 0, and the
process count check prints `0`. Run the fast suite last, also in a scope
(`-p TasksMax=200` for pytest workers).

### Added done criteria

- [ ] After a scoped generator run, `python3 -c "import sys; sys.path.insert(0,'scripts/lib'); from pathlib import Path; from index_freshness import newer_source; print([newer_source(Path('.'), s) for s in ('skills','agents')])"` prints `[None, None]`
- [ ] `pgrep -fc "$(git rev-parse --show-toplevel)/scripts/"` prints `0`

### Added STOP condition

- The process count check is non-zero after any run.
