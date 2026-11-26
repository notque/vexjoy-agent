# Plan 014: the hook benchmark times what Claude Code runs, in an isolated HOME

> **Executor instructions**: follow this plan step by step. Run every
> verification command and confirm the expected result before the next step.
> If a STOP condition occurs, stop and report. Do not improvise. Do not run
> any step marked OWNER-GATED. When done, update this plan's row in
> `plans/README.md`, unless a reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat c68ac1fe..HEAD -- scripts/benchmark-hooks.py scripts/tests/test_benchmark_hooks.py CONTRIBUTING.md docs/for-developers.md hooks/tests/test_pretool_private_name_leak_gate.py`
> If an in-scope file changed, compare the "Current state" excerpts with the
> live code. A mismatch is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Kind**: fix
- **Planned at**: commit `c68ac1fe`, 2026-11-26

## Why this matters

`CONTRIBUTING.md:123` sets a 50 ms hook budget and says
`scripts/benchmark-hooks.py` validates it. The script cannot: it times the
wrong thing, and running it is unsafe.

- It times every `hooks/*.py` file on disk (82), not the 72 registrations
  Claude Code runs, and has no PreToolUse payload at all. 54 of the 72
  registered hooks fall back to a UserPromptSubmit payload, so most gates
  exit early and look fast. 12 of its 23 `HOOK_EVENT_MAP` names no longer
  exist.
- It runs each file with the caller's environment from the repo root: the
  real HOME, real session ids, and any API keys. So `sync-to-user-claude.py`
  runs a real `vexinstall sync --target all` on each iteration,
  `rules-distill-trigger.py` can launch its weekly background job (one
  `claude -p --model opus` session per skill), and other hooks write into the
  live `~/.claude/learning` store.
- Its default threshold is 200 ms, not 50, and no CI job or test runs it.

Every hook performance plan needs a trustworthy before/after number. The
audit that wrote this plan used a prototype of the design below and measured,
for example, 10 PreToolUse hooks on one Bash call at 704 ms summed and 87 ms
for the slowest hook on the planning host. Claude Code runs an event's hooks
in parallel, so the slowest hook is the delay a tool call sees and the sum is
the CPU it costs.

## Current state

- `scripts/benchmark-hooks.py` (216 lines), to be rewritten:
  - Lines 33-65, `INPUTS`: payloads for UserPromptSubmit, PostToolUse,
    SessionStart, PreCompact, Stop; none carries `session_id`, `cwd`, or a
    PreToolUse shape.
  - Lines 68-89, `HOOK_EVENT_MAP` (23 names).
  - Lines 92-99, `discover_hooks()`: `sorted(HOOKS_DIR.glob("*.py"))`.
  - Lines 108-150, `benchmark_hook()`:
    `subprocess.run([sys.executable, str(hook_path)], input=input_data, capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT))`,
    with no `env=` argument.
  - Lines 156-160 in `main()` (line 153), flags: `--ci`, `--threshold` (default 200), `--verbose`,
    `--json`, `--iterations` (default 5). Keep all five flag names.
- `scripts/smoke-test-hooks.py`: the safe-execution precedent to follow.
  `_safe_execution_environment` (lines 150-178) builds the child environment
  from scratch with a throwaway HOME and `VEXJOY_SYNC_DISABLED=1`; its comment
  explains why HOME must never be the repo or the real home. Match that
  approach. Do not import from it or change it.
- `.claude/settings.json` `hooks` key: `{event: [{"matcher": str (optional), "hooks": [{"command": str, "timeout": int, ...}]}]}`.
  Commands look like
  `sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/<name>.py"`.
  Claude Code treats a missing, empty, or `*` matcher as every tool, and
  otherwise matches the matcher as a regex against the whole tool name.
- References to update: `CONTRIBUTING.md:123`, `docs/for-developers.md:167`,
  and the comment at `hooks/tests/test_pretool_private_name_leak_gate.py:586`
  (`# Performance — repo benchmark budget (scripts/benchmark-hooks.py: 200ms)`).
  `hooks/README.md:93` (`python3 scripts/benchmark-hooks.py`) stays valid.
- Conventions: scripts are deterministic CLIs with an argparse `main()`
  returning an exit code; see `scripts/smoke-test-hooks.py`. Tests live in
  `scripts/tests/`, write only under `tmp_path`, and change env with
  `monkeypatch` (`CONTRIBUTING.md`, Testing).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| New tests | `python3 -m pytest scripts/tests/test_benchmark_hooks.py -n 0 -q` | all pass |
| Benchmark, quick | `nice -n 10 python3 scripts/benchmark-hooks.py --iterations 2 --event UserPromptSubmit` | exit 0; a table |
| Benchmark, full | `nice -n 10 python3 scripts/benchmark-hooks.py --iterations 3` | exit 0; about 2-3 minutes |
| Doc commands | `python3 scripts/validate-doc-commands.py` | exit 0 |
| Lint job | `bash scripts/ci-local.sh` | exit 0 |

## Scope

**In scope** (the only files to modify):
- `scripts/benchmark-hooks.py` (rewrite)
- `scripts/tests/test_benchmark_hooks.py` (create)
- `CONTRIBUTING.md` (line 123 only)
- `docs/for-developers.md` (line 167 only)
- `hooks/tests/test_pretool_private_name_leak_gate.py` (the line 586 comment only)

**Out of scope** (do not touch, though they look related):
- `scripts/smoke-test-hooks.py`, `.github/workflows/test.yml`: no new CI job.
  Wall-clock budgets on shared runners are noisy; gating CI on them is a
  separate decision.
- Lifecycle events (SessionStart, Stop, SubagentStart, SubagentStop,
  PreCompact, PostCompact, SessionEnd, StopFailure): several of those hooks
  sync installs or start background jobs. This benchmark never runs them.
- Any hook file.

## Git workflow

- Branch: `perf/safe-hook-benchmark`.
- One commit. Message: one lowercase past-tense sentence, no type prefix, no
  trailing period, then a blank line and `Verified-By: tests`. Example from
  `git log`: `dropped the trivial intent skip so every /d route runs the intent check again, trivial ones included, at the owner's call`.
- Do not push, open a PR, merge, deploy, or tag.

## Steps

### Step 1: Write the failing tests

Create `scripts/tests/test_benchmark_hooks.py`. Load the script with
`importlib.util.spec_from_file_location("benchmark_hooks", <repo>/scripts/benchmark-hooks.py)`
(hyphenated file name). Tests:

1. `test_matcher_semantics`: `bh.matches("", "Grep")`, `bh.matches("*", "Grep")`,
   `bh.matches("Write|Edit", "Edit")`, and `bh.matches("Bash", None)` are
   true; `bh.matches("Write|Edit", "MultiEdit")` and
   `bh.matches("Bash", "BashOutput")` are false.
2. `test_registered_selects_by_event_and_tool`: with a settings dict holding
   a PreToolUse group `{"matcher": "Bash", "hooks": [{"command": "a"}]}`, a
   group with no matcher `{"hooks": [{"command": "b"}]}`, and a PostToolUse
   group `{"hooks": [{"command": "c"}]}`:
   `bh.registered(s, "PreToolUse", "Bash") == ["a", "b"]`,
   `bh.registered(s, "PreToolUse", "Read") == ["b"]`.
3. `test_env_drops_keys_and_live_ids(monkeypatch, tmp_path)`: set
   `TYPESAFE_API_KEY`, `AI_GATEWAY_API_KEY`, `GH_TOKEN`, `ANTHROPIC_API_KEY`,
   and `CLAUDE_SESSION_ID=live-1` with `monkeypatch.setenv`; call
   `bh.build_env(tmp_path, home=tmp_path / "home", work=tmp_path / "work", session_id="bench-x")`.
   Assert none of the four key names is in the result, `CLAUDE_SESSION_ID`
   is `bench-x`, `HOME` is `str(tmp_path / "home")`, and
   `VEXJOY_SYNC_DISABLED == "1"`.
4. `test_runs_the_registered_command_under_the_sandbox_home(tmp_path)`: write
   a fixture settings file with one UserPromptSubmit command
   `printf %s "$HOME" > "$TMPDIR/seen-home"`; run
   `bh.main(["--settings", str(fixture), "--sandbox-root", str(tmp_path / "sb"), "--iterations", "1", "--event", "UserPromptSubmit", "--json"])`.
   Assert exit 0, and that `tmp_path / "sb" / "tmp" / "seen-home"` holds a
   path under `tmp_path` and not `str(Path.home())`.
5. `test_cleanup_removes_only_the_bench_session_files(tmp_path)`: create
   `tmp_path / ".claude-backups" / "bench-x" / "f"`,
   `tmp_path / "claude-routing-outcomes-bench-x.json.lock"`, and
   `tmp_path / "claude-other-live-1.state"`; call
   `bh.cleanup_tmp("bench-x", base=tmp_path)`. Assert the first two are gone
   and the third remains.

**Verify**: `python3 -m pytest scripts/tests/test_benchmark_hooks.py -n 0 -q` → all 5 fail (missing functions or flags).

### Step 2: Rewrite `scripts/benchmark-hooks.py`

Replace the file. Keep the shebang, a module docstring that says what is
measured and that the real `~/.claude` is never touched, and these pieces:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
DEFAULT_THRESHOLD_MS = 50  # CONTRIBUTING.md hook budget
ITERATIONS = 5
EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit")  # per-call events only

# (event, tool, tool_input); "{work}" is replaced with the scratch repo path.
CASES = [
    ("PreToolUse", "Bash", {"command": "ls -la", "description": "List files"}),
    ("PreToolUse", "Bash", {"command": "git status --short", "description": "Show status"}),
    ("PreToolUse", "Write", {"file_path": "{work}/new_mod.py", "content": "x = 1\n"}),
    ("PreToolUse", "Edit", {"file_path": "{work}/app.py", "old_string": "return 1", "new_string": "return 2"}),
    ("PreToolUse", "Read", {"file_path": "{work}/app.py"}),
    ("PreToolUse", "Grep", {"pattern": "return", "path": "{work}"}),
    ("PostToolUse", "Bash", {"command": "ls -la", "description": "List files"}),
    ("PostToolUse", "Write", {"file_path": "{work}/new_mod.py", "content": "x = 1\n"}),
    ("PostToolUse", "Edit", {"file_path": "{work}/app.py", "old_string": "return 1", "new_string": "return 2"}),
    ("PostToolUse", "Read", {"file_path": "{work}/app.py"}),
    ("UserPromptSubmit", None, None),
]
PROMPT = "fix the failing parser test and add a regression case"  # never "/d ...": that path calls Jev
```

Functions (names are fixed by the tests):

- `matches(matcher: str, tool: str | None) -> bool`: true when `tool is None`
  or `matcher in ("", "*")`, else `re.fullmatch(matcher, tool) is not None`.
- `registered(settings: dict, event: str, tool: str | None) -> list[str]`:
  every `command` of every group under `settings["hooks"][event]` whose
  `group.get("matcher", "")` matches, in file order.
- `make_sandbox(root: Path) -> tuple[Path, Path]`: create
  `root/home/.claude/` with symlinks `hooks`, `scripts`, `skills` pointing at
  `REPO_ROOT/hooks`, `REPO_ROOT/scripts`, `REPO_ROOT/skills`, an empty
  `learning/` dir, and a copy of the settings file; create `root/tmp/`; create
  `root/work/` as a git repo (`git init -q -b feature/bench`), write
  `app.py` with `def f():\n    return 1\n`, and commit it with
  `git -c user.name=bench -c user.email=bench@example.invalid commit -qm init`.
  Return `(home, work)`.
- `build_env(root: Path, *, home: Path, work: Path, session_id: str) -> dict[str, str]`:
  built from scratch, never from `os.environ` wholesale. Keys: `PATH`
  (`os.pathsep.join([str(Path(sys.executable).resolve().parent), "/usr/local/bin", "/usr/bin", "/bin"])`),
  `HOME=str(home)`, `USER` (from `os.environ`, default `bench`),
  `SHELL=/bin/sh`, `TMPDIR=str(root / "tmp")`, `CLAUDE_PROJECT_DIR=str(work)`,
  `CLAUDE_LEARNING_DIR=str(home / ".claude" / "learning")`,
  `CLAUDE_HOOK_ERRORS_PATH=str(root / "hook-errors.jsonl")`,
  `CLAUDE_SESSION_ID=session_id` (`pretool-file-backup.py` keys its
  `/tmp/.claude-backups/<id>` dir on it), `VEXJOY_SYNC_DISABLED=1`,
  `RULES_DISTILL_TRIGGER_BYPASS=1`, plus `LANG` and `LC_ALL` copied from
  `os.environ` when set.
- `payload(event, tool, tool_input, *, work: Path, session_id: str, transcript: Path) -> str`:
  JSON with `session_id`, `transcript_path`, `cwd=str(work)`,
  `hook_event_name=event`; for a tool case add `tool_name` and `tool_input`
  (with `{work}` replaced); for PostToolUse add
  `tool_response={"stdout": "ok", "stderr": "", "success": True}`; for
  UserPromptSubmit add `prompt=PROMPT`.
- `time_command(command: str, data: str, env: dict, cwd: Path, runs: int) -> dict`:
  run `["sh", "-c", command]` (the registered command string, as Claude Code
  runs it; `$HOME` expands to the sandbox home) with `input=data`,
  `capture_output=True`, `text=True`, `timeout=30`; one untimed warm-up run,
  then `runs` timed runs with `time.perf_counter()`. Return
  `{"median_ms", "p90_ms", "rc", "out_bytes"}`. A timeout counts as 30000 ms.
- `cleanup_tmp(session_id: str, base: Path = Path("/tmp")) -> None`: remove
  `base / ".claude-backups" / session_id` (tree) and every entry matching
  `base.glob(f"*{session_id}*")`. Only names containing the bench session id.
- `main(argv: list[str] | None = None) -> int`: flags `--iterations`
  (default 5), `--threshold` (ms, default 50), `--event` (one of `EVENTS`),
  `--json`, `--verbose` (print every hook row; default prints the slowest 5
  per case), `--ci` (exit 1 when any hook median exceeds the threshold),
  `--settings` (default `SETTINGS`), `--sandbox-root` (default: a
  `tempfile.mkdtemp(prefix="vexjoy-hookbench-")` removed at the end; when
  given, keep it). Use one session id per run:
  `f"bench-{uuid.uuid4().hex[:12]}"`. Always call `cleanup_tmp` in a
  `finally`.

Output per case: `## <event>:<tool>[ (<first word of command>)]: <n> hooks, sum <s> ms, slowest <m> ms (<hook name>)`,
then hook rows `<name> median <x> p90 <y> rc=<r>` sorted by median, slowest
first, with ` OVER` appended when the median exceeds the threshold. The hook
name is the last path component of the command with the trailing `"`
removed. `--json` prints
`{"threshold_ms", "iterations", "cases": [{"case", "hooks": [...], "sum_ms", "max_ms"}]}`.

**Verify**: `python3 -m pytest scripts/tests/test_benchmark_hooks.py -n 0 -q` → 5 passed.

### Step 3: Run it for real

**Verify**:
- `nice -n 10 python3 scripts/benchmark-hooks.py --iterations 2 --event UserPromptSubmit` → exit 0; one case with 8 hooks (the count registered at the planned commit).
- `nice -n 10 python3 scripts/benchmark-hooks.py --iterations 3` → exit 0; 11 cases; `PreToolUse:Bash (ls)` lists 10 hooks (9 if plan 012 already merged); `PreToolUse:Grep` lists 1 hook (0 after plan 012).
- `ls ~/.claude/learning/` → the same files and sizes as before the run (take `ls -la` before and after; `learning.db` mtime may change only if a live session wrote it, so compare sizes of `hook-errors.jsonl` and `route-events.jsonl` instead and confirm no line containing `bench-` was added: `grep -c bench- ~/.claude/learning/route-events.jsonl` before and after shows the same count).
- `ls -d /tmp/.claude-backups/bench-* 2>/dev/null | wc -l` → `0`.

### Step 4: Update the docs and the stale comment

- `CONTRIBUTING.md:123` →
  ``**50ms hook budget.** Hooks fire on every tool call. Keep them fast. `python3 scripts/benchmark-hooks.py` times every registered per-call hook in an isolated HOME and marks medians over 50 ms.``
- `docs/for-developers.md:167` →
  ``**50ms hook budget.** Hooks fire on every tool call or prompt. Keep them fast. Profile with `python3 scripts/benchmark-hooks.py`; it runs registered hooks in an isolated HOME and marks medians over 50 ms.``
- `hooks/tests/test_pretool_private_name_leak_gate.py:586` →
  `# Performance — this test's own 200 ms budget (scripts/benchmark-hooks.py marks medians over 50 ms)`.

**Verify**:
- `python3 scripts/validate-doc-commands.py` → exit 0.
- `bash scripts/ci-local.sh` → exit 0.

## Test plan

- New `scripts/tests/test_benchmark_hooks.py` with 5 tests: matcher
  semantics, registration selection, environment isolation (no keys, no live
  ids, sandbox HOME), the registered command runs under the sandbox HOME, and
  cleanup touches only the bench session's files.
- Model the subprocess-free tests on `scripts/tests/test_validate_hook_health.py`
  style (plain functions, `tmp_path`, `monkeypatch`).
- Verification: `python3 -m pytest scripts/tests/test_benchmark_hooks.py -n 0 -q` → 5 passed.

## Done criteria

- [ ] `python3 -m pytest scripts/tests/test_benchmark_hooks.py -n 0 -q` exits 0 with 5 tests
- [ ] `grep -n "HOOK_EVENT_MAP\|discover_hooks" scripts/benchmark-hooks.py` returns no matches
- [ ] `grep -n "os.environ" scripts/benchmark-hooks.py` shows reads of single keys only (`USER`, `LANG`, `LC_ALL`), no copy of the whole environment
- [ ] Step 3's full run exits 0 and leaves no `/tmp/.claude-backups/bench-*` dir
- [ ] `bash scripts/ci-local.sh` exits 0
- [ ] `git status --short` shows no file outside the in-scope list
- [ ] `plans/README.md` row for 014 updated

## STOP conditions

Stop and report if:

- The code at the "Current state" locations does not match the excerpts.
- A step's verification fails twice after a reasonable fix attempt.
- The fix needs a file outside the in-scope list.
- Any benchmark run starts a `claude` process, makes a network call, or
  writes under the real `~/.claude` (check `ps -eo pid,args | grep -c "claude -p"`
  during the full run and step 3's `learning` checks). Stop the run, report
  the hook and the evidence; do not add it to a skip list on your own.
- A registered per-call hook needs `~/.claude` state the sandbox lacks and
  fails (`rc` not 0 or 2) in the benchmark but passes in
  `python3 scripts/smoke-test-hooks.py --ci`: report it.

## Maintenance notes

- The sandbox links `scripts` and `skills` from the checkout, because some
  hooks read them through `~/.claude`. That is also why lifecycle events stay
  out: on 2026-11-26 an audit run of the Stop hook `rules-distill-trigger.py`
  in such a sandbox started `rules-distill.py`, which launched nested
  `claude -p` sessions (unauthenticated, killed after about 10 s). Adding a
  lifecycle event needs its own review of what each hook starts.
- Numbers on a loaded shared host move by 10-20 percent between runs.
  Compare before/after on the same host, same `--iterations`, back to back.
- A later plan can add an advisory CI job (report only, never a gate) once
  the numbers are stable on runners.
- Reviewer: confirm the child environment is built from scratch and that
  `cleanup_tmp` cannot match names outside the bench session id.
