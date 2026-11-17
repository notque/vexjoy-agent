# Plan 008: Account names and aliases are checked before they reach a shell file

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 871f6499..HEAD -- scripts/manage-accounts.py scripts/tests/test_manage_accounts.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Kind**: fix
- **Planned at**: commit `871f6499`, 2026-11-16

## Why this matters

`scripts/manage-accounts.py` registers extra Claude Code account profiles and
writes one shell alias per account into the user's shell startup file. The
account name and the alias are copied into that shell code as typed. The only
check on a name is "not empty, no slash, no leading dot", and an alias is
checked only for uniqueness. A name or alias holding a quote, `$(`, a
backtick, or a semicolon becomes code that runs in every new terminal. Agents
call this script, so the value is not always something the owner typed. After
this plan, both values must match a plain identifier pattern, and the alias
writers skip any stored entry that does not.

## Current state

- `scripts/manage-accounts.py`: the account CLI. Subcommands: `add`, `check`,
  `list`, `launch`, `remove`, `link`, `install-aliases` (parsers at lines
  463-493).

  ```python
  # scripts/manage-accounts.py:86-90
  def cmd_add(args: argparse.Namespace) -> int:
      """Register a new account and create its config directory."""
      name = args.name.strip()
      if not name or "/" in name or name.startswith("."):
          print(f"error: invalid account name '{name}'", file=sys.stderr)
          return 1
  ```

  ```python
  # scripts/manage-accounts.py:97-101
      # Validate alias uniqueness
      alias = args.alias or _default_alias(accounts)
      if alias == DEFAULT_PROFILE_ALIAS:
          print(f"error: alias '{alias}' is reserved for the default profile", file=sys.stderr)
          return 1
  ```

  The two writers interpolate the stored values:

  ```python
  # scripts/manage-accounts.py:326-333 (inside _fish_alias_block)
      for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
          alias = info.get("alias", f"c_{name}")
          cfg = info.get("config_dir", str(config_dir(name)))
          # Fish: function-based alias so CLAUDE_CONFIG_DIR is set for the subprocess
          lines.append(f"function {alias}")
          lines.append(f'    set -lx CLAUDE_CONFIG_DIR "{cfg}"')
          lines.append(f"    claude {' '.join(DEFAULT_CLAUDE_ARGS)} $argv")
          lines.append("end")
  ```

  ```python
  # scripts/manage-accounts.py:341-344 (inside _bash_alias_block)
      for name, info in sorted(accounts.items(), key=lambda kv: kv[1].get("alias", kv[0])):
          alias = info.get("alias", f"c_{name}")
          cfg = info.get("config_dir", str(config_dir(name)))
          lines.append(f"alias {alias}='CLAUDE_CONFIG_DIR=\"{cfg}\" claude {' '.join(DEFAULT_CLAUDE_ARGS)}'")
  ```

  `config_dir(name)` (line 76) builds the profile directory path from the
  name, so the name reaches `cfg`. The registry is a JSON file a person can
  edit by hand, so the writers cannot trust stored values either.
  `DEFAULT_PROFILE_ALIAS = "cm0"` (line 49); generated default aliases follow
  the same shape (`_default_alias`, line 197).

- `scripts/tests/test_manage_accounts.py`: existing tests for this script.
  Read it first and reuse its loader and fixtures.
- Convention: CLI errors print `error: <message>` to stderr and return 1.
  Exemplar: `scripts/manage-accounts.py:89-90`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Script tests | `nice -n 10 python3 -m pytest scripts/tests/test_manage_accounts.py -q -n 0` | all pass |
| Installer account tests | `nice -n 10 python3 -m pytest scripts/tests/test_vexinstall_accounts.py -q -n 0` | all pass |
| Lint | `ruff check . --config pyproject.toml` | exit 0 |
| Format | `ruff format --check . --config pyproject.toml` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `scripts/manage-accounts.py`
- `scripts/tests/test_manage_accounts.py`

**Out of scope** (do not touch, though they look related):
- The user's real shell startup files and the real account registry. Tests
  use `tmp_path` and a patched home directory only. Never run `add`,
  `remove`, or `install-aliases` against the real home directory.
- `DEFAULT_CLAUDE_ARGS`: the launch flags are the owner's choice.
- `scripts/vexinstall/`: the installer calls this script; its behavior is
  unchanged for valid names.

## Git workflow

- Branch: `fix/account-name-validation`.
- One commit. Message style: one lowercase past-tense sentence, no type prefix,
  no trailing period. Example from `git log`:
  `installed repo env and attribution into every account profile and the base settings, not just hooks`
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Record the baseline

**Verify**: both pytest commands exit 0. If one fails before any edit, STOP.

### Step 2: Add the validator and use it in `cmd_add`

Near the constants at the top of `scripts/manage-accounts.py`, add (and add
`import re` if the file does not import it):

```python
# Names and aliases are written into shell startup files, so they are limited
# to characters no shell treats as syntax.
_SAFE_IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")


def _is_safe_ident(value: str) -> bool:
    return bool(_SAFE_IDENT_RE.fullmatch(value))
```

In `cmd_add`, replace the name condition with
`if not _is_safe_ident(name):` and keep the same error line. After the alias
is resolved (line 98) and before the reserved-alias check, add:

```python
    if not _is_safe_ident(alias):
        print(f"error: invalid alias '{alias}' (letters, digits, '-' and '_' only)", file=sys.stderr)
        return 1
```

**Verify**: `nice -n 10 python3 -m pytest scripts/tests/test_manage_accounts.py -q -n 0` → all pass.

### Step 3: Make the alias writers skip unsafe stored entries

Add one helper and call it at the top of the `for` loop in both
`_fish_alias_block` and `_bash_alias_block`, and in any other function in the
file that writes an alias line (search: `grep -n "CLAUDE_CONFIG_DIR" scripts/manage-accounts.py`):

```python
_UNSAFE_PATH_CHARS = frozenset("\"'`$\\\n\r;")


def _shell_safe_entry(alias: str, cfg: str) -> bool:
    """True when a registry entry can be written into a shell file as is."""
    if _is_safe_ident(alias) and not (_UNSAFE_PATH_CHARS & set(cfg)):
        return True
    print(f"warning: skipped account alias {alias!r}: unsafe characters in alias or config_dir", file=sys.stderr)
    return False
```

In each loop: `if not _shell_safe_entry(alias, cfg): continue`.

**Verify**: `nice -n 10 python3 -m pytest scripts/tests/test_manage_accounts.py -q -n 0` → all pass.

### Step 4: Add the tests

Add the cases in "Test plan" to `scripts/tests/test_manage_accounts.py`.

**Verify**: both pytest commands exit 0; the first reports at least 6 more tests than the step 1 baseline.

### Step 5: Lint

**Verify**: `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0.

## Test plan

In `scripts/tests/test_manage_accounts.py`, following that file's existing
structure:

- `add` rejects each of these names with return code 1 and writes no registry
  entry: a name with a space, one with `;`, one with `$(`, one with a single
  quote, one starting with a digit.
- `add` rejects an alias holding a backtick, and one holding a single quote.
- `add` accepts `work-2` and `team_b` as names and `cm9` as an alias.
- `_bash_alias_block` and `_fish_alias_block`, given a registry dict with one
  safe entry and one entry whose alias holds `;`, return text that contains
  the safe alias and does not contain the unsafe one; stderr holds `warning:`.
- The same two writers skip an entry whose `config_dir` holds a double quote.

## Done criteria

- [ ] Both pytest commands exit 0
- [ ] `grep -n "_is_safe_ident" scripts/manage-accounts.py` shows the definition and at least three call sites
- [ ] `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` exit 0
- [ ] `git status --short` shows only the two in-scope files and `plans/README.md`
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- An existing test registers a name or alias the new pattern rejects: the
  pattern may be too strict for real use. Report the value's shape.
- `scripts/tests/test_vexinstall_accounts.py` fails after the change.
- A test would need to write to the real home directory or a real shell startup file.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

- Reviewer: check that no alias line is written without passing
  `_shell_safe_entry`, including any zsh path.
- A profile directory whose path holds a space is still allowed; a quote,
  backslash, `$`, backtick, semicolon, or newline is not.
- Deferred: `remove` and `launch` take a name too. They look it up in the
  registry and do not write shell code, so they are unchanged.
